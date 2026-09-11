"""Landing page and role dashboards."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import (
    first_student,
    get_current_user,
    render,
    require_student,
    require_teacher,
    session_token,
    student_profile,
)
from app.models import Assignment, Book, Course, Enrollment, Grade, TeacherApiKey, User, UserKind
from app.security import verify_csrf
from app.services import ai_costs, ai_usage as usage_svc
from app.services import attendance as attendance_svc
from app.services import gemma as gemma_svc
from app.services import grades as grades_svc
from app.services import pages as pages_svc
from app.services import read_pages as read_pages_svc

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
                joinedload(Enrollment.course).joinedload(Course.books),
                joinedload(Enrollment.course).joinedload(Course.categories),
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
    keys = db.scalars(
        select(TeacherApiKey).where(TeacherApiKey.user_id == user.id).order_by(TeacherApiKey.name.asc())
    ).all()
    gemma = gemma_svc.status()
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
        api_keys=keys,
        gemma_available=gemma.available,
        gemma_detail=gemma.detail,
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.post("/teacher/quick-assign")
def teacher_quick_assign(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    course_id: int = Form(...),
    book_id: int = Form(0),
    pages: str = Form(""),
    bulk_pages: str = Form(""),
    has_work: str = Form(""),
    due_date: str = Form(""),
    show_on_calendar: str = Form("1"),
    points_earned: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/teacher?error=That+form+expired.", status_code=303)
    course = db.get(Course, course_id)
    if not course:
        return RedirectResponse("/teacher?error=Pick+a+class.", status_code=303)
    book = db.get(Book, book_id) if book_id else None
    if book and book.course_id != course.id:
        return RedirectResponse("/teacher?error=That+book+is+not+in+this+class.", status_code=303)
    if not book and not pages.strip() and not bulk_pages.strip():
        return RedirectResponse("/teacher?error=Add+a+book+and+pages+first.", status_code=303)
    parsed_due = date.today()
    if due_date.strip():
        try:
            parsed_due = date.fromisoformat(due_date.strip())
        except ValueError:
            return RedirectResponse("/teacher?error=That+due+date+is+not+valid.", status_code=303)
    default_work = bool(has_work)
    specs = pages_svc.parse_bulk(bulk_pages, default_has_work=default_work)
    if not specs:
        spec = pages_svc.parse_line(pages, default_has_work=default_work)
        if spec:
            specs = [spec]
    if not specs:
        return RedirectResponse(
            "/teacher?error=Type+pages+like+12-15+or+one+range+per+line.",
            status_code=303,
        )
    workish = any(s.has_work for s in specs)
    category = pages_svc.default_category(course, workish)
    if not category:
        return RedirectResponse("/teacher?error=This+class+needs+a+grade+category.", status_code=303)
    count = pages_svc.create_page_assignments(
        db,
        course=course,
        user_id=user.id,
        book=book,
        specs=specs,
        category=category,
        due_date=parsed_due,
        show_on_calendar=bool(show_on_calendar),
    )
    score_raw = (points_earned or "").strip()
    if score_raw and count == 1:
        try:
            earned = float(score_raw)
        except ValueError:
            earned = None
        student = first_student(db)
        enrollment = None
        if student:
            enrollment = db.scalar(
                select(Enrollment).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == student.id,
                )
            )
        newest = (
            db.scalars(
                select(Assignment)
                .where(Assignment.course_id == course.id)
                .order_by(Assignment.id.desc())
            ).first()
        )
        if earned is not None and enrollment and newest and newest.has_work:
            db.add(
                Grade(
                    enrollment_id=enrollment.id,
                    assignment_id=newest.id,
                    points_earned=earned,
                    entered_by_user_id=user.id,
                )
            )
    db.commit()
    label = "page set" if count == 1 else "page sets"
    return RedirectResponse(f"/teacher?ok={count}+{label}+added.", status_code=303)


@router.get("/api/ai/estimate")
def ai_estimate(
    provider: str = "",
    images: int = 1,
    user: User = Depends(require_teacher),
):
    if provider not in {"openai", "anthropic", "gemma"}:
        return JSONResponse({"error": "Pick a model first."}, status_code=400)
    return JSONResponse(ai_costs.estimate_usd(provider, images))


@router.get("/api/ai/balance")
def ai_balance(
    key_id: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    if not key_id:
        return JSONResponse({"label": "Gemma does not use a paid key.", "usd_this_month": 0})
    row = db.get(TeacherApiKey, key_id)
    if not row or row.user_id != user.id:
        return JSONResponse({"error": "That key is not yours."}, status_code=404)
    spent = usage_svc.key_month_total(db, user.id, row.name)
    return JSONResponse(
        {
            "label": f"${spent:.3f} logged on this key this month. Vendors often will not tell us the remaining credit.",
            "usd_this_month": spent,
        }
    )


@router.post("/teacher/read-pages")
async def read_pages(
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    provider: str = Form(""),
    key_id: int = Form(0),
    book_id: int = Form(0),
    files: list[UploadFile] = File(default=[]),
):
    if provider not in {"openai", "anthropic", "gemma"}:
        return JSONResponse({"error": "Pick a model first."}, status_code=400)
    blobs: list[bytes] = []
    for item in files:
        if not item.filename:
            continue
        data = await item.read()
        if data:
            blobs.append(data)
    if not blobs:
        return JSONResponse({"error": "Add at least one photo."}, status_code=400)
    book = db.get(Book, book_id) if book_id else None
    key_row = db.get(TeacherApiKey, key_id) if key_id else None
    if key_row and key_row.user_id != user.id:
        return JSONResponse({"error": "That key is not yours."}, status_code=403)
    guess = await read_pages_svc.guess_pages(provider=provider, images=blobs, book=book, key_row=key_row)
    student = first_student(db)
    usage_svc.log_event(
        db,
        user=user,
        student_id=student.id if student else None,
        guess=guess,
        key_name=key_row.name if key_row else "Gemma",
    )
    db.commit()
    payload = read_pages_svc.guess_as_dict(guess)
    payload["estimate"] = ai_costs.estimate_usd(provider, len(blobs), guess.model)
    if guess.error:
        return JSONResponse(payload, status_code=400)
    return JSONResponse(payload)


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
