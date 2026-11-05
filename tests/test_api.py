import importlib
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import delete, update


class DatabaseConfigurationTests(unittest.TestCase):
    def test_settings_engine_and_session_factory_use_database_url(self) -> None:
        config = importlib.import_module("config")
        db = importlib.import_module("db")

        self.assertEqual(
            config.settings.database_url,
            "postgresql+psycopg://catalog_app:change-me@localhost:5432/course_catalog",
        )
        self.assertIsInstance(config.settings.sql_echo, bool)
        self.assertEqual(db.engine.echo, config.settings.sql_echo)
        self.assertEqual(db.engine.url.database, "course_catalog")
        self.assertIs(db.SessionLocal.kw["bind"], db.engine)


class DatabaseModelTests(unittest.TestCase):
    def test_metadata_describes_the_lab_6_schema(self) -> None:
        orm_models = importlib.import_module("models")

        self.assertEqual(
            set(orm_models.Base.metadata.tables),
            {"courses", "students", "enrollments"},
        )

        course = orm_models.Course.__table__
        student = orm_models.Student.__table__
        enrollment = orm_models.Enrollment.__table__

        self.assertEqual(course.c.is_elective.server_default.arg.text, "false")
        self.assertEqual(course.c.likes.server_default.arg.text, "0")
        self.assertTrue(student.c.id.identity.always)
        self.assertTrue(enrollment.c.id.identity.always)
        self.assertTrue(enrollment.c.student_id.index)

        foreign_keys = {
            column.name: next(iter(column.foreign_keys)).ondelete
            for column in (enrollment.c.course_id, enrollment.c.student_id)
        }
        self.assertEqual(
            foreign_keys,
            {"course_id": "RESTRICT", "student_id": "CASCADE"},
        )

        names = {
            item.name
            for table in orm_models.Base.metadata.tables.values()
            for item in (*table.constraints, *table.indexes)
        }
        self.assertTrue(
            {
                "courses_credits_check",
                "courses_likes_check",
                "students_name_check",
                "students_email_key",
                "enrollments_course_id_student_id_key",
                "enrollments_course_id_fkey",
                "enrollments_student_id_fkey",
                "enrollments_student_id_idx",
            }.issubset(names)
        )


class CourseDatabaseRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schemas = importlib.import_module("schemas")
        cls.course_schema = getattr(schemas, "CourseOut", None)
        cls.main = importlib.import_module("main")
        cls.client = TestClient(cls.main.app)

    def test_course_schema_reads_orm_attributes(self) -> None:
        self.assertIsNotNone(self.course_schema, "CourseOut must be defined")
        self.assertTrue(self.course_schema.model_config["from_attributes"])

    def test_root_and_course_list_read_the_database(self) -> None:
        self.assertEqual(
            self.client.get("/").json(),
            {"message": "Course Catalog API is running"},
        )

        response = self.client.get("/courses")
        self.assertEqual(response.status_code, 200)
        courses = response.json()
        self.assertEqual(len(courses), 6)
        self.assertEqual(courses[0]["id"], "ai-integration")

    def test_filter_sort_and_pagination_are_applied_in_sql(self) -> None:
        response = self.client.get(
            "/courses",
            params={"is_elective": "true", "sort": "title", "page_size": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([course["id"] for course in response.json()], ["ai-integration"])

    def test_single_course_and_missing_course(self) -> None:
        response = self.client.get("/courses/backend-fastapi")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Backend Foundations: FastAPI")

        missing = self.client.get("/courses/not-a-course")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), {"detail": "Course not found"})

    def test_like_is_persisted_and_then_restored(self) -> None:
        models = importlib.import_module("models")
        db_module = importlib.import_module("db")

        before = self.client.get("/courses/api-design").json()["likes"]
        response = self.client.post("/courses/api-design/like")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["likes"], before + 1)

        with db_module.SessionLocal.begin() as session:
            session.execute(
                update(models.Course)
                .where(models.Course.id == "api-design")
                .values(likes=before)
            )

    def test_course_routes_use_the_database_dependency(self) -> None:
        db_module = importlib.import_module("db")
        self.assertTrue(hasattr(db_module, "get_db"))


class EnrollmentDatabaseRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        main = importlib.import_module("main")
        cls.client = TestClient(main.app)
        cls.db_module = importlib.import_module("db")
        cls.models = importlib.import_module("models")

    def setUp(self) -> None:
        self._remove_test_student()

    def tearDown(self) -> None:
        self._remove_test_student()

    def _remove_test_student(self) -> None:
        with self.db_module.SessionLocal.begin() as session:
            session.execute(
                delete(self.models.Student).where(
                    self.models.Student.email == "lab7-test@example.com"
                )
            )

    def test_schemas_define_the_database_contract(self) -> None:
        schemas = importlib.import_module("schemas")
        for name in (
            "StudentIn",
            "StudentOut",
            "EnrollmentIn",
            "EnrollmentOut",
            "EnrollmentDetail",
            "CourseStats",
        ):
            self.assertTrue(hasattr(schemas, name), f"{name} must be defined")

    def test_enrollment_list_and_course_statistics_use_joins(self) -> None:
        enrollments = self.client.get("/enrollments")
        self.assertEqual(enrollments.status_code, 200)
        self.assertEqual(len(enrollments.json()), 6)
        self.assertEqual(enrollments.json()[0]["courseTitle"], "Modern Frontend: React & Next.js")
        self.assertEqual(enrollments.json()[0]["studentName"], "Aigerim Sadykova")

        stats = self.client.get("/stats/courses")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(sum(row["enrolled"] for row in stats.json()), 6)
        self.assertEqual(stats.json()[0], {"courseId": "ai-integration", "enrolled": 3})
        self.assertEqual(
            {row["courseId"]: row["enrolled"] for row in stats.json()}["web-security"],
            0,
        )

    def test_student_and_enrollment_are_created_by_the_database(self) -> None:
        student_response = self.client.post(
            "/students",
            json={"name": "Lab Seven", "email": "lab7-test@example.com"},
        )
        self.assertEqual(student_response.status_code, 201)
        student_id = student_response.json()["id"]

        enrollment_response = self.client.post(
            "/enrollments",
            json={"courseId": "web-security", "studentId": student_id},
        )
        self.assertEqual(enrollment_response.status_code, 201)
        self.assertEqual(enrollment_response.json()["courseId"], "web-security")
        self.assertIsNotNone(enrollment_response.json()["enrolledAt"])

    def test_short_name_is_rejected_before_the_database(self) -> None:
        response = self.client.post(
            "/students",
            json={"name": "N", "email": "lab7-test@example.com"},
        )
        self.assertEqual(response.status_code, 422)

    def test_known_constraint_errors_are_mapped_to_client_responses(self) -> None:
        client = TestClient(self.client.app, raise_server_exceptions=False)
        cases = (
            (
                "/students",
                {"name": "Aigerim Two", "email": "aigerim@example.com"},
                409,
                "Student with this email already exists",
            ),
            (
                "/enrollments",
                {"courseId": "ai-integration", "studentId": 3},
                409,
                "Student is already enrolled in this course",
            ),
            (
                "/enrollments",
                {"courseId": "nope", "studentId": 3},
                404,
                "Course not found",
            ),
            (
                "/enrollments",
                {"courseId": "web-security", "studentId": 999},
                404,
                "Student not found",
            ),
        )

        for path, body, status, detail in cases:
            with self.subTest(detail=detail):
                response = client.post(path, json=body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"detail": detail})


if __name__ == "__main__":
    unittest.main()
