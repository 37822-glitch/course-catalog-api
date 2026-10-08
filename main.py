from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query

from data import find_course, get_all_courses
from models import Course


app = FastAPI(title="Course Catalog API")


def pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, int]:
    return {"offset": (page - 1) * page_size, "limit": page_size}


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Course Catalog API is running"}


@app.get("/courses", response_model=list[Course])
def read_courses(
    is_elective: bool | None = None,
    sort: Literal["popular", "title"] = "popular",
    q: str | None = None,
    p: dict = Depends(pagination),
) -> list[Course]:
    courses = get_all_courses()

    if is_elective is not None:
        courses = [
            course for course in courses if course.is_elective == is_elective
        ]

    if q is not None:
        query = q.lower()
        courses = [course for course in courses if query in course.title.lower()]

    if sort == "title":
        courses.sort(key=lambda course: course.title)
    else:
        courses.sort(key=lambda course: course.likes, reverse=True)

    offset = p["offset"]
    limit = p["limit"]
    return courses[offset : offset + limit]


@app.get("/courses/{course_id}", response_model=Course)
def read_course(course_id: str) -> Course:
    course = find_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course
