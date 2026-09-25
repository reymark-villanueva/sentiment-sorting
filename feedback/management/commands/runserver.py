"""
Overrides the default `runserver` port.

On this machine, port 8000 (Django's hardcoded default) is permanently held
by a local PostgreSQL instance unrelated to this project, which makes plain
`python manage.py runserver` fail with a misleading
"Error: You don't have permission to access that port." — it's not actually
a permissions problem, the port is just already in use.

Subclassing the staticfiles runserver command (rather than the bare
django.core one) keeps the usual DEBUG-mode static file serving behavior;
only the default port changes. You can still pass an explicit host:port
(e.g. `python manage.py runserver 8000`) to override this.
"""

from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)


class Command(StaticfilesRunserverCommand):
    default_port = '8123'
