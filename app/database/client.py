"""
Supabase client configuration for backend.
Uses ANON_KEY with JWT token for RLS protection.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from app.auth.context import get_current_jwt_token

load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")  # Anon key for RLS protection

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env file. "
        "Backend uses ANON_KEY with JWT token for RLS protection."
    )

# Create Supabase client singleton with ANON_KEY
_supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def get_supabase_client(jwt_token: str = None) -> Client:
    """
    Get the configured Supabase client.
    If jwt_token is provided, set it to enable RLS protection.
    If jwt_token is None, try to get it from context.
    
    Args:
        jwt_token: Optional JWT token to set for RLS. If None, tries to get from context.
    
    Returns:
        Supabase client instance with JWT set (if available)
    """
    # If jwt_token not provided, try to get from context
    if not jwt_token:
        jwt_token = get_current_jwt_token()
    
    if jwt_token:
        # Set JWT token to enable RLS
        _supabase_client.postgrest.auth(jwt_token)
    
    return _supabase_client

