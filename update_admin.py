#!/usr/bin/env python
"""
Update Django admin user password
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'slack_integration.settings')
django.setup()

from django.contrib.auth.models import User

# Update admin user
try:
    user = User.objects.get(username='admin')
    user.email = 'xawadamir0@gmail.com'
    user.set_password('1qazZAQ!')
    user.save()
    
    print("Admin user updated successfully!")
    print("Your login credentials:")
    print("   Username: admin")
    print("   Password: 1qazZAQ!")
    print("   Email: xawadamir0@gmail.com")
    print("")
    print("You can now login at: http://localhost:8000/admin/")
    
except User.DoesNotExist:
    # Create new user if doesn't exist
    User.objects.create_superuser('admin', 'xawadamir0@gmail.com', '1qazZAQ!')
    print("New admin user created!")
    print("Username: admin")
    print("Password: 1qazZAQ!")
    print("Login at: http://localhost:8000/admin/")