"""Weighted grade calculations."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, Enrollment, Grade, GradeCategory, SchoolYear


@dataclass
class CategoryResult:
    category: GradeCategory
    earned: float
    possible: float
    percent: float | None
    used: bool


@dataclass
class CourseResult:
    percent: float | None
    letter: str
    categories: list[CategoryResult]


def letter_for(percent: float | None, year: SchoolYear) -> str:
    if percent is None:
        return "—"
    if percent >= year.a_min:
        return "A"
    if percent >= year.b_min:
        return "B"
    if percent >= year.c_min:
        return "C"
    if percent >= year.d_min:
        return "D"
    return "F"


def assignment_percent(earned: float | None, possible: float) -> float | None:
    if earned is None or possible <= 0:
        return None
    return round((earned / possible) * 100.0, 2)


def course_result(db: Session, enrollment: Enrollment) -> CourseResult:
    course = enrollment.course
    year = course.school_year
    categories = list(course.categories)
    grades = {g.assignment_id: g for g in enrollment.grades}
    results: list[CategoryResult] = []

    for cat in categories:
        assignments = [a for a in course.assignments if a.category_id == cat.id]
        earned = 0.0
        possible = 0.0
        scored = False
        for assignment in assignments:
            grade = grades.get(assignment.id)
            if grade is None or assignment.points_possible <= 0:
                continue
            earned += grade.points_earned
            possible += assignment.points_possible
            scored = True
        percent = round((earned / possible) * 100.0, 2) if scored and possible > 0 else None
        results.append(
            CategoryResult(
                category=cat,
                earned=earned,
                possible=possible,
                percent=percent,
                used=scored,
            )
        )

    used = [r for r in results if r.used]
    if not used:
        return CourseResult(percent=None, letter="—", categories=results)

    weight_sum = sum(r.category.weight for r in used)
    if weight_sum <= 0:
        return CourseResult(percent=None, letter="—", categories=results)

    total = sum((r.percent or 0) * (r.category.weight / weight_sum) for r in used)
    percent = round(total, 2)
    return CourseResult(percent=percent, letter=letter_for(percent, year), categories=results)


def waiting_assignments(db: Session, enrollment: Enrollment) -> list[Assignment]:
    scored_ids = {g.assignment_id for g in enrollment.grades}
    return [a for a in enrollment.course.assignments if a.id not in scored_ids]


def grade_for(db: Session, enrollment_id: int, assignment_id: int) -> Grade | None:
    return db.scalar(
        select(Grade).where(
            Grade.enrollment_id == enrollment_id, Grade.assignment_id == assignment_id
        )
    )
