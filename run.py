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
    
    # Initialize database schema (safe to call repeatedly)
    print("\nEnsuring database schema is up to date...")
    from database import init_database
    init_database()
    print("✓ Database ready")
    
    print("\nStarting Streamlit application...")
    print("The app will open in your browser automatically.")
    print("Press Ctrl+C to stop the server.\n")
    
    # Run streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])

if __name__ == '__main__':
    main()
