"""Gradebook and student grade views."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import first_student, render, require_student, require_teacher, session_token, student_profile
from app.models import (
    Assignment,
    AssignmentStatus,
    CalendarEvent,
    Course,
    Enrollment,
    Grade,
    GradeCategory,
    User,
)
from app.security import verify_csrf
from app.services import grades as grades_svc

router = APIRouter()


def _course_or_redirect(db: Session, course_id: int) -> Course | RedirectResponse:
    course = db.get(Course, course_id)
    if not course:
        return RedirectResponse("/courses", status_code=303)
    return course


@router.get("/courses/{course_id}")
def gradebook(
    course_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    course = db.get(Course, course_id)
    if not course:
        return RedirectResponse("/courses", status_code=303)
    student = first_student(db)
    enrollment = None
    result = None
    if student:
        enrollment = db.scalar(
            select(Enrollment).where(
                Enrollment.course_id == course.id, Enrollment.student_id == student.id
            )
        )
        if enrollment:
            enrollment = db.scalar(
                select(Enrollment)
                .where(Enrollment.id == enrollment.id)
                .options(
                    joinedload(Enrollment.grades),
                    joinedload(Enrollment.course).joinedload(Course.assignments),
                    joinedload(Enrollment.course).joinedload(Course.categories),
                    joinedload(Enrollment.course).joinedload(Course.school_year),
                )
            )
            result = grades_svc.course_result(db, enrollment)
    grade_map = {g.assignment_id: g for g in (enrollment.grades if enrollment else [])}
    assignments = sorted(
        course.assignments,
        key=lambda a: (a.due_date is None, a.due_date or date.max, a.id),
    )
    return render(
        request,
        "teacher/gradebook.html",
        user,
        _db=db,
        school_year=course.school_year,
        course=course,
        student=student,
        enrollment=enrollment,
        result=result,
        assignments=assignments,
        grade_map=grade_map,
        categories=course.categories,
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.post("/courses/{course_id}/assignments")
def create_assignment(
    course_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    title: str = Form(...),
    category_id: int = Form(...),
    points_possible: float = Form(100),
    due_date: str = Form(""),
    description: str = Form(""),
    show_on_calendar: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"/courses/{course_id}?error=That+form+expired.", status_code=303)
    course = db.get(Course, course_id)
    category = db.get(GradeCategory, category_id)
    name = title.strip()
    if not course or not category or category.course_id != course.id or not name:
        return RedirectResponse(f"/courses/{course_id}?error=Could+not+add+that+assignment.", status_code=303)
    parsed_due = None
    if due_date.strip():
        try:
            parsed_due = date.fromisoformat(due_date.strip())
        except ValueError:
            return RedirectResponse(f"/courses/{course_id}?error=That+due+date+is+not+valid.", status_code=303)
    assignment = Assignment(
        course_id=course.id,
        category_id=category.id,
        title=name,
        description=description.strip(),
        points_possible=max(points_possible, 0.01),
        due_date=parsed_due,
        show_on_calendar=bool(show_on_calendar),
        status=AssignmentStatus.ASSIGNED,
    )
    db.add(assignment)
    db.flush()
    if assignment.show_on_calendar and assignment.due_date:
        db.add(
            CalendarEvent(
                created_by_user_id=user.id,
                assignment_id=assignment.id,
                title=f"{course.title}: {assignment.title}",
                description=assignment.description,
                starts_at=datetime.combine(assignment.due_date, datetime.min.time()),
                all_day=True,
            )
        )
    db.commit()
    return RedirectResponse(f"/courses/{course.id}?ok=Assignment+added.", status_code=303)


@router.post("/courses/{course_id}/assignments/{assignment_id}/delete")
def delete_assignment(
    course_id: int,
    assignment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"/courses/{course_id}?error=That+form+expired.", status_code=303)
    assignment = db.get(Assignment, assignment_id)
    if assignment and assignment.course_id == course_id:
        events = db.scalars(
            select(CalendarEvent).where(CalendarEvent.assignment_id == assignment.id)
        ).all()
        for event in events:
            db.delete(event)
        db.delete(assignment)
        db.commit()
    return RedirectResponse(f"/courses/{course_id}?ok=Assignment+removed.", status_code=303)


@router.post("/courses/{course_id}/grades")
def save_grade(
    course_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    assignment_id: int = Form(...),
    enrollment_id: int = Form(...),
    points_earned: str = Form(""),
    notes: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"/courses/{course_id}?error=That+form+expired.", status_code=303)
    assignment = db.get(Assignment, assignment_id)
    enrollment = db.get(Enrollment, enrollment_id)
    if not assignment or not enrollment or assignment.course_id != course_id:
        return RedirectResponse(f"/courses/{course_id}?error=Could+not+save+that+score.", status_code=303)
    raw = points_earned.strip()
    existing = grades_svc.grade_for(db, enrollment.id, assignment.id)
    if raw == "":
        if existing:
            db.delete(existing)
            assignment.status = AssignmentStatus.ASSIGNED
            db.commit()
        return RedirectResponse(f"/courses/{course_id}?ok=Score+cleared.", status_code=303)
    try:
        earned = float(raw)
    except ValueError:
        return RedirectResponse(f"/courses/{course_id}?error=Score+must+be+a+number.", status_code=303)
    if existing:
        existing.points_earned = earned
        existing.notes = notes.strip()
        existing.entered_by_user_id = user.id
    else:
        db.add(
            Grade(
                enrollment_id=enrollment.id,
                assignment_id=assignment.id,
                points_earned=earned,
                notes=notes.strip(),
                entered_by_user_id=user.id,
            )
        )
    assignment.status = AssignmentStatus.SCORED
    db.commit()
    return RedirectResponse(f"/courses/{course_id}?ok=Score+saved.", status_code=303)


@router.get("/grades")
def student_grades(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_student),
):
    student = student_profile(db, user)
    enrollments = db.scalars(
        select(Enrollment)
        .join(Course)
        .where(Enrollment.student_id == student.id)
        .options(
            joinedload(Enrollment.course).joinedload(Course.assignments),
            joinedload(Enrollment.course).joinedload(Course.categories),
            joinedload(Enrollment.course).joinedload(Course.school_year),
            joinedload(Enrollment.grades),
        )
        .order_by(Course.title.asc())
    ).unique().all()
    rows = []
    for enrollment in enrollments:
        result = grades_svc.course_result(db, enrollment)
        grade_map = {g.assignment_id: g for g in enrollment.grades}
        assignments = sorted(
            enrollment.course.assignments,
            key=lambda a: (a.due_date is None, a.due_date or date.max, a.id),
        )
        rows.append((enrollment, result, assignments, grade_map))
    return render(
        request,
        "student/grades.html",
        user,
        _db=db,
        student=student,
        rows=rows,
    )
