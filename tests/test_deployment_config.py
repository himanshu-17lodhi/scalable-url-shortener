import json
from pathlib import Path
from app.config import Settings


def test_supabase_database_url_normalization():
    """Verify Supabase postgres:// and postgresql:// URLs normalize to postgresql+asyncpg://."""
    supabase_postgres_url = "postgres://postgres.ref:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    s1 = Settings(_env_file=None, DATABASE_URL=supabase_postgres_url)
    assert s1.DATABASE_URL.startswith("postgresql+asyncpg://")

    supabase_postgresql_url = "postgresql://postgres.ref:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    s2 = Settings(_env_file=None, DATABASE_URL=supabase_postgresql_url)
    assert s2.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_upstash_redis_url_configuration():
    """Verify Upstash rediss:// TLS Redis URLs are accepted by Settings."""
    upstash_redis_url = "rediss://default:secret_token@global-endpoint.upstash.io:6379"
    s = Settings(_env_file=None, REDIS_URL=upstash_redis_url)
    assert s.REDIS_URL == upstash_redis_url
    assert s.REDIS_URL.startswith("rediss://")


def test_vercel_config_file_validity():
    """Verify vercel.json exists and routes to app/main.py ASGI entrypoint."""
    vercel_json_path = Path("vercel.json")
    assert vercel_json_path.exists()
    with open(vercel_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["builds"][0]["src"] == "app/main.py"
    assert data["builds"][0]["use"] == "@vercel/python"
