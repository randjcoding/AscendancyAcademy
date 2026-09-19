"""SQLAlchemy models for Ascendancy Academy."""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _enum(enum_cls, name: str):
    return Enum(enum_cls, name=name, values_callable=lambda x: [e.value for e in x])


class UserKind(str, enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    SICK = "sick"
    EXCUSED = "excused"
    OFF = "off"


class AssignmentStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    SCORED = "scored"


class BookKind(str, enum.Enum):
    WORKBOOK = "workbook"
    CURRICULUM = "curriculum"
    NOVEL = "novel"
    TEXTBOOK = "textbook"
    OTHER = "other"


class ShareScope:
    PERSONAL = "personal"
    SCHOOL = "school"
    CLASS = "class"
    ALL = (PERSONAL, SCHOOL, CLASS)


class ReminderStatus:
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


BOOK_KIND_LABELS = {
    BookKind.WORKBOOK: "Workbook",
    BookKind.CURRICULUM: "Curriculum",
    BookKind.NOVEL: "Novel",
    BookKind.TEXTBOOK: "Textbook",
    BookKind.OTHER: "Other",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    nickname: Mapped[str] = mapped_column(String(80), default="")
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    kind: Mapped[UserKind] = mapped_column(_enum(UserKind, "user_kind"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="teacher", index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[AccountStatus] = mapped_column(
        _enum(AccountStatus, "account_status"), default=AccountStatus.ACTIVE, index=True
    )
    theme_preference: Mapped[str] = mapped_column(String(20), default="ascendancy")
    density_preference: Mapped[str] = mapped_column(String(20), default="cozy")
    list_view_preference: Mapped[str] = mapped_column(String(20), default="cards")
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    spell_help: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    sessions: Mapped[list["SessionRow"]] = relationship(back_populates="user")
    teacher_profile: Mapped[Optional["Teacher"]] = relationship(back_populates="user")
    student_profile: Mapped[Optional["Student"]] = relationship(back_populates="user")
    api_keys: Mapped[list["TeacherApiKey"]] = relationship(back_populates="user")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def display_name(self) -> str:
        nick = (self.nickname or "").strip()
        return nick or self.full_name

    @property
    def initials(self) -> str:
        parts = f"{self.first_name[:1]}{self.last_name[:1]}".upper()
        return parts or "?"

    @property
    def is_teacher(self) -> bool:
        return self.kind == UserKind.TEACHER

    @property
    def is_student(self) -> bool:
        return self.kind == UserKind.STUDENT

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    @property
    def can_manage_people(self) -> bool:
        return self.role in {"admin", "super_admin"} or self.is_admin


class SessionRow(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuthEvent(Base):
    __tablename__ = "auth_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    user: Mapped["User"] = relationship(back_populates="teacher_profile")
    student_links: Mapped[list["StudentTeacher"]] = relationship(back_populates="teacher")
    course_links: Mapped[list["CourseTeacher"]] = relationship(back_populates="teacher")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    preferred_name: Mapped[str] = mapped_column(String(80), default="")

    user: Mapped["User"] = relationship(back_populates="student_profile")
    teacher_links: Mapped[list["StudentTeacher"]] = relationship(back_populates="student")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student")
    attendance_days: Mapped[list["AttendanceDay"]] = relationship(back_populates="student")

    @property
    def display_name(self) -> str:
        if (self.preferred_name or "").strip():
            return self.preferred_name.strip()
        return self.user.full_name


class StudentTeacher(Base):
    __tablename__ = "student_teachers"
    __table_args__ = (UniqueConstraint("student_id", "teacher_id", name="uq_student_teacher"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), index=True)

    student: Mapped["Student"] = relationship(back_populates="teacher_links")
    teacher: Mapped["Teacher"] = relationship(back_populates="student_links")


class SchoolYear(Base):
    __tablename__ = "school_years"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(32), unique=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    instructional_day_target: Mapped[int] = mapped_column(Integer, default=180)
    a_min: Mapped[float] = mapped_column(Float, default=90.0)
    b_min: Mapped[float] = mapped_column(Float, default=80.0)
    c_min: Mapped[float] = mapped_column(Float, default=70.0)
    d_min: Mapped[float] = mapped_column(Float, default=60.0)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    courses: Mapped[list["Course"]] = relationship(back_populates="school_year")
    attendance_days: Mapped[list["AttendanceDay"]] = relationship(back_populates="school_year")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey("school_years.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160))
    color: Mapped[str] = mapped_column(String(16), default="#2D6A4F")
    notes: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    schedule: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    grade_level: Mapped[str] = mapped_column(String(80), default="")
    credit_hours: Mapped[str] = mapped_column(String(40), default="")
    goals: Mapped[str] = mapped_column(Text, default="")
    materials: Mapped[str] = mapped_column(Text, default="")
    teacher_notes: Mapped[str] = mapped_column(Text, default="")
    student_brief: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    school_year: Mapped["SchoolYear"] = relationship(back_populates="courses")
    teacher_links: Mapped[list["CourseTeacher"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    categories: Mapped[list["GradeCategory"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="GradeCategory.sort_order"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    book_links: Mapped[list["CourseBook"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="CourseBook.sort_order"
    )

    @property
    def books(self) -> list["Book"]:
        return [link.book for link in self.book_links]


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default=BookKind.OTHER.value)
    isbn: Mapped[str] = mapped_column(String(32), default="")
    upc: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course_links: Mapped[list["CourseBook"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="book")

    @property
    def courses(self) -> list["Course"]:
        return [link.course for link in self.course_links]

    @property
    def kind_label(self) -> str:
        try:
            return BOOK_KIND_LABELS.get(BookKind(self.kind), "Book")
        except ValueError:
            return "Book"

    @property
    def code_label(self) -> str:
        return (self.isbn or self.upc or "").strip()


class CourseBook(Base):
    __tablename__ = "course_books"
    __table_args__ = (UniqueConstraint("course_id", "book_id", name="uq_course_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped["Course"] = relationship(back_populates="book_links")
    book: Mapped["Book"] = relationship(back_populates="course_links")


class CourseTeacher(Base):
    __tablename__ = "course_teachers"
    __table_args__ = (UniqueConstraint("course_id", "teacher_id", name="uq_course_teacher"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), index=True)

    course: Mapped["Course"] = relationship(back_populates="teacher_links")
    teacher: Mapped["Teacher"] = relationship(back_populates="course_links")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_enrollment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)

    course: Mapped["Course"] = relationship(back_populates="enrollments")
    student: Mapped["Student"] = relationship(back_populates="enrollments")
    grades: Mapped[list["Grade"]] = relationship(
        back_populates="enrollment", cascade="all, delete-orphan"
    )


class GradeCategory(Base):
    __tablename__ = "grade_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    weight: Mapped[float] = mapped_column(Float, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped["Course"] = relationship(back_populates="categories")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="category")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("grade_categories.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    points_possible: Mapped[float] = mapped_column(Float, default=100)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    show_on_calendar: Mapped[bool] = mapped_column(Boolean, default=True)
    book_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pages: Mapped[str] = mapped_column(String(80), default="")
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_work: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        _enum(AssignmentStatus, "assignment_status"), default=AssignmentStatus.ASSIGNED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    course: Mapped["Course"] = relationship(back_populates="assignments")
    category: Mapped["GradeCategory"] = relationship(back_populates="assignments")
    book: Mapped[Optional["Book"]] = relationship(back_populates="assignments")
    grades: Mapped[list["Grade"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )

    @property
    def page_label(self) -> str:
        if not (self.pages or "").strip():
            return ""
        pages = self.pages.strip()
        if "-" in pages or "," in pages:
            return f"pp. {pages}"
        return f"p. {pages}"


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (UniqueConstraint("enrollment_id", "assignment_id", name="uq_grade"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), index=True
    )
    points_earned: Mapped[float] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")
    entered_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    enrollment: Mapped["Enrollment"] = relationship(back_populates="grades")
    assignment: Mapped["Assignment"] = relationship(back_populates="grades")


class AttendanceDay(Base):
    __tablename__ = "attendance_days"
    __table_args__ = (UniqueConstraint("student_id", "on_date", name="uq_attendance_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    school_year_id: Mapped[int] = mapped_column(
        ForeignKey("school_years.id", ondelete="CASCADE"), index=True
    )
    on_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(_enum(AttendanceStatus, "attendance_status"))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    entered_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="attendance_days")
    school_year: Mapped["SchoolYear"] = relationship(back_populates="attendance_days")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    notes: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    show_on_calendar: Mapped[bool] = mapped_column(Boolean, default=True)
    scope: Mapped[str] = mapped_column(String(16), default=ShareScope.SCHOOL, index=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    inbox: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    color: Mapped[str] = mapped_column(String(16), default="#d4b44a")
    scope: Mapped[str] = mapped_column(String(16), default=ShareScope.PERSONAL, index=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    lifetime: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    school_year_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("school_years.id", ondelete="SET NULL"), nullable=True, index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sections: Mapped[list["NoteSection"]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan", order_by="NoteSection.sort_order"
    )
    pages: Mapped[list["NotePage"]] = relationship(back_populates="notebook")


class NoteSection(Base):
    __tablename__ = "note_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notebook_id: Mapped[int] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="Pages")
    color: Mapped[str] = mapped_column(String(16), default="#2d6a4f")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    notebook: Mapped["Notebook"] = relationship(back_populates="sections")
    pages: Mapped[list["NotePage"]] = relationship(back_populates="section")


class NotePage(Base):
    __tablename__ = "note_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notebook_id: Mapped[int] = mapped_column(ForeignKey("notebooks.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("note_sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("note_pages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(16), default=ShareScope.PERSONAL, index=True)
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Untitled")
    kind: Mapped[str] = mapped_column(String(16), default="note")
    body_html: Mapped[str] = mapped_column(Text, default="")
    body_json: Mapped[str] = mapped_column(Text, default="")
    body_plain: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    notebook: Mapped["Notebook"] = relationship(back_populates="pages")
    section: Mapped[Optional["NoteSection"]] = relationship(back_populates="pages")
    history: Mapped[list["NoteHistory"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )
    boxes: Mapped[list["NoteBox"]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="NoteBox.z"
    )


class NoteBox(Base):
    __tablename__ = "note_boxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("note_pages.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    x: Mapped[int] = mapped_column(Integer, default=40)
    y: Mapped[int] = mapped_column(Integer, default=24)
    w: Mapped[int] = mapped_column(Integer, default=720)
    h: Mapped[int] = mapped_column(Integer, default=160)
    z: Mapped[int] = mapped_column(Integer, default=1)
    bg: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    body_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    page: Mapped["NotePage"] = relationship(back_populates="boxes")


class NoteHistory(Base):
    __tablename__ = "note_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("note_pages.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    body_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    page: Mapped["NotePage"] = relationship(back_populates="history")


class PageTask(Base):
    __tablename__ = "page_tasks"
    __table_args__ = (UniqueConstraint("page_id", "task_id", name="uq_page_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("note_pages.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReminderJob(Base):
    __tablename__ = "reminder_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    send_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    subject: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    recipient: Mapped[str] = mapped_column(String(255), default="")
    audience: Mapped[str] = mapped_column(String(16), default="personal")
    channel: Mapped[str] = mapped_column(String(16), default="email")
    sms_to: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    recurrence: Mapped[str] = mapped_column(String(32), default="")
    recurrence_json: Mapped[str] = mapped_column(Text, default="")
    repeat_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    series_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ReminderStatus.PENDING, index=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    email_delivered_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sms_delivered_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["ReminderItem"]] = relationship(
        back_populates="reminder",
        order_by="ReminderItem.sort_order",
        cascade="all, delete-orphan",
    )


class ReminderItem(Base):
    __tablename__ = "reminder_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(
        ForeignKey("reminder_jobs.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[str] = mapped_column(String(16))
    item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reminder: Mapped["ReminderJob"] = relationship(back_populates="items")


class TeacherApiKey(Base):
    __tablename__ = "teacher_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    provider: Mapped[str] = mapped_column(String(32), index=True)
    secret_enc: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="api_keys")


class NamedColor(Base):
    __tablename__ = "named_colors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    hex: Mapped[str] = mapped_column(String(16))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AiUsageEvent(Base):
    __tablename__ = "ai_usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(80), default="")
    key_name: Mapped[str] = mapped_column(String(80), default="")
    purpose: Mapped[str] = mapped_column(String(40), default="read_pages", index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usd: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AssessmentStatusKind(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Assessment(Base):
    """A test a parent builds and a student takes."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled test")
    instructions: Mapped[str] = mapped_column(Text, default="")
    course_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_text: Mapped[str] = mapped_column(Text, default="")
    model_provider: Mapped[str] = mapped_column(String(32), default="")
    model_name: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    allow_retries: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_credit: Mapped[str] = mapped_column(String(8), default="full")
    shuffle: Mapped[bool] = mapped_column(Boolean, default=False)
    points_possible: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    questions: Mapped[list["AssessmentQuestion"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentQuestion.sort_order",
    )
    attempts: Mapped[list["AssessmentAttempt"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(8), default="mc")
    prompt: Mapped[str] = mapped_column(Text, default="")
    points: Mapped[float] = mapped_column(Float, default=1)
    data_json: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")

    assessment: Mapped["Assessment"] = relationship(back_populates="questions")


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True
    )
    enrollment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("enrollments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="in_progress", index=True)
    score_points: Mapped[float] = mapped_column(Float, default=0)
    score_possible: Mapped[float] = mapped_column(Float, default=0)
    percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grade_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("grades.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    assessment: Mapped["Assessment"] = relationship(back_populates="attempts")
    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_questions.id", ondelete="CASCADE"), index=True
    )
    response_json: Mapped[str] = mapped_column(Text, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    points_earned: Mapped[float] = mapped_column(Float, default=0)
    retried: Mapped[bool] = mapped_column(Boolean, default=False)
    first_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    attempt: Mapped["AssessmentAttempt"] = relationship(back_populates="answers")


class ActivityAttempt(Base):
    __tablename__ = "activity_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    activity_id: Mapped[str] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0)
    time_taken_seconds: Mapped[int] = mapped_column(Integer, default=0)
    stars_earned: Mapped[int] = mapped_column(Integer, default=0)
    detail_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ActivityProgress(Base):
    __tablename__ = "activity_progress"
    __table_args__ = (UniqueConstraint("student_id", "activity_id", name="uq_activity_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str] = mapped_column(String(80), index=True)
    best_accuracy: Mapped[float] = mapped_column(Float, default=0)
    best_stars: Mapped[int] = mapped_column(Integer, default=0)
    plays: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_played_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ActivityPathProgress(Base):
    __tablename__ = "activity_path_progress"
    __table_args__ = (UniqueConstraint("student_id", "activity_id", name="uq_activity_path_progress"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str] = mapped_column(String(80), index=True)
    progress_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ActivityItemStat(Base):
    __tablename__ = "activity_item_stats"
    __table_args__ = (UniqueConstraint("student_id", "activity_id", "item_id", name="uq_activity_item_stat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str] = mapped_column(String(80), index=True)
    item_id: Mapped[str] = mapped_column(String(16), default="")
    seen: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    wrong: Mapped[int] = mapped_column(Integer, default=0)
    last_wrong_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class UserAiGrant(Base):
    __tablename__ = "user_ai_grants"
    __table_args__ = (UniqueConstraint("user_id", "purpose", name="uq_user_ai_grant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
