# Course Catalog API

A standalone FastAPI backend for the Lab 4 course catalog.

## Requirements

- Python 3.10 or newer

## Set up the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
fastapi dev main.py
```

The API runs at <http://127.0.0.1:8000>. Interactive documentation is available
at <http://127.0.0.1:8000/docs>, with ReDoc at
<http://127.0.0.1:8000/redoc>.

## Test

```bash
python -m unittest discover -s tests -v
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Confirm that the API is running |
| `GET` | `/courses` | List, filter, sort, and paginate courses |
| `GET` | `/courses/{course_id}` | Get one course or return a 404 |

### Course query parameters

- `is_elective=true` returns the two elective courses.
- `is_elective=false` returns the four required courses.
- `sort=title` sorts alphabetically; all other values use likes descending.
- `page` defaults to `1` and `page_size` defaults to `20`.

Filtering happens before sorting, and pagination is applied last through a
FastAPI dependency.

## What was verified

- `GET /` returned `{"message": "Course Catalog API is running"}`.
- `GET /courses` returned all six courses ordered by likes: `ai-integration`,
  `modern-frontend`, `web-security`, `backend-fastapi`,
  `databases-postgresql`, and `api-design`.
- `GET /courses?is_elective=true` returned `ai-integration` and `api-design`.
- `GET /courses?is_elective=false` returned the four required courses.
- `GET /courses?sort=title` returned the expected alphabetical order.
- Pagination with `page_size=2` returned the expected two courses on pages
  1–3 and an empty list on page 4.
- `GET /courses/web-security` returned the matching course.
- `GET /courses/nope` returned `404` with `{"detail": "Course not found"}`.
- `/docs`, `/redoc`, and `/openapi.json` loaded successfully.
- The OpenAPI schema contained exactly three application paths.
- All 15 automated tests passed on Python 3.12.
