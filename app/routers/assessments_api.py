"""Test Maker API: build tests with a model, take them, and record grades."""
from __future__ import annotations

import json
import random
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import first_student, student_profile, teacher_profile
from app.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentQuestion,
    Assignment,
    AssignmentStatus,
    Course,
    CourseTeacher,
    Enrollment,
    Grade,
    GradeCategory,
    Student,
    User,
)
from app.routers.api import _csrf_bad, _err, _must_user
from app.seed import COURSE_COLOR_VALUES
from app.services import ai_costs
from app.services import ai_usage as usage_svc
from app.services import assessments as svc
from app.services import attendance as attendance_svc
from app.services import ocr
from app.services import youtube

router = APIRouter(prefix="/api/tests")

PROVIDERS = {"openai", "anthropic", "gemma"}


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------

class GenerateBody(BaseModel):
    csrf: str = ""
    provider: str = "openai"
    key_id: int = 0
    content: str = ""
    title: str = ""
    course_id: int = 0
    count: int = 10
    difficulty: str = "medium"
    grade_level: str = ""
    types: list[str] = []


class RefineBody(BaseModel):
    csrf: str = ""
    provider: str = "openai"
    key_id: int = 0
    instruction: str = ""


class EditBody(BaseModel):
    csrf: str = ""
    title: str = ""
    instructions: str = ""
    allow_retries: bool | None = None
    retry_credit: str = ""
    shuffle: bool | None = None
    questions: list[dict] | None = None


class PublishBody(BaseModel):
    csrf: str = ""
    course_id: int = 0
    new_course_title: str = ""
    due_date: str = ""
    allow_retries: bool | None = None
    retry_credit: str = ""
    shuffle: bool | None = None


class ImportBody(BaseModel):
    csrf: str = ""
    json_text: str = ""
    title: str = ""
    course_id: int = 0


class CsrfBody(BaseModel):
    csrf: str = ""


class AnswerIn(BaseModel):
    question_id: int
    response: dict = {}


class SubmitBody(BaseModel):
    csrf: str = ""
    answers: list[AnswerIn] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _key_row(db: Session, user: User, key_id: int):
    if not key_id:
        return None
    from app.models import TeacherApiKey

    row = db.get(TeacherApiKey, key_id)
    if not row or row.user_id != user.id:
        return None
    return row


def _teacher_assessment(db: Session, user: User, test_id: int) -> Assessment | JSONResponse:
    a = db.get(Assessment, test_id)
    if not a or a.deleted_at is not None:
        return _err("That test is gone.", 404)
    if a.created_by_user_id != user.id and not user.is_teacher:
        return _err("You cannot open that test.", 403)
    return a


def _assessment_json(a: Assessment) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "instructions": a.instructions,
        "course_id": a.course_id,
        "assignment_id": a.assignment_id,
        "status": a.status,
        "allow_retries": a.allow_retries,
        "retry_credit": a.retry_credit,
        "shuffle": a.shuffle,
        "points_possible": a.points_possible,
        "model_provider": a.model_provider,
        "model_name": a.model_name,
        "source_text": a.source_text or "",
        "question_count": len(a.questions),
        "questions": [svc.question_full(q) for q in a.questions],
        "created_at": a.created_at.isoformat() if a.created_at else "",
    }


def _course_title(db: Session, course_id: int | None) -> str:
    if not course_id:
        return ""
    course = db.get(Course, course_id)
    return course.title if course else ""


def _current_student(db: Session, user: User) -> Student | None:
    if user.is_student:
        return db.scalar(select(Student).where(Student.user_id == user.id))
    return first_student(db)


# ---------------------------------------------------------------------------
# Ingest content (photos OCR, pasted text, YouTube)
# ---------------------------------------------------------------------------

@router.post("/ingest")
async def ingest(
    request: Request,
    db: Session = Depends(get_db),
    csrf: str = Form(""),
    text: str = Form(""),
    youtube_url: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, csrf):
        return _err("That form expired.", 403)
    parts: list[str] = []
    notes: list[str] = []
    if text.strip():
        parts.append(text.strip())
    if youtube_url.strip():
        result = youtube.fetch_transcript(youtube_url)
        if result.text:
            parts.append(result.text)
            notes.append("Added the video transcript.")
        elif result.error:
            notes.append(result.error)
    blobs: list[bytes] = []
    for item in files or []:
        if not item.filename:
            continue
        data = await item.read()
        if data:
            blobs.append(data)
    if blobs:
        read = ocr.read_images(blobs)
        if read.strip():
            parts.append(read.strip())
            notes.append(f"Read {len(blobs)} photo(s).")
        else:
            notes.append("Could not read text from the photo(s). Type or paste it instead.")
    return {"ok": True, "content": "\n\n".join(parts).strip(), "notes": notes}


# ---------------------------------------------------------------------------
# Generate / refine with a model
# ---------------------------------------------------------------------------

@router.get("/estimate")
def estimate(request: Request, provider: str = "", db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if provider not in PROVIDERS:
        return _err("Pick a model first.")
    return ai_costs.estimate_usd(provider, 0)


@router.get("/prompt-spec")
def prompt_spec(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    return {"spec": svc.PROMPT_SPEC}


@router.post("/generate")
async def generate(body: GenerateBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if body.provider not in PROVIDERS:
        return _err("Pick a model first.")
    if not body.content.strip():
        return _err("Add some material first.")
    key_row = _key_row(db, user, body.key_id)
    if body.provider != "gemma" and not key_row:
        return _err("Pick a saved key for that model.")
    opts = {
        "count": max(1, min(50, int(body.count or 10))),
        "difficulty": body.difficulty,
        "grade_level": body.grade_level,
        "types": body.types,
    }
    result = await svc.generate(body.provider, key_row, body.content, opts)
    student = first_student(db)
    usage_svc.log_ai(
        db,
        user=user,
        student_id=student.id if student else None,
        provider=result.provider,
        model=result.model,
        key_name=key_row.name if key_row else "Gemma",
        purpose="make_test",
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        usd=result.usd,
        error=result.error,
    )
    if result.error:
        db.commit()
        return _err(result.error)
    a = Assessment(
        title=(body.title.strip() or result.title or "Untitled test")[:255],
        created_by_user_id=user.id,
        course_id=body.course_id or None,
        source_text=body.content.strip()[:20000],
        model_provider=result.provider,
        model_name=result.model,
        status="draft",
    )
    db.add(a)
    db.flush()
    svc.store_questions(db, a, result.questions)
    db.commit()
    db.refresh(a)
    return {"ok": True, "test": _assessment_json(a), "estimate": ai_costs.estimate_usd(result.provider, 0, result.model)}


@router.post("/{test_id}/refine")
async def refine(test_id: int, body: RefineBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    a = _teacher_assessment(db, user, test_id)
    if isinstance(a, JSONResponse):
        return a
    if body.provider not in PROVIDERS:
        return _err("Pick a model first.")
    key_row = _key_row(db, user, body.key_id)
    if body.provider != "gemma" and not key_row:
        return _err("Pick a saved key for that model.")
    current = [svc.question_editable(q) for q in a.questions]
    result = await svc.refine(body.provider, key_row, current, body.instruction, a.source_text)
    student = first_student(db)
    usage_svc.log_ai(
        db,
        user=user,
        student_id=student.id if student else None,
        provider=result.provider,
        model=result.model,
        key_name=key_row.name if key_row else "Gemma",
        purpose="make_test",
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        usd=result.usd,
        error=result.error,
    )
    if result.error:
        db.commit()
        return _err(result.error)
    svc.store_questions(db, a, result.questions)
    a.model_provider = result.provider
    a.model_name = result.model
    db.commit()
    db.refresh(a)
    return {"ok": True, "test": _assessment_json(a)}


# ---------------------------------------------------------------------------
# List / read / hand-edit / import / delete
# ---------------------------------------------------------------------------

@router.get("")
def list_tests(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    rows = db.scalars(
        select(Assessment)
        .where(Assessment.deleted_at.is_(None))
        .order_by(Assessment.created_at.desc())
    ).all()
    return {
        "tests": [
            {
                "id": a.id,
                "title": a.title,
                "status": a.status,
                "course_id": a.course_id,
                "course_title": _course_title(db, a.course_id),
                "question_count": len(a.questions),
                "points_possible": a.points_possible,
                "created_at": a.created_at.isoformat() if a.created_at else "",
            }
            for a in rows
        ]
    }


@router.post("/import")
def import_json(body: ImportBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    raw = (body.json_text or "").strip()
    if not raw:
        return _err("Paste the JSON a model gave you.")
    parsed = svc._extract_json(raw)
    title = body.title.strip() or str(parsed.get("title") or "").strip() or "Imported test"
    questions = svc.parse_questions(parsed.get("questions") if isinstance(parsed, dict) else parsed)
    if not questions:
        return _err("That JSON had no questions we could read. Check the format and try again.")
    a = Assessment(
        title=title[:255],
        created_by_user_id=user.id,
        course_id=body.course_id or None,
        model_provider="import",
        model_name="import",
        status="draft",
    )
    db.add(a)
    db.flush()
    svc.store_questions(db, a, questions)
    db.commit()
    db.refresh(a)
    return {"ok": True, "test": _assessment_json(a)}


@router.get("/{test_id}")
def get_test(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    a = _teacher_assessment(db, user, test_id)
    if isinstance(a, JSONResponse):
        return a
    payload = _assessment_json(a)
    payload["course_title"] = _course_title(db, a.course_id)
    return {"ok": True, "test": payload}


@router.post("/{test_id}")
def edit_test(test_id: int, body: EditBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    a = _teacher_assessment(db, user, test_id)
    if isinstance(a, JSONResponse):
        return a
    if body.title.strip():
        a.title = body.title.strip()[:255]
    if body.instructions is not None:
        a.instructions = body.instructions
    if body.allow_retries is not None:
        a.allow_retries = body.allow_retries
    if body.retry_credit in {"half", "full"}:
        a.retry_credit = body.retry_credit
    if body.shuffle is not None:
        a.shuffle = body.shuffle
    if body.questions is not None:
        questions = svc.parse_questions(body.questions)
        if not questions:
            return _err("A test needs at least one valid question.")
        svc.store_questions(db, a, questions)
    db.commit()
    db.refresh(a)
    return {"ok": True, "test": _assessment_json(a)}


@router.post("/{test_id}/delete")
def delete_test(test_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    a = _teacher_assessment(db, user, test_id)
    if isinstance(a, JSONResponse):
        return a
    a.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Publish -> assign a class, build a gradebook assignment
# ---------------------------------------------------------------------------

def _tests_category(db: Session, course: Course) -> GradeCategory | None:
    for cat in course.categories:
        if cat.name.strip().lower() == "tests":
            return cat
    return course.categories[0] if course.categories else None


def _create_course(db: Session, user: User, title: str) -> Course | JSONResponse:
    year = attendance_svc.current_year(db)
    name = title.strip()
    if not year or not name:
        return _err("Need a class name and a school year.")
    color = COURSE_COLOR_VALUES[0]
    teacher = teacher_profile(db, user)
    student = first_student(db)
    course = Course(school_year_id=year.id, title=name[:160], color=color)
    db.add(course)
    db.flush()
    db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
    if student:
        db.add(Enrollment(course_id=course.id, student_id=student.id))
    for cat_name, weight, order in (("Tests", 25.0, 0), ("Quizzes", 25.0, 1), ("Assignments", 25.0, 2), ("Other", 25.0, 3)):
        db.add(GradeCategory(course_id=course.id, name=cat_name, weight=weight, sort_order=order))
    db.flush()
    return course


@router.post("/{test_id}/publish")
def publish(test_id: int, body: PublishBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    a = _teacher_assessment(db, user, test_id)
    if isinstance(a, JSONResponse):
        return a
    if not a.questions:
        return _err("Add at least one question before publishing.")
    course: Course | None = None
    if body.new_course_title.strip():
        made = _create_course(db, user, body.new_course_title)
        if isinstance(made, JSONResponse):
            return made
        course = made
    elif body.course_id:
        course = db.get(Course, body.course_id)
    elif a.course_id:
        course = db.get(Course, a.course_id)
    if not course:
        return _err("Pick a class or make a new one.")
    if body.allow_retries is not None:
        a.allow_retries = body.allow_retries
    if body.retry_credit in {"half", "full"}:
        a.retry_credit = body.retry_credit
    if body.shuffle is not None:
        a.shuffle = body.shuffle
    parsed_due = None
    if body.due_date.strip():
        try:
            parsed_due = date.fromisoformat(body.due_date.strip())
        except ValueError:
            return _err("That due date is not valid.")
    category = _tests_category(db, course)
    if not category:
        return _err("This class needs a grade category.")
    assignment = db.get(Assignment, a.assignment_id) if a.assignment_id else None
    if assignment is None:
        assignment = Assignment(
            course_id=course.id,
            category_id=category.id,
            title=a.title[:255],
            description="Test taken online.",
            points_possible=a.points_possible or 0,
            due_date=parsed_due,
            show_on_calendar=bool(parsed_due),
            has_work=True,
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(assignment)
        db.flush()
    else:
        assignment.course_id = course.id
        assignment.category_id = category.id
        assignment.title = a.title[:255]
        assignment.points_possible = a.points_possible or 0
        if parsed_due:
            assignment.due_date = parsed_due
    a.course_id = course.id
    a.assignment_id = assignment.id
    a.status = "published"
    db.commit()
    db.refresh(a)
    payload = _assessment_json(a)
    payload["course_title"] = course.title
    return {"ok": True, "test": payload}


# ---------------------------------------------------------------------------
# Parent results
# ---------------------------------------------------------------------------

@router.get("/results/all")
def results(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    attempts = db.scalars(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.status == "graded")
        .order_by(AssessmentAttempt.submitted_at.desc())
    ).all()
    rows = []
    for at in attempts:
        a = at.assessment
        if not a or a.deleted_at is not None:
            continue
        student = db.get(Student, at.student_id)
        rows.append(
            {
                "attempt_id": at.id,
                "test_id": a.id,
                "test_title": a.title,
                "student_name": student.display_name if student else "Student",
                "attempt_no": at.attempt_no,
                "score_points": round(at.score_points, 2),
                "score_possible": round(at.score_possible, 2),
                "percent": at.percent,
                "allow_retries": a.allow_retries,
                "submitted_at": at.submitted_at.isoformat() if at.submitted_at else "",
            }
        )
    return {"results": rows}


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: int, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    at = db.get(AssessmentAttempt, attempt_id)
    if not at:
        return _err("That attempt is gone.", 404)
    student = _current_student(db, user)
    is_owner = student is not None and at.student_id == student.id
    if not user.is_teacher and not is_owner:
        return _err("You cannot see that attempt.", 403)
    a = at.assessment
    answer_by_q = {ans.question_id: ans for ans in at.answers}
    questions = []
    for q in a.questions:
        ans = answer_by_q.get(q.id)
        item = svc.question_full(q) if user.is_teacher else svc.question_public(q)
        item["your_response"] = json.loads(ans.response_json) if ans and ans.response_json else None
        item["points_earned"] = round(ans.points_earned, 2) if ans else 0
        item["is_correct"] = bool(ans.is_correct) if ans else False
        item["first_correct"] = bool(ans.first_correct) if ans else False
        item["retried"] = bool(ans.retried) if ans else False
        questions.append(item)
    return {
        "attempt": {
            "id": at.id,
            "test_id": a.id,
            "test_title": a.title,
            "status": at.status,
            "attempt_no": at.attempt_no,
            "score_points": round(at.score_points, 2),
            "score_possible": round(at.score_possible, 2),
            "percent": at.percent,
            "allow_retries": a.allow_retries,
            "retry_credit": a.retry_credit,
        },
        "questions": questions,
    }


# ---------------------------------------------------------------------------
# Student: assigned, start, submit, retry
# ---------------------------------------------------------------------------

@router.get("/student/assigned")
def assigned(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student = _current_student(db, user)
    if not student:
        return {"tests": []}
    course_ids = set(db.scalars(select(Enrollment.course_id).where(Enrollment.student_id == student.id)).all())
    rows = db.scalars(
        select(Assessment)
        .where(Assessment.status == "published", Assessment.deleted_at.is_(None))
        .order_by(Assessment.created_at.desc())
    ).all()
    out = []
    for a in rows:
        if a.course_id not in course_ids:
            continue
        attempt = db.scalar(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == student.id)
            .order_by(AssessmentAttempt.id.desc())
        )
        done = attempt is not None and attempt.status == "graded"
        can_retry = bool(done and a.allow_retries and any(not ans.first_correct for ans in attempt.answers))
        out.append(
            {
                "id": a.id,
                "title": a.title,
                "course_title": _course_title(db, a.course_id),
                "question_count": len(a.questions),
                "points_possible": a.points_possible,
                "status": attempt.status if attempt else "not_started",
                "percent": attempt.percent if attempt else None,
                "attempt_id": attempt.id if attempt else None,
                "can_retry": can_retry,
            }
        )
    return {"tests": out}


def _take_json(a: Assessment) -> dict:
    questions = [svc.question_public(q) for q in a.questions]
    if a.shuffle:
        random.shuffle(questions)
    return {
        "id": a.id,
        "title": a.title,
        "instructions": a.instructions,
        "points_possible": a.points_possible,
        "allow_retries": a.allow_retries,
        "retry_credit": a.retry_credit,
        "questions": questions,
    }


def _open_assessment_for_student(db: Session, student: Student, test_id: int) -> Assessment | JSONResponse:
    a = db.get(Assessment, test_id)
    if not a or a.deleted_at is not None or a.status != "published":
        return _err("That test is not available.", 404)
    course_ids = set(db.scalars(select(Enrollment.course_id).where(Enrollment.student_id == student.id)).all())
    if a.course_id not in course_ids:
        return _err("That test is not assigned to you.", 403)
    return a


@router.get("/{test_id}/take")
def take(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student = _current_student(db, user)
    if not student:
        return _err("Student required", 403)
    a = _open_assessment_for_student(db, student, test_id)
    if isinstance(a, JSONResponse):
        return a
    return {"ok": True, "test": _take_json(a)}


def _enrollment_for(db: Session, student: Student, course_id: int | None):
    if not course_id:
        return None
    return db.scalar(
        select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.student_id == student.id)
    )


def _write_grade(db: Session, a: Assessment, attempt: AssessmentAttempt, student: Student, user: User) -> None:
    if not a.assignment_id:
        return
    enrollment = _enrollment_for(db, student, a.course_id)
    if not enrollment:
        return
    attempt.enrollment_id = enrollment.id
    existing = db.scalar(
        select(Grade).where(Grade.assignment_id == a.assignment_id, Grade.enrollment_id == enrollment.id)
    )
    if existing:
        existing.points_earned = round(attempt.score_points, 3)
        existing.notes = f"Test auto-graded ({attempt.percent}%)."
        existing.entered_by_user_id = user.id
        db.flush()
        attempt.grade_id = existing.id
    else:
        grade = Grade(
            enrollment_id=enrollment.id,
            assignment_id=a.assignment_id,
            points_earned=round(attempt.score_points, 3),
            notes=f"Test auto-graded ({attempt.percent}%).",
            entered_by_user_id=user.id,
        )
        db.add(grade)
        db.flush()
        attempt.grade_id = grade.id


def _finalize(db: Session, attempt: AssessmentAttempt, a: Assessment) -> None:
    total = sum(ans.points_earned for ans in attempt.answers)
    possible = a.points_possible or sum(q.points for q in a.questions)
    attempt.score_points = round(total, 3)
    attempt.score_possible = round(possible, 3)
    attempt.percent = round((total / possible) * 100.0, 2) if possible > 0 else None
    attempt.status = "graded"
    attempt.submitted_at = datetime.utcnow()


@router.post("/{test_id}/submit")
def submit(test_id: int, body: SubmitBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    student = _current_student(db, user)
    if not student:
        return _err("Student required", 403)
    a = _open_assessment_for_student(db, student, test_id)
    if isinstance(a, JSONResponse):
        return a
    prior = db.scalars(
        select(AssessmentAttempt)
        .where(AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == student.id)
    ).all()
    attempt = AssessmentAttempt(
        assessment_id=a.id,
        student_id=student.id,
        attempt_no=len(prior) + 1,
        status="in_progress",
    )
    db.add(attempt)
    db.flush()
    responses = {ans.question_id: (ans.response or {}) for ans in body.answers}
    for q in a.questions:
        response = responses.get(q.id, {})
        fraction = svc.grade_fraction(q, response)
        earned = round(q.points * fraction, 3)
        correct = fraction >= 1.0
        db.add(
            AssessmentAnswer(
                attempt_id=attempt.id,
                question_id=q.id,
                response_json=json.dumps(response),
                is_correct=correct,
                points_earned=earned,
                first_correct=correct,
                retried=False,
            )
        )
    db.flush()
    _finalize(db, attempt, a)
    _write_grade(db, a, attempt, student, user)
    db.commit()
    db.refresh(attempt)
    return attempt_detail(attempt.id, request, db)


@router.post("/attempts/{attempt_id}/retry")
def retry(attempt_id: int, body: SubmitBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    student = _current_student(db, user)
    if not student:
        return _err("Student required", 403)
    attempt = db.get(AssessmentAttempt, attempt_id)
    if not attempt or attempt.student_id != student.id:
        return _err("That attempt is not yours.", 403)
    a = attempt.assessment
    if not a or not a.allow_retries:
        return _err("Retries are off for this test.")
    factor = 0.5 if a.retry_credit == "half" else 1.0
    question_by_id = {q.id: q for q in a.questions}
    answer_by_q = {ans.question_id: ans for ans in attempt.answers}
    responses = {ans.question_id: (ans.response or {}) for ans in body.answers}
    for qid, response in responses.items():
        q = question_by_id.get(qid)
        ans = answer_by_q.get(qid)
        if not q or not ans or ans.first_correct:
            continue  # only wrong-on-first questions may be retried
        old_fraction = (ans.points_earned / q.points) if q.points else 0.0
        new_fraction = svc.grade_fraction(q, response)
        if new_fraction > old_fraction:
            credited = old_fraction + (new_fraction - old_fraction) * factor
            ans.points_earned = round(q.points * credited, 3)
            ans.response_json = json.dumps(response)
            ans.is_correct = new_fraction >= 1.0
            ans.retried = True
    db.flush()
    _finalize(db, attempt, a)
    _write_grade(db, a, attempt, student, user)
    db.commit()
    db.refresh(attempt)
    return attempt_detail(attempt.id, request, db)
