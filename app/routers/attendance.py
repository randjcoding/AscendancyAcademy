"""Attendance month grid and one-tap present."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import first_student, render, require_login, require_teacher, session_token, student_profile
from app.models import AttendanceDay, AttendanceStatus, Student, User, UserKind
from app.security import verify_csrf
from app.services import attendance as attendance_svc

router = APIRouter()


def _visible_student(db: Session, user: User, student_id: int | None) -> Student | None:
    if user.kind == UserKind.STUDENT:
        return student_profile(db, user)
    if student_id:
        return db.get(Student, student_id)
    return first_student(db)


@router.get("/attendance")
def attendance_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    year: int | None = None,
    month: int | None = None,
    student_id: int | None = None,
):
    if user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    student = _visible_student(db, user, student_id)
    school_year = attendance_svc.current_year(db)
    today = date.today()
    view_year = year or today.year
    view_month = month or today.month
    cells = []
    totals = None
    if student:
        cells = attendance_svc.month_cells(db, student.id, view_year, view_month)
        if school_year:
            totals = attendance_svc.totals(db, student, school_year)
    prev_month = view_month - 1 or 12
    prev_year = view_year - 1 if view_month == 1 else view_year
    next_month = view_month + 1 if view_month < 12 else 1
    next_year = view_year + 1 if view_month == 12 else view_year
    return render(
        request,
        "attendance/month.html",
        user,
        _db=db,
        school_year=school_year,
        student=student,
        cells=cells,
        totals=totals,
        view_year=view_year,
        view_month=view_month,
        month_name=date(view_year, view_month, 1).strftime("%B"),
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        can_edit=user.kind == UserKind.TEACHER,
        today=today,
    )


@router.post("/attendance/day")
def set_day(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    student_id: int = Form(...),
    on_date: str = Form(...),
    status: str = Form(""),
    next: str = Form("/attendance"),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/attendance?error=expired", status_code=303)
    student = db.get(Student, student_id)
    school_year = attendance_svc.current_year(db)
    try:
        day = date.fromisoformat(on_date)
    except ValueError:
        return RedirectResponse("/attendance", status_code=303)
    if not student or not school_year:
        return RedirectResponse("/attendance", status_code=303)
    record = attendance_svc.day_record(db, student.id, day)
    if status == "clear":
        if record:
            db.delete(record)
            db.commit()
        dest = next if next.startswith("/") else "/attendance"
        return RedirectResponse(dest, status_code=303)
    if status in {s.value for s in AttendanceStatus}:
        chosen = AttendanceStatus(status)
    else:
        chosen = attendance_svc.next_status(attendance_svc.implied_status(day, record))
    if record:
        record.status = chosen
        record.entered_by_user_id = user.id
    else:
        db.add(
            AttendanceDay(
                student_id=student.id,
                school_year_id=school_year.id,
                on_date=day,
                status=chosen,
                entered_by_user_id=user.id,
            )
        )
    db.commit()
    dest = next if next.startswith("/") else "/attendance"
    return RedirectResponse(dest, status_code=303)


@router.post("/attendance/today")
def mark_today(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    student_id: int = Form(...),
    status: str = Form("present"),
    next: str = Form("/teacher"),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/teacher", status_code=303)
    student = db.get(Student, student_id)
    school_year = attendance_svc.current_year(db)
    today = date.today()
    chosen = AttendanceStatus.PRESENT
    if status in {s.value for s in AttendanceStatus}:
        chosen = AttendanceStatus(status)
    if student and school_year:
        record = attendance_svc.day_record(db, student.id, today)
        if record:
            record.status = chosen
            record.entered_by_user_id = user.id
        else:
            db.add(
                AttendanceDay(
                    student_id=student.id,
                    school_year_id=school_year.id,
                    on_date=today,
                    status=chosen,
                    entered_by_user_id=user.id,
                )
            )
        db.commit()
    dest = next if next.startswith("/") else "/teacher"
    return RedirectResponse(dest, status_code=303)


@router.post("/attendance/today-present")
def mark_today_present(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    student_id: int = Form(...),
    next: str = Form("/teacher"),
):
    return mark_today(
        request,
        db=db,
        user=user,
        csrf_token=csrf_token,
        student_id=student_id,
        status="present",
        next=next,
    )
