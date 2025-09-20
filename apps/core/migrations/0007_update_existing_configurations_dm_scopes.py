from django.db import migrations

def update_existing_scopes(apps, schema_editor):
    """
    Update existing SlackAppConfiguration records to include comprehensive DM scopes
    """
    SlackAppConfiguration = apps.get_model('core', 'SlackAppConfiguration')

    new_comprehensive_scopes = 'channels:read,groups:read,im:read,mpim:read,chat:write,files:write,users:read,im:write,mpim:write,users:read.email'

    for config in SlackAppConfiguration.objects.all():
        current_scopes = set(config.scopes.split(','))
        new_scopes = set(new_comprehensive_scopes.split(','))

        # Add any missing scopes
        updated_scopes = current_scopes.union(new_scopes)
        config.scopes = ','.join(sorted(updated_scopes))
        config.save()

def reverse_scopes_update(apps, schema_editor):
    """
    Remove the added DM scopes from existing configurations
    """
    SlackAppConfiguration = apps.get_model('core', 'SlackAppConfiguration')

    scopes_to_remove = {'im:read', 'mpim:read', 'mpim:write', 'users:read.email'}

    for config in SlackAppConfiguration.objects.all():
        current_scopes = set(config.scopes.split(','))
        updated_scopes = current_scopes - scopes_to_remove
        config.scopes = ','.join(sorted(updated_scopes))
        config.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_update_scopes_for_dm_support'),
    ]

    operations = [
        migrations.RunPython(update_existing_scopes, reverse_scopes_update),
    ]