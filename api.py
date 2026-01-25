"""
FastAPI server cho version management APIs.
Chạy server này song song với WorkflowServer (server.py).

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from memory_helper_functions.slide_storage import get_slide_versions, get_slide_version_content, _load_slide_index

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


@app.get("/api/slides/active")
async def get_active_slide():
    """
    Lấy active slide_id từ slide_index.
    
    Returns:
        {
            "active_slide_id": "slide_001" hoặc null nếu không có
        }
    """
    index = _load_slide_index()
    return {
        "active_slide_id": index.active_slide_id
    }


@app.get("/api/slides/{slide_id}/versions")
async def list_slide_versions(slide_id: str):
    """
    Lấy danh sách tất cả versions của một slide.
    
    Args:
        slide_id: ID của slide (ví dụ: "slide_001")
    
    Returns:
        {
            "slide_id": "slide_001",
            "versions": [
                {
                    "version": 1,
                    "timestamp": "2026-01-25T14:00:00",
                    "user_request": "Tạo slide về AI"
                },
                {
                    "version": 2,
                    "timestamp": "2026-01-25T14:30:00",
                    "user_request": "Đổi màu nền",
                    "is_current": true
                }
            ],
            "total_versions": 2
        }
    
    Raises:
        404: Slide không tồn tại
    """
    versions = get_slide_versions(slide_id)
    
    if versions is None:
        raise HTTPException(
            status_code=404,
            detail=f"Slide '{slide_id}' not found"
        )
    
    return {
        "slide_id": slide_id,
        "versions": versions,
        "total_versions": len(versions)
    }


@app.get("/api/slides/{slide_id}/versions/{version}")
async def get_slide_version(slide_id: str, version: int):
    """
    Lấy nội dung HTML của một version cụ thể.
    
    Args:
        slide_id: ID của slide (ví dụ: "slide_001")
        version: Version number cần lấy
    
    Returns:
        {
            "slide_id": "slide_001",
            "version": 2,
            "html_content": "<!DOCTYPE html>..."
        }
    
    Raises:
        404: Slide hoặc version không tồn tại
    """
    html_content = get_slide_version_content(slide_id, version)
    
    if html_content is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for slide '{slide_id}'"
        )
    
    return {
        "slide_id": slide_id,
        "version": version,
        "html_content": html_content
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)

