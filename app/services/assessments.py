"""Build, normalize, and grade parent-made tests.

One JSON contract (PROMPT_SPEC) is shared by the in-app model calls AND the
portable prompt parents paste into GPT or Perplexity, so the two never drift.
Only objective question types live here, and every one auto-grades with no
extra tokens: multiple choice, true/false, matching, and fill-in-the-blank.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.models import Assessment, AssessmentQuestion, TeacherApiKey
from app.services import ai_costs, gemma
from app.services.secrets import decrypt_secret

QUESTION_TYPES = ("mc", "tf", "match", "fill")

# The canonical contract. Shown to parents verbatim and sent to the models.
PROMPT_SPEC = """You write tests for a homeschool. Return ONLY one JSON object,
no prose, no code fences. Shape:

{
  "title": "short test name",
  "questions": [ ...question objects... ]
}

Every question object has:
  "type": one of "mc" | "tf" | "match" | "fill"
  "prompt": the question text the student reads
  "points": a positive number (default 1)
  "explanation": optional short reason for the answer (may be "")

Type-specific fields:

1) Multiple choice  -> "type": "mc"
   "options": a list of 2 to 6 answer choices (strings)
   "correct": a list of the index numbers (0-based) of the correct option(s)
   "multiple": true if more than one option is correct, else false
   Example:
   {"type":"mc","prompt":"What is 2 + 3?","points":1,
    "options":["4","5","6"],"correct":[1],"multiple":false}

2) True / False  -> "type": "tf"
   "answer": true or false
   Example:
   {"type":"tf","prompt":"The sun is a star.","points":1,"answer":true}

3) Matching  -> "type": "match"
   "left": a list of 10 to 20 terms (strings)
   "right": a list of 10 to 20 definitions (strings); may hold a few extra
            definitions that match nothing, to make it harder
   "pairs": a list of [leftIndex, rightIndex] number pairs giving the answer
   The student answers by choosing, for each numbered term, the letter of its
   definition. Example (shortened):
   {"type":"match","prompt":"Match each word to its meaning.","points":5,
    "left":["cat","dog"],"right":["barks","meows","swims"],
    "pairs":[[0,1],[1,0]]}

4) Fill in the blank  -> "type": "fill"
   Use ____ in the prompt to show the blank.
   "accepted": a list of answers counted as correct (strings)
   "case_sensitive": true or false (usually false)
   Example:
   {"type":"fill","prompt":"The capital of France is ____.","points":1,
    "accepted":["Paris"],"case_sensitive":false}

Rules:
- Base every question only on the material you are given. Do not invent facts.
- Keep prompts clear for the grade level requested.
- Return valid JSON only."""


@dataclass
class GenResult:
    questions: list[dict]
    title: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    usd: float
    error: str = ""


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}
    # drop code fences if a model added them
    text = re.sub(r"^```(?:json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        # maybe it returned a bare list
        arr = re.search(r"\[.*\]", text, re.S)
        if arr:
            try:
                return {"questions": json.loads(arr.group(0))}
            except json.JSONDecodeError:
                return {}
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, list):
        return {"questions": data}
    return data if isinstance(data, dict) else {}


async def _openai_chat(key: str, model: str, system: str, user_text: str) -> tuple[str, dict]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(resp.text[:240] or "OpenAI error")
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, {
        "prompt_tokens": usage.get("prompt_tokens") or 0,
        "completion_tokens": usage.get("completion_tokens") or 0,
    }


async def _anthropic_chat(key: str, model: str, system: str, user_text: str) -> tuple[str, dict]:
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": user_text}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(resp.text[:240] or "Anthropic error")
    data = resp.json()
    parts = data.get("content") or []
    text = ""
    if parts and isinstance(parts[0], dict):
        text = parts[0].get("text") or ""
    usage = data.get("usage") or {}
    return text, {
        "prompt_tokens": usage.get("input_tokens") or 0,
        "completion_tokens": usage.get("output_tokens") or 0,
    }


async def _call_model(provider: str, key_row: TeacherApiKey | None, user_text: str) -> GenResult:
    model = ai_costs.model_for(provider)
    try:
        if provider == "gemma":
            text = await gemma.complete(
                [
                    {"role": "system", "content": PROMPT_SPEC},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.3,
            )
            usage: dict = {}
        else:
            if not key_row:
                return GenResult([], "", provider, model, 0, 0, 0.0, "Pick a saved key first.")
            secret = decrypt_secret(key_row.secret_enc)
            if not secret:
                return GenResult([], "", provider, model, 0, 0, 0.0, "That key could not be read.")
            if provider == "openai":
                text, usage = await _openai_chat(secret, model, PROMPT_SPEC, user_text)
            elif provider == "anthropic":
                text, usage = await _anthropic_chat(secret, model, PROMPT_SPEC, user_text)
            else:
                return GenResult([], "", provider, model, 0, 0, 0.0, "Unknown model.")
    except gemma.GemmaError as exc:
        return GenResult([], "", provider, model, 0, 0, 0.0, exc.message)
    except Exception as exc:  # noqa: BLE001 - surface a friendly message
        return GenResult([], "", provider, model, 0, 0, 0.0, str(exc)[:240])

    data = _extract_json(text)
    raw_questions = data.get("questions") if isinstance(data, dict) else None
    questions = parse_questions(raw_questions if raw_questions is not None else data)
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    usd = ai_costs.charge_usd(model, prompt_tokens, completion_tokens)
    title = str((data.get("title") if isinstance(data, dict) else "") or "").strip()
    error = "" if questions else "The model did not return any usable questions. Try again or a different model."
    return GenResult(questions, title, provider, model, prompt_tokens, completion_tokens, usd, error)


def _generation_request(content: str, opts: dict) -> str:
    count = int(opts.get("count") or 10)
    difficulty = str(opts.get("difficulty") or "medium").strip() or "medium"
    grade = str(opts.get("grade_level") or "").strip()
    types = [t for t in (opts.get("types") or []) if t in QUESTION_TYPES] or ["mc", "tf"]
    lines = [
        f"Make {count} questions at a {difficulty} difficulty.",
        f"Use only these question types: {', '.join(types)}.",
    ]
    if grade:
        lines.append(f"Aim the reading level at grade {grade}.")
    lines.append("Material to build the test from is below:")
    lines.append("")
    lines.append(content.strip() or "(no material provided)")
    return "\n".join(lines)


async def generate(provider: str, key_row: TeacherApiKey | None, content: str, opts: dict) -> GenResult:
    return await _call_model(provider, key_row, _generation_request(content, opts))


async def refine(
    provider: str,
    key_row: TeacherApiKey | None,
    questions: list[dict],
    instruction: str,
    source_text: str = "",
) -> GenResult:
    current = json.dumps({"questions": questions}, ensure_ascii=False)
    parts = [
        "Here is the current test as JSON:",
        current,
        "",
        f"Change request from the teacher: {instruction.strip() or 'improve the test'}",
        "",
        "Return the FULL updated test as JSON in the same shape. Keep good "
        "questions, apply the change, and do not drop the answer keys.",
    ]
    if source_text.strip():
        parts += ["", "Original source material (for reference):", source_text.strip()[:6000]]
    return await _call_model(provider, key_row, "\n".join(parts))


# ---------------------------------------------------------------------------
# Normalize model / imported JSON into our stored shape
# ---------------------------------------------------------------------------

def _clean_str(value) -> str:
    return str(value if value is not None else "").strip()


def _as_list(value) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _norm_mc(q: dict) -> dict | None:
    options_raw = _as_list(q.get("options"))
    options = [{"id": f"o{i + 1}", "text": _clean_str(o)} for i, o in enumerate(options_raw) if _clean_str(o)]
    if len(options) < 2:
        return None
    options = options[:6]
    valid_ids = {o["id"] for o in options}
    correct: list[str] = []
    for c in _as_list(q.get("correct")):
        if isinstance(c, bool):
            continue
        if isinstance(c, (int, float)):
            idx = int(c)
            if 0 <= idx < len(options):
                correct.append(options[idx]["id"])
        else:
            token = _clean_str(c)
            if token in valid_ids:
                correct.append(token)
            else:
                # allow letter answers like "B" or matching option text
                letter = token.upper()
                if len(letter) == 1 and "A" <= letter <= "Z":
                    idx = ord(letter) - ord("A")
                    if 0 <= idx < len(options):
                        correct.append(options[idx]["id"])
                else:
                    for o in options:
                        if o["text"].lower() == token.lower():
                            correct.append(o["id"])
                            break
    correct = list(dict.fromkeys(correct))
    if not correct:
        correct = [options[0]["id"]]
    multiple = bool(q.get("multiple")) or len(correct) > 1
    return {"options": options, "correct": correct, "multiple": multiple}


def _norm_tf(q: dict) -> dict:
    answer = q.get("answer")
    if isinstance(answer, str):
        answer = answer.strip().lower() in {"true", "t", "yes", "1"}
    return {"answer": bool(answer)}


def _norm_match(q: dict) -> dict | None:
    left_raw = _as_list(q.get("left"))
    right_raw = _as_list(q.get("right"))
    left = [{"id": f"l{i + 1}", "text": _clean_str(v)} for i, v in enumerate(left_raw) if _clean_str(v)]
    right = [{"id": f"r{i + 1}", "text": _clean_str(v)} for i, v in enumerate(right_raw) if _clean_str(v)]
    if len(left) < 2 or len(right) < 2:
        return None
    pairs: dict[str, str] = {}
    for pair in _as_list(q.get("pairs")):
        li = ri = None
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            li, ri = pair[0], pair[1]
        elif isinstance(pair, dict):
            li = pair.get("left")
            ri = pair.get("right")
        if isinstance(li, (int, float)) and isinstance(ri, (int, float)):
            li, ri = int(li), int(ri)
            if 0 <= li < len(left) and 0 <= ri < len(right):
                pairs[left[li]["id"]] = right[ri]["id"]
    if not pairs:
        return None
    return {"left": left, "right": right, "pairs": pairs}


def _norm_fill(q: dict) -> dict | None:
    accepted_raw = q.get("accepted")
    if isinstance(accepted_raw, str):
        accepted_raw = [accepted_raw]
    accepted = [_clean_str(a) for a in _as_list(accepted_raw) if _clean_str(a)]
    if not accepted:
        single = _clean_str(q.get("answer"))
        if single:
            accepted = [single]
    if not accepted:
        return None
    return {"accepted": accepted, "case_sensitive": bool(q.get("case_sensitive"))}


def parse_questions(raw) -> list[dict]:
    """Turn model/imported JSON into normalized question dicts we can store."""
    items = raw if isinstance(raw, list) else (raw.get("questions") if isinstance(raw, dict) else None)
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        qtype = _clean_str(item.get("type")).lower()
        prompt = _clean_str(item.get("prompt")) or _clean_str(item.get("question"))
        if qtype not in QUESTION_TYPES:
            continue
        try:
            points = float(item.get("points") or 1)
        except (TypeError, ValueError):
            points = 1.0
        if points <= 0:
            points = 1.0
        if qtype == "mc":
            data = _norm_mc(item)
        elif qtype == "tf":
            data = _norm_tf(item)
        elif qtype == "match":
            data = _norm_match(item)
        else:
            data = _norm_fill(item)
        if data is None:
            continue
        if not prompt:
            prompt = {
                "mc": "Choose the best answer.",
                "tf": "True or false?",
                "match": "Match each term to its definition.",
                "fill": "Fill in the blank.",
            }[qtype]
        out.append(
            {
                "type": qtype,
                "prompt": prompt,
                "points": round(points, 3),
                "data": data,
                "explanation": _clean_str(item.get("explanation")),
            }
        )
    return out


def store_questions(db, assessment: Assessment, questions: list[dict]) -> None:
    """Replace an assessment's questions with a fresh normalized set."""
    for existing in list(assessment.questions):
        db.delete(existing)
    db.flush()
    total = 0.0
    for i, q in enumerate(questions):
        db.add(
            AssessmentQuestion(
                assessment_id=assessment.id,
                sort_order=i,
                type=q["type"],
                prompt=q["prompt"],
                points=q["points"],
                data_json=json.dumps(q["data"]),
                explanation=q.get("explanation", ""),
            )
        )
        total += float(q["points"])
    assessment.points_possible = round(total, 3)
    db.flush()


# ---------------------------------------------------------------------------
# Serialize for the web (teacher gets the key, student never does)
# ---------------------------------------------------------------------------

def question_public(q: AssessmentQuestion) -> dict:
    """What the student taking the test may see - no answers."""
    data = _load(q.data_json)
    payload = {"id": q.id, "type": q.type, "prompt": q.prompt, "points": q.points}
    if q.type == "mc":
        payload["options"] = data.get("options", [])
        payload["multiple"] = bool(data.get("multiple"))
    elif q.type == "match":
        payload["left"] = data.get("left", [])
        payload["right"] = data.get("right", [])
    elif q.type == "fill":
        payload["blank"] = True
    return payload


def question_full(q: AssessmentQuestion) -> dict:
    """What the parent building/reviewing the test sees - answers included."""
    payload = question_public(q)
    data = _load(q.data_json)
    payload["explanation"] = q.explanation or ""
    if q.type == "mc":
        payload["correct"] = data.get("correct", [])
    elif q.type == "tf":
        payload["answer"] = bool(data.get("answer"))
    elif q.type == "match":
        payload["pairs"] = data.get("pairs", {})
    elif q.type == "fill":
        payload["accepted"] = data.get("accepted", [])
        payload["case_sensitive"] = bool(data.get("case_sensitive"))
    return payload


def question_editable(q: AssessmentQuestion) -> dict:
    """Flat shape the refine box and portable prompt round-trip through."""
    data = _load(q.data_json)
    payload: dict = {"type": q.type, "prompt": q.prompt, "points": q.points, "explanation": q.explanation or ""}
    if q.type == "mc":
        options = data.get("options", [])
        payload["options"] = [o["text"] for o in options]
        id_to_index = {o["id"]: i for i, o in enumerate(options)}
        payload["correct"] = [id_to_index[c] for c in data.get("correct", []) if c in id_to_index]
        payload["multiple"] = bool(data.get("multiple"))
    elif q.type == "tf":
        payload["answer"] = bool(data.get("answer"))
    elif q.type == "match":
        left = data.get("left", [])
        right = data.get("right", [])
        payload["left"] = [v["text"] for v in left]
        payload["right"] = [v["text"] for v in right]
        lidx = {v["id"]: i for i, v in enumerate(left)}
        ridx = {v["id"]: i for i, v in enumerate(right)}
        payload["pairs"] = [[lidx[l], ridx[r]] for l, r in data.get("pairs", {}).items() if l in lidx and r in ridx]
    elif q.type == "fill":
        payload["accepted"] = data.get("accepted", [])
        payload["case_sensitive"] = bool(data.get("case_sensitive"))
    return payload


# ---------------------------------------------------------------------------
# Grading (objective, zero tokens)
# ---------------------------------------------------------------------------

def _load(blob: str) -> dict:
    try:
        value = json.loads(blob or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def grade_fraction(q: AssessmentQuestion, response: dict) -> float:
    """Return how right an answer is, from 0.0 to 1.0."""
    data = _load(q.data_json)
    response = response if isinstance(response, dict) else {}
    if q.type == "mc":
        chosen = response.get("selected")
        if isinstance(chosen, str):
            chosen = [chosen]
        chosen_set = {str(c) for c in _as_list(chosen)}
        correct_set = {str(c) for c in data.get("correct", [])}
        return 1.0 if chosen_set and chosen_set == correct_set else 0.0
    if q.type == "tf":
        return 1.0 if bool(response.get("answer")) == bool(data.get("answer")) else 0.0
    if q.type == "match":
        pairs = data.get("pairs", {})
        if not pairs:
            return 0.0
        given = response.get("pairs")
        given = given if isinstance(given, dict) else {}
        correct = sum(1 for left_id, right_id in pairs.items() if str(given.get(left_id)) == str(right_id))
        return round(correct / len(pairs), 4)
    if q.type == "fill":
        text = _clean_str(response.get("text"))
        accepted = data.get("accepted", [])
        if bool(data.get("case_sensitive")):
            return 1.0 if any(text == _clean_str(a) for a in accepted) else 0.0
        low = text.lower()
        return 1.0 if any(low == _clean_str(a).lower() for a in accepted) else 0.0
    return 0.0
