"""School book catalog."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import render, require_teacher, session_token
from app.models import Book, Course, CourseBook, User
from app.security import verify_csrf
from app.services import attendance as attendance_svc
from app.services import catalog as catalog_svc

router = APIRouter(prefix="/books")


def _year_courses(db: Session) -> list[Course]:
    year = attendance_svc.current_year(db)
    if not year:
        return []
    return list(
        db.scalars(
            select(Course)
            .where(Course.school_year_id == year.id)
            .options(joinedload(Course.book_links).joinedload(CourseBook.book))
            .order_by(Course.title.asc())
        ).unique().all()
    )


@router.get("")
def catalog(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    books = db.scalars(
        select(Book).options(joinedload(Book.course_links).joinedload(CourseBook.course)).order_by(Book.title.asc())
    ).unique().all()
    return render(
        request,
        "teacher/books.html",
        user,
        _db=db,
        books=books,
        courses=_year_courses(db),
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.post("")
def add_catalog_book(
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
    assign_classes: str = Form(""),
    course_ids: list[int] = Form(default=[]),
):
    dest = next if next.startswith("/") else "/books"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    fields = catalog_svc.book_fields(title, author, notes, kind, isbn, upc, lookup)
    if not fields["title"]:
        return RedirectResponse(f"{dest}?error=Type+a+title+or+scan+an+ISBN.", status_code=303)
    book = catalog_svc.create_book(db, fields)
    if assign_classes:
        catalog_svc.set_book_courses(db, book, [int(c) for c in course_ids])
    db.commit()
    return RedirectResponse(f"{dest}?ok=Book+added.", status_code=303)


@router.get("/{book_id}")
def edit_book_page(
    book_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    book = db.scalar(
        select(Book)
        .where(Book.id == book_id)
        .options(joinedload(Book.course_links).joinedload(CourseBook.course))
    )
    if not book:
        return RedirectResponse("/books", status_code=303)
    return render(
        request,
        "teacher/book_edit.html",
        user,
        _db=db,
        book=book,
        courses=_year_courses(db),
        linked_ids={link.course_id for link in book.course_links},
        error=request.query_params.get("error", ""),
    )


@router.post("/{book_id}")
def update_book(
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
    assign_classes: str = Form(""),
    course_ids: list[int] = Form(default=[]),
):
    dest = next if next.startswith("/") else "/books"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    book = db.get(Book, book_id)
    if not book:
        return RedirectResponse("/books", status_code=303)
    fields = catalog_svc.book_fields(title, author, notes, kind, isbn, upc, lookup)
    if not fields["title"]:
        return RedirectResponse(f"/books/{book_id}?error=Type+a+title+or+scan+an+ISBN.", status_code=303)
    book.title = fields["title"]
    book.author = fields["author"]
    book.notes = fields["notes"]
    book.kind = fields["kind"]
    book.isbn = fields["isbn"]
    book.upc = fields["upc"]
    if assign_classes:
        catalog_svc.set_book_courses(db, book, [int(c) for c in course_ids])
    db.add(book)
    db.commit()
    return RedirectResponse(f"{dest}?ok=Book+updated.", status_code=303)


@router.post("/{book_id}/delete")
def delete_catalog_book(
    book_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    next: str = Form(""),
):
    dest = next if next.startswith("/") else "/books"
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse(f"{dest}?error=That+form+expired.", status_code=303)
    book = db.get(Book, book_id)
    if book:
        db.delete(book)
        db.commit()
    return RedirectResponse(f"{dest}?ok=Book+removed.", status_code=303)
