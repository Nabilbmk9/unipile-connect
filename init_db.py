#!/usr/bin/env python3
"""
Database initialization script for Unipile Connect
"""
import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

def main():
    print("🚀 Initializing Unipile Connect Database...")
    
    try:
        # Import database functions
        from app.database import init_db, create_tables
        
        print("✅ Database modules imported successfully")
        
        # Create tables
        print("📊 Creating database tables...")
        create_tables()
        print("✅ Tables created successfully")
        
        # Initialize database
        print("🔧 Initializing database...")
        init_db()
        print("✅ Database initialized successfully")
        
        print("\n🎉 Database setup complete!")
        print("📱 You can now run the application with: python run.py")
        print("👤 Users can register new accounts through the application")
        print("🔐 No default users are created - this is a production-ready system")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
