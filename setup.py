#!/usr/bin/env python
"""
Quick setup script for Slack Integration Django app
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_integration.settings')
    django.setup()

def run_migrations():
    """Run database migrations"""
    print("🔄 Running database migrations...")
    execute_from_command_line(['manage.py', 'makemigrations'])
    execute_from_command_line(['manage.py', 'migrate'])
    print("✅ Database migrations completed!")

def create_superuser():
    """Create Django superuser"""
    print("\n👤 Creating Django superuser...")
    print("You'll need this to access the admin panel and authenticate users.")
    execute_from_command_line(['manage.py', 'createsuperuser'])

def collect_static():
    """Collect static files"""
    print("\n📁 Collecting static files...")
    execute_from_command_line(['manage.py', 'collectstatic', '--noinput'])
    print("✅ Static files collected!")

def test_slack_config():
    """Test Slack configuration"""
    print("\n🔍 Testing Slack configuration...")
    
    from django.conf import settings
    
    required_settings = [
        'SLACK_CLIENT_ID',
        'SLACK_CLIENT_SECRET', 
        'SLACK_SIGNING_SECRET',
        'SLACK_REDIRECT_URI'
    ]
    
    missing = []
    for setting in required_settings:
        if not getattr(settings, setting, None):
            missing.append(setting)
    
    if missing:
        print(f"❌ Missing Slack settings: {', '.join(missing)}")
        print("Please check your .env file!")
        return False
    else:
        print("✅ All Slack settings configured!")
        print(f"   Client ID: {settings.SLACK_CLIENT_ID}")
        print(f"   Redirect URI: {settings.SLACK_REDIRECT_URI}")
        return True

def main():
    """Main setup function"""
    print("🚀 Setting up Slack Integration Django App")
    print("=" * 50)
    
    # Setup Django
    setup_django()
    
    # Run migrations
    run_migrations()
    
    # Test configuration
    config_ok = test_slack_config()
    
    # Collect static files
    collect_static()
    
    print("\n" + "=" * 50)
    
    if config_ok:
        print("🎉 Setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Create a superuser account (optional but recommended):")
        print("   python manage.py createsuperuser")
        print("\n2. Start the development server:")
        print("   python manage.py runserver")
        print("\n3. Open your browser and go to:")
        print("   http://localhost:8000/")
        print("\n4. In your Slack app settings, make sure the redirect URL is:")
        print("   http://localhost:8000/api/slack/auth/callback/")
        
        print("\n🔧 Available endpoints:")
        print("   • Home: http://localhost:8000/")
        print("   • Dashboard: http://localhost:8000/dashboard/")
        print("   • Admin: http://localhost:8000/admin/")
        print("   • API: http://localhost:8000/api/slack/")
    else:
        print("❌ Setup completed with configuration issues!")
        print("Please fix the Slack configuration in your .env file.")

if __name__ == '__main__':
    main()