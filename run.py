#!/usr/bin/env python3
"""
Simple startup script for Unipile Connect
"""
import os
import sys
import uvicorn
from pathlib import Path

def main():
    # Add the app directory to Python path
    app_dir = Path(__file__).parent / "app"
    sys.path.insert(0, str(app_dir))
    
    # Check if required packages are installed
    try:
        import fastapi
        import uvicorn
        import jinja2
        import requests
        from dotenv import load_dotenv
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return 1
    
    # Check if .env file exists
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        print("⚠️  Warning: .env file not found")
        print("Creating default .env file...")
        
        default_env = """# Unipile Configuration
UNIPILE_API_BASE=https://api8.unipile.com:13816/api/v1
UNIPILE_API_HOST=https://api8.unipile.com:13816
UNIPILE_API_KEY=your-unipile-api-key-here
APP_BASE_URL=http://127.0.0.1:8000

# Database Configuration
DATABASE_URL=sqlite:///./unipile_connect.db

# Authentication Configuration
SECRET_KEY=your-secret-key-change-this-in-production
"""
        with open(env_file, 'w') as f:
            f.write(default_env)
        print("✅ Created default .env file")
        print("⚠️  Please update UNIPILE_API_KEY with your actual key")
    
    # Check if database exists and initialize if needed
    db_file = Path(__file__).parent / "unipile_connect.db"
    if not db_file.exists():
        print("🗄️  Database not found, initializing...")
        try:
            from app.database import init_db, create_tables
            create_tables()
            init_db()
            print("✅ Database initialized successfully")
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            print("Please run: python init_db.py")
            return 1
    
    print("🚀 Starting Unipile Connect...")
    print("🌐 Open: http://127.0.0.1:8000")
    print("👤 Create your first account at: http://127.0.0.1:8000/users/register")
    print("⏹️  Press Ctrl+C to stop")
    
    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
