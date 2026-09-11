"""Course setup for teachers."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import first_student, render, require_teacher, session_token, teacher_profile
from app.models import Book, BookKind, Course, CourseTeacher, Enrollment, GradeCategory, User
from app.services import books as books_svc
from app.security import verify_csrf
from app.seed import COURSE_COLORS
from app.services import attendance as attendance_svc
from app.services import grades as grades_svc

router = APIRouter(prefix="/courses")
lookup_router = APIRouter()


@router.get("")
def course_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    year = attendance_svc.current_year(db)
    courses = []
    if year:
        courses = db.scalars(
            select(Course)
            .where(Course.school_year_id == year.id)
            .options(
                joinedload(Course.enrollments),
                joinedload(Course.assignments),
                joinedload(Course.categories),
                joinedload(Course.books),
            )
            .order_by(Course.title.asc())
        ).unique().all()
    student = first_student(db)
    rows = []
    for course in courses:
        enrollment = next((e for e in course.enrollments if student and e.student_id == student.id), None)
        result = grades_svc.course_result(db, enrollment) if enrollment else None
        rows.append((course, enrollment, result))
    return render(
        request,
        "teacher/courses.html",
        user,
        _db=db,
        school_year=year,
        rows=rows,
        student=student,
        colors=COURSE_COLORS,
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.post("/new")
def create_course(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    title: str = Form(...),
    color: str = Form("#2D6A4F"),
    notes: str = Form(""),
    tests_weight: float = Form(40),
    quizzes_weight: float = Form(20),
    assignments_weight: float = Form(30),
    other_weight: float = Form(10),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/courses?error=That+form+expired.+Try+again.", status_code=303)
    year = attendance_svc.current_year(db)
    student = first_student(db)
    teacher = teacher_profile(db, user)
    name = title.strip()
    if not year or not name:
        return RedirectResponse("/courses?error=Need+a+class+name+and+a+school+year.", status_code=303)
    weights = [
        ("Tests", tests_weight, 0),
        ("Quizzes", quizzes_weight, 1),
        ("Assignments", assignments_weight, 2),
        ("Other", other_weight, 3),
    ]
    if abs(sum(w for _, w, _ in weights) - 100) > 0.01:
        return RedirectResponse("/courses?error=Category+weights+must+add+up+to+100.", status_code=303)
    course = Course(school_year_id=year.id, title=name, color=color.strip() or "#2D6A4F", notes=notes.strip())
    db.add(course)
    db.flush()
    db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
    if student:
        db.add(Enrollment(course_id=course.id, student_id=student.id))
    for cat_name, weight, order in weights:
        db.add(GradeCategory(course_id=course.id, name=cat_name, weight=weight, sort_order=order))
    db.commit()
    return RedirectResponse(f"/courses/{course.id}", status_code=303)


@router.post("/{course_id}/delete")
def delete_course(
    course_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/courses?error=That+form+expired.+Try+again.", status_code=303)
    course = db.get(Course, course_id)
    if course:
        db.delete(course)
        db.commit()
    return RedirectResponse("/courses?ok=Class+removed.", status_code=303)


@router.post("/{course_id}/books")
def add_book(
    course_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    title: str = Form(""),
    author: str = Form(""),
    notes: str = Form(""),
    kind: str = Form("other"),
    isbn: str = Form(""),
    upc: str = Form(""),
    lookup: str = Form(""),
    next: str = Form(""),
):
    dest = next if next.startswith("/") else f"/courses/{course_id}"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    course = db.get(Course, course_id)
    if not course:
        return RedirectResponse("/courses", status_code=303)
    fields = _book_fields(title, author, notes, kind, isbn, upc, lookup)
    if not fields["title"]:
        return RedirectResponse(f"{dest}?error=Type+a+title+or+scan+an+ISBN.", status_code=303)
    db.add(
        Book(
            course_id=course.id,
            sort_order=len(course.books),
            **fields,
        )
    )
    db.commit()
    return RedirectResponse(f"{dest}?ok=Book+added.", status_code=303)


def _book_fields(title, author, notes, kind, isbn, upc, lookup):
    name = title.strip()
    author_name = author.strip()
    code = (isbn or upc or lookup).strip()
    if not name and code:
        hits = books_svc.lookup(code)
        if hits:
            hit = hits[0]
            name = hit.title
            author_name = author_name or hit.author
            isbn = hit.isbn or isbn
            upc = hit.upc or upc or code
            if kind == "other":
                kind = hit.kind
    kind_val = kind.strip().lower()
    if kind_val not in {k.value for k in BookKind}:
        kind_val = BookKind.OTHER.value
    return {
        "title": name,
        "author": author_name,
        "notes": notes.strip(),
        "kind": kind_val,
        "isbn": books_svc.normalize_code(isbn) or books_svc.normalize_code(lookup),
        "upc": books_svc.normalize_code(upc) or books_svc.normalize_code(lookup),
    }


@router.get("/{course_id}/books/{book_id}")
def edit_book_page(
    course_id: int,
    book_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    course = db.get(Course, course_id)
    book = db.get(Book, book_id)
    if not course or not book or book.course_id != course_id:
        return RedirectResponse("/courses", status_code=303)
    return render(
        request,
        "teacher/book_edit.html",
        user,
        _db=db,
        course=course,
        book=book,
        error=request.query_params.get("error", ""),
    )


@router.post("/{course_id}/books/{book_id}")
def update_book(
    course_id: int,
    book_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    title: str = Form(""),
    author: str = Form(""),
    notes: str = Form(""),
    kind: str = Form("other"),
    isbn: str = Form(""),
    upc: str = Form(""),
    lookup: str = Form(""),
    next: str = Form(""),
):
    dest = next if next.startswith("/") else f"/courses/{course_id}"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    book = db.get(Book, book_id)
    if not book or book.course_id != course_id:
        return RedirectResponse("/courses", status_code=303)
    fields = _book_fields(title, author, notes, kind, isbn, upc, lookup)
    if not fields["title"]:
        return RedirectResponse(
            f"/courses/{course_id}/books/{book_id}?error=Type+a+title+or+scan+an+ISBN.",
            status_code=303,
        )
    book.title = fields["title"]
    book.author = fields["author"]
    book.notes = fields["notes"]
    book.kind = fields["kind"]
    book.isbn = fields["isbn"]
    book.upc = fields["upc"]
    db.add(book)
    db.commit()
    return RedirectResponse(f"{dest}?ok=Book+updated.", status_code=303)


@lookup_router.get("/api/books/lookup")
def book_lookup(
    q: str = "",
    user: User = Depends(require_teacher),
):
    hits = books_svc.lookup(q)
    return JSONResponse({"results": books_svc.hits_as_dicts(hits)})


@router.post("/{course_id}/books/{book_id}/delete")
def delete_book(
    course_id: int,
    book_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    next: str = Form(""),
):
    dest = next if next.startswith("/") else f"/courses/{course_id}"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    book = db.get(Book, book_id)
    if book and book.course_id == course_id:
        db.delete(book)
        db.commit()
    return RedirectResponse(f"{dest}?ok=Book+removed.", status_code=303)
