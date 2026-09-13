"""One house clock: America/New_York, stored naive."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import settings

HOUSE_TZ = ZoneInfo(settings.timezone or "America/New_York")


def house_now() -> datetime:
    return datetime.now(HOUSE_TZ).replace(tzinfo=None)


def house_today() -> date:
    return house_now().date()
