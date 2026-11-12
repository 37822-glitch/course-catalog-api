# course-catalog-api

Backend of the course catalog: FastAPI, SQLAlchemy 2.1, PostgreSQL, Alembic and
GraphQL on Strawberry as a second entrance (Labs 4–8, "Advanced Web Technologies").

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

REST docs: <http://localhost:8000/docs>. GraphiQL:
<http://localhost:8000/graphql>. The password `change-me` is for training; real
projects do not commit passwords.

## What changed in the API

- REST rule failures now use RFC 9457 Problem Details with
  `application/problem+json` and a stable `type` URI. The shared rules live in
  `services.py`; `problem.py` translates their codes for HTTP.
- `/graphql` now accepts GraphQL POST requests and opens GraphiQL in a browser.
  GraphiQL is an interactive development client, while an application sends the
  same query and variables as JSON.
- `enroll` and `likeCourse` return expected rule failures inside `data` as
  `userErrors`. Invalid query text or an unexpected resolver failure appears in
  top-level `errors`.
- Every response has an `X-SQL-Queries` header. It counts database statements in
  that HTTP request and makes N+1 behavior measurable.
- GraphQL rejects a depth above 5, more than 10 aliases, a `limit` outside
  1–100, and invalid numeric student IDs. Unexpected exception text is masked;
  `GRAPHQL_INTROSPECTION` controls schema introspection.
- REST gained `GET /students/{id}` and
  `GET /students/{id}/enrollments` for the REST version of the My courses page.

## Example queries

The “My courses” query (in the GraphiQL Variables panel: `{"id": "2"}`):

```graphql
query MyCourses($id: ID!) {
  student(id: $id) {
    name
    enrollments {
      id
      course { title credits level }
    }
  }
}
```

The `enroll` mutation:

```graphql
mutation {
  enroll(input: {courseId: "api-design", studentId: "1"}) {
    enrollment { id course { title } student { name } }
    userErrors { code message }
  }
}
```

A successful answer has an enrollment and no rule errors:

```json
{
  "data": {
    "enroll": {
      "enrollment": {
        "id": "7",
        "course": { "title": "API Design: REST vs GraphQL" },
        "student": { "name": "Aigerim Sadykova" }
      },
      "userErrors": []
    }
  }
}
```

Repeating an existing enrollment, for example `courseId: "ai-integration"` and
`studentId: "3"`, returns a rule error inside `data`:

```json
{
  "data": {
    "enroll": {
      "enrollment": null,
      "userErrors": [
        {
          "code": "ALREADY_ENROLLED",
          "message": "Student is already enrolled in this course"
        }
      ]
    }
  }
}
```

## REST vs GraphQL comparison

The “My courses” screen of student 2; numbers from `measure.py` on the starting
data.

| Criterion | REST | GraphQL | Source |
|-----------|------|---------|--------|
| Requests and rounds per screen | 5 requests, 2 rounds | 1 request, 1 round | `measure.py`, step 8 |
| Bytes in the responses | 1130 bytes | 339 bytes | `measure.py`, step 8 |
| SQL queries per screen | 5 | 3 | `measure.py`, `X-SQL-Queries` |
| SQL growth with more students | Separate resource requests grow with the resources the screen needs | With DataLoaders: 3 queries for both 3 and 20 students; before them the two nested queries grew from 7/7 to 27/24 | `try_n_plus_1.py`, experiments 4–5 |
| Error in the query text | Route and parameter shape is fixed by the server; an unknown route is an HTTP error | Status remains 200 and details arrive in `errors`, including a `Did you mean` hint | experiments 1 and 8 |
| Expected rule error (repeated enrollment) | 409 Problem Details | 200 with `ALREADY_ENROLLED` in `data.enroll.userErrors` | steps 1 and 4 |
| HTTP cache | Standard HTTP methods, URLs, status codes, and cache headers work directly with shared HTTP caches | Usually POST to one URL, so ordinary HTTP caching needs application-aware persisted queries or another GraphQL cache | lecture section 14 |
| Protection from “expensive” queries | Route code fixes the work; each route applies its own pagination | Query depth 5, at most 10 aliases, checked arguments, masked internal errors, configurable introspection | experiments 6 and 7 |

**Conclusion.** I would keep simple resource lists and CRUD endpoints on REST,
because their URLs and HTTP semantics remain easy to cache and inspect. For a
composite personal screen such as My courses, GraphQL is the better fit: it used
1 request instead of 5, 1 network round instead of 2, 339 bytes instead of
1130, and 3 SQL statements instead of 5. DataLoaders also kept the nested query
at 3 SQL statements when the data grew from 3 to 20 students.

## Experiment log

| # | Experiment | What I saw | Cause | How I fixed it |
|---|------------|------------|-------|----------------|
| 1 | a typo in a field name, an argument name in `snake_case` | `Cannot query field 'titel' ... Did you mean 'title'`; `is_elective` was unknown | Strawberry exposes the typed schema and converts Python names to camelCase | used `title` and `isElective` |
| 2 | `\| None` removed from the `course` query, a nonexistent course | the nullable field first returned `{"course": null}`; after making it non-null, null propagated and `data` became null | GraphQL propagates null through a non-null field | restored `CourseType \| None` |
| 3 | a mutation with the GET method | HTTP 400: mutations are not allowed with GET | GET must stay read-only; GraphQL mutations use POST | sent the mutation as a POST body |
| 4 | `more_students.sql`: 3 and 20 students, the SQL counter | before loaders the two queries were 7/7 and then 27/24 SQL statements | nested relationship resolvers issued one query per parent row | added per-request DataLoaders |
| 5 | a DataLoader batch function that does not match rows by key | one version raised `WrongNumberOfResultsReturned`; another silently attached the wrong course | database row order and missing keys do not match the loader key list by position | grouped rows by key and returned one result for every requested key |
| 6 | six dangerous queries without protection and with it | before: depth and 12 aliases ran and database errors leaked; after: five short errors, and rejected queries used 0 SQL | the unprotected client controlled query cost and raw resolver exceptions | enabled depth, alias, argument, and masking protection |
| 7 | introspection off, a typo in a field name | `__schema` was rejected, ordinary queries worked, and `Did you mean` still revealed field names | disabling introspection hides the schema map but is not authorization | restored introspection for development and kept authorization as a separate concern |
| 8 | client failures: a typo, no `errors` check, the API stopped | `GraphQLRequestError: Cannot query field 'titel'`; without the check, only a null destructuring error; with no API, `fetch failed` | GraphQL can return errors with HTTP 200, while a network failure has no response | `gql` checks both `res.ok` and `body.errors`, then restored the working query |

## Decisions

- Rules and their error codes live once in `services.py` so REST and GraphQL do
  not duplicate checks that could drift apart. REST translates a code to an HTTP
  status and Problem Details; GraphQL translates the same code to `userErrors`.
- Loaders are created in each request `Context` because their cache must not leak
  objects between users or outlive the SQLAlchemy session. A batch function
  matches rows by key because SQL does not promise the same order as the input
  keys and some keys may have no row.
- `check_limit` and `parse_id` give clients clear messages for expected invalid
  input. `MaskErrors` is the second layer for unforeseen database or programming
  failures: it keeps the full traceback on the server but prevents implementation
  details from reaching the client.

## Bonus

- **Validation errors as Problem Details.** The `RequestValidationError` handler
  reads every item from `exc.errors()` and maps its location and message into an
  `errors` list. RFC 9457 permits extension members, so this list supplements the
  required Problem Details fields and lets the client fix every invalid value in
  one response.
