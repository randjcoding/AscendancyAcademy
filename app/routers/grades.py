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
    Book,
    CalendarEvent,
    Course,
    CourseBook,
    Enrollment,
    Grade,
    GradeCategory,
    User,
)
from app.services import catalog as catalog_svc
from app.security import verify_csrf
from app.services import grades as grades_svc
from app.services import pages as pages_svc

router = APIRouter()


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
                    joinedload(Enrollment.course).joinedload(Course.book_links).joinedload(CourseBook.book),
                    joinedload(Enrollment.course).joinedload(Course.school_year),
                )
            )
            result = grades_svc.course_result(db, enrollment)
    grade_map = {g.assignment_id: g for g in (enrollment.grades if enrollment else [])}
    assignments = sorted(
        course.assignments,
        key=lambda a: (
            a.due_date is None,
            a.due_date or date.max,
            a.page_start is None,
            a.page_start or 0,
            a.id,
        ),
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
        books=course.books,
        catalog_books=catalog_svc.all_books(db),
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
    title: str = Form(""),
    category_id: int = Form(0),
    points_possible: float = Form(100),
    due_date: str = Form(""),
    description: str = Form(""),
    show_on_calendar: str = Form(""),
    book_id: int = Form(0),
    pages: str = Form(""),
    has_work: str = Form(""),
    bulk_pages: str = Form(""),
):
    dest = f"/courses/{course_id}"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    course = db.get(Course, course_id)
    if not course:
        return RedirectResponse("/courses", status_code=303)
    parsed_due = None
    if due_date.strip():
        try:
            parsed_due = date.fromisoformat(due_date.strip())
        except ValueError:
            return RedirectResponse(f"{dest}?error=That+due+date+is+not+valid.", status_code=303)
    book = db.get(Book, book_id) if book_id else None
    if book and not catalog_svc.linked(book, course.id):
        book = None
    default_work = bool(has_work)
    specs = pages_svc.parse_bulk(bulk_pages, default_has_work=default_work)
    if not specs:
        spec = pages_svc.parse_line(pages, default_has_work=default_work)
        if spec:
            specs = [spec]
        elif title.strip():
            specs = [pages_svc.PageSpec(pages="", page_start=None, has_work=default_work, extra="")]
        else:
            return RedirectResponse(f"{dest}?error=Add+pages+or+a+name.", status_code=303)
    workish = any(s.has_work for s in specs)
    category = db.get(GradeCategory, category_id) if category_id else None
    if not category or category.course_id != course.id:
        category = pages_svc.default_category(course, workish)
    if not category:
        return RedirectResponse(f"{dest}?error=This+class+needs+a+grade+category.", status_code=303)
    if len(specs) == 1 and title.strip():
        spec = specs[0]
        assignment = Assignment(
            course_id=course.id,
            category_id=category.id,
            title=title.strip(),
            description=description.strip(),
            points_possible=max(points_possible, 0.01) if spec.has_work else 0.0,
            due_date=parsed_due,
            show_on_calendar=bool(show_on_calendar),
            book_id=book.id if book else None,
            pages=spec.pages,
            page_start=spec.page_start,
            has_work=bool(spec.has_work),
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
        count = 1
    else:
        count = pages_svc.create_page_assignments(
            db,
            course=course,
            user_id=user.id,
            book=book,
            specs=specs,
            category=category,
            due_date=parsed_due,
            show_on_calendar=bool(show_on_calendar),
            description=description,
        )
    db.commit()
    label = "assignment" if count == 1 else "assignments"
    return RedirectResponse(f"{dest}?ok={count}+{label}+added.", status_code=303)


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
