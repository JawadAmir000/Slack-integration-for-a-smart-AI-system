#!/usr/bin/env python
"""
Create Django admin user script
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_integration.settings')
django.setup()

from django.contrib.auth.models import User

# Admin user credentials
username = 'admin'
email = 'xawadamir0@gmail.com'
password = '1qazZAQ!'

# Create admin user if it doesn't exist
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print("Admin user created successfully!")
    print("Login credentials:")
    print(f"   Username: {username}")
    print(f"   Password: {password}")
    print(f"   Email: {email}")
    print("Login at: http://localhost:8000/admin/")
else:
    print(f"Admin user '{username}' already exists!")
    print("Use existing credentials:")
    print(f"   Username: {username}")
    print(f"   Password: {password}")
    print("Login at: http://localhost:8000/admin/")