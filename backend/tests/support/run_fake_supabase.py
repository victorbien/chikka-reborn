"""Serve FakeSupabase over HTTP for a local end-to-end run. TEST USE ONLY.

    python -m tests.support.run_fake_supabase --port 54400 --database-url postgresql+asyncpg://...

Secrets come from the environment so they never appear in shell history.
"""

import argparse
import os

import uvicorn

from tests.support.fake_supabase import FakeSupabase


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=54400)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    fake = FakeSupabase(
        database_url=args.database_url,
        jwt_secret=os.environ["SUPABASE_JWT_SECRET"],
        anon_key=os.environ["SUPABASE_ANON_KEY"],
        service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )
    uvicorn.run(fake.app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
