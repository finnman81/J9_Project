"""
Quick start script for the Literacy Assessment System
"""
import subprocess
import sys
import os

def main():
    print("=" * 60)
    print("Literacy Assessment System - Quick Start")
    print("=" * 60)
    
    # Check if database exists, if not initialize it
    if not os.path.exists('database/literacy_assessments.db'):
        print("\nInitializing database...")
        from database import init_database
        init_database()
        print("✓ Database initialized")
        
        # Check if normalized_grades.xlsx exists for migration
        if os.path.exists('normalized_grades.xlsx'):
            migrate = input("\nFound normalized_grades.xlsx. Migrate existing data? (y/n): ")
            if migrate.lower() == 'y':
                print("Migrating data...")
                from migrate_data import migrate_excel_to_database
                migrate_excel_to_database()
                print("✓ Data migrated")
    
    print("\nStarting Streamlit application...")
    print("The app will open in your browser automatically.")
    print("Press Ctrl+C to stop the server.\n")
    
    # Run streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])

if __name__ == '__main__':
    main()
