import unittest

from data import find_course, get_all_courses
from models import Course


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


if __name__ == "__main__":
    unittest.main()
