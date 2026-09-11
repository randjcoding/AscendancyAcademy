"""Look up books by ISBN, UPC, or title. Open Library first, Google Books next."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict

from app.models import BookKind

USER_AGENT = "AscendancyAcademy/1.0 (homeschool desk)"
TIMEOUT = 5


@dataclass
class BookHit:
    title: str
    author: str = ""
    isbn: str = ""
    upc: str = ""
    kind: str = BookKind.OTHER.value
    notes: str = ""
    source: str = ""


def digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def isbn13_to_isbn10(code: str) -> str:
    if len(code) != 13 or not code.startswith("978") or not code.isdigit():
        return ""
    core = code[3:12]
    total = sum(int(digit) * (10 - i) for i, digit in enumerate(core))
    check = (11 - (total % 11)) % 11
    return core + ("X" if check == 10 else str(check))


def code_variants(raw: str) -> list[str]:
    code = normalize_code(raw)
    if not code:
        return []
    out = [code]
    ten = isbn13_to_isbn10(code)
    if ten and ten not in out:
        out.append(ten)
    return out


def normalize_code(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    code = re.sub(r"[^0-9Xx]", "", text).upper()
    if len(code) == 10 and code[:9].isdigit() and code[9] in "0123456789X":
        return code
    if code.isdigit() and len(code) in {8, 12, 13}:
        return code
    return ""


def guess_kind(title: str, subjects: list[str]) -> BookKind:
    blob = " ".join([title] + subjects).lower()
    if any(word in blob for word in ("workbook", "practice", "work book")):
        return BookKind.WORKBOOK
    if any(word in blob for word in ("curriculum", "homeschool", "lesson", "teacher guide")):
        return BookKind.CURRICULUM
    if any(word in blob for word in ("novel", "fiction", "juvenile fiction", "young adult")):
        return BookKind.NOVEL
    if any(word in blob for word in ("textbook", "algebra", "science", "history", "grammar")):
        return BookKind.TEXTBOOK
    return BookKind.OTHER


def _get(url: str) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None


def lookup_open_library(query: str) -> list[BookHit]:
    code = normalize_code(query)
    hits: list[BookHit] = []
    if len(code) in {10, 13}:
        data = _get(f"https://openlibrary.org/isbn/{code}.json")
        if isinstance(data, dict) and data.get("title"):
            authors = ""
            works = data.get("authors") or []
            if works:
                first = works[0]
                key = first.get("key") if isinstance(first, dict) else None
                if key:
                    person = _get(f"https://openlibrary.org{key}.json")
                    if isinstance(person, dict):
                        authors = person.get("name") or ""
            subjects = [str(s) for s in (data.get("subjects") or [])[:8]]
            hits.append(
                BookHit(
                    title=data["title"],
                    author=authors,
                    isbn=code if len(code) in {10, 13} else "",
                    upc=code,
                    kind=guess_kind(data["title"], subjects).value,
                    notes="; ".join(subjects[:3]),
                    source="Open Library",
                )
            )
    params = urllib.parse.urlencode({"q": query.strip(), "limit": 5})
    search = _get(f"https://openlibrary.org/search.json?{params}")
    if isinstance(search, dict):
        for doc in (search.get("docs") or [])[:5]:
            title = (doc.get("title") or "").strip()
            if not title:
                continue
            isbn = ""
            for cand in doc.get("isbn") or []:
                raw = normalize_code(str(cand))
                if len(raw) in {10, 13}:
                    isbn = raw
                    break
            author = ""
            names = doc.get("author_name") or []
            if names:
                author = str(names[0])
            subjects = [str(s) for s in (doc.get("subject") or [])[:8]]
            hit = BookHit(
                title=title,
                author=author,
                isbn=isbn,
                upc=isbn,
                kind=guess_kind(title, subjects).value,
                notes="; ".join(subjects[:3]),
                source="Open Library",
            )
            if not any(h.title.lower() == hit.title.lower() and h.author.lower() == hit.author.lower() for h in hits):
                hits.append(hit)
    return hits[:5]


def lookup_open_library_isbn(code: str) -> list[BookHit]:
    data = _get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{code}&format=json&jscmd=data")
    if not isinstance(data, dict):
        return []
    info = data.get(f"ISBN:{code}") or next(iter(data.values()), None)
    if not isinstance(info, dict) or not info.get("title"):
        return []
    authors = ""
    people = info.get("authors") or []
    if people and isinstance(people[0], dict):
        authors = people[0].get("name") or ""
    subjects = [str(s.get("name") if isinstance(s, dict) else s) for s in (info.get("subjects") or [])[:8]]
    return [
        BookHit(
            title=info["title"],
            author=authors,
            isbn=code,
            upc=code,
            kind=guess_kind(info["title"], subjects).value,
            notes="; ".join(subjects[:3]),
            source="Open Library",
        )
    ]


def lookup_open_library_search_isbn(code: str) -> list[BookHit]:
    params = urllib.parse.urlencode({"isbn": code, "limit": 5})
    search = _get(f"https://openlibrary.org/search.json?{params}")
    hits: list[BookHit] = []
    if not isinstance(search, dict):
        return hits
    for doc in (search.get("docs") or [])[:5]:
        title = (doc.get("title") or "").strip()
        if not title:
            continue
        isbn = ""
        for cand in doc.get("isbn") or []:
            raw = normalize_code(str(cand))
            if len(raw) in {10, 13}:
                isbn = raw
                break
        author = ""
        names = doc.get("author_name") or []
        if names:
            author = str(names[0])
        subjects = [str(s) for s in (doc.get("subject") or [])[:8]]
        hits.append(
            BookHit(
                title=title,
                author=author,
                isbn=isbn or code,
                upc=isbn or code,
                kind=guess_kind(title, subjects).value,
                notes="; ".join(subjects[:3]),
                source="Open Library",
            )
        )
    return hits


def lookup_google(query: str, *, isbn_prefix: bool = True) -> list[BookHit]:
    code = normalize_code(query)
    if isbn_prefix and len(code) in {10, 12, 13}:
        q = f"isbn:{code}"
    else:
        q = query.strip() or code
    params = urllib.parse.urlencode({"q": q, "maxResults": 5})
    data = _get(f"https://www.googleapis.com/books/v1/volumes?{params}")
    hits: list[BookHit] = []
    if not isinstance(data, dict):
        return hits
    for item in (data.get("items") or [])[:5]:
        info = item.get("volumeInfo") or {}
        title = (info.get("title") or "").strip()
        if not title:
            continue
        authors = ", ".join(info.get("authors") or [])
        isbn = ""
        upc = code if len(code) >= 8 else ""
        for ident in info.get("industryIdentifiers") or []:
            typ = (ident.get("type") or "").upper()
            val = normalize_code(ident.get("identifier") or "")
            if typ in {"ISBN_13", "ISBN_10"} and val:
                isbn = val
            if typ == "OTHER" and val:
                upc = val
        cats = [str(c) for c in (info.get("categories") or [])]
        hits.append(
            BookHit(
                title=title,
                author=authors,
                isbn=isbn,
                upc=upc or isbn,
                kind=guess_kind(title, cats).value,
                notes=(info.get("description") or "")[:180],
                source="Google Books",
            )
        )
    return hits


def _merge(hits: list[BookHit], extra: list[BookHit]) -> list[BookHit]:
    for hit in extra:
        if not any(h.title.lower() == hit.title.lower() for h in hits):
            hits.append(hit)
    return hits


def lookup(query: str) -> list[BookHit]:
    q = (query or "").strip()
    if not q:
        return []
    hits: list[BookHit] = []
    variants = code_variants(q)
    if variants:
        for code in variants:
            _merge(hits, lookup_open_library_isbn(code))
            if hits:
                return hits[:6]
            _merge(hits, lookup_open_library_search_isbn(code))
            if hits:
                return hits[:6]
        for code in variants:
            _merge(hits, lookup_google(code, isbn_prefix=True))
            if hits:
                return hits[:6]
            _merge(hits, lookup_google(code, isbn_prefix=False))
            if hits:
                return hits[:6]
        return []
    _merge(hits, lookup_open_library(q))
    if len(hits) < 2:
        _merge(hits, lookup_google(q, isbn_prefix=False))
    return hits[:6]


def hits_as_dicts(hits: list[BookHit]) -> list[dict]:
    return [asdict(h) for h in hits]
