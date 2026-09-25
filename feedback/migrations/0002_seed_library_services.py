"""
Data migration: seed the 8 standard ISU Cauayan Campus Library service categories.
"""

from django.db import migrations

SERVICES = [
    {
        'name': 'Facilities',
        'icon': 'building',
        'description': 'Reading carrels, air-conditioning, lighting, and cleanliness.',
        'order': 1,
    },
    {
        'name': 'Library Staff',
        'icon': 'users',
        'description': 'Desk librarians, catalog reference assistance, and courteous guidance.',
        'order': 2,
    },
    {
        'name': 'Internet/Wi-Fi',
        'icon': 'wifi',
        'description': 'Campus Wi-Fi connectivity, bandwidth speed, and signal coverage.',
        'order': 3,
    },
    {
        'name': 'Computer Services',
        'icon': 'monitor',
        'description': 'OPAC research terminals, desktop PCs, and printing stations.',
        'order': 4,
    },
    {
        'name': 'Borrowing & Returning',
        'icon': 'book-open',
        'description': 'Circulation desk book loans, renewals, and RFID drop box.',
        'order': 5,
    },
    {
        'name': 'Study Areas',
        'icon': 'layout',
        'description': 'Silent research zones, collaborative discussion pods, and cubicles.',
        'order': 6,
    },
    {
        'name': 'Online Resources',
        'icon': 'globe',
        'description': 'Philippine e-Library, ScienceDirect, and EBSCO subscription portals.',
        'order': 7,
    },
    {
        'name': 'Other',
        'icon': 'help-circle',
        'description': 'General university inquiries, lost & found, and facility suggestions.',
        'order': 8,
    },
]


def seed_services(apps, schema_editor):
    LibraryService = apps.get_model('feedback', 'LibraryService')
    for entry in SERVICES:
        LibraryService.objects.update_or_create(
            name=entry['name'],
            defaults={
                'icon': entry['icon'],
                'description': entry['description'],
                'order': entry['order'],
                'is_active': True,
            },
        )


def unseed_services(apps, schema_editor):
    LibraryService = apps.get_model('feedback', 'LibraryService')
    LibraryService.objects.filter(name__in=[entry['name'] for entry in SERVICES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_services, unseed_services),
    ]
