import unittest

from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from data import find_course, get_all_courses
from main import app, pagination
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


class CourseQueryTests(unittest.TestCase):
    def test_filter_elective_courses(self) -> None:
        response = client.get("/courses?is_elective=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["id"] for course in response.json()],
            ["ai-integration", "api-design"],
        )

    def test_filter_required_courses(self) -> None:
        response = client.get("/courses?is_elective=false")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["id"] for course in response.json()],
            [
                "modern-frontend",
                "web-security",
                "backend-fastapi",
                "databases-postgresql",
            ],
        )

    def test_sort_courses_by_title(self) -> None:
        response = client.get("/courses?sort=title")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["id"] for course in response.json()],
            [
                "ai-integration",
                "api-design",
                "backend-fastapi",
                "modern-frontend",
                "databases-postgresql",
                "web-security",
            ],
        )

    def test_pagination_slices_after_popularity_sort(self) -> None:
        expected_pages = {
            1: ["ai-integration", "modern-frontend"],
            2: ["web-security", "backend-fastapi"],
            3: ["databases-postgresql", "api-design"],
            4: [],
        }

        for page, expected_ids in expected_pages.items():
            with self.subTest(page=page):
                response = client.get(f"/courses?page={page}&page_size=2")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [course["id"] for course in response.json()], expected_ids
                )

    def test_course_list_registers_pagination_dependency(self) -> None:
        route = next(
            route
            for route in app.routes
            if isinstance(route, APIRoute)
            and route.path == "/courses"
            and "GET" in route.methods
        )

        self.assertIn(pagination, [dependency.call for dependency in route.dependant.dependencies])

    def test_openapi_contains_exactly_three_application_paths(self) -> None:
        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()["paths"]),
            {"/", "/courses", "/courses/{course_id}"},
        )


if __name__ == "__main__":
    unittest.main()
