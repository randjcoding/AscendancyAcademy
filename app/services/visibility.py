"""Who can see, write, or check off a shared note or task."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CourseTeacher,
    Enrollment,
    NotePage,
    Notebook,
    ShareScope,
    Student,
    Task,
    Teacher,
    User,
)


def teacher_course_ids(db: Session, user: User) -> set[int]:
    profile = db.scalar(select(Teacher).where(Teacher.user_id == user.id))
    if not profile:
        return set()
    rows = db.scalars(select(CourseTeacher.course_id).where(CourseTeacher.teacher_id == profile.id)).all()
    return set(rows)


def student_course_ids(db: Session, user: User) -> set[int]:
    profile = db.scalar(select(Student).where(Student.user_id == user.id))
    if not profile:
        return set()
    rows = db.scalars(select(Enrollment.course_id).where(Enrollment.student_id == profile.id)).all()
    return set(rows)


def class_ids_for(db: Session, user: User) -> set[int]:
    if user.is_teacher:
        ids = teacher_course_ids(db, user)
        return ids or student_course_ids(db, user)
    return student_course_ids(db, user)


def can_see_scope(db: Session, user: User, scope: str, owner_user_id: int | None, course_id: int | None) -> bool:
    kind = (scope or ShareScope.PERSONAL).strip().lower()
    if kind == ShareScope.PERSONAL:
        return owner_user_id == user.id
    if kind == ShareScope.SCHOOL:
        return True
    if kind == ShareScope.CLASS:
        if not course_id:
            return user.is_teacher
        if user.is_teacher:
            return True
        return course_id in student_course_ids(db, user)
    return False


def can_write_scope(db: Session, user: User, scope: str, owner_user_id: int | None, course_id: int | None) -> bool:
    kind = (scope or ShareScope.PERSONAL).strip().lower()
    if kind == ShareScope.PERSONAL:
        return owner_user_id == user.id
    if kind in {ShareScope.SCHOOL, ShareScope.CLASS}:
        return bool(user.is_teacher) and can_see_scope(db, user, kind, owner_user_id, course_id)
    return False


def can_see_notebook(db: Session, user: User, notebook: Notebook) -> bool:
    if notebook.deleted_at:
        return False
    return can_see_scope(db, user, notebook.scope, notebook.owner_user_id, notebook.course_id)


def can_write_notebook(db: Session, user: User, notebook: Notebook) -> bool:
    if notebook.deleted_at:
        return False
    return can_write_scope(db, user, notebook.scope, notebook.owner_user_id, notebook.course_id)


def can_see_page(db: Session, user: User, page: NotePage) -> bool:
    return can_see_scope(db, user, page.scope, page.owner_user_id, page.course_id)


def can_write_page(db: Session, user: User, page: NotePage) -> bool:
    if page.deleted_at and not user.is_teacher:
        return can_write_scope(db, user, page.scope, page.owner_user_id, page.course_id)
    return can_write_scope(db, user, page.scope, page.owner_user_id, page.course_id)


def can_see_task(db: Session, user: User, task: Task) -> bool:
    if task.deleted_at:
        return False
    return can_see_scope(db, user, task.scope or ShareScope.SCHOOL, task.owner_user_id, task.course_id)


def can_write_task(db: Session, user: User, task: Task) -> bool:
    if task.deleted_at:
        return False
    return can_write_scope(db, user, task.scope or ShareScope.SCHOOL, task.owner_user_id, task.course_id)


def can_complete_task(db: Session, user: User, task: Task) -> bool:
    if task.deleted_at:
        return False
    kind = (task.scope or ShareScope.SCHOOL).strip().lower()
    if kind == ShareScope.PERSONAL:
        return task.owner_user_id == user.id
    if kind == ShareScope.SCHOOL:
        return True
    if kind == ShareScope.CLASS:
        return can_see_task(db, user, task)
    return False


def visible_tasks(db: Session, user: User) -> list[Task]:
    rows = db.scalars(select(Task).where(Task.deleted_at.is_(None)).order_by(Task.completed.asc(), Task.id.desc())).all()
    return [t for t in rows if can_see_task(db, user, t)]
