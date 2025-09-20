# Generated manually to update existing SlackAppConfiguration scopes

from django.db import migrations


def update_existing_scopes(apps, schema_editor):
    """
    Update existing SlackAppConfiguration records to include im:write scope
    """
    SlackAppConfiguration = apps.get_model('core', 'SlackAppConfiguration')

    for config in SlackAppConfiguration.objects.all():
        scopes = config.scopes
        if 'im:write' not in scopes:
            # Add im:write scope if not already present
            config.scopes = scopes + ',im:write'
            config.save()


def reverse_update_scopes(apps, schema_editor):
    """
    Remove im:write scope from existing configurations
    """
    SlackAppConfiguration = apps.get_model('core', 'SlackAppConfiguration')

    for config in SlackAppConfiguration.objects.all():
        scopes = config.scopes
        if 'im:write' in scopes:
            # Remove im:write scope
            config.scopes = scopes.replace(',im:write', '').replace('im:write,', '').replace('im:write', '')
            config.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_im_write_scope'),
    ]

    operations = [
        migrations.RunPython(update_existing_scopes, reverse_update_scopes),
    ]