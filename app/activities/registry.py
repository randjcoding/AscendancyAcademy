"""Load every JSON file in catalog/ once. Drop a new file to add an activity."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.activities.schema import ActivityDef

CATALOG_DIR = Path(__file__).resolve().parent / "catalog"


@lru_cache(maxsize=1)
def all_activities() -> dict[str, ActivityDef]:
    out: dict[str, ActivityDef] = {}
    if not CATALOG_DIR.is_dir():
        return out
    for path in sorted(CATALOG_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        activity = ActivityDef.model_validate(data)
        out[activity.activity_id] = activity
    return out


def get_activity(activity_id: str) -> ActivityDef | None:
    return all_activities().get(activity_id)


def public_card(activity: ActivityDef, progress: dict | None = None) -> dict:
    row = {
        "activity_id": activity.activity_id,
        "title": activity.title,
        "category": activity.category,
        "icon": activity.icon,
        "type": activity.type,
        "modes": list(activity.modes),
        "passing_criteria": activity.passing_criteria.model_dump(),
        "item_count": len(activity.content),
    }
    if progress:
        row.update(progress)
    return row
