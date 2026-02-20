#!/usr/bin/env python3
"""
Check database status: migration, views, and data availability.
Helps diagnose why the dashboard might not be loading.
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

def main():
    print("=" * 70)
    print("Database Status Check")
    print("=" * 70)
    print()
    
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL not set in .env")
        print("   Please set DATABASE_URL in .env file")
        return
    
    import psycopg2
    try:
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        
        # Check migration_v3 views
        print("📋 Checking Migration V3 Views:")
        views_to_check = [
            'v_support_status',
            'v_priority_students',
            'v_growth_last_two',
            'v_teacher_roster'
        ]
        
        for view_name in views_to_check:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (view_name,))
            exists = cur.fetchone()[0]
            status = "✓" if exists else "✗"
            print(f"   {status} {view_name}")
        
        print()
        
        # Check required tables
        print("📋 Checking Required Tables:")
        tables_to_check = [
            'students_core',
            'student_enrollments',
            'assessments',
            'benchmark_thresholds'
        ]
        
        for table_name in tables_to_check:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                )
            """, (table_name,))
            exists = cur.fetchone()[0]
            status = "✓" if exists else "✗"
            print(f"   {status} {table_name}")
        
        print()
        
        # Check data counts
        print("📊 Data Counts:")
        
        # students_core
        try:
            cur.execute("SELECT COUNT(*) FROM students_core")
            count = cur.fetchone()[0]
            print(f"   students_core: {count} rows")
        except Exception as e:
            print(f"   students_core: ERROR - {e}")
        
        # student_enrollments
        try:
            cur.execute("SELECT COUNT(*) FROM student_enrollments")
            count = cur.fetchone()[0]
            print(f"   student_enrollments: {count} rows")
            if count == 0:
                print("      ⚠️  WARNING: No enrollments found! Dashboard needs enrollments.")
        except Exception as e:
            print(f"   student_enrollments: ERROR - {e}")
        
        # assessments
        try:
            cur.execute("SELECT COUNT(*) FROM assessments")
            count = cur.fetchone()[0]
            print(f"   assessments: {count} rows")
        except Exception as e:
            print(f"   assessments: ERROR - {e}")
        
        # benchmark_thresholds
        try:
            cur.execute("SELECT COUNT(*) FROM benchmark_thresholds")
            count = cur.fetchone()[0]
            print(f"   benchmark_thresholds: {count} rows")
            if count == 0:
                print("      ⚠️  WARNING: No benchmark thresholds! Dashboard needs thresholds.")
        except Exception as e:
            print(f"   benchmark_thresholds: ERROR - {e}")
        
        print()
        
        # Test v_support_status view if it exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_schema = 'public' 
                AND table_name = 'v_support_status'
            )
        """)
        view_exists = cur.fetchone()[0]
        
        if view_exists:
            print("🧪 Testing v_support_status view:")
            try:
                cur.execute("SELECT COUNT(*) FROM v_support_status")
                count = cur.fetchone()[0]
                print(f"   ✓ View returns {count} rows")
                if count == 0:
                    print("      ⚠️  WARNING: View exists but returns no data!")
                    print("      This could mean:")
                    print("        1. No student_enrollments data")
                    print("        2. No assessments linked to enrollments")
                    print("        3. Missing benchmark_thresholds")
            except Exception as e:
                print(f"   ✗ ERROR querying view: {e}")
        else:
            print("🧪 v_support_status view does not exist")
            print("   Run: python run_migration_v3.py")
        
        print()
        
        # Check if assessments have enrollment_id
        try:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(enrollment_id) as with_enrollment_id,
                    COUNT(*) - COUNT(enrollment_id) as missing_enrollment_id
                FROM assessments
            """)
            row = cur.fetchone()
            total, with_enrollment, missing = row
            print("📋 Assessment enrollment_id status:")
            print(f"   Total assessments: {total}")
            print(f"   With enrollment_id: {with_enrollment}")
            print(f"   Missing enrollment_id: {missing}")
            if missing > 0:
                print("      ⚠️  Some assessments are missing enrollment_id")
        except Exception as e:
            print(f"   ERROR: {e}")
        
        cur.close()
        conn.close()
        
        print()
        print("=" * 70)
        print("Summary:")
        print("=" * 70)
        print()
        print("If views are missing: Run 'python run_migration_v3.py'")
        print("If student_enrollments is empty: Create enrollments for your students")
        print("If benchmark_thresholds is empty: Run threshold setup scripts")
        print()
        
    except psycopg2.Error as e:
        print(f"❌ Database connection error: {e}")
        print()
        print("Check:")
        print("  1. DATABASE_URL is correct in .env")
        print("  2. Database is accessible")
        print("  3. Network connection is working")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
