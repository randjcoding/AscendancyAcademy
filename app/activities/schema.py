"""Pydantic contract for activity definition files.

A new activity is a JSON file in catalog/ that matches this shape.
The runner dispatches on ``type``; adding a type later does not rewrite tables.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PassingCriteria(BaseModel):
    star_1: float = 1
    star_2: float = 80
    star_3: float = 100


class MapPlace(BaseModel):
    id: str
    name: str
    capital: str = ""
    capital_phonetic: str = ""
    tip: str = ""
    region: str = ""


class ActivityDef(BaseModel):
    activity_id: str
    title: str
    category: str = "Practice"
    icon: str = "star"
    type: str = "interactive_map_drill"
    passing_criteria: PassingCriteria = Field(default_factory=PassingCriteria)
    modes: list[str] = Field(default_factory=list)
    content: list[dict[str, Any]] = Field(default_factory=list)

    def places(self) -> list[MapPlace]:
        if self.type != "interactive_map_drill":
            return []
        return [MapPlace.model_validate(row) for row in self.content]


def stars_for(criteria: PassingCriteria, *, finished: bool, accuracy: float) -> int:
    """Same math for every activity. star_1 = finished a run; 2/3 = accuracy %."""
    if not finished:
        return 0
    stars = 1
    if accuracy + 1e-9 >= float(criteria.star_2):
        stars = 2
    if accuracy + 1e-9 >= float(criteria.star_3):
        stars = 3
    if float(criteria.star_1) <= 0:
        return stars
    return stars


AI_PURPOSES = ("read_pages", "make_test")
ModeName = Literal["study", "find_on_map", "name_the_capital", "flashcards"]
