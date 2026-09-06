"""Landing page and role dashboards."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import (
    first_student,
    get_current_user,
    render,
    require_student,
    require_teacher,
    student_profile,
)
from app.models import Assignment, Course, Enrollment, Grade, User, UserKind
from app.services import attendance as attendance_svc
from app.services import grades as grades_svc

router = APIRouter()


@router.get("/")
def root(request: Request, user: User | None = Depends(get_current_user)):
    if not user:
        return render(request, "auth/choose.html", None)
    if user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    if user.kind == UserKind.TEACHER:
        return RedirectResponse("/teacher", status_code=303)
    return RedirectResponse("/student", status_code=303)


@router.get("/teacher")
def teacher_home(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    student = first_student(db)
    year = attendance_svc.current_year(db)
    today = date.today()
    today_record = None
    week = []
    totals = None
    waiting: list[tuple[Enrollment, Assignment]] = []
    courses = []
    upcoming = []
    if student and year:
        today_record = attendance_svc.day_record(db, student.id, today)
        week = attendance_svc.week_strip(db, student.id, today)
        totals = attendance_svc.totals(db, student, year)
        enrollments = db.scalars(
            select(Enrollment)
            .join(Course)
            .where(
                Enrollment.student_id == student.id,
                Course.school_year_id == year.id,
            )
            .options(
                joinedload(Enrollment.course).joinedload(Course.assignments),
                joinedload(Enrollment.grades),
            )
        ).unique().all()
        courses = [e.course for e in enrollments]
        for enrollment in enrollments:
            for assignment in grades_svc.waiting_assignments(db, enrollment):
                waiting.append((enrollment, assignment))
        upcoming = (
            db.scalars(
                select(Assignment)
                .join(Course)
                .where(
                    Course.school_year_id == year.id,
                    Assignment.due_date.is_not(None),
                    Assignment.due_date >= today,
                )
                .order_by(Assignment.due_date.asc())
                .limit(8)
            ).all()
        )
    waiting.sort(key=lambda pair: (pair[1].due_date is None, pair[1].due_date or today))
    return render(
        request,
        "teacher/home.html",
        user,
        _db=db,
        school_year=year,
        student=student,
        today=today,
        today_record=today_record,
        today_status=attendance_svc.implied_status(today, today_record),
        week=week,
        totals=totals,
        waiting=waiting[:8],
        courses=courses,
        upcoming=upcoming,
    )


@router.get("/student")
def student_home(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_student),
):
    student = student_profile(db, user)
    year = attendance_svc.current_year(db)
    today = date.today()
    totals = attendance_svc.totals(db, student, year) if year else None
    enrollments = []
    due = []
    recent = []
    if year:
        enrollments = db.scalars(
            select(Enrollment)
            .join(Course)
            .where(
                Enrollment.student_id == student.id,
                Course.school_year_id == year.id,
            )
            .options(
                joinedload(Enrollment.course).joinedload(Course.assignments),
                joinedload(Enrollment.course).joinedload(Course.categories),
                joinedload(Enrollment.course).joinedload(Course.school_year),
                joinedload(Enrollment.grades),
            )
        ).unique().all()
        due = (
            db.scalars(
                select(Assignment)
                .join(Course)
                .join(Enrollment)
                .where(
                    Enrollment.student_id == student.id,
                    Course.school_year_id == year.id,
                    Assignment.due_date.is_not(None),
                    Assignment.due_date >= today,
                )
                .order_by(Assignment.due_date.asc())
                .limit(8)
            ).all()
        )
        recent = (
            db.scalars(
                select(Grade)
                .join(Enrollment)
                .where(Enrollment.student_id == student.id)
                .order_by(Grade.updated_at.desc())
                .limit(6)
            ).all()
        )
    course_rows = [(e, grades_svc.course_result(db, e)) for e in enrollments]
    return render(
        request,
        "student/home.html",
        user,
        _db=db,
        school_year=year,
        student=student,
        totals=totals,
        course_rows=course_rows,
        due=due,
        recent=recent,
        today=today,
    )
