# Course Catalog API

The FastAPI backend for the YZ-AWT course catalog. Lab 5 adds browser-safe
camelCase responses, CORS, persistent-in-memory likes, and enrollment routes
for the Next.js frontend.

## What changed

- `CORSMiddleware` grants the exact browser origin
  `http://localhost:3000` permission to read API responses. The policy allows
  only the `GET` and `POST` methods and the `Content-Type` request header used
  by this lab.
- `CamelModel` keeps Python field names in snake_case while publishing JSON and
  validation errors with camelCase names such as `isElective`, `courseId`, and
  `studentName`.
- `POST /courses/{course_id}/like` increments a course's in-memory counter and
  returns the updated course, `POST /enrollments` validates and creates a record
  with `201 Created`, and `GET /enrollments` lists the records created since the
  current server process started.

An updated like response has the complete course shape:

```json
{
  "id": "web-security",
  "title": "Web Security Essentials",
  "description": "JWT/OAuth2, XSS, CSRF, and SQL injection defense.",
  "credits": 4,
  "isElective": false,
  "likes": 22
}
```

Creating the first enrollment returns:

```json
{
  "id": 1,
  "courseId": "web-security",
  "studentName": "Aigerim"
}
```

`GET /enrollments` returns the same records as a JSON array.

## Requirements and setup

- Python 3.10 or newer

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
fastapi dev main.py --host 127.0.0.1 --port 8000
```

The API is available at <http://localhost:8000>. Open Swagger UI at
<http://localhost:8000/docs>, ReDoc at <http://localhost:8000/redoc>, and the
OpenAPI schema at <http://localhost:8000/openapi.json>.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Health message |
| `GET` | `/courses` | Filter, search, sort, and paginate courses |
| `GET` | `/courses/{course_id}` | Read one course |
| `POST` | `/courses/{course_id}/like` | Increment and return a course's likes |
| `POST` | `/enrollments` | Validate and create an enrollment |
| `GET` | `/enrollments` | List in-memory enrollments |

Successful course and enrollment responses use camelCase aliases:

```json
{
  "courseId": "web-security",
  "studentName": "Aigerim"
}
```

`studentName` must have at least two characters. Unknown course identifiers
return `404` with `{"detail":"Course not found"}`. New enrollments return
`201 Created`.

## Course query parameters

- `is_elective=true` returns electives; `false` returns required courses.
- `sort=popular` sorts by likes and `sort=title` sorts alphabetically.
- `q` performs a case-insensitive title search.
- `page` starts at `1`; `page_size` must be between `1` and `100`.

Filtering and search occur before sorting, with pagination applied last.

## CORS configuration

The default allowed origin is exactly `http://localhost:3000`. Configure one
or more comma-separated origins before startup when another frontend origin is
required:

```bash
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 fastapi dev main.py
```

The final policy deliberately permits only `GET` and `POST`, and only the
`Content-Type` request header. A trailing slash changes an origin and is not
accepted unless explicitly configured.

## Runtime state

Likes and enrollments are intentionally stored in memory for this lab. They
persist across requests in one process and reset when the API restarts. No
database is required.

## Selected bonus tasks

- Pydantic alias generation creates a single camelCase API contract.
- `CORS_ORIGINS` supports environment-specific frontend origins.
- CORS methods and headers use explicit allowlists instead of wildcards.

The two intentionally destructive bonus experiments are not retained in the
final source.

## Verify

```bash
python -m unittest discover -s tests -v
```
