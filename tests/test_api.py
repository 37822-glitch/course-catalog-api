import unittest

from fastapi.testclient import TestClient

from data import find_course, get_all_courses
from main import app
from models import Course


client = TestClient(app)


class CourseModelTests(unittest.TestCase):
    def test_defaults_are_false_and_zero(self) -> None:
        course = Course(
            id="sample",
            title="Sample Course",
            description="A sample course.",
            credits=3,
        )

        self.assertFalse(course.is_elective)
        self.assertEqual(course.likes, 0)

    def test_required_fields_are_preserved(self) -> None:
        course = Course(
            id="sample",
            title="Sample Course",
            description="A sample course.",
            credits=3,
            is_elective=True,
            likes=8,
        )

        self.assertEqual(course.id, "sample")
        self.assertEqual(course.title, "Sample Course")
        self.assertEqual(course.description, "A sample course.")
        self.assertEqual(course.credits, 3)
        self.assertTrue(course.is_elective)
        self.assertEqual(course.likes, 8)


class CourseDataTests(unittest.TestCase):
    def test_catalog_contains_the_six_lab_courses(self) -> None:
        courses = get_all_courses()

        self.assertEqual(
            [course.id for course in courses],
            [
                "modern-frontend",
                "backend-fastapi",
                "databases-postgresql",
                "api-design",
                "web-security",
                "ai-integration",
            ],
        )

    def test_get_all_courses_returns_a_copy(self) -> None:
        first_result = get_all_courses()
        first_result.clear()

        self.assertEqual(len(get_all_courses()), 6)

    def test_find_course_returns_match_or_none(self) -> None:
        self.assertEqual(find_course("web-security").title, "Web Security Essentials")
        self.assertIsNone(find_course("nope"))


class BasicRouteTests(unittest.TestCase):
    def test_root_reports_that_api_is_running(self) -> None:
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Course Catalog API is running"})

    def test_courses_default_to_popularity_order(self) -> None:
        response = client.get("/courses")

        self.assertEqual(response.status_code, 200)
        courses = response.json()
        self.assertEqual(
            [course["id"] for course in courses],
            [
                "ai-integration",
                "modern-frontend",
                "web-security",
                "backend-fastapi",
                "databases-postgresql",
                "api-design",
            ],
        )
        self.assertEqual(
            set(courses[0]),
            {"id", "title", "description", "credits", "is_elective", "likes"},
        )

    def test_get_course_returns_the_requested_course(self) -> None:
        response = client.get("/courses/web-security")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": "web-security",
                "title": "Web Security Essentials",
                "description": "JWT/OAuth2, XSS, CSRF, and SQL injection defense.",
                "credits": 4,
                "is_elective": False,
                "likes": 21,
            },
        )

    def test_get_course_returns_required_404(self) -> None:
        response = client.get("/courses/nope")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Course not found"})


if __name__ == "__main__":
    unittest.main()
