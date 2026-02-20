#!/usr/bin/env python3
"""
Startup script for School Assessment System.
Launches the FastAPI backend and React frontend in separate PowerShell windows.
"""
import subprocess
import sys
import os
import socket
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).resolve().parent

def find_available_port(start_port=8000, max_attempts=10):
    """Find an available port starting from start_port, trying up to max_attempts ports."""
    for i in range(max_attempts):
        port = start_port + i
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    # If all ports are taken, return the last one tried (will fail with clear error)
    return start_port + max_attempts - 1

def check_migration():
    """Check if migration_v3 has been applied."""
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    
    url = os.environ.get("DATABASE_URL")
    if not url:
        return False
    
    try:
        import psycopg2
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_schema = 'public' 
                AND table_name = 'v_support_status'
            )
        """)
        exists = cur.fetchone()[0]
        cur.close()
        conn.close()
        return exists
    except Exception:
        return False

def main():
    print("=" * 70)
    print("School Assessment System - Starting Application")
    print("=" * 70)
    print()
    
    # Check if .env exists
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        print("⚠️  Warning: .env file not found. Make sure DATABASE_URL is set.")
        print()
    
    # Check if migration_v3 has been applied
    print("🔍 Checking database migration status...")
    migration_applied = check_migration()
    if not migration_applied:
        print("⚠️  WARNING: Migration V3 not detected!")
        print()
        print("   The dashboard requires migration_v3 to be run first.")
        print("   Run this command to apply the migration:")
        print()
        print("   python run_migration_v3.py")
        print()
        response = input("   Continue anyway? (y/n): ").strip().lower()
        if response != 'y':
            print("\n   Exiting. Please run the migration first.")
            return
        print()
    else:
        print("✓ Migration V3 is applied")
        print()
    
    # Find an available port for the backend
    print("🔍 Finding available port for backend...")
    backend_port = find_available_port(start_port=8000)
    if backend_port != 8000:
        print(f"   Port 8000 is in use, using port {backend_port} instead")
    else:
        print(f"   Using port {backend_port}")
    print()
    
    # Update frontend .env file with the detected port
    web_env_file = PROJECT_ROOT / "web" / ".env"
    web_env_content = f"VITE_API_URL=http://127.0.0.1:{backend_port}\n"
    web_env_file.write_text(web_env_content, encoding="utf-8")
    print(f"✓ Updated web/.env with API URL: http://127.0.0.1:{backend_port}")
    print()
    
    # Start backend API server in a new PowerShell window
    print(f"🚀 Starting FastAPI backend server (port {backend_port})...")
    backend_cmd = [
        "powershell",
        "-NoExit",
        "-Command",
        f"cd '{PROJECT_ROOT}'; uvicorn api.main:app --reload --port {backend_port}"
    ]
    backend_process = subprocess.Popen(
        backend_cmd,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    print("   ✓ Backend window opened")
    print()
    
    # Wait a moment for backend to start
    import time
    time.sleep(2)
    
    # Start frontend dev server in a new PowerShell window
    print("🚀 Starting React frontend dev server (port 5173)...")
    frontend_cmd = [
        "powershell",
        "-NoExit",
        "-Command",
        f"cd '{PROJECT_ROOT / 'web'}'; npm run dev"
    ]
    frontend_process = subprocess.Popen(
        frontend_cmd,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    print("   ✓ Frontend window opened")
    print()
    
    print("=" * 70)
    print("✅ Both servers are starting!")
    print()
    print("📋 Server URLs:")
    print(f"   • Backend API:  http://localhost:{backend_port}")
    print(f"   • API Docs:     http://localhost:{backend_port}/docs")
    print("   • Frontend:     http://localhost:5173")
    print()
    print("💡 Two PowerShell windows have been opened:")
    print("   • One for the backend (uvicorn)")
    print("   • One for the frontend (npm run dev)")
    print()
    print("⚠️  To stop the servers, close the PowerShell windows or press Ctrl+C in each.")
    print("=" * 70)
    print()
    
    # Keep script running (optional - user can close this window too)
    try:
        input("Press Enter to exit this window (servers will keep running)...")
    except KeyboardInterrupt:
        print("\n\nClosing...")
        # Optionally kill processes (commented out - let user close windows manually)
        # backend_process.terminate()
        # frontend_process.terminate()

if __name__ == "__main__":
    main()
