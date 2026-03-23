import os
from dotenv import load_dotenv

load_dotenv()

# Supabase PostgreSQL configuration
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Service role key - bypasses RLS, use ONLY on backend (never expose to frontend)
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
