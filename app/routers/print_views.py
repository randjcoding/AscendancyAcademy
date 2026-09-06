"""Printable calendars and paper grading sheets."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import first_student, render, require_login, require_teacher, student_profile
from app.models import Assignment, Enrollment, Student, User, UserKind
from app.services import attendance as attendance_svc
from app.services import grades as grades_svc

router = APIRouter(prefix="/print")


def _student_for(db: Session, user: User, student_id: int | None) -> Student | None:
    if user.kind == UserKind.STUDENT:
        return student_profile(db, user)
    if student_id:
        return db.get(Student, student_id)
    return first_student(db)


@router.get("/attendance/month")
def print_month(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    year: int | None = None,
    month: int | None = None,
    student_id: int | None = None,
    blank: int = 1,
    filled: int = 0,
):
    if user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    student = _student_for(db, user, student_id)
    if not student:
        return RedirectResponse("/attendance", status_code=303)
    today = date.today()
    view_year = year or today.year
    view_month = month or today.month
    school_year = attendance_svc.current_year(db)
    cells = attendance_svc.month_cells(db, student.id, view_year, view_month)
    show_filled = bool(filled) and not blank
    return render(
        request,
        "print/blank_month.html",
        user,
        student=student,
        school_year=school_year,
        view_year=view_year,
        view_month=view_month,
        month_name=date(view_year, view_month, 1).strftime("%B"),
        cells=cells,
        blank=not show_filled,
        ocr_code=attendance_svc.ocr_code(student, view_year, view_month),
    )


@router.get("/attendance/year")
def print_year(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    student_id: int | None = None,
    blank: int = 1,
):
    if user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    student = _student_for(db, user, student_id)
    school_year = attendance_svc.current_year(db)
    if not student or not school_year:
        return RedirectResponse("/attendance", status_code=303)
    months = []
    for y, m in attendance_svc.year_months(school_year):
        months.append(
            {
                "year": y,
                "month": m,
                "name": date(y, m, 1).strftime("%B %Y"),
                "cells": attendance_svc.month_cells(db, student.id, y, m),
                "ocr_code": attendance_svc.ocr_code(student, y, m),
            }
        )
    totals = attendance_svc.totals(db, student, school_year)
    return render(
        request,
        "print/year_packet.html",
        user,
        student=student,
        school_year=school_year,
        months=months,
        totals=totals,
        blank=bool(blank),
        printed_on=date.today(),
    )


@router.get("/grade-sheet/{assignment_id}")
def grade_sheet(
    assignment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        return RedirectResponse("/courses", status_code=303)
    student = first_student(db)
    enrollment = None
    grade = None
    if student:
        from sqlalchemy import select

        enrollment = db.scalar(
            select(Enrollment).where(
                Enrollment.course_id == assignment.course_id,
                Enrollment.student_id == student.id,
            )
        )
        if enrollment:
            grade = grades_svc.grade_for(db, enrollment.id, assignment.id)
    return render(
        request,
        "print/grade_sheet.html",
        user,
        assignment=assignment,
        course=assignment.course,
        student=student,
        grade=grade,
        printed_on=date.today(),
    )
