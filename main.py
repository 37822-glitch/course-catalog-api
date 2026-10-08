from fastapi import FastAPI

from data import get_all_courses
from models import Course


app = FastAPI(title="Course Catalog API")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Course Catalog API is running"}


@app.get("/courses", response_model=list[Course])
def read_courses() -> list[Course]:
    courses = get_all_courses()
    return sorted(courses, key=lambda course: course.likes, reverse=True)
