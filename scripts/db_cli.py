#!/usr/bin/env python3
"""
Run SQL against the Supabase database using DATABASE_URL from .env.
Usage:
  python scripts/db_cli.py "SELECT * FROM students LIMIT 5"
  python scripts/db_cli.py -f schema/migration_v3_teacher_first.sql
  echo "SELECT 1" | python scripts/db_cli.py
"""
import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set. Add it to .env in the project root.", file=sys.stderr)
        sys.exit(1)

    import psycopg2
    import psycopg2.extras

    sql = None
    if len(sys.argv) >= 2:
        if sys.argv[1] == "-f" and len(sys.argv) >= 3:
            path = ROOT / sys.argv[2]
            if not path.exists():
                print(f"File not found: {path}", file=sys.stderr)
                sys.exit(1)
            sql = path.read_text(encoding="utf-8", errors="replace")
        else:
            sql = " ".join(sys.argv[1:])
    if not sql and not sys.stdin.isatty():
        sql = sys.stdin.read()

    if not sql or not sql.strip():
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(0)

    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(sql)
        if cur.description:
            rows = cur.fetchall()
            if rows:
                # Print as simple table (header + rows)
                keys = list(rows[0].keys())
                widths = [max(len(str(k)), max(len(str(r[k])) for r in rows)) for k in keys]
                header = " | ".join(k.ljust(widths[i]) for i, k in enumerate(keys))
                print(header)
                print("-" * len(header))
                for r in rows:
                    print(" | ".join(str(r[k]).ljust(widths[i]) for i, k in enumerate(keys)))
                print(f"\n({len(rows)} row(s))")
            else:
                print("(0 rows)")
        else:
            print(f"OK ({cur.rowcount} row(s) affected)")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
