"""Teaching groups for the capitals learning path. Must match web/src/activities/pathRegions.ts."""

PATH_GAMES = (
    "find_the_state",
    "find_on_map",
    "name_the_capital",
    "city_trap",
    "quiz",
    "match",
)
PATH_PASS = 90.0

PATH_REGIONS: list[dict] = [
    {"id": "new_england", "label": "New England", "ids": ["ME", "NH", "VT", "MA", "RI", "CT"]},
    {"id": "mid_atlantic", "label": "Mid-Atlantic", "ids": ["NY", "NJ", "PA", "DE", "MD"]},
    {"id": "south", "label": "South", "ids": ["VA", "WV", "NC", "SC", "GA", "FL", "KY", "TN", "AL", "MS", "AR", "LA", "OK", "TX"]},
    {"id": "midwest", "label": "Midwest", "ids": ["OH", "MI", "IN", "WI", "IL", "MN", "IA", "MO", "ND", "SD", "NE", "KS"]},
    {"id": "mountain_west", "label": "Mountain West", "ids": ["MT", "ID", "WY", "NV", "UT", "CO", "AZ", "NM"]},
    {"id": "pacific", "label": "Pacific", "ids": ["WA", "OR", "CA", "AK", "HI"]},
]

PATH_ORDER = [row["id"] for row in PATH_REGIONS]
ID_TO_REGION = {sid: row["id"] for row in PATH_REGIONS for sid in row["ids"]}


def all_ids() -> list[str]:
    return [sid for row in PATH_REGIONS for sid in row["ids"]]
