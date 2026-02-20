#!/usr/bin/env python3
"""
Run migration_v3 to set up database views required for the dashboard.
Safe to run multiple times (idempotent).
"""
import sys
import os
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def main():
    print("=" * 70)
    print("Running Migration V3: Teacher-First Dashboard")
    print("=" * 70)
    print()
    
    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ ERROR: DATABASE_URL not set.")
        print("   Please set DATABASE_URL in .env file in the project root.")
        sys.exit(1)
    
    # Check if migration already applied (check for v_support_status view)
    import psycopg2
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_schema = 'public' 
                AND table_name = 'v_support_status'
            )
        """)
        view_exists = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        if view_exists:
            print("✓ Migration V3 already applied (v_support_status view exists)")
            print()
            print("If you're still seeing errors, check:")
            print("  1. Ensure student_enrollments table has data")
            print("  2. Ensure API server is running: uvicorn api.main:app --reload --port 8000")
            return
    except Exception as e:
        print(f"⚠️  Warning: Could not check migration status: {e}")
        print("   Proceeding with migration...")
        print()
    
    # Run migration
    migration_file = ROOT / "schema" / "migration_v3_teacher_first.sql"
    if not migration_file.exists():
        print(f"❌ ERROR: Migration file not found: {migration_file}")
        sys.exit(1)
    
    print(f"📄 Reading migration file: {migration_file.name}")
    sql = migration_file.read_text(encoding="utf-8", errors="replace")
    
    print("🔄 Running migration...")
    print("   (This may take a moment...)")
    print()
    
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Execute migration SQL
        cur.execute(sql)
        
        cur.close()
        conn.close()
        
        print("✅ Migration V3 completed successfully!")
        print()
        print("The following views should now be available:")
        print("  • v_teacher_roster")
        print("  • v_support_status")
        print("  • v_priority_students")
        print("  • v_growth_last_two")
        print()
        print("You can now start the app with: python start_app.py")
        
    except Exception as e:
        print(f"❌ ERROR running migration: {e}")
        print()
        print("Common issues:")
        print("  1. Ensure base schema is set up (students_core, student_enrollments)")
        print("  2. Check DATABASE_URL is correct")
        print("  3. Ensure you have permissions to create views")
        sys.exit(1)

if __name__ == "__main__":
    main()
