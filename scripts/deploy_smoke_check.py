#!/usr/bin/env python3
"""
Deploy smoke check: verify API /health, optional auth behavior, and optional DB connectivity.
Usage:
  python scripts/deploy_smoke_check.py --api-url https://api.example.com
  python scripts/deploy_smoke_check.py --api-url https://api.example.com --check-db
  python scripts/deploy_smoke_check.py --api-url https://api.example.com --check-auth
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(description="Smoke check a deployed API")
    parser.add_argument(
        "--api-url",
        required=True,
        help="Base URL of the API (e.g. https://api.example.com)",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Also verify DATABASE_URL connectivity (requires DATABASE_URL in env)",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Verify that protected routes return 401 without a token",
    )
    args = parser.parse_args()

    base = args.api_url.rstrip("/")
    failed = []

    # 1. Health
    try:
        req = urllib.request.Request(f"{base}/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read().decode()
            if r.status != 200:
                failed.append(f"/health returned status {r.status}")
            else:
                body = json.loads(data)
                if body.get("status") != "ok":
                    failed.append(f"/health body missing status=ok: {body}")
                else:
                    print("OK /health")
    except Exception as e:
        failed.append(f"/health: {e}")

    # 2. Optional: protected route returns 401 without token
    if args.check_auth:
        req = urllib.request.Request(f"{base}/api/students", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                failed.append(
                    "/api/students returned 200 without Authorization (expected 401 in production)"
                )
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print("OK /api (auth required, got 401 without token)")
            else:
                failed.append(f"/api/students returned {e.code} (expected 401)")
        except Exception as e:
            failed.append(f"/api auth check: {e}")

    # 3. Optional: DB connectivity
    if args.check_db:
        url = os.environ.get("DATABASE_URL")
        if not url:
            failed.append("--check-db requested but DATABASE_URL not set")
        else:
            try:
                import psycopg2
                conn = psycopg2.connect(url)
                conn.close()
                print("OK database (DATABASE_URL reachable)")
            except Exception as e:
                failed.append(f"database: {e}")

    if failed:
        print("\nFailed:", file=sys.stderr)
        for f in failed:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)
    print("\nSmoke check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
