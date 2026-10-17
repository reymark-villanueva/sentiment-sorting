# Isabela State University - Cauayan Campus Library
## Feedback & Student Sentiment Monitoring System

A Django 5.x web application for collecting student/faculty library feedback
and giving library staff a real-time sentiment monitoring dashboard.

- **Backend:** Django 5.x, SQLite (dev) / Supabase Postgres (production on Vercel)
- **Frontend:** Pure Django templates (`{% extends %}` / `{% block %}` / `{% static %}`), vanilla CSS with custom-property design tokens, vanilla JS — no Tailwind/Bootstrap/React/build tooling.

---

## Project Layout

```
isu_library_project/     # Django project package (settings, root urls, wsgi/asgi)
feedback/                 # Core app: models, forms, views, urls, admin, tests, migrations
templates/
├── base.html              # Public site layout (nav, footer, messages)
├── home.html               # Public portal hero + service grid + campus stats
├── feedback_step.html      # 4-step feedback wizard (service → rating → comments → submit)
├── partials/
│   └── _service_icon.html  # Shared service-icon SVG partial (used by all 3 templates below)
└── admin/
    ├── base_admin.html     # Staff console shell (collapsible sidebar)
    └── dashboard.html      # Real-time sentiment monitoring dashboard
static/
├── css/style.css           # Design system (CSS custom properties)
├── js/feedback.js          # Feedback wizard controller
├── js/admin.js              # Sidebar toggle, filters, scrollspy
├── js/dashboard-charts.js  # Renders the sentiment trend line chart from real bucketed data
└── img/                    # logo.svg, library_hero.svg
```

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

python manage.py migrate       # applies schema + seeds the 8 standard library services
python manage.py createsuperuser
python manage.py runserver
```

Settings come from a `.env` file in the project root (copy `.env.example`; `.env` is git-ignored) or
from the real environment, which takes priority. `DEBUG` is on locally and always off on Vercel (set
`DJANGO_DEBUG=0` or `1` to override); with `DEBUG` off the app refuses to start without
`DJANGO_SECRET_KEY`. After pulling an update, run `pip install -r requirements.txt` and
`python manage.py migrate` first.

## Deploying to Vercel + Supabase

1. **Supabase:** create a project (pick the region closest to your users) and copy the *Transaction
   pooler* connection string from the Connect page. Put it in your local `.env` as `DATABASE_URL`.
   Then run `python manage.py migrate` and `python manage.py createsuperuser` from your computer; they
   create the tables, seed the 8 library services, and create the first staff account. Turn off
   Supabase's Data API, or enable row-level security on every table, so the tables are not readable
   through the public API.
2. **Vercel:** import the GitHub repo and add these environment variables: `DJANGO_SECRET_KEY`,
   `DATABASE_URL`, `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY` (and `ALLOWED_HOSTS` /
   `CSRF_TRUSTED_ORIGINS` for a custom domain; `*.vercel.app` URLs are allowed automatically).
3. Add the deployed domain to the reCAPTCHA key's allowed domains.

`vercel.json` routes every request to `api/index.py`, `.vercelignore` keeps the bundle small, and
WhiteNoise serves the static files, so there is no build step.

Visit:
- `/` — public portal
- `/feedback/` — feedback wizard
- `/admin/dashboard/` — staff sentiment dashboard (requires a staff account)
- `/django-admin/` — Django's built-in model admin (services, users, raw feedback logs)

## Tests

```bash
python manage.py test feedback
```
