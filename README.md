# course-catalog-api

Backend of the course catalog: FastAPI, SQLAlchemy 2.1, PostgreSQL, and Alembic
migrations (Labs 4–7 of "Advanced Web Technologies").

## How to run

You need Python 3.11 or newer and PostgreSQL 16 or newer.

Once, as the `postgres` superuser, create the role and the database:

```sql
CREATE ROLE catalog_app LOGIN PASSWORD 'change-me';
CREATE DATABASE course_catalog OWNER catalog_app;
```

Then, from the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
psql -h localhost -U catalog_app -d course_catalog -v ON_ERROR_STOP=1 -f seed.sql
alembic check
fastapi dev main.py
```

API documentation: <http://localhost:8000/docs>. The password `change-me` is
for teaching; real passwords must not be stored in a repository. To see the SQL
while studying the lab, add `SQL_ECHO=true` only to the local `.env` file.

## What changed in the API

- Courses, students, and enrollments now live in PostgreSQL, so data survives an
  API restart. Every request receives its own SQLAlchemy `Session`.
- `POST /enrollments` now accepts `courseId` and `studentId`; a student must
  first be created with `POST /students`.
- `POST /students`, `GET /enrollments`, and `GET /stats/courses` were added.
  The enrollment list uses joins to include `courseTitle` and `studentName`.
- Courses have the required `level` field. `GET /courses?level=beginner`
  filters it together with the existing elective filter, sorting, and pages.
- Named UNIQUE and foreign-key violations become specific `409` or `404`
  responses. Pydantic rejects a short student name with `422`; an unknown
  database violation is still raised as a server error.

## Migrations

| Command | What it does |
|---------|--------------|
| `alembic upgrade head` | applies all the missing migrations |
| `alembic downgrade -1` | rolls back the last migration |
| `alembic current` | shows the version of the database |
| `alembic history` | shows the chain of migrations |
| `alembic revision --autogenerate -m "text"` | writes a draft from models vs. database |
| `alembic check` | reports whether the models and the database have diverged |
| `alembic upgrade 0001:0002 --sql` | prints the SQL of a migration without running it |
| `alembic stamp head` | marks the database as up to date without running migrations |

Migration `0001` creates the catalog tables. An existing Lab 6 database needed
`alembic stamp head`, because applying `0001` to its existing tables produced
`DuplicateTable`. Migration `0002` adds and fills the required course level.

## Experiment log

| # | Experiment | What I saw | Cause | How I fixed it |
|---|------------|------------|-------|----------------|
| 1 | the `uq` template in `naming_convention` changed | model-only names were `students_email_unique` and `enrollments_course_id_unique`; the database kept its `_key` names | the shortened template omitted the full multi-column name and did not match PostgreSQL | restored `%(table_name)s_%(column_0_N_name)s_key`; `check_models.py` returned `none` twice |
| 2 | `min_length` removed from `StudentIn`, name `N` | the request reached PostgreSQL, violated `students_name_check`, and returned `500` | without Pydantic validation the CHECK was the last protection, and that CHECK is intentionally absent from the HTTP mapping | restored `Field(min_length=2)`; the request returned `422` before SQL |
| 3 | a typo in a constraint name in the dictionary | duplicate email violated the real `students_email_key`, but the API returned `500` | dictionary lookup requires the exact name reported by `exc.orig.diag.constraint_name` | restored the `students_email_key` key; the response returned `409` |
| 4 | `title` without `NOT NULL`, then changed to `varchar(100)` | `alembic check` reported `modify_nullable`, then `modify_type`, and exited non-zero | the live schema differed from `Base.metadata` | restored `NOT NULL` and the `text` type; the check became clean |
| 5 | automatic migration `0002` on existing data | `NotNullViolation`: `courses.level` contained null values; the database stayed at `0001` | autogenerate added a required column in one step and cannot reason about existing rows | changed it to add nullable, backfill by elective status, then set `NOT NULL` |
| 6 | `import models` commented out in `env.py` | autogenerate proposed dropping the index and all three application tables | no model import meant empty `Base.metadata`, so every real table looked extra | deleted the dangerous `0003`, restored the import, and verified a clean check |
| 7 | a `phone` field in the model without a migration | `alembic check` detected an added `students.phone` column and failed | the model had advanced beyond the database schema | removed the experimental field; only migrations `0001` and `0002` remain |
| 8 | two migrations from revision `0002` | `alembic heads` showed `0003` and `0004`; `upgrade head` failed with “Multiple head revisions” | both branches had the same parent, so the history had no single destination | created a `0005` merge to verify the solution, then removed all three experimental files and returned to head `0002` |

## Decisions

- The response is selected by constraint name because one SQLSTATE such as
  `23505` can represent several different UNIQUE constraints. The error is
  caught after `commit()` so the database remains the authority and there is no
  race between a preliminary `SELECT` and the later `INSERT`.
- Likes use `UPDATE courses SET likes = likes + 1 ... RETURNING` so PostgreSQL
  performs one atomic increment. Reading and writing in Python can lose an
  update when two requests read the same old value.
- Migration `0002` has three steps because a required column cannot be added to
  a non-empty table without values. It first permits NULL, deterministically
  backfills all existing rows, and only then enforces `NOT NULL`, in one
  transaction.

## Migration 0002 self-check

| What to check | Result |
|---------------|--------|
| Goal and steps | Yes — add `level`, fill all old rows, then require it |
| Data | Yes — elective courses become `beginner`; all others become `intermediate` |
| Renames and drops | Yes — the upgrade has none; the downgrade drops `level` and therefore its values |
| Rollback | Yes — `downgrade -1` removed the column and `upgrade head` recreated and refilled it |
| Verification | Yes — the static SQL was read, the full cycle passed, and `alembic check` is clean |
| History | Yes — the final chain is `<base> -> 0001 -> 0002`, with one head |
| Application | Yes — ORM, response schema, level filter, migration, and repeatable seed agree |

## Bonus

- **Task 1 — CHECK autogenerate limitation.** Adding the level-value CHECK to
  the model left `alembic check` clean and produced an empty autogenerated
  migration, because Alembic does not compare CHECK constraints. A manual
  migration rejected `level='expert'`. A plain constraint name in `downgrade`
  was transformed into `courses_courses_level_check_check`; wrapping the final
  name in `op.f()` made the rollback work. The experimental model change and
  migration were removed afterward.
- **Task 3 — N+1.** `python try_n_plus_1.py` measured 7 queries for lazy loading
  and 2 for `selectinload`, with the same 6 enrollments. N+1 is visible by
  enabling SQL echo and counting repeated relationship queries. `selectinload`
  keeps the parent query separate and fetches all children with one `IN` query;
  `joinedload` uses a join in one result set and may duplicate parent rows.
