# Isabela State University - Cauayan Campus Library
## Feedback & Student Sentiment Monitoring System

A Django 5.x web application for collecting student/faculty library feedback
and giving library staff a real-time sentiment monitoring dashboard.

- **Backend:** Django 5.x, SQLite (dev)
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

Visit:
- `/` — public portal
- `/feedback/` — feedback wizard
- `/admin/dashboard/` — staff sentiment dashboard (requires a staff account)
- `/django-admin/` — Django's built-in model admin (services, users, raw feedback logs)

## Tests

```bash
python manage.py test feedback
```
