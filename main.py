from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db import get_db
from models import Course
from schemas import CourseOut


app = FastAPI(title="Course Catalog API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SessionDep = Annotated[Session, Depends(get_db)]


def pagination(page: int = 1, page_size: int = 20) -> dict[str, int]:
    return {"offset": (page - 1) * page_size, "limit": page_size}


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Course Catalog API is running"}


@app.get("/courses", response_model=list[CourseOut])
def list_courses(
    db: SessionDep,
    is_elective: bool | None = None,
    sort: str = "popular",
    p: dict = Depends(pagination),
) -> list[Course]:
    stmt = select(Course)

    if is_elective is not None:
        stmt = stmt.where(Course.is_elective == is_elective)

    if sort == "title":
        stmt = stmt.order_by(Course.title)
    else:
        stmt = stmt.order_by(Course.likes.desc(), Course.id)

    stmt = stmt.limit(p["limit"]).offset(p["offset"])
    return list(db.scalars(stmt).all())


@app.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: str, db: SessionDep) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@app.post("/courses/{course_id}/like", response_model=CourseOut)
def like_course(course_id: str, db: SessionDep) -> Course:
    stmt = (
        update(Course)
        .where(Course.id == course_id)
        .values(likes=Course.likes + 1)
        .returning(Course)
    )
    course = db.scalars(stmt).one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    db.commit()
    return course
