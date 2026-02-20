#!/usr/bin/env python
"""
Quick inspection script: print teacher KPI totals by school_year for Math/Reading.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from api.routers.dashboard import dashboard_filters
from api.routers.metrics import get_teacher_kpis


def main():
    f = dashboard_filters()
    years = f.get("school_years", [])
    print("Years from filters:", years)
    for subj in ("Reading", "Math"):
        print(f"\nSubject: {subj}")
        for y in years:
            year_param = None if y == "All" else y
            kpis = get_teacher_kpis(school_year=year_param, subject=subj)
            print(
                f"  Year {y!r}: total_students={kpis['total_students']}, "
                f"assessed={kpis['assessed_students']}"
            )


if __name__ == "__main__":
    main()

