"""
FastAPI server cho version management APIs.
Chạy server này song song với WorkflowServer (server.py).

Usage:
    uvicorn api:app --host 0.0.0.0 --port 9000 --reload
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from memory_helper_functions.presentation_storage import (
    _get_active_presentation,
    _get_presentation_versions,
    _get_version_content
)
from config.supabase_client import get_supabase_client

app = FastAPI(
    title="Slide Version API",
    description="API endpoints cho quản lý versions của slides",
    version="1.0.0"
)

# CORS middleware để FE có thể gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép mọi origin (dev only, production nên limit)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Slide Version API",
        "version": "1.0.0"
    }


async def verify_auth(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify JWT token and return user_id.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        supabase = get_supabase_client()
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return user_response.user.id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


@app.get("/api/presentations/active")
async def get_active_presentation_api(
    conversation_id: str,
    user_id: str = Depends(verify_auth)
):
    """
    Get active presentation_id for a conversation.
    
    Args:
        conversation_id: UUID of conversation
    
    Returns:
        {
            "active_presentation_id": "uuid" or null
        }
    """
    # Verify user owns conversation
    supabase = get_supabase_client()
    conv = supabase.from_('conversations').select('user_id').eq('id', conversation_id).execute()
    
    if not conv.data or conv.data[0]['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    presentation_id = _get_active_presentation(conversation_id)
    return {
        "active_presentation_id": presentation_id
    }


@app.get("/api/presentations/{presentation_id}/versions")
async def list_presentation_versions(
    presentation_id: str,
    user_id: str = Depends(verify_auth)
):
    """
    Get all versions of a presentation.
    
    Args:
        presentation_id: UUID of presentation
    
    Returns:
        {
            "presentation_id": "uuid",
            "versions": [...],
            "total_versions": 2
        }
    """
    # Verify user owns presentation (via conversation)
    supabase = get_supabase_client()
    pres = supabase.from_('presentations').select('conversation_id').eq('id', presentation_id).execute()
    
    if not pres.data:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    conv = supabase.from_('conversations').select('user_id').eq('id', pres.data[0]['conversation_id']).execute()
    
    if not conv.data or conv.data[0]['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    versions = _get_presentation_versions(presentation_id)
    
    if versions is None:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    return {
        "presentation_id": presentation_id,
        "versions": versions,
        "total_versions": len(versions)
    }


@app.get("/api/presentations/{presentation_id}/versions/{version}")
async def get_presentation_version(
    presentation_id: str,
    version: int,
    user_id: str = Depends(verify_auth)
):
    """
    Get pages content of a specific version.
    
    Args:
        presentation_id: UUID of presentation
        version: Version number
    
    Returns:
        {
            "presentation_id": "uuid",
            "version": 2,
            "pages": [...],
            "total_pages": 2,
            "html_content": "..." (pages as list)
        }
    """
    # Verify user owns presentation
    supabase = get_supabase_client()
    pres = supabase.from_('presentations').select('conversation_id').eq('id', presentation_id).execute()
    
    if not pres.data:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    conv = supabase.from_('conversations').select('user_id').eq('id', pres.data[0]['conversation_id']).execute()
    
    if not conv.data or conv.data[0]['user_id'] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    version_data = _get_version_content(presentation_id, version)
    
    if version_data is None:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    
    # Convert PageContent objects to dicts for JSON response
    pages_list = []
    for page in version_data["pages"]:
        pages_list.append({
            "page_number": page.page_number,
            "html_content": page.html_content,
            "page_title": page.page_title
        })
    
    return {
        "presentation_id": presentation_id,
        "version": version,
        "pages": pages_list,
        "total_pages": version_data["total_pages"],
        "html_content": pages_list  # For backward compatibility
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)

