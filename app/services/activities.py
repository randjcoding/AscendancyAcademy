"""Record activity attempts, stars, and play streaks."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.activities.path_regions import PATH_GAMES, PATH_ORDER, PATH_PASS, PATH_REGIONS
from app.activities.registry import get_activity
from app.activities.schema import stars_for
from app.models import ActivityAttempt, ActivityItemStat, ActivityPathProgress, ActivityProgress, Student, User, UserAiGrant
from app.services.clock import house_today


def can_use_ai(db: Session, user: User, purpose: str | None = None) -> bool:
    if user.is_teacher:
        return True
    grants = list(db.scalars(select(UserAiGrant.purpose).where(UserAiGrant.user_id == user.id)).all())
    if purpose:
        return purpose in grants
    return bool(grants)


def grant_list(db: Session, user_id: int) -> list[str]:
    return list(db.scalars(select(UserAiGrant.purpose).where(UserAiGrant.user_id == user_id)).all())


def student_for(db: Session, user: User) -> Student | None:
    if user.is_student:
        return db.scalar(select(Student).where(Student.user_id == user.id))
    return None


def progress_row(db: Session, student_id: int, activity_id: str) -> dict:
    row = db.scalar(
        select(ActivityProgress).where(
            ActivityProgress.student_id == student_id,
            ActivityProgress.activity_id == activity_id,
        )
    )
    if not row:
        return {
            "best_accuracy": 0,
            "best_stars": 0,
            "plays": 0,
            "streak": 0,
            "last_played_on": "",
        }
    return {
        "best_accuracy": row.best_accuracy,
        "best_stars": row.best_stars,
        "plays": row.plays,
        "streak": row.streak,
        "last_played_on": row.last_played_on.isoformat() if row.last_played_on else "",
    }


def family_streak(db: Session, student_id: int) -> int:
    """Longest current daily streak across all activities."""
    rows = db.scalars(select(ActivityProgress).where(ActivityProgress.student_id == student_id)).all()
    return max((r.streak for r in rows), default=0)


def record_attempt(
    db: Session,
    *,
    user: User,
    activity_id: str,
    mode: str,
    score: int,
    total: int,
    time_taken_seconds: int,
    detail: dict | None = None,
    bind_student_id: int | None = None,
) -> dict:
    activity = get_activity(activity_id)
    if not activity:
        raise ValueError("That activity is gone.")
    score = max(0, int(score))
    total = max(0, int(total))
    accuracy = round((score / total) * 100.0, 2) if total else 0.0
    finished = total > 0 or mode == "study"
    if mode == "study":
        visited = int((detail or {}).get("visited") or score)
        finished = visited >= 10
        accuracy = 0.0
        score = visited
        total = len(activity.content) or 50
    stars = stars_for(activity.passing_criteria, finished=finished, accuracy=accuracy)
    student = student_for(db, user)
    sid = student.id if student else bind_student_id
    attempt = ActivityAttempt(
        user_id=user.id,
        student_id=sid,
        activity_id=activity_id,
        mode=mode,
        score=score,
        total=total,
        accuracy=accuracy,
        time_taken_seconds=max(0, int(time_taken_seconds)),
        stars_earned=stars,
        detail_json=json.dumps(detail or {}),
    )
    db.add(attempt)
    progress = None
    if sid:
        progress = _bump_progress(db, sid, activity_id, accuracy, stars, finished)
        if mode != "study":
            _record_item_stats(db, sid, activity_id, detail or {})
        path_info = (detail or {}).get("path")
        if isinstance(path_info, dict):
            apply_path_attempt(db, sid, activity_id, mode, path_info)
    db.commit()
    db.refresh(attempt)
    return {
        "attempt_id": attempt.id,
        "stars_earned": stars,
        "accuracy": accuracy,
        "score": score,
        "total": total,
        "progress": progress_row(db, sid, activity_id) if sid else None,
        "streak": progress.streak if progress else 0,
    }


def _bump_progress(
    db: Session,
    student_id: int,
    activity_id: str,
    accuracy: float,
    stars: int,
    finished: bool,
) -> ActivityProgress:
    row = db.scalar(
        select(ActivityProgress).where(
            ActivityProgress.student_id == student_id,
            ActivityProgress.activity_id == activity_id,
        )
    )
    today = house_today()
    if not row:
        row = ActivityProgress(
            student_id=student_id,
            activity_id=activity_id,
            best_accuracy=accuracy if finished else 0,
            best_stars=stars,
            plays=1 if finished else 0,
            streak=1 if finished else 0,
            last_played_on=today if finished else None,
        )
        db.add(row)
        db.flush()
        return row
    if finished:
        row.plays = (row.plays or 0) + 1
        row.best_accuracy = max(row.best_accuracy or 0, accuracy)
        row.best_stars = max(row.best_stars or 0, stars)
        last = row.last_played_on
        if last == today:
            pass
        elif last == today - timedelta(days=1):
            row.streak = (row.streak or 0) + 1
        else:
            row.streak = 1
        row.last_played_on = today
    db.flush()
    return row


def _record_item_stats(db: Session, student_id: int, activity_id: str, detail: dict) -> None:
    raw = detail.get("items")
    if not isinstance(raw, list):
        return
    now = datetime.utcnow()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("id") or "").strip()[:16]
        if not item_id:
            continue
        correct = bool(entry.get("correct"))
        row = db.scalar(
            select(ActivityItemStat).where(
                ActivityItemStat.student_id == student_id,
                ActivityItemStat.activity_id == activity_id,
                ActivityItemStat.item_id == item_id,
            )
        )
        if not row:
            row = ActivityItemStat(
                student_id=student_id,
                activity_id=activity_id,
                item_id=item_id,
                seen=0,
                correct=0,
                wrong=0,
            )
            db.add(row)
        row.seen = (row.seen or 0) + 1
        row.last_seen_at = now
        if correct:
            row.correct = (row.correct or 0) + 1
        else:
            row.wrong = (row.wrong or 0) + 1
            row.last_wrong_at = now
    db.flush()


def item_stats(db: Session, student_id: int, activity_id: str) -> list[dict]:
    activity = get_activity(activity_id)
    places = {p.id: p for p in activity.places()} if activity else {}
    rows = db.scalars(
        select(ActivityItemStat).where(
            ActivityItemStat.student_id == student_id,
            ActivityItemStat.activity_id == activity_id,
        )
    ).all()
    out = []
    for row in rows:
        place = places.get(row.item_id)
        seen = row.seen or 0
        miss = round(((row.wrong or 0) / seen) * 100, 1) if seen else 0.0
        out.append(
            {
                "id": row.item_id,
                "name": place.name if place else row.item_id,
                "capital": place.capital if place else "",
                "seen": seen,
                "correct": row.correct or 0,
                "wrong": row.wrong or 0,
                "miss_rate": miss,
                "last_wrong_at": row.last_wrong_at.isoformat() if row.last_wrong_at else "",
            }
        )
    out.sort(key=lambda item: (item["wrong"] == 0, -item["miss_rate"], -item["wrong"], item["name"]))
    return out


def teacher_struggle(db: Session, activity_id: str | None = None) -> list[dict]:
    students = db.scalars(select(Student).order_by(Student.id)).all()
    out = []
    for student in students:
        q = select(ActivityItemStat.activity_id).where(ActivityItemStat.student_id == student.id)
        if activity_id:
            aids = [activity_id]
        else:
            aids = sorted({row for row in db.scalars(q).all() if row})
        activities = []
        for aid in aids:
            hard = [item for item in item_stats(db, student.id, aid) if item["wrong"] > 0][:10]
            if hard:
                activities.append({"activity_id": aid, "hard": hard})
        out.append(
            {
                "student_id": student.id,
                "name": student.display_name,
                "activities": activities,
            }
        )
    return out


def history(db: Session, *, student_id: int | None, user_id: int, activity_id: str, limit: int = 20) -> list[dict]:
    q = select(ActivityAttempt).where(ActivityAttempt.activity_id == activity_id)
    if student_id:
        q = q.where(ActivityAttempt.student_id == student_id)
    else:
        q = q.where(ActivityAttempt.user_id == user_id)
    rows = db.scalars(q.order_by(ActivityAttempt.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "mode": r.mode,
            "score": r.score,
            "total": r.total,
            "accuracy": r.accuracy,
            "stars": r.stars_earned,
            "seconds": r.time_taken_seconds,
            "when": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def _empty_path() -> dict:
    return {
        "regions": {row["id"]: {"intro_done": False, "games": {}} for row in PATH_REGIONS},
        "final": {},
        "beaten": False,
    }


def _load_path(db: Session, student_id: int, activity_id: str) -> tuple[ActivityPathProgress, dict]:
    row = db.scalar(
        select(ActivityPathProgress).where(
            ActivityPathProgress.student_id == student_id,
            ActivityPathProgress.activity_id == activity_id,
        )
    )
    if not row:
        row = ActivityPathProgress(student_id=student_id, activity_id=activity_id, progress_json="{}")
        db.add(row)
        db.flush()
    raw = {}
    try:
        raw = json.loads(row.progress_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    data = _empty_path()
    data["beaten"] = bool(raw.get("beaten"))
    if isinstance(raw.get("final"), dict):
        data["final"] = {k: float(v) for k, v in raw["final"].items() if k in PATH_GAMES}
    regions = raw.get("regions") if isinstance(raw.get("regions"), dict) else {}
    leftover = regions.get("alaska_hawaii") if isinstance(regions.get("alaska_hawaii"), dict) else {}
    for rid in PATH_ORDER:
        src = regions.get(rid) if isinstance(regions.get(rid), dict) else {}
        games = src.get("games") if isinstance(src.get("games"), dict) else {}
        data["regions"][rid] = {
            "intro_done": bool(src.get("intro_done")),
            "games": {k: float(v) for k, v in games.items() if k in PATH_GAMES},
        }
    if leftover and "pacific" in data["regions"]:
        dest = data["regions"]["pacific"]
        extra = leftover.get("games") if isinstance(leftover.get("games"), dict) else {}
        for mode, val in extra.items():
            if mode in PATH_GAMES:
                dest["games"][mode] = max(float(dest["games"].get(mode) or 0), float(val or 0))
        if leftover.get("intro_done"):
            dest["intro_done"] = True
    return row, data


def _region_passed(games: dict) -> bool:
    return all(float(games.get(mode) or 0) + 1e-9 >= PATH_PASS for mode in PATH_GAMES)


def path_unlocked(data: dict) -> dict:
    unlocked = []
    for i, rid in enumerate(PATH_ORDER):
        if i == 0:
            unlocked.append(rid)
            continue
        prev = data["regions"][PATH_ORDER[i - 1]]
        if prev["intro_done"] and _region_passed(prev["games"]):
            unlocked.append(rid)
        else:
            break
    final_open = all(
        data["regions"][rid]["intro_done"] and _region_passed(data["regions"][rid]["games"]) for rid in PATH_ORDER
    )
    beaten = final_open and _region_passed(data.get("final") or {})
    return {"unlocked": unlocked, "final_open": final_open, "beaten": beaten}


def public_path(data: dict) -> dict:
    locks = path_unlocked(data)
    trail = []
    for row in PATH_REGIONS:
        rid = row["id"]
        info = data["regions"][rid]
        trail.append(
            {
                "id": rid,
                "label": row["label"],
                "ids": row["ids"],
                "intro_done": info["intro_done"],
                "games": {mode: info["games"].get(mode) for mode in PATH_GAMES},
                "passed": info["intro_done"] and _region_passed(info["games"]),
                "unlocked": rid in locks["unlocked"],
            }
        )
    return {
        "regions": trail,
        "final": {mode: data["final"].get(mode) for mode in PATH_GAMES},
        "final_open": locks["final_open"],
        "beaten": locks["beaten"] or data["beaten"],
        "games": list(PATH_GAMES),
        "pass": PATH_PASS,
    }


def path_for(db: Session, student_id: int, activity_id: str) -> dict:
    _row, data = _load_path(db, student_id, activity_id)
    return public_path(data)


def teacher_paths(db: Session, activity_id: str) -> list[dict]:
    students = db.scalars(select(Student).order_by(Student.id)).all()
    return [
        {"student_id": s.id, "name": s.display_name, "path": path_for(db, s.id, activity_id)}
        for s in students
    ]


def apply_path_intro(db: Session, student_id: int, activity_id: str, region: str) -> dict:
    if region not in PATH_ORDER:
        raise ValueError("Pick a region first.")
    row, data = _load_path(db, student_id, activity_id)
    locks = path_unlocked(data)
    if region not in locks["unlocked"]:
        raise ValueError("That region is still locked.")
    data["regions"][region]["intro_done"] = True
    row.progress_json = json.dumps(data)
    db.flush()
    return public_path(data)


def apply_path_attempt(db: Session, student_id: int, activity_id: str, mode: str, path_info: dict) -> None:
    if mode not in PATH_GAMES:
        return
    region = str(path_info.get("region") or "")
    final = bool(path_info.get("final"))
    try:
        first_pass = float(path_info.get("first_pass"))
    except (TypeError, ValueError):
        return
    row, data = _load_path(db, student_id, activity_id)
    locks = path_unlocked(data)
    if final:
        if not locks["final_open"]:
            return
        prev = data["final"].get(mode) or 0
        data["final"][mode] = max(prev, first_pass)
        if _region_passed(data["final"]):
            data["beaten"] = True
    else:
        if region not in PATH_ORDER or region not in locks["unlocked"]:
            return
        if not data["regions"][region]["intro_done"]:
            return
        prev = data["regions"][region]["games"].get(mode) or 0
        data["regions"][region]["games"][mode] = max(prev, first_pass)
    row.progress_json = json.dumps(data)
    db.flush()


def teacher_results(db: Session) -> list[dict]:
    students = db.scalars(select(Student).order_by(Student.id)).all()
    out = []
    for student in students:
        name = student.display_name
        rows = db.scalars(select(ActivityProgress).where(ActivityProgress.student_id == student.id)).all()
        out.append(
            {
                "student_id": student.id,
                "name": name,
                "streak": max((r.streak for r in rows), default=0),
                "activities": [
                    {
                        "activity_id": r.activity_id,
                        "best_stars": r.best_stars,
                        "best_accuracy": r.best_accuracy,
                        "plays": r.plays,
                        "hard": [item for item in item_stats(db, student.id, r.activity_id) if item["wrong"] > 0][:8],
                    }
                    for r in rows
                ],
            }
        )
    return out
