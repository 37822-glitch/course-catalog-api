import importlib
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import select


class ServicesAndProblemDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.services = importlib.import_module("services")
        cls.db_module = importlib.import_module("db")
        cls.models = importlib.import_module("models")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_duplicate_email_is_problem_details(self) -> None:
        response = self.client.post(
            "/students",
            json={"name": "Aigerim Two", "email": "aigerim@example.com"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        self.assertEqual(
            response.json(),
            {
                "type": "https://example.com/problems/email-taken",
                "title": "Email already in use",
                "status": 409,
                "detail": "Student with this email already exists",
                "instance": "/students",
            },
        )

    def test_missing_course_is_problem_details(self) -> None:
        response = self.client.get("/courses/no-such")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        self.assertEqual(response.json()["type"], "https://example.com/problems/course-not-found")
        self.assertEqual(response.json()["instance"], "/courses/no-such")

    def test_starlette_errors_use_about_blank_and_keep_allow_header(self) -> None:
        missing = self.client.get("/nope")
        wrong_method = self.client.delete("/courses")

        self.assertEqual(
            missing.json(),
            {
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "instance": "/nope",
            },
        )
        self.assertEqual(wrong_method.status_code, 405)
        self.assertEqual(wrong_method.headers["allow"], "GET")
        self.assertEqual(wrong_method.json()["title"], "Method Not Allowed")

    def test_service_rolls_back_after_known_constraint_error(self) -> None:
        with self.db_module.SessionLocal() as session:
            with self.assertRaises(self.services.ServiceError) as caught:
                self.services.create_student(
                    session, "Aigerim Two", "aigerim@example.com"
                )

            self.assertEqual(caught.exception.code, "EMAIL_TAKEN")
            count = session.scalar(
                select(self.models.Student).where(
                    self.models.Student.email == "aigerim@example.com"
                )
            )
            self.assertIsNotNone(count)


class GraphQLCourseQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_courses_query_returns_requested_fields_in_popularity_order(self) -> None:
        response = self.client.post(
            "/graphql",
            json={"query": "{ courses(limit: 2) { id title credits } }"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "data": {
                    "courses": [
                        {
                            "id": "ai-integration",
                            "title": "AI/LLM Integration",
                            "credits": 5,
                        },
                        {
                            "id": "modern-frontend",
                            "title": "Modern Frontend: React & Next.js",
                            "credits": 5,
                        },
                    ]
                }
            },
        )

    def test_course_query_returns_null_for_an_unknown_id(self) -> None:
        response = self.client.post(
            "/graphql",
            json={"query": '{ course(id: "nope") { title } }'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": {"course": None}})

    def test_schema_exposes_course_fields_and_camel_case(self) -> None:
        graphql_api = importlib.import_module("graphql_api")
        schema = graphql_api.schema.as_str()

        self.assertIn("type Course", schema)
        self.assertIn("isElective: Boolean!", schema)
        self.assertIn("courses(isElective: Boolean = null, limit: Int! = 20)", schema)
        self.assertIn("course(id: ID!): Course", schema)


class GraphQLNestedQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_my_courses_returns_student_enrollments_and_courses(self) -> None:
        response = self.client.post(
            "/graphql",
            json={
                "query": """
                query MyCourses($id: ID!) {
                  student(id: $id) {
                    name
                    enrollments { id course { title credits level } }
                  }
                }
                """,
                "variables": {"id": "2"},
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("errors", response.json())
        student = response.json()["data"]["student"]
        self.assertEqual(student["name"], "Daniyar Bekov")
        self.assertEqual(
            [item["course"]["title"] for item in student["enrollments"]],
            [
                "Modern Frontend: React & Next.js",
                "Backend Foundations: FastAPI",
                "AI/LLM Integration",
            ],
        )

    def test_schema_exposes_student_enrollment_and_nested_queries(self) -> None:
        graphql_api = importlib.import_module("graphql_api")
        schema = graphql_api.schema.as_str()

        self.assertIn("type Student", schema)
        self.assertIn("type Enrollment", schema)
        self.assertIn("students(limit: Int! = 20): [Student!]!", schema)
        self.assertIn("student(id: ID!): Student", schema)
        self.assertIn("enrollments(limit: Int! = 20): [Enrollment!]!", schema)


class GraphQLMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.db_module = importlib.import_module("db")
        cls.models = importlib.import_module("models")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_repeated_enrollment_returns_expected_user_error(self) -> None:
        response = self.client.post(
            "/graphql",
            json={
                "query": """
                mutation {
                  enroll(input: {courseId: "ai-integration", studentId: "3"}) {
                    enrollment { id }
                    userErrors { code message }
                  }
                }
                """
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("errors", response.json())
        payload = response.json()["data"]["enroll"]
        self.assertIsNone(payload["enrollment"])
        self.assertEqual(payload["userErrors"][0]["code"], "ALREADY_ENROLLED")

    def test_create_student_uses_shared_name_and_email_validation(self) -> None:
        cases = (
            ("N", "valid@example.com", "INVALID_NAME"),
            ("Valid Name", "not-an-email", "INVALID_EMAIL"),
        )

        for name, email, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                response = self.client.post(
                    "/graphql",
                    json={
                        "query": """
                        mutation CreateStudent($input: CreateStudentInput!) {
                          createStudent(input: $input) {
                            student { id }
                            userErrors { code message }
                          }
                        }
                        """,
                        "variables": {"input": {"name": name, "email": email}},
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertNotIn("errors", response.json())
                payload = response.json()["data"]["createStudent"]
                self.assertIsNone(payload["student"])
                self.assertEqual(payload["userErrors"][0]["code"], expected_code)

    def test_like_course_returns_incremented_course(self) -> None:
        before = self.client.get("/courses/api-design").json()["likes"]
        try:
            response = self.client.post(
                "/graphql",
                json={
                    "query": """
                    mutation {
                      likeCourse(id: "api-design") {
                        course { id likes }
                        userErrors { code }
                      }
                    }
                    """
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertNotIn("errors", response.json())
            payload = response.json()["data"]["likeCourse"]
            self.assertEqual(payload["course"]["likes"], before + 1)
            self.assertEqual(payload["userErrors"], [])
        finally:
            with self.db_module.SessionLocal.begin() as session:
                session.execute(
                    self.models.Course.__table__.update()
                    .where(self.models.Course.id == "api-design")
                    .values(likes=before)
                )


class SQLQueryCounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_rest_course_list_reports_one_sql_query(self) -> None:
        response = self.client.get("/courses")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-sql-queries"], "1")

    def test_student_nested_query_uses_three_batched_sql_queries(self) -> None:
        response = self.client.post(
            "/graphql",
            json={
                "query": "{ students { name enrollments { course { title } } } }"
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("errors", response.json())
        self.assertEqual(response.headers["x-sql-queries"], "3")

    def test_enrollment_nested_query_uses_three_batched_sql_queries(self) -> None:
        response = self.client.post(
            "/graphql",
            json={
                "query": "{ enrollments { id course { title } student { name } } }"
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("errors", response.json())
        self.assertEqual(response.headers["x-sql-queries"], "3")
        first = response.json()["data"]["enrollments"][0]
        self.assertEqual(first["course"]["title"], "Modern Frontend: React & Next.js")
        self.assertEqual(first["student"]["name"], "Aigerim Sadykova")


class GraphQLProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def _first_error(self, query: str) -> tuple[str, str]:
        response = self.client.post("/graphql", json={"query": query})
        return response.json()["errors"][0]["message"], response.headers["x-sql-queries"]

    def test_depth_and_alias_limits_reject_queries_before_database_access(self) -> None:
        cycle = """
        query Cycle {
          student(id: 2) {
            enrollments { student { enrollments { student { enrollments { id } } } } }
          }
        }
        """
        aliases = "{ " + " ".join(
            f'a{i}: course(id: "api-design") {{ title }}' for i in range(1, 13)
        ) + " }"

        depth_message, depth_sql = self._first_error(cycle)
        alias_message, alias_sql = self._first_error(aliases)

        self.assertIn("exceeds maximum operation depth of 5", depth_message)
        self.assertEqual(depth_sql, "0")
        self.assertEqual(alias_message, "12 aliases found. Allowed: 10")
        self.assertEqual(alias_sql, "0")

    def test_argument_checks_are_clear_and_internal_errors_are_masked(self) -> None:
        limit_message, _ = self._first_error("{ courses(limit: -1) { id } }")
        id_message, _ = self._first_error('{ student(id: "abc") { name } }')
        huge_id_message, _ = self._first_error(
            '{ student(id: "99999999999999999999") { name } }'
        )

        self.assertEqual(limit_message, "limit must be between 1 and 100")
        self.assertEqual(id_message, "Invalid ID: 'abc'")
        self.assertEqual(huge_id_message, "Unexpected error.")

    def test_introspection_is_enabled_by_default(self) -> None:
        config = importlib.import_module("config")
        response = self.client.post(
            "/graphql",
            json={"query": "{ __schema { queryType { name } } }"},
        )

        self.assertTrue(config.settings.graphql_introspection)
        self.assertEqual(response.json()["data"]["__schema"]["queryType"]["name"], "Query")


class MyCoursesRestRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_student_and_student_enrollments_supply_the_rest_screen(self) -> None:
        student = self.client.get("/students/2")
        enrollments = self.client.get("/students/2/enrollments")

        self.assertEqual(student.status_code, 200)
        self.assertEqual(student.json()["name"], "Daniyar Bekov")
        self.assertEqual(enrollments.status_code, 200)
        self.assertEqual(
            [item["courseId"] for item in enrollments.json()],
            ["modern-frontend", "backend-fastapi", "ai-integration"],
        )
        self.assertEqual(student.headers["x-sql-queries"], "1")
        self.assertEqual(enrollments.headers["x-sql-queries"], "1")

    def test_unknown_student_is_problem_details(self) -> None:
        response = self.client.get("/students/99")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        self.assertEqual(
            response.json()["type"],
            "https://example.com/problems/student-not-found",
        )


class ValidationProblemDetailsBonusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def test_all_request_validation_errors_use_problem_details(self) -> None:
        response = self.client.post(
            "/students",
            json={"name": "N", "email": "bad"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.headers["content-type"], "application/problem+json")
        self.assertEqual(
            response.json()["type"],
            "https://example.com/problems/validation-error",
        )
        self.assertEqual(response.json()["detail"], "2 invalid value(s) in the request")
        self.assertEqual(
            [(item["in"], item["field"]) for item in response.json()["errors"]],
            [("body", "name"), ("body", "email")],
        )


class CreateStudentBonusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app, raise_server_exceptions=False)

    def create_student(self, name: str, email: str) -> dict:
        response = self.client.post(
            "/graphql",
            json={
                "query": """
                mutation CreateStudent($input: CreateStudentInput!) {
                  createStudent(input: $input) {
                    student { id name }
                    userErrors { code message }
                  }
                }
                """,
                "variables": {"input": {"name": name, "email": email}},
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_whitespace_name_is_one_shared_rule_with_rest_translation(self) -> None:
        response = self.client.post(
            "/students",
            json={"name": "  ", "email": "sp@example.com"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["type"],
            "https://example.com/problems/invalid-name",
        )
        self.assertEqual(response.json()["detail"], "Name must have at least 2 characters")

    def test_create_student_mutation_returns_shared_rule_errors(self) -> None:
        invalid = self.create_student("N", "n@example.com")
        duplicate = self.create_student("Nurlan Abenov", "aigerim@example.com")

        self.assertEqual(
            invalid["data"]["createStudent"]["userErrors"][0]["code"],
            "INVALID_NAME",
        )
        self.assertIsNone(invalid["data"]["createStudent"]["student"])
        self.assertEqual(
            duplicate["data"]["createStudent"]["userErrors"][0]["code"],
            "EMAIL_TAKEN",
        )

    def test_schema_exposes_create_student_mutation(self) -> None:
        graphql_api = importlib.import_module("graphql_api")

        self.assertIn(
            "createStudent(input: CreateStudentInput!): CreateStudentPayload!",
            graphql_api.schema.as_str(),
        )


if __name__ == "__main__":
    unittest.main()
