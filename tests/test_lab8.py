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


if __name__ == "__main__":
    unittest.main()
