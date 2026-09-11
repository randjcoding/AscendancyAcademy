"""JSON API for the React desk."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.dependencies import (
    DENSITIES,
    DENSITY_LABELS,
    LIST_VIEWS,
    THEME_LABELS,
    THEMES,
    first_student,
    session_token,
    student_profile,
    teacher_profile,
)
from app.models import (
    BOOK_KIND_LABELS,
    Assignment,
    AttendanceDay,
    AttendanceStatus,
    Book,
    BookKind,
    CalendarEvent,
    Course,
    CourseBook,
    CourseTeacher,
    Enrollment,
    Grade,
    GradeCategory,
    Student,
    Task,
    TeacherApiKey,
    User,
    UserKind,
)
from app.services.secrets import encrypt_secret
from app.security import (
    FAILURE_MESSAGE,
    authenticate,
    create_session,
    csrf_token_for,
    delete_all_sessions,
    delete_session,
    get_user_by_session,
    hash_password,
    verify_csrf,
    verify_password,
)
from app.seed import COURSE_COLORS, COURSE_COLOR_VALUES
from app.services import attendance as attendance_svc
from app.services import catalog as catalog_svc
from app.services import documents as docs
from app.services import grades as grades_svc
from app.services import pages as pages_svc
from app.services.documents import DocumentsError
from app.services.turnstile import turnstile_token_from_request, verify_turnstile

router = APIRouter(prefix="/api")


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _current(request: Request, db: Session) -> User | None:
    return get_user_by_session(db, session_token(request))


def _must_user(request: Request, db: Session) -> User | JSONResponse:
    user = _current(request, db)
    if not user:
        return _err("Login required", 401)
    return user


def _user_json(user: User, request: Request) -> dict:
    tok = session_token(request)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "kind": user.kind.value,
        "role": getattr(user, "role", None) or ("student" if user.is_student else "teacher"),
        "is_teacher": user.is_teacher,
        "is_student": user.is_student,
        "can_manage_people": user.can_manage_people,
        "must_change_password": user.must_change_password,
        "theme": user.theme_preference or "ascendancy",
        "density": user.density_preference or "cozy",
        "list_view": user.list_view_preference or "cards",
        "csrf": csrf_token_for(tok) if tok else "",
    }


def _book_json(book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "kind": book.kind,
        "kind_label": book.kind_label,
        "isbn": book.isbn,
        "upc": book.upc,
        "code_label": book.code_label,
        "course_ids": [link.course_id for link in book.course_links],
        "courses": [link.course.title for link in book.course_links],
    }


def _csrf_bad(request: Request, token: str) -> bool:
    return not verify_csrf(session_token(request), token)


class LoginBody(BaseModel):
    door: str
    email: str
    password: str
    next: str = ""
    turnstile: str = ""


class ThemeBody(BaseModel):
    theme: str = ""
    density: str = ""
    csrf: str = ""


class ViewBody(BaseModel):
    view: str = "cards"
    csrf: str = ""


class PasswordBody(BaseModel):
    current_password: str = ""
    new_password: str
    confirm_password: str
    csrf: str = ""
    forced: bool = False


class CourseBody(BaseModel):
    title: str
    color: str = "#2D6A4F"
    equal_weights: bool = True
    tests_weight: float = 25
    quizzes_weight: float = 25
    assignments_weight: float = 25
    other_weight: float = 25
    csrf: str = ""


class BookBody(BaseModel):
    title: str = ""
    author: str = ""
    notes: str = ""
    kind: str = "other"
    isbn: str = ""
    upc: str = ""
    lookup: str = ""
    course_ids: list[int] = []
    csrf: str = ""


class AssignPagesBody(BaseModel):
    course_id: int
    book_id: int = 0
    pages: str = ""
    bulk_pages: str = ""
    has_work: bool = True
    due_date: str = ""
    show_on_calendar: bool = True
    points_earned: str = ""
    title: str = ""
    category_id: int = 0
    csrf: str = ""


class DayBody(BaseModel):
    student_id: int
    on_date: str
    status: str = ""
    csrf: str = ""


class TaskBody(BaseModel):
    title: str
    due_date: str = ""
    notes: str = ""
    show_on_calendar: bool = True
    csrf: str = ""


class EventBody(BaseModel):
    title: str
    starts_at: str
    csrf: str = ""


class GradeBody(BaseModel):
    assignment_id: int
    enrollment_id: int
    points_earned: str = ""
    notes: str = ""
    csrf: str = ""


class KeyBody(BaseModel):
    name: str = ""
    provider: str = "openai"
    secret: str = ""
    csrf: str = ""


class LinkBody(BaseModel):
    book_id: int = 0
    csrf: str = ""


class MoveBody(BaseModel):
    paths: list[str]
    dest: str = ""
    csrf: str = ""


class PeoplePasswordBody(BaseModel):
    user_id: int
    new_password: str
    csrf: str = ""


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    user = _current(request, db)
    year = attendance_svc.current_year(db)
    return {
        "user": _user_json(user, request) if user else None,
        "site_name": settings.site_name,
        "school_year": year.label if year else "",
        "themes": THEMES,
        "theme_labels": THEME_LABELS,
        "densities": DENSITIES,
        "density_labels": DENSITY_LABELS,
        "list_views": LIST_VIEWS,
        "book_kinds": [(k.value, BOOK_KIND_LABELS[k]) for k in BookKind],
        "colors": [{"hex": h, "name": n} for h, n in COURSE_COLORS],
        "turnstile": {"enabled": settings.turnstile_enabled, "site_key": settings.turnstile_site_key},
    }


@router.post("/login")
async def api_login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    door = body.door if body.door in {"teacher", "student"} else "teacher"
    expected = UserKind.TEACHER if door == "teacher" else UserKind.STUDENT
    if settings.turnstile_enabled:
        token = body.turnstile or await turnstile_token_from_request(request)
        if not verify_turnstile(request, token):
            return _err("Please confirm you are a person.")
    user = authenticate(db, body.email, body.password, request)
    if not user:
        return _err(FAILURE_MESSAGE)
    if user.kind != expected:
        msg = (
            "This is the student door. Teachers sign in next door."
            if expected == UserKind.STUDENT
            else "This is the teacher door. Students sign in next door."
        )
        return _err(msg)
    session = create_session(db, user, request)
    dest = body.next if body.next.startswith("/") else ("/teacher" if user.is_teacher else "/student")
    if user.must_change_password:
        dest = "/password"
    payload = _user_json(user, request)
    payload["csrf"] = csrf_token_for(session)
    resp = JSONResponse({"ok": True, "user": payload, "next": dest})
    resp.set_cookie(
        key=settings.session_cookie_name,
        value=session,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookie_for(request),
        max_age=settings.session_ttl_hours * 3600,
        domain=settings.cookie_domain or None,
    )
    return resp


@router.post("/logout")
def api_logout(request: Request, db: Session = Depends(get_db)):
    delete_session(db, session_token(request))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(key=settings.session_cookie_name, domain=settings.cookie_domain or None)
    return resp


@router.post("/theme")
def api_theme(body: ThemeBody, request: Request, db: Session = Depends(get_db)):
    user = _current(request, db)
    theme = body.theme if body.theme in THEMES else (user.theme_preference if user else "ascendancy")
    density = body.density if body.density in DENSITIES else (user.density_preference if user else "cozy")
    if user:
        if body.csrf and _csrf_bad(request, body.csrf):
            return _err("That form expired.", 403)
        user.theme_preference = theme
        user.density_preference = density
        db.add(user)
        db.commit()
    resp = JSONResponse({"ok": True, "theme": theme, "density": density})
    resp.set_cookie("aa_theme", theme, max_age=60 * 60 * 24 * 365, samesite="lax")
    resp.set_cookie("aa_density", density, max_age=60 * 60 * 24 * 365, samesite="lax")
    return resp


@router.post("/view")
def api_view(body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    view = body.view if body.view in LIST_VIEWS else "cards"
    user.list_view_preference = view
    db.add(user)
    db.commit()
    resp = JSONResponse({"ok": True, "list_view": view})
    resp.set_cookie("aa_view", view, max_age=60 * 60 * 24 * 365, samesite="lax")
    return resp


@router.post("/password")
def api_password(body: PasswordBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if len(body.new_password) < 10:
        return _err("Password must be at least 10 characters.")
    if body.new_password != body.confirm_password:
        return _err("Passwords do not match.")
    forced = body.forced or user.must_change_password
    if not forced and user.password_hash and not verify_password(body.current_password, user.password_hash):
        return _err("Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.add(user)
    delete_all_sessions(db, user.id)
    session = create_session(db, user, request)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        key=settings.session_cookie_name,
        value=session,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookie_for(request),
        max_age=settings.session_ttl_hours * 3600,
    )
    return resp


@router.get("/desk")
def api_desk(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    student = first_student(db)
    year = attendance_svc.current_year(db)
    today = date.today()
    courses = []
    week = []
    totals = None
    today_record = None
    waiting = []
    upcoming = []
    if student and year:
        today_record = attendance_svc.day_record(db, student.id, today)
        week = attendance_svc.week_strip(db, student.id, today)
        totals = attendance_svc.totals(db, student, year)
        enrollments = db.scalars(
            select(Enrollment)
            .join(Course)
            .where(Enrollment.student_id == student.id, Course.school_year_id == year.id)
            .options(
                joinedload(Enrollment.course).joinedload(Course.book_links).joinedload(CourseBook.book),
                joinedload(Enrollment.course).joinedload(Course.categories),
                joinedload(Enrollment.course).joinedload(Course.assignments),
                joinedload(Enrollment.grades),
            )
        ).unique().all()
        courses = [e.course for e in enrollments]
        for enrollment in enrollments:
            for assignment in grades_svc.waiting_assignments(db, enrollment):
                waiting.append(
                    {
                        "course_id": enrollment.course_id,
                        "course": enrollment.course.title,
                        "title": assignment.title,
                        "pages": assignment.page_label,
                        "due": assignment.due_date.isoformat() if assignment.due_date else "",
                    }
                )
        upcoming = [
            {
                "course_id": a.course_id,
                "course": a.course.title,
                "title": a.title,
                "due": a.due_date.isoformat() if a.due_date else "",
            }
            for a in db.scalars(
                select(Assignment)
                .join(Course)
                .where(Course.school_year_id == year.id, Assignment.due_date.is_not(None), Assignment.due_date >= today)
                .order_by(Assignment.due_date.asc())
                .limit(8)
            ).all()
        ]
    from app.services import gemma as gemma_svc

    keys = db.scalars(select(TeacherApiKey).where(TeacherApiKey.user_id == user.id).order_by(TeacherApiKey.name)).all()
    implied = attendance_svc.implied_status(today, today_record)
    return {
        "today": today.isoformat(),
        "student": {"id": student.id, "name": student.display_name} if student else None,
        "today_status": implied.value if implied else "",
        "today_locked": bool(today_record.locked) if today_record else False,
        "totals": asdict(totals) if totals else None,
        "gemma_available": gemma_svc.status().available,
        "week": [
            {
                "date": d["date"].isoformat(),
                "status": d["status"].value if d["status"] else "",
                "recorded": d["recorded"],
                "locked": d.get("locked", False),
                "is_today": d["is_today"],
            }
            for d in week
        ],
        "courses": [_course_json_simple(c) for c in courses],
        "catalog_books": [_book_json(b) for b in catalog_svc.all_books(db)],
        "waiting": waiting[:8],
        "upcoming": upcoming,
        "keys": [{"id": k.id, "name": k.name, "provider": k.provider} for k in keys],
    }


def _course_json_simple(course: Course, result=None) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "color": course.color,
        "books": [_book_json(b) for b in course.books],
        "categories": [{"id": c.id, "name": c.name, "weight": c.weight} for c in course.categories],
        "percent": getattr(result, "percent", None),
        "letter": getattr(result, "letter", None),
        "book_count": len(course.books),
    }


@router.get("/courses")
def api_courses(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    year = attendance_svc.current_year(db)
    student = first_student(db)
    courses = []
    if year:
        courses = db.scalars(
            select(Course)
            .where(Course.school_year_id == year.id)
            .options(
                joinedload(Course.enrollments),
                joinedload(Course.categories),
                joinedload(Course.book_links).joinedload(CourseBook.book),
            )
            .order_by(Course.title.asc())
        ).unique().all()
    rows = []
    for course in courses:
        enrollment = next((e for e in course.enrollments if student and e.student_id == student.id), None)
        result = grades_svc.course_result(db, enrollment) if enrollment else None
        rows.append(_course_json_simple(course, result))
    return {"courses": rows}


@router.post("/courses")
def api_create_course(body: CourseBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    year = attendance_svc.current_year(db)
    name = body.title.strip()
    if not year or not name:
        return _err("Need a class name and a school year.")
    color = body.color.strip()
    if not color.startswith("#") or len(color) not in {4, 7}:
        color = COURSE_COLOR_VALUES[0]
    if body.equal_weights:
        weights = [("Tests", 25.0, 0), ("Quizzes", 25.0, 1), ("Assignments", 25.0, 2), ("Other", 25.0, 3)]
    else:
        weights = [
            ("Tests", body.tests_weight, 0),
            ("Quizzes", body.quizzes_weight, 1),
            ("Assignments", body.assignments_weight, 2),
            ("Other", body.other_weight, 3),
        ]
        if abs(sum(w for _, w, _ in weights) - 100) > 0.01:
            return _err("Percents must add up to 100.")
    teacher = teacher_profile(db, user)
    student = first_student(db)
    course = Course(school_year_id=year.id, title=name, color=color)
    db.add(course)
    db.flush()
    db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
    if student:
        db.add(Enrollment(course_id=course.id, student_id=student.id))
    for cat_name, weight, order in weights:
        db.add(GradeCategory(course_id=course.id, name=cat_name, weight=weight, sort_order=order))
    db.commit()
    return {"ok": True, "id": course.id}


@router.get("/courses/{course_id}")
def api_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    course = db.get(Course, course_id)
    if not course:
        return _err("Class not found", 404)
    student = first_student(db)
    enrollment = None
    result = None
    if student:
        enrollment = db.scalar(
            select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.student_id == student.id)
        )
        if enrollment:
            enrollment = db.scalar(
                select(Enrollment)
                .where(Enrollment.id == enrollment.id)
                .options(joinedload(Enrollment.grades), joinedload(Enrollment.course).joinedload(Course.assignments))
            )
            result = grades_svc.course_result(db, enrollment)
    grade_map = {g.assignment_id: {"points": g.points_earned, "notes": g.notes} for g in (enrollment.grades if enrollment else [])}
    assignments = sorted(
        course.assignments,
        key=lambda a: (a.due_date is None, a.due_date or date.max, a.id),
    )
    return {
        "course": _course_json_simple(course, result),
        "student": {"id": student.id, "name": student.display_name} if student else None,
        "enrollment_id": enrollment.id if enrollment else None,
        "result": {
            "percent": result.percent if result else None,
            "letter": result.letter if result else None,
            "categories": [
                {"name": c.category.name, "weight": c.category.weight, "percent": c.percent}
                for c in (result.categories if result else [])
            ],
        }
        if result
        else None,
        "assignments": [
            {
                "id": a.id,
                "title": a.title,
                "pages": a.pages,
                "page_label": a.page_label,
                "has_work": a.has_work,
                "due": a.due_date.isoformat() if a.due_date else "",
                "category": a.category.name if a.category else "",
                "points_possible": a.points_possible,
                "book": a.book.title if a.book else "",
                "grade": grade_map.get(a.id),
            }
            for a in assignments
        ],
        "catalog_books": [_book_json(b) for b in catalog_svc.all_books(db)],
    }


@router.post("/courses/{course_id}/delete")
def api_delete_course(course_id: int, body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    course = db.get(Course, course_id)
    if course:
        db.delete(course)
        db.commit()
    return {"ok": True}


@router.get("/books")
def api_books(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    books = db.scalars(
        select(Book).options(joinedload(Book.course_links).joinedload(CourseBook.course)).order_by(Book.title)
    ).unique().all()
    year = attendance_svc.current_year(db)
    courses = []
    if year:
        courses = db.scalars(select(Course).where(Course.school_year_id == year.id).order_by(Course.title)).all()
    return {
        "books": [_book_json(b) for b in books],
        "courses": [{"id": c.id, "title": c.title} for c in courses],
    }


@router.post("/books")
def api_add_book(body: BookBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    fields = catalog_svc.book_fields(body.title, body.author, body.notes, body.kind, body.isbn, body.upc, body.lookup)
    if not fields["title"]:
        return _err("Type a title or scan an ISBN.")
    book = catalog_svc.create_book(db, fields)
    catalog_svc.set_book_courses(db, book, body.course_ids)
    db.commit()
    return {"ok": True, "id": book.id}


@router.post("/books/{book_id}")
def api_update_book(book_id: int, body: BookBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    book = db.get(Book, book_id)
    if not book:
        return _err("Book not found", 404)
    fields = catalog_svc.book_fields(body.title, body.author, body.notes, body.kind, body.isbn, body.upc, body.lookup)
    if not fields["title"]:
        return _err("Type a title or scan an ISBN.")
    for key, val in fields.items():
        setattr(book, key, val)
    catalog_svc.set_book_courses(db, book, body.course_ids)
    db.add(book)
    db.commit()
    return {"ok": True}


@router.post("/books/{book_id}/delete")
def api_delete_book(book_id: int, body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    book = db.get(Book, book_id)
    if book:
        db.delete(book)
        db.commit()
    return {"ok": True}


@router.post("/courses/{course_id}/books/link")
def api_link_book(course_id: int, body: LinkBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    course = db.get(Course, course_id)
    book = db.get(Book, body.book_id) if body.book_id else None
    if not course or not book:
        return _err("Pick a school book.")
    catalog_svc.link_book(db, course, book)
    db.commit()
    return {"ok": True}


@router.post("/courses/{course_id}/books/{book_id}/unlink")
def api_unlink_book(course_id: int, book_id: int, body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    catalog_svc.unlink_book(db, course_id, book_id)
    db.commit()
    return {"ok": True}


@router.post("/pages")
def api_assign_pages(body: AssignPagesBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    course = db.get(Course, body.course_id)
    if not course:
        return _err("Pick a class.")
    book = db.get(Book, body.book_id) if body.book_id else None
    parsed_due = date.today()
    if body.due_date:
        try:
            parsed_due = date.fromisoformat(body.due_date)
        except ValueError:
            return _err("That due date is not valid.")
    specs = pages_svc.parse_bulk(body.bulk_pages, default_has_work=body.has_work)
    if not specs:
        spec = pages_svc.parse_line(body.pages, default_has_work=body.has_work)
        if spec:
            specs = [spec]
        elif body.title.strip():
            specs = [pages_svc.PageSpec(pages="", page_start=None, has_work=body.has_work, extra="")]
    if not specs:
        return _err("Add pages or a name.")
    workish = any(s.has_work for s in specs)
    category = db.get(GradeCategory, body.category_id) if body.category_id else None
    if not category or category.course_id != course.id:
        category = pages_svc.default_category(course, workish)
    if not category:
        return _err("This class needs a grade category.")
    count = pages_svc.create_page_assignments(
        db,
        course=course,
        user_id=user.id,
        book=book,
        specs=specs,
        category=category,
        due_date=parsed_due,
        show_on_calendar=body.show_on_calendar,
    )
    db.commit()
    return {"ok": True, "count": count}


@router.post("/grades")
def api_save_grade(body: GradeBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    assignment = db.get(Assignment, body.assignment_id)
    enrollment = db.get(Enrollment, body.enrollment_id)
    if not assignment or not enrollment:
        return _err("Could not save that score.")
    raw = body.points_earned.strip()
    existing = db.scalar(
        select(Grade).where(Grade.assignment_id == assignment.id, Grade.enrollment_id == enrollment.id)
    )
    if raw == "":
        if existing:
            db.delete(existing)
            db.commit()
        return {"ok": True}
    try:
        earned = float(raw)
    except ValueError:
        return _err("Score must be a number.")
    if existing:
        existing.points_earned = earned
        existing.notes = body.notes
        existing.entered_by_user_id = user.id
    else:
        db.add(
            Grade(
                enrollment_id=enrollment.id,
                assignment_id=assignment.id,
                points_earned=earned,
                notes=body.notes,
                entered_by_user_id=user.id,
            )
        )
    db.commit()
    return {"ok": True}


@router.get("/attendance")
def api_attendance(request: Request, db: Session = Depends(get_db), year: int | None = None, month: int | None = None):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student = student_profile(db, user) if user.is_student else first_student(db)
    today = date.today()
    view_year = year or today.year
    view_month = month or today.month
    school_year = attendance_svc.current_year(db)
    cells = []
    totals = None
    if student:
        cells = attendance_svc.month_cells(db, student.id, view_year, view_month)
        if school_year:
            totals = attendance_svc.totals(db, student, school_year)
    return {
        "student": {"id": student.id, "name": student.display_name} if student else None,
        "can_edit": user.is_teacher,
        "view_year": view_year,
        "view_month": view_month,
        "month_name": date(view_year, view_month, 1).strftime("%B"),
        "totals": asdict(totals) if totals else None,
        "weeks": [
            [
                {
                    "date": day["date"].isoformat(),
                    "day": day["date"].day,
                    "in_month": day["in_month"],
                    "status": day["status"].value if day["status"] else "",
                    "recorded": day["recorded"],
                    "locked": day.get("locked", False),
                    "is_today": day["is_today"],
                }
                for day in week
            ]
            for week in cells
        ],
    }


@router.post("/attendance/day")
def api_attendance_day(body: DayBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    try:
        day = date.fromisoformat(body.on_date)
    except ValueError:
        return _err("Bad date")
    student = db.get(Student, body.student_id)
    school_year = attendance_svc.current_year(db)
    if not student or not school_year:
        return _err("No student")
    record = attendance_svc.day_record(db, student.id, day)
    status = body.status
    if status == "unlock":
        if record:
            record.locked = False
            db.add(record)
            db.commit()
        return {"ok": True}
    if status == "lock":
        if record:
            record.locked = True
            db.add(record)
            db.commit()
        return {"ok": True}
    if record and record.locked:
        return {"ok": True, "locked": True}
    if status == "clear":
        if record:
            db.delete(record)
            db.commit()
        return {"ok": True}
    if status in {s.value for s in AttendanceStatus}:
        chosen = AttendanceStatus(status)
    else:
        chosen = attendance_svc.next_status(record.status if record else None)
        if chosen is None:
            if record:
                db.delete(record)
                db.commit()
            return {"ok": True}
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
    return {"ok": True}


@router.get("/tasks")
def api_tasks(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    tasks = db.scalars(select(Task).where(Task.deleted_at.is_(None)).order_by(Task.completed.asc(), Task.id.desc())).all()
    return {
        "can_edit": user.is_teacher,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "notes": t.notes,
                "completed": t.completed,
                "due": t.due_at.date().isoformat() if t.due_at else "",
            }
            for t in tasks
        ],
    }


@router.post("/tasks")
def api_create_task(body: TaskBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    name = body.title.strip()
    if not name:
        return _err("Type a task.")
    due_at = None
    if body.due_date:
        due_at = datetime.combine(date.fromisoformat(body.due_date), datetime.min.time())
    student = first_student(db)
    db.add(
        Task(
            created_by_user_id=user.id,
            student_id=student.id if student else None,
            title=name,
            notes=body.notes,
            due_at=due_at,
            show_on_calendar=body.show_on_calendar,
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/toggle")
def api_toggle_task(task_id: int, body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    task = db.get(Task, task_id)
    if task and not task.deleted_at:
        task.completed = not task.completed
        db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/delete")
def api_delete_task(task_id: int, body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    task = db.get(Task, task_id)
    if task:
        task.deleted_at = datetime.utcnow()
        db.commit()
    return {"ok": True}


@router.post("/calendar/events")
def api_add_event(body: EventBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    starts = datetime.fromisoformat(body.starts_at.replace("Z", ""))
    student = first_student(db)
    db.add(
        CalendarEvent(
            created_by_user_id=user.id,
            student_id=student.id if student else None,
            title=body.title.strip(),
            starts_at=starts,
            all_day=True,
        )
    )
    db.commit()
    return {"ok": True}


@router.get("/documents")
def api_documents(request: Request, path: str = "", db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    try:
        listing = docs.list_dir(path)
    except DocumentsError as exc:
        return _err(exc.message, exc.status)
    return listing


@router.post("/documents/folder")
def api_doc_folder(request: Request, db: Session = Depends(get_db), parent: str = Form(""), name: str = Form(""), csrf: str = Form("")):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, csrf):
        return _err("That form expired.", 403)
    try:
        rel = docs.create_folder(parent, name)
    except DocumentsError as exc:
        return _err(exc.message)
    return {"ok": True, "rel": rel}


@router.post("/documents/upload")
async def api_doc_upload(
    request: Request,
    db: Session = Depends(get_db),
    parent: str = Form(""),
    csrf: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, csrf):
        return _err("That form expired.", 403)
    saved = 0
    last = ""
    for item in files:
        if not item.filename:
            continue
        data = await item.read()
        try:
            docs.save_upload(parent, item.filename, data)
            saved += 1
        except DocumentsError as exc:
            last = exc.message
    if not saved:
        return _err(last or "Choose a file.")
    return {"ok": True, "saved": saved}


@router.post("/documents/delete")
def api_doc_delete(body: MoveBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    try:
        for path in body.paths:
            docs.delete_entry(path)
    except DocumentsError as exc:
        return _err(exc.message)
    return {"ok": True}


@router.post("/documents/move")
def api_doc_move(body: MoveBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    try:
        moved = docs.move_entries(body.paths, body.dest)
    except DocumentsError as exc:
        return _err(exc.message)
    return {"ok": True, "moved": moved}


@router.get("/keys")
def api_keys(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    keys = db.scalars(select(TeacherApiKey).where(TeacherApiKey.user_id == user.id).order_by(TeacherApiKey.name)).all()
    return {"keys": [{"id": k.id, "name": k.name, "provider": k.provider} for k in keys]}


@router.post("/keys")
def api_add_key(body: KeyBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if not body.secret.strip():
        return _err("Paste the secret key.")
    db.add(
        TeacherApiKey(
            user_id=user.id,
            name=body.name.strip() or body.provider.title(),
            provider=body.provider,
            secret_enc=encrypt_secret(body.secret.strip()),
        )
    )
    db.commit()
    return {"ok": True}


@router.post("/keys/{key_id}/delete")
def api_del_key(key_id: int, body: ViewBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    row = db.get(TeacherApiKey, key_id)
    if row and row.user_id == user.id:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/usage")
def api_usage(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    from app.services import ai_usage as usage_svc

    rows = usage_svc.month_rows(db)
    names = {}
    out = []
    for row in rows:
        if row.user_id not in names:
            owner = db.get(User, row.user_id)
            names[row.user_id] = owner.full_name if owner else "Teacher"
        out.append(
            {
                "when": row.created_at.isoformat() if row.created_at else "",
                "who": names[row.user_id],
                "model": row.model,
                "purpose": row.purpose,
                "tokens": row.prompt_tokens + row.completion_tokens,
                "usd": row.usd,
                "status": row.status,
            }
        )
    return {"rows": out, "month_total": float(usage_svc.month_total(db) or 0), "month_label": datetime.utcnow().strftime("%B %Y")}


@router.get("/people")
def api_people(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.can_manage_people:
        return _err("Admin required", 403)
    people = db.scalars(select(User).order_by(User.first_name)).all()
    return {
        "people": [
            {"id": p.id, "name": p.full_name, "email": p.email, "role": getattr(p, "role", ""), "kind": p.kind.value}
            for p in people
        ]
    }


@router.post("/people/password")
def api_people_password(body: PeoplePasswordBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.can_manage_people:
        return _err("Admin required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if len(body.new_password) < 10:
        return _err("Password must be at least 10 characters.")
    target = db.get(User, body.user_id)
    if not target:
        return _err("Person not found")
    if getattr(target, "role", "") == "super_admin" and not user.is_super_admin:
        return _err("Only Joe can change that password.")
    target.password_hash = hash_password(body.new_password)
    target.must_change_password = True
    db.add(target)
    db.commit()
    return {"ok": True}


@router.get("/student")
def api_student_home(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student = student_profile(db, user) if user.is_student else first_student(db)
    year = attendance_svc.current_year(db)
    today = date.today()
    totals = attendance_svc.totals(db, student, year) if student and year else None
    courses = []
    due = []
    recent = []
    if student and year:
        enrollments = db.scalars(
            select(Enrollment)
            .join(Course)
            .where(Enrollment.student_id == student.id, Course.school_year_id == year.id)
            .options(
                joinedload(Enrollment.course).joinedload(Course.assignments),
                joinedload(Enrollment.course).joinedload(Course.categories),
                joinedload(Enrollment.grades),
            )
        ).unique().all()
        for enrollment in enrollments:
            result = grades_svc.course_result(db, enrollment)
            courses.append(_course_json_simple(enrollment.course, result))
        due = [
            {
                "title": a.title,
                "course": a.course.title,
                "due": a.due_date.isoformat() if a.due_date else "",
            }
            for a in db.scalars(
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
        ]
        recent = [
            {
                "title": g.assignment.title if g.assignment else "Score",
                "earned": g.points_earned,
                "possible": g.assignment.points_possible if g.assignment else None,
            }
            for g in db.scalars(
                select(Grade)
                .join(Enrollment)
                .where(Enrollment.student_id == student.id)
                .options(joinedload(Grade.assignment))
                .order_by(Grade.updated_at.desc())
                .limit(6)
            ).unique().all()
        ]
    return {
        "student": {"id": student.id, "name": student.display_name} if student else None,
        "totals": asdict(totals) if totals else None,
        "courses": courses,
        "due": due,
        "recent": recent,
    }


@router.get("/student/grades")
def api_student_grades(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student = student_profile(db, user) if user.is_student else first_student(db)
    if not student:
        return {"rows": []}
    enrollments = db.scalars(
        select(Enrollment)
        .join(Course)
        .where(Enrollment.student_id == student.id)
        .options(
            joinedload(Enrollment.course).joinedload(Course.assignments),
            joinedload(Enrollment.course).joinedload(Course.categories),
            joinedload(Enrollment.grades),
        )
        .order_by(Course.title.asc())
    ).unique().all()
    rows = []
    for enrollment in enrollments:
        result = grades_svc.course_result(db, enrollment)
        grade_map = {g.assignment_id: g.points_earned for g in enrollment.grades}
        assignments = sorted(
            enrollment.course.assignments,
            key=lambda a: (a.due_date is None, a.due_date or date.max, a.id),
        )
        rows.append(
            {
                "course": _course_json_simple(enrollment.course, result),
                "result": {
                    "percent": result.percent if result else None,
                    "letter": result.letter if result else None,
                },
                "assignments": [
                    {
                        "id": a.id,
                        "title": a.title,
                        "due": a.due_date.isoformat() if a.due_date else "",
                        "points_possible": a.points_possible,
                        "earned": grade_map.get(a.id),
                    }
                    for a in assignments
                ],
            }
        )
    return {"student": {"id": student.id, "name": student.display_name}, "rows": rows}


@router.get("/photos")
def api_photos(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    try:
        listing = docs.list_dir(docs.PHOTOS_FOLDER)
    except DocumentsError as exc:
        return _err(exc.message, exc.status)
    return listing


@router.post("/photos")
async def api_upload_photos(
    request: Request,
    db: Session = Depends(get_db),
    csrf: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, csrf):
        return _err("That form expired.", 403)
    saved = 0
    last = ""
    for item in files:
        if not item.filename:
            continue
        data = await item.read()
        try:
            docs.save_upload(docs.PHOTOS_FOLDER, item.filename, data)
            saved += 1
        except DocumentsError as exc:
            last = exc.message
    if not saved:
        return _err(last or "Choose one or more pictures.")
    return {"ok": True, "saved": saved}
