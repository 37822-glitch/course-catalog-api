import unittest
from unittest.mock import patch

import main
import models
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from data import find_course, get_all_courses
from main import app, cors_origins, pagination
from models import Course


client = TestClient(app)


class CorsTests(unittest.TestCase):
    def test_allowed_frontend_origin_receives_permission_header(self) -> None:
        response = client.get(
            "/courses",
            headers={"Origin": "http://localhost:3000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:3000",
        )

    def test_unlisted_origins_receive_no_permission_header(self) -> None:
        for origin in ("https://example.com", "http://localhost:3000/"):
            with self.subTest(origin=origin):
                response = client.get("/courses", headers={"Origin": origin})

                self.assertEqual(response.status_code, 200)
                self.assertNotIn("access-control-allow-origin", response.headers)

    def test_enrollment_json_preflight_is_allowed(self) -> None:
        response = client.options(
            "/enrollments",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:3000",
        )
        self.assertIn("POST", response.headers["access-control-allow-methods"])
        self.assertIn(
            "content-type",
            response.headers["access-control-allow-headers"].lower(),
        )

    def test_unlisted_method_and_header_preflights_are_rejected(self) -> None:
        cases = (
            ({"Access-Control-Request-Method": "DELETE"}, "method"),
            (
                {
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization",
                },
                "headers",
            ),
        )

        for extra_headers, reason in cases:
            with self.subTest(reason=reason):
                response = client.options(
                    "/enrollments",
                    headers={
                        "Origin": "http://localhost:3000",
                        **extra_headers,
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(f"Disallowed CORS {reason}", response.text)


class CorsConfigurationTests(unittest.TestCase):
    def test_default_origin_is_localhost(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(cors_origins(), ["http://localhost:3000"])

    def test_multiple_origins_are_read_from_the_environment(self) -> None:
        configured = "http://localhost:3000,http://127.0.0.1:3000"

        with patch.dict("os.environ", {"CORS_ORIGINS": configured}, clear=True):
            self.assertEqual(
                cors_origins(),
                ["http://localhost:3000", "http://127.0.0.1:3000"],
            )


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

    def test_course_serializes_python_field_names_as_camel_case(self) -> None:
        course = Course(
            id="sample",
            title="Sample Course",
            description="A sample course.",
            credits=3,
            is_elective=True,
        )

        payload = course.model_dump(by_alias=True)

        self.assertEqual(payload.get("isElective"), True)
        self.assertNotIn("is_elective", payload)

    def test_enrollment_input_accepts_aliases_and_python_names(self) -> None:
        enrollment_type = getattr(models, "EnrollmentIn", None)
        self.assertIsNotNone(enrollment_type, "EnrollmentIn must be defined")

        camel_case = enrollment_type.model_validate(
            {"courseId": "web-security", "studentName": "Aigerim"}
        )
        snake_case = enrollment_type.model_validate(
            {"course_id": "api-design", "student_name": "Dana"}
        )

        self.assertEqual(camel_case.course_id, "web-security")
        self.assertEqual(camel_case.student_name, "Aigerim")
        self.assertEqual(snake_case.course_id, "api-design")
        self.assertEqual(snake_case.student_name, "Dana")


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
            {"id", "title", "description", "credits", "isElective", "likes"},
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
                "isElective": False,
                "likes": 21,
            },
        )

    def test_get_course_returns_required_404(self) -> None:
        response = client.get("/courses/nope")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Course not found"})


class MutationRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.course = find_course("web-security")
        assert self.course is not None
        self.original_likes = self.course.likes
        enrollments = getattr(main, "ENROLLMENTS", None)
        if enrollments is not None:
            enrollments.clear()

    def tearDown(self) -> None:
        self.course.likes = self.original_likes
        enrollments = getattr(main, "ENROLLMENTS", None)
        if enrollments is not None:
            enrollments.clear()

    def test_like_increments_and_persists_on_the_course(self) -> None:
        first_response = client.post("/courses/web-security/like")
        second_response = client.get("/courses/web-security")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["likes"], self.original_likes + 1)
        self.assertEqual(second_response.json()["likes"], self.original_likes + 1)

    def test_like_unknown_course_returns_required_404(self) -> None:
        response = client.post("/courses/nope/like")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Course not found"})

    def test_enrollment_is_created_and_visible_in_the_list(self) -> None:
        response = client.post(
            "/enrollments",
            json={"courseId": "web-security", "studentName": "Aigerim"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "id": 1,
                "courseId": "web-security",
                "studentName": "Aigerim",
            },
        )
        self.assertEqual(client.get("/enrollments").json(), [response.json()])

    def test_one_letter_student_name_returns_alias_aware_422(self) -> None:
        response = client.post(
            "/enrollments",
            json={"courseId": "web-security", "studentName": "A"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "studentName"])

    def test_enrollment_unknown_course_returns_required_404(self) -> None:
        response = client.post(
            "/enrollments",
            json={"courseId": "nope", "studentName": "Aigerim"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Course not found"})

    def test_openapi_contains_exactly_six_application_operations(self) -> None:
        paths = client.get("/openapi.json").json()["paths"]
        operations = {
            (method.upper(), path)
            for path, methods in paths.items()
            for method in methods
        }

        self.assertEqual(
            operations,
            {
                ("GET", "/"),
                ("GET", "/courses"),
                ("GET", "/courses/{course_id}"),
                ("POST", "/courses/{course_id}/like"),
                ("POST", "/enrollments"),
                ("GET", "/enrollments"),
            },
        )


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

    def test_invalid_sort_value_returns_422(self) -> None:
        response = client.get("/courses?sort=banana")

        self.assertEqual(response.status_code, 422)

    def test_search_title_is_case_insensitive(self) -> None:
        response = client.get("/courses?q=REACT")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["id"] for course in response.json()],
            ["modern-frontend"],
        )

    def test_search_title_matches_multiple_courses(self) -> None:
        response = client.get("/courses?q=api")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [course["id"] for course in response.json()],
            ["backend-fastapi", "api-design"],
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

    def test_page_must_be_at_least_one(self) -> None:
        response = client.get("/courses?page=0")

        self.assertEqual(response.status_code, 422)

    def test_page_size_must_be_between_one_and_one_hundred(self) -> None:
        for page_size in (0, 1000):
            with self.subTest(page_size=page_size):
                response = client.get(f"/courses?page_size={page_size}")
                self.assertEqual(response.status_code, 422)

    def test_course_list_registers_pagination_dependency(self) -> None:
        route = next(
            route
            for route in app.routes
            if isinstance(route, APIRoute)
            and route.path == "/courses"
            and "GET" in route.methods
        )

        self.assertIn(pagination, [dependency.call for dependency in route.dependant.dependencies])

if __name__ == "__main__":
    unittest.main()
