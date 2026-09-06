# Ascendancy Academy

Homeschool desk for the DiFede family: attendance, weighted grades, calendar, and printable records.

- Local: `http://127.0.0.1:8030`
- Rocky: `http://192.168.68.71:8030`
- Public (after tunnel): `https://aa.difedes.com`

## Stack

FastAPI + Jinja + SQLAlchemy + Alembic + Postgres (sqlite is fine for a local laptop copy).

OpenAPI / docs / ReDoc are disabled. Debug is off.

## Local run

1. Copy `.env.example` to `.env` and fill secrets. Never commit `.env`.
2. `python -m venv .venv` then install `requirements.txt`.
3. `python run.py`

First boot creates tables and seeds Joe, Mrs. DiFede, and Gregory. Change the seed passwords on first login.

## Teacher vs student

- `/login/teacher` — enter attendance and grades
- `/login/student` — read-only grades, attendance, calendar

## Print

- Blank OCR-ready month: `/print/attendance/month?blank=1`
- Year retention packet: `/print/attendance/year?blank=1`
- Paper grading sheet: `/print/grade-sheet/<assignment_id>`

Deploy steps: [deploy/README.md](deploy/README.md).
