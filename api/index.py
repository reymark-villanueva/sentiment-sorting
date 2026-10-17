"""Vercel entry point: exposes the Django WSGI app as `app` for the @vercel/python runtime."""
import sys
from pathlib import Path

# api/ is a sub-folder, so put the project root (manage.py, feedback/, ...) on the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from isu_library_project.wsgi import application  # noqa: E402

app = application
