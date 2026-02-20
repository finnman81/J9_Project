#!/usr/bin/env python3
"""
Test the API endpoints to see what they're actually returning.
Helps diagnose why the frontend might be getting null responses.
"""
import sys
import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

def test_endpoint(name, func, *args, **kwargs):
    """Test an API endpoint function."""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")
    try:
        result = func(*args, **kwargs)
        if result is None:
            print("❌ Result: None")
        elif isinstance(result, dict):
            print(f"✓ Result: dict with {len(result)} keys")
            print(f"  Keys: {list(result.keys())[:10]}...")
            # Check if it's an empty response
            if result.get('total_students') == 0:
                print("  ⚠️  WARNING: total_students is 0")
            elif 'total_students' in result:
                print(f"  total_students: {result.get('total_students')}")
        else:
            print(f"✓ Result: {type(result).__name__}")
            print(f"  Value: {str(result)[:200]}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=" * 70)
    print("API Endpoints Test")
    print("=" * 70)
    
    # Import API functions
    from api.routers.metrics import get_teacher_kpis, get_priority_students, get_growth_metrics, get_distribution
    from core.database import get_v_support_status
    
    # Test with Reading subject
    print("\n📋 Testing with subject='Reading'")
    test_endpoint("get_teacher_kpis", get_teacher_kpis, subject="Reading")
    test_endpoint("get_priority_students", get_priority_students, subject_area="Reading")
    test_endpoint("get_growth_metrics", get_growth_metrics, subject="Reading")
    test_endpoint("get_distribution", get_distribution, subject="Reading")
    
    # Test with Math subject
    print("\n📋 Testing with subject='Math'")
    test_endpoint("get_teacher_kpis", get_teacher_kpis, subject="Math")
    test_endpoint("get_priority_students", get_priority_students, subject_area="Math")
    test_endpoint("get_growth_metrics", get_growth_metrics, subject="Math")
    test_endpoint("get_distribution", get_distribution, subject="Math")
    
    # Test the underlying view
    print("\n📋 Testing underlying view: get_v_support_status")
    try:
        df_reading = get_v_support_status(subject_area="Reading")
        print(f"✓ Reading: {len(df_reading)} rows")
        if len(df_reading) > 0:
            print(f"  Columns: {list(df_reading.columns)[:10]}")
        
        df_math = get_v_support_status(subject_area="Math")
        print(f"✓ Math: {len(df_math)} rows")
        if len(df_math) > 0:
            print(f"  Columns: {list(df_math.columns)[:10]}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("\nIf endpoints return None or errors, check:")
    print("  1. API server logs for exceptions")
    print("  2. Browser console for network errors")
    print("  3. CORS headers if requests are blocked")

if __name__ == "__main__":
    main()
