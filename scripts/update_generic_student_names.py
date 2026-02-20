#!/usr/bin/env python3
"""
Update generic upper-grade student names (e.g. "Fifth Student 01", "Sixth Student 10")
to real first names in students_core and students tables.

Safe to run multiple times. Use --dry-run to preview changes without updating.
"""

import re
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

# Pool of real first names (80+ so we can assign one per generic student)
FIRST_NAMES = [
    "Liam", "Emma", "Noah", "Olivia", "Aiden", "Ava", "Lucas", "Sophia", "Mason", "Isabella",
    "Ethan", "Mia", "James", "Charlotte", "Alexander", "Amelia", "Henry", "Harper", "Sebastian", "Evelyn",
    "Jack", "Abigail", "Owen", "Ella", "Samuel", "Scarlett", "Matthew", "Grace", "Joseph", "Chloe",
    "Levi", "Victoria", "Mateo", "Riley", "David", "Aria", "John", "Lily", "Wyatt", "Aubrey",
    "Carter", "Zoey", "Julian", "Penelope", "Luke", "Lillian", "Grayson", "Addison", "Isaac", "Layla",
    "Jayden", "Natalie", "Theodore", "Camila", "Gabriel", "Hannah", "Anthony", "Brooklyn", "Dylan", "Zoe",
    "Leo", "Nora", "Lincoln", "Leah", "Jaxon", "Savannah", "Asher", "Audrey", "Christopher", "Claire",
    "Josiah", "Eleanor", "Andrew", "Skylar", "Theodore", "Ellie", "Joshua", "Sadie", "Ezra", "Aaliyah",
    "Colton", "Paisley", "Caleb", "Kennedy", "Hunter", "Samantha", "Christian", "Violet", "Isaiah", "Stella",
]

# Pattern: "Fifth Student 01", "Sixth Student 10", "Eighth Student 03", or "Sixth Student 10 Sixth" etc.
GENERIC_PATTERN = re.compile(
    r"^(Fifth|Sixth|Seventh|Eighth)\s+Student\s+\d+",
    re.IGNORECASE,
)


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("[DRY RUN] No changes will be written.\n")

    from core.database import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()

    # 1) Find all generic display_name in students_core
    cur.execute(
        """
        SELECT student_uuid, display_name
        FROM students_core
        WHERE display_name ~ '^(Fifth|Sixth|Seventh|Eighth) Student [0-9]+'
        ORDER BY display_name
        """
    )
    core_rows = cur.fetchall()

    # 2) Find all generic student_name in students (legacy)
    cur.execute(
        """
        SELECT student_id, student_name
        FROM students
        WHERE student_name ~ '^(Fifth|Sixth|Seventh|Eighth) Student [0-9]+'
        ORDER BY student_name
        """
    )
    legacy_rows = cur.fetchall()

    # Build unique generic -> new name mapping (use same new name for same generic base)
    # Normalize to "Grade Student NN" so "Sixth Student 10 Sixth" and "Sixth Student 10" map to same name
    def normalize(name):
        m = GENERIC_PATTERN.match(name.strip())
        return m.group(0) if m else name

    seen_generic = set()
    name_index = [0]  # use closure to pick next name

    def assign_name(generic_display):
        key = normalize(generic_display)
        if key not in seen_generic:
            seen_generic.add(key)
            if name_index[0] >= len(FIRST_NAMES):
                raise SystemExit("Not enough first names in pool. Add more to FIRST_NAMES.")
            new_name = FIRST_NAMES[name_index[0]]
            name_index[0] += 1
            return new_name
        # Already assigned - need to return same name for same key
        # So we need to store key -> new_name mapping
        return None  # will build map instead

    generic_to_new = {}
    for row in core_rows:
        uuid, display_name = row[0], row[1]
        key = normalize(display_name)
        if key not in generic_to_new:
            if len(generic_to_new) >= len(FIRST_NAMES):
                raise SystemExit("Not enough first names in pool.")
            generic_to_new[key] = FIRST_NAMES[len(generic_to_new)]
    for row in legacy_rows:
        sid, student_name = row[0], row[1]
        key = normalize(student_name)
        if key not in generic_to_new:
            if len(generic_to_new) >= len(FIRST_NAMES):
                raise SystemExit("Not enough first names in pool.")
            generic_to_new[key] = FIRST_NAMES[len(generic_to_new)]

    if not generic_to_new:
        print("No generic student names found. Nothing to update.")
        conn.close()
        return

    print(f"Found {len(generic_to_new)} unique generic names to replace with real first names.\n")

    # Update students_core by display_name (may have suffix like " Sixth")
    updates_core = 0
    for row in core_rows:
        student_uuid, display_name = row[0], row[1]
        key = normalize(display_name)
        new_name = generic_to_new[key]
        if display_name == new_name:
            continue
        print(f"  students_core: {display_name!r} -> {new_name!r}")
        if not dry_run:
            cur.execute(
                "UPDATE students_core SET display_name = %s WHERE student_uuid = %s",
                (new_name, student_uuid),
            )
            updates_core += cur.rowcount
    if not dry_run and updates_core:
        print(f"  Updated {updates_core} students_core row(s).")

    # Update students by student_name
    updates_legacy = 0
    for row in legacy_rows:
        student_id, student_name = row[0], row[1]
        key = normalize(student_name)
        new_name = generic_to_new[key]
        if student_name == new_name:
            continue
        print(f"  students: {student_name!r} -> {new_name!r}")
        if not dry_run:
            cur.execute(
                "UPDATE students SET student_name = %s WHERE student_id = %s",
                (new_name, student_id),
            )
            updates_legacy += cur.rowcount
    if not dry_run and updates_legacy:
        print(f"  Updated {updates_legacy} students row(s).")

    if not dry_run and (updates_core or updates_legacy):
        conn.commit()
        print("\n[OK] Generic student names updated.")
    elif dry_run:
        print("\n[DRY RUN] Re-run without --dry-run to apply changes.")

    conn.close()


if __name__ == "__main__":
    main()
