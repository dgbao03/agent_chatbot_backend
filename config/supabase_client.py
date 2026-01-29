"""
Supabase client configuration for backend.
Uses SERVICE_ROLE_KEY for full access to database (bypasses RLS).
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # Service role key for backend

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file. "
        "Backend needs SERVICE_ROLE_KEY (not ANON_KEY) for full database access."
    )

# Create Supabase client with service role key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_supabase_client() -> Client:
    """
    Get the configured Supabase client.
    This client has full access to the database (bypasses RLS).
    """
    return supabase

