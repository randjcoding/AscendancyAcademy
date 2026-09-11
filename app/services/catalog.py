"""School book catalog and class links."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Book, BookKind, Course, CourseBook
from app.services import books as books_svc


def book_fields(title, author, notes, kind, isbn, upc, lookup) -> dict:
    name = (title or "").strip()
    author_name = (author or "").strip()
    code = (isbn or upc or lookup or "").strip()
    if not name and code:
        hits = books_svc.lookup(code)
        if hits:
            hit = hits[0]
            name = hit.title
            author_name = author_name or hit.author
            isbn = hit.isbn or isbn
            upc = hit.upc or upc or code
            if (kind or "other") == "other":
                kind = hit.kind
    kind_val = (kind or "other").strip().lower()
    if kind_val not in {k.value for k in BookKind}:
        kind_val = BookKind.OTHER.value
    return {
        "title": name,
        "author": author_name,
        "notes": (notes or "").strip(),
        "kind": kind_val,
        "isbn": books_svc.normalize_code(isbn) or books_svc.normalize_code(lookup),
        "upc": books_svc.normalize_code(upc) or books_svc.normalize_code(lookup),
    }


def all_books(db: Session) -> list[Book]:
    return list(db.scalars(select(Book).order_by(Book.title.asc())).all())


def linked(book: Book, course_id: int) -> bool:
    return any(link.course_id == course_id for link in book.course_links)


def link_book(db: Session, course: Course, book: Book) -> CourseBook:
    existing = db.scalar(
        select(CourseBook).where(CourseBook.course_id == course.id, CourseBook.book_id == book.id)
    )
    if existing:
        return existing
    row = CourseBook(course_id=course.id, book_id=book.id, sort_order=len(course.book_links))
    db.add(row)
    db.flush()
    return row


def unlink_book(db: Session, course_id: int, book_id: int) -> None:
    row = db.scalar(
        select(CourseBook).where(CourseBook.course_id == course_id, CourseBook.book_id == book_id)
    )
    if row:
        db.delete(row)


def create_book(db: Session, fields: dict) -> Book:
    book = Book(**fields)
    db.add(book)
    db.flush()
    return book


def set_book_courses(db: Session, book: Book, course_ids: list[int]) -> None:
    wanted = set(course_ids)
    have = {link.course_id: link for link in book.course_links}
    for course_id, link in list(have.items()):
        if course_id not in wanted:
            db.delete(link)
    for course_id in wanted:
        if course_id in have:
            continue
        course = db.get(Course, course_id)
        if course:
            link_book(db, course, book)
