from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from bs4 import BeautifulSoup


BANNED_WORDS = {
    "viagogo",
    "seatsbrokers",
    "gigsberg",
    "ftn",
    "hello ticket",
    "vivid",
    "stubhub",
    "fanpass",
    "seastnet",
    "ticketnetwork",
    "ticombo",
}

ORDER_ID_PATTERNS = [
    r"order\s*id\s*[:#-]?\s*([a-z0-9-]{5,})",
    r"order\s*#\s*([a-z0-9-]{5,})",
    r"the customer for order\s*#\s*([a-z0-9-]{5,})",
    r"for\s+order\s*#?\s*([a-z0-9-]{5,})",
    r"order\s*-\s*([a-z0-9-]{5,})",
]

ATTENDEE_HEADER_RE = re.compile(r"^(attendee|ticket holder)\s*#?\s*(\d+)\s*:?\s*$", re.IGNORECASE)
DATE_RE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-[a-z]{3}-\d{4}|\d{1,2}\s+[a-z]{3,9}\s+\d{4})$",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

NOISE_PATTERNS = [
    re.compile(r"\b(event|venue|section|row|notes?|price|quantity|requested|privacy policy)\b", re.IGNORECASE),
    re.compile(r"\b(help (centre|center)|my account|copyright|all rights reserved)\b", re.IGNORECASE),
    re.compile(r"\b(please do not reply|do not reply|contains attachment|attachment|survey)\b", re.IGNORECASE),
    re.compile(r"\b(from|to|subject|sent|wrote|reply-to)\b", re.IGNORECASE),
]

ATTENDEE_SIGNAL_PATTERNS = [
    re.compile(r"\battendee\b", re.IGNORECASE),
    re.compile(r"\bticket holder\b", re.IGNORECASE),
    re.compile(r"\bfull name\b", re.IGNORECASE),
    re.compile(r"\bfirst name\b", re.IGNORECASE),
    re.compile(r"\blast name\b", re.IGNORECASE),
    re.compile(r"\bdate of birth\b|\bdob\b", re.IGNORECASE),
    re.compile(r"\bnationality\b", re.IGNORECASE),
    re.compile(r"\bcountry of birth\b", re.IGNORECASE),
    re.compile(r"\bfan id\b", re.IGNORECASE),
    re.compile(r"\be-?mail\b", re.IGNORECASE),
    re.compile(r"\bphone( number)?\b", re.IGNORECASE),
    re.compile(r"\bgender\b", re.IGNORECASE),
    re.compile(r"\bcity of birth\b", re.IGNORECASE),
]

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "full_name": ("full name", "attendee full name", "name", "customer name"),
    "first_name": ("first name",),
    "last_name": ("last name",),
    "date_of_birth": ("date of birth", "dob", "birth date"),
    "nationality": ("nationality", "country of birth"),
    "gender": ("gender",),
    "city_of_birth": ("city of birth",),
    "province_of_birth": ("province of city of birth", "province of birth"),
    "fan_id": ("fan id",),
    "email": ("email", "e-mail", "mail"),
    "phone": ("phone number", "phone"),
}

DISPLAY_LABELS = {
    "full_name": "Full Name",
    "first_name": "First Name",
    "last_name": "Last Name",
    "date_of_birth": "Date Of Birth",
    "nationality": "Nationality",
    "gender": "Gender",
    "city_of_birth": "City Of Birth",
    "province_of_birth": "Province Of City Of Birth",
    "fan_id": "Fan ID",
    "email": "Email",
    "phone": "Phone Number",
}

FIELD_PRIORITY = {
    "full_name": 0,
    "first_name": 1,
    "last_name": 2,
    "date_of_birth": 3,
    "gender": 4,
    "city_of_birth": 5,
    "province_of_birth": 6,
    "nationality": 7,
    "fan_id": 8,
    "email": 9,
    "phone": 10,
}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def html_to_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = soup.get_text("\n")
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def clean_text(text: str) -> str:
    lines = [_normalize_space(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def extract_order_id(text: str) -> str | None:
    for pattern in ORDER_ID_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip().upper()
            # Keep only IDs that include at least one digit.
            if re.search(r"\d", candidate):
                return candidate
    return None


def _line_has_signal(line: str) -> bool:
    return any(pattern.search(line) for pattern in ATTENDEE_SIGNAL_PATTERNS)


def _line_is_date(line: str) -> bool:
    return bool(DATE_RE.match(line.strip()))


def _line_is_noise(line: str) -> bool:
    lower = line.lower().strip()
    if not lower:
        return True
    if "http://" in lower or "https://" in lower or "www." in lower:
        return True
    if any(word in lower for word in BANNED_WORDS):
        return True
    return any(pattern.search(lower) for pattern in NOISE_PATTERNS)


def _sanitize_value(value: str) -> str:
    output = value
    for word in BANNED_WORDS:
        output = re.sub(re.escape(word), "", output, flags=re.IGNORECASE)
    output = re.sub(r"\s{2,}", " ", output).strip(" -–|,")
    return output.strip()


def _canonicalize_label(label: str) -> str | None:
    cleaned = re.sub(r"\([^)]*\)", "", label).lower()
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    cleaned = _normalize_space(cleaned)
    for canonical, aliases in FIELD_ALIASES.items():
        if cleaned in aliases:
            return canonical
    return None


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _is_probable_name(value: str) -> bool:
    if ":" in value or any(char.isdigit() for char in value):
        return False
    words = [word for word in re.split(r"\s+", value.strip()) if word]
    if not 2 <= len(words) <= 5:
        return False
    bad_tokens = {"dear", "kind", "regards", "hello", "team", "thank", "you"}
    if any(word.lower() in bad_tokens for word in words):
        return False
    return bool(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ' -]+", value))


def _is_probable_nationality(value: str) -> bool:
    if ":" in value or any(char.isdigit() for char in value):
        return False
    if len(value.split()) > 8:
        return False
    return bool(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ' -]+", value))


def _dedupe_blocks(blocks: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for block in blocks:
        cleaned_lines = []
        for line in _split_lines(block):
            line = _sanitize_value(line)
            if not line:
                continue
            if _line_is_noise(line) and not _line_has_signal(line):
                continue
            cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _extract_table_blocks(content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    blocks: list[str] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        # Read rows from direct row containers only (thead/tbody/tfoot/table),
        # and direct cells only. This avoids nested table pollution.
        row_parents = table.find_all(["thead", "tbody", "tfoot"], recursive=False)
        if not row_parents:
            row_parents = [table]

        seen_rows = set()
        for parent in row_parents:
            for tr in parent.find_all("tr", recursive=False):
                marker = id(tr)
                if marker in seen_rows:
                    continue
                seen_rows.add(marker)
                cells = [
                    _normalize_space(cell.get_text(" ", strip=True))
                    for cell in tr.find_all(["th", "td"], recursive=False)
                ]
                if any(cells):
                    rows.append(cells)

        if len(rows) < 2:
            continue

        for idx, header_row in enumerate(rows[:-1]):
            canonical_headers = [_canonicalize_label(cell) for cell in header_row]
            if sum(1 for item in canonical_headers if item) < 2:
                continue

            for data_row in rows[idx + 1 :]:
                pairs: list[tuple[str, str]] = []
                for col_idx, value in enumerate(data_row):
                    if col_idx >= len(canonical_headers):
                        break
                    canonical = canonical_headers[col_idx]
                    if not canonical:
                        continue
                    value = _sanitize_value(value)
                    if not value:
                        continue
                    pairs.append((canonical, value))

                if not pairs:
                    continue
                if not any(field in {"full_name", "first_name", "last_name", "date_of_birth", "nationality"} for field, _ in pairs):
                    continue

                ordered_pairs = sorted(pairs, key=lambda item: FIELD_PRIORITY.get(item[0], 999))
                block_lines = [f"{DISPLAY_LABELS[field]}: {value}" for field, value in ordered_pairs]
                blocks.append("\n".join(block_lines))
            break

    return _dedupe_blocks(blocks)


def _extract_labeled_blocks(lines: list[str]) -> list[str]:
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    group_order: list[str] = []
    current_group = "1"

    for line in lines:
        header_match = ATTENDEE_HEADER_RE.match(line)
        if header_match:
            current_group = header_match.group(2)
            if current_group not in group_order:
                group_order.append(current_group)
            continue

        label_match = re.match(
            r"^(?P<label>[A-Za-zÀ-ÖØ-öø-ÿ0-9\s'()/\.-]+?)(?:\s+(?P<index>\d+))?\s*:\s*(?P<value>.+)$",
            line,
        )
        if not label_match:
            continue

        label = _normalize_space(label_match.group("label"))
        value = _sanitize_value(_normalize_space(label_match.group("value")))
        if not value:
            continue

        canonical = _canonicalize_label(label)
        if not canonical:
            continue

        explicit_index = label_match.group("index")
        group_key = explicit_index if explicit_index else current_group
        current_group = group_key
        if group_key not in group_order:
            group_order.append(group_key)
        groups[group_key].append((canonical, value))

    blocks: list[str] = []
    for group_key in group_order:
        fields = groups.get(group_key, [])
        if not fields:
            continue
        fields = sorted(fields, key=lambda item: FIELD_PRIORITY.get(item[0], 999))
        lines_out = [f"{DISPLAY_LABELS[field]}: {value}" for field, value in fields]
        # Require at least one strong attendee field to avoid false positives.
        if not any(
            field in {"full_name", "first_name", "last_name", "date_of_birth", "fan_id", "email"}
            for field, _ in fields
        ):
            continue
        blocks.append("\n".join(lines_out))

    return _dedupe_blocks(blocks)


def _extract_split_label_value_blocks(lines: list[str]) -> list[str]:
    """
    Handle templates where labels and values are split across lines/cells, e.g.:
      Full Name:
      Tim Kosak
    and where attendee headers can be split too:
      Ticket Holder #
      1
    """
    groups: dict[str, list[tuple[str, str]]] = defaultdict(list)
    group_order: list[str] = []
    current_group = "1"
    i = 0

    while i < len(lines):
        line = _normalize_space(lines[i])
        lower = line.lower()

        # Ticket holder header can be "Ticket Holder # 1" or split in two lines.
        holder_match = re.match(r"^ticket holder\s*#?\s*(\d+)?\s*$", lower, re.IGNORECASE)
        if holder_match:
            index = holder_match.group(1)
            if not index and i + 1 < len(lines) and re.fullmatch(r"\d+", _normalize_space(lines[i + 1])):
                index = _normalize_space(lines[i + 1])
                i += 1
            if index:
                current_group = index
                if current_group not in group_order:
                    group_order.append(current_group)
            i += 1
            continue

        # Label with inline value is already handled by _extract_labeled_blocks.
        # Here we specifically parse "Label:" followed by value on the next line.
        label_only = re.match(r"^(?P<label>[A-Za-zÀ-ÖØ-öø-ÿ0-9\s'()/\.-]+?)\s*:\s*$", line)
        if label_only and i + 1 < len(lines):
            label = _normalize_space(label_only.group("label"))
            canonical = _canonicalize_label(label)
            if canonical:
                value = _sanitize_value(_normalize_space(lines[i + 1]))
                if value and not _line_is_noise(value):
                    if current_group not in group_order:
                        group_order.append(current_group)
                    groups[current_group].append((canonical, value))
                    i += 2
                    continue

        i += 1

    blocks: list[str] = []
    for group_key in group_order:
        fields = groups.get(group_key, [])
        if not fields:
            continue
        fields = sorted(fields, key=lambda item: FIELD_PRIORITY.get(item[0], 999))
        if not any(
            field in {"full_name", "first_name", "last_name", "date_of_birth", "fan_id", "email"}
            for field, _ in fields
        ):
            continue
        block_lines = [f"{DISPLAY_LABELS[field]}: {value}" for field, value in fields]
        blocks.append("\n".join(block_lines))

    return _dedupe_blocks(blocks)


def _extract_triplet_blocks(lines: list[str]) -> list[str]:
    blocks = []
    i = 0
    while i <= len(lines) - 3:
        a, b, c = lines[i], lines[i + 1], lines[i + 2]
        if (
            _is_probable_name(a)
            and _line_is_date(b)
            and _is_probable_nationality(c)
            and not _line_is_noise(a)
            and not _line_is_noise(c)
        ):
            block = f"Full Name: {a}\nDate Of Birth: {b}\nNationality: {c}"
            blocks.append(block)
            i += 3
            continue
        i += 1
    return _dedupe_blocks(blocks)


def _extract_candidate_zone(lines: list[str]) -> list[str]:
    if not lines:
        return []

    scored_indices = []
    for idx, line in enumerate(lines):
        score = 0
        if _line_has_signal(line):
            score += 3
        if ATTENDEE_HEADER_RE.match(line):
            score += 3
        if _line_is_date(line):
            score += 1
        if _is_probable_name(line):
            score += 1
        if _line_is_noise(line):
            score -= 3
        if score >= 2:
            scored_indices.append(idx)

    if scored_indices:
        start = max(0, min(scored_indices) - 5)
        end = min(len(lines), max(scored_indices) + 30)
        return lines[start:end]

    # Fallback for compact templates with no explicit labels (e.g. name/date/nationality sequences).
    anchor_patterns = [
        re.compile(r"provided the following details", re.IGNORECASE),
        re.compile(r"please note", re.IGNORECASE),
        re.compile(r"details for .* attendees?", re.IGNORECASE),
    ]
    for idx, line in enumerate(lines):
        if any(pattern.search(line) for pattern in anchor_patterns):
            return lines[idx : min(len(lines), idx + 35)]

    return lines


def extract_attendee_blocks(content: str) -> list[str]:
    text = clean_text(html_to_text(content))
    lines = _split_lines(text)
    zone = _extract_candidate_zone(lines)

    blocks = []
    blocks.extend(_extract_table_blocks(content))
    blocks.extend(_extract_labeled_blocks(zone))
    blocks.extend(_extract_split_label_value_blocks(zone))

    if not blocks:
        blocks.extend(_extract_triplet_blocks(zone))

    return _dedupe_blocks(blocks)


def should_skip_email(content: str) -> bool:
    """
    First-pass filter:
    - True => skip email (no attendee data found)
    - False => process/display extracted attendee blocks
    """
    blocks = extract_attendee_blocks(content)
    return len(blocks) == 0


def parse_email_content(content: str) -> dict:
    text = clean_text(html_to_text(content))
    attendee_blocks = extract_attendee_blocks(content)
    order_id = extract_order_id(text)
    return {
        "order_id": order_id,
        "attendee_blocks": attendee_blocks,
        "attendee_raw_text": "\n\n".join(attendee_blocks),
        "should_skip": len(attendee_blocks) == 0,
    }
