from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable

from .classifier import classify_document

MONEY_RE = re.compile(
    r"""(?<![\d.])
        (?P<open>\()?\s*
        (?P<sign1>-)?\s*
        (?:USD\s*)?\$?\s*
        (?P<sign2>-)?\s*
        (?P<dollars>[0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)
        \s*\.\s*
        (?P<cents>[0-9]{2})
        \s*(?P<close>\))?
        (?!\d)(?!\s*%)
    """,
    re.IGNORECASE | re.VERBOSE,
)

DOCUMENT_PATTERNS = [
    re.compile(
        r"\b(?:invoice|inv|receipt|order|transaction)\s*(?:#|no\.?|number|num|id)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{1,})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:invoice|receipt|order|transaction)\s+id\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{1,})\b",
        re.IGNORECASE,
    ),
]

DOCUMENT_LABEL_ONLY_RE = re.compile(
    r"^\s*(?:invoice|inv|receipt|order|transaction)\s*(?:#|no\.?|number|num|id)?\s*[:#-]?\s*$",
    re.IGNORECASE,
)

DATE_PATTERNS = [
    re.compile(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.]([0-2]?\d|3[01])\b"),
    re.compile(r"\b(0?[1-9]|1[0-2])[/.-]([0-2]?\d|3[01])[/.-](20\d{2}|\d{2})\b"),
]

MONTH_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+([0-2]?\d|3[01])"
    r"(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b",
    re.IGNORECASE,
)

IGNORE_VENDOR_TERMS = {
    "invoice",
    "receipt",
    "thank you",
    "customer copy",
    "merchant copy",
    "order",
    "transaction",
    "bill to",
    "ship to",
    "sold to",
    "remit to",
    "statement",
    "account number",
    "account #",
    "date",
    "subtotal",
    "tax",
    "total",
    "amount due",
    "balance due",
}

STREET_RE = re.compile(
    r"\b\d{1,6}\s+.+\b(?:st(?:reet)?|rd|road|ave(?:nue)?|blvd|boulevard|dr(?:ive)?|ln|lane|ct|court|"
    r"way|pkwy|parkway|hwy|highway|cir|circle|pl|place)\b",
    re.IGNORECASE,
)

PAGE_MARKER_RE = re.compile(r"^-{0,3}\s*page\s+\d+(?:\s+of\s+\d+)?\s*-{0,3}$", re.IGNORECASE)

INVALID_DOCUMENT_TOKENS = {
    "date",
    "number",
    "num",
    "no",
    "id",
    "total",
    "amount",
    "due",
    "page",
}


@dataclass
class ParsedDocument:
    document_type: str = "unknown"
    vendor: str | None = None
    document_number: str | None = None
    date: str | None = None
    subtotal_cents: int | None = None
    tax_cents: int | None = None
    total_cents: int | None = None
    ocr_confidence: float | None = None
    raw_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def clean_lines(lines: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for raw in lines:
        line = re.sub(r"\s+", " ", str(raw)).strip(" \t|_")
        if line:
            cleaned.append(line)
    return cleaned


def _money_matches(line: str) -> list[tuple[int, int, int]]:
    matches: list[tuple[int, int, int]] = []
    for match in MONEY_RE.finditer(line):
        dollars = int(match.group("dollars").replace(",", ""))
        cents = int(match.group("cents"))
        value = dollars * 100 + cents
        negative = bool(match.group("sign1") or match.group("sign2"))
        parenthesized = bool(match.group("open") and match.group("close"))
        if negative or parenthesized:
            value = -value
        matches.append((value, match.start(), match.end()))
    return matches


def parse_money(line: str) -> list[int]:
    return [value for value, _, _ in _money_matches(line)]


def _label_spans(text: str, label: str) -> list[tuple[int, int]]:
    pattern = re.compile(rf"(?<!\w){re.escape(label)}(?!\w)", re.IGNORECASE)
    return [match.span() for match in pattern.finditer(text)]


def _contains_label(text: str, label: str) -> bool:
    return bool(_label_spans(text, label))


def find_labeled_amount(
    lines: list[str],
    labels: tuple[str, ...],
    excludes: tuple[str, ...] = (),
) -> int | None:
    candidates: list[int] = []

    for index, line in enumerate(lines):
        lower = line.lower()
        if any(_contains_label(lower, ex) for ex in excludes):
            continue

        money = _money_matches(line)
        for label in labels:
            spans = _label_spans(lower, label)
            for _, label_end in spans:
                after = [item for item in money if item[1] >= label_end]
                if after:
                    candidates.append(after[0][0])
                    break

                # OCR/layout extraction sometimes places a label and its value
                # on consecutive lines rather than one logical line.
                if index + 1 < len(lines):
                    next_money = _money_matches(lines[index + 1])
                    if next_money:
                        candidates.append(next_money[0][0])
                        break

    return candidates[-1] if candidates else None


def find_total(lines: list[str]) -> int | None:
    priority_groups = [
        (("grand total", "invoice total"), ("tax total", "total tax", "total savings")),
        (("total amount", "total due"), ("tax total", "total tax", "total savings")),
        (("amount due", "balance due"), ("past due",)),
        (("total",), ("tax total", "total tax", "total savings")),
        (("amount paid",), ("change",)),
    ]
    for labels, excludes in priority_groups:
        amount = find_labeled_amount(lines, labels, excludes)
        if amount is not None:
            return amount

    standalone: list[int] = []
    all_amounts: list[int] = []
    for line in lines:
        amounts = parse_money(line)
        all_amounts.extend(amounts)
        stripped = re.sub(r"^(?:USD\s*)?\$?\s*", "", line, flags=re.IGNORECASE).strip()
        if len(amounts) == 1 and re.fullmatch(
            r"-?[0-9]{1,3}(?:,[0-9]{3})*\s*\.\s*[0-9]{2}",
            stripped,
        ):
            standalone.append(amounts[0])

    if len(all_amounts) == 1:
        return all_amounts[0]

    if standalone:
        candidate = standalone[-1]
        preceding: list[int] = []
        for line in lines:
            line_amounts = parse_money(line)
            stripped = re.sub(r"^(?:USD\s*)?\$?\s*", "", line, flags=re.IGNORECASE).strip()
            is_standalone = (
                len(line_amounts) == 1
                and re.fullmatch(
                    r"-?[0-9]{1,3}(?:,[0-9]{3})*\s*\.\s*[0-9]{2}",
                    stripped,
                )
            )
            if is_standalone and line_amounts[0] == candidate:
                break
            preceding.extend(line_amounts)

        if preceding and abs(sum(preceding) - candidate) <= 2:
            return candidate

    return None


def find_document_number(lines: list[str]) -> str | None:
    for index, line in enumerate(lines[:35]):
        # Handle pure field-label lines first. Otherwise a permissive inline
        # regex can backtrack through "Invoice Number" and hallucinate "ber".
        if DOCUMENT_LABEL_ONLY_RE.fullmatch(line) and index + 1 < len(lines):
            candidate = lines[index + 1].strip(" .:-")
            if re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{1,}", candidate, re.IGNORECASE):
                if (
                    candidate.lower() not in INVALID_DOCUMENT_TOKENS
                    and not re.fullmatch(r"20\d{2}", candidate)
                ):
                    return candidate
            continue

        for pattern in DOCUMENT_PATTERNS:
            match = pattern.search(line)
            if match:
                candidate = match.group(1).strip(" .:-")
                if (
                    candidate
                    and candidate.lower() not in INVALID_DOCUMENT_TOKENS
                    and not re.fullmatch(r"20\d{2}", candidate)
                ):
                    return candidate
    return None


def _normalize_numeric_date(month: str, day: str, year: str) -> str | None:
    if len(year) == 2:
        year = "20" + year
    try:
        return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extract_date(line: str) -> str | None:
    match = DATE_PATTERNS[0].search(line)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass

    match = DATE_PATTERNS[1].search(line)
    if match:
        normalized = _normalize_numeric_date(match.group(1), match.group(2), match.group(3))
        if normalized:
            return normalized

    match = MONTH_RE.search(line)
    if match:
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                parsed = datetime.strptime(
                    f"{match.group(1)} {match.group(2)} {match.group(3)}",
                    fmt,
                )
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def find_date(lines: list[str]) -> str | None:
    preferred_labels = (
        "invoice date",
        "transaction date",
        "purchase date",
        "receipt date",
        "order date",
        "sale date",
    )
    rejected_labels = (
        "due date",
        "payment due",
        "ship date",
        "delivery date",
        "service date",
    )

    for index, line in enumerate(lines[:40]):
        lower = line.lower()
        if any(label in lower for label in preferred_labels):
            found = _extract_date(line)
            if found:
                return found
            if index + 1 < len(lines):
                found = _extract_date(lines[index + 1])
                if found:
                    return found

    for line in lines[:40]:
        lower = line.lower()
        if any(label in lower for label in rejected_labels):
            continue
        found = _extract_date(line)
        if found:
            return found
    return None


def looks_like_vendor(line: str) -> bool:
    lower = line.lower()
    if len(line) < 3 or len(line) > 80:
        return False
    if PAGE_MARKER_RE.fullmatch(line):
        return False
    if any(term in lower for term in IGNORE_VENDOR_TERMS):
        return False
    if re.fullmatch(r"[\d\W_]+", line):
        return False
    if re.search(r"(?:tel|phone|fax)\s*[:#]?", lower):
        return False
    if re.search(r"(?:www\.|https?://|\S+@\S+)", lower):
        return False
    if re.search(r"\b\d{5}(?:-\d{4})?\b", line):
        return False
    if STREET_RE.search(line):
        return False
    if _extract_date(line):
        return False
    if parse_money(line):
        return False
    return True


def _vendor_score(line: str, position: int) -> float:
    score = max(0.0, 12.0 - position)
    alpha = [ch for ch in line if ch.isalpha()]
    if alpha and sum(ch.isupper() for ch in alpha) / len(alpha) > 0.75:
        score += 3.0
    if re.search(
        r"\b(?:llc|inc\.?|corp\.?|company|co\.?|services|supply|store|market|restaurant)\b",
        line,
        re.IGNORECASE,
    ):
        score += 2.0
    if len(line.split()) == 1:
        score += 0.5
    return score


def find_vendor(lines: list[str]) -> str | None:
    candidates: list[tuple[float, str]] = []
    for position, line in enumerate(lines[:15]):
        if looks_like_vendor(line):
            candidates.append((_vendor_score(line, position), line))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def parse_document(lines: Iterable[str], confidences: Iterable[float] | None = None) -> ParsedDocument:
    cleaned = clean_lines(lines)
    confidence_list = [
        float(value)
        for value in (confidences or [])
        if isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0
    ]
    avg_conf = round(sum(confidence_list) / len(confidence_list), 4) if confidence_list else None

    parsed = ParsedDocument(
        document_type=classify_document(cleaned),
        vendor=find_vendor(cleaned),
        document_number=find_document_number(cleaned),
        date=find_date(cleaned),
        subtotal_cents=find_labeled_amount(cleaned, ("subtotal", "sub total")),
        tax_cents=find_labeled_amount(
            cleaned,
            ("sales tax", "tax"),
            excludes=("tax id", "tax #", "tax no", "tax number"),
        ),
        total_cents=find_total(cleaned),
        ocr_confidence=avg_conf,
        raw_lines=cleaned,
    )

    if parsed.vendor is None:
        parsed.warnings.append("Could not confidently identify vendor/merchant.")
    if parsed.date is None:
        parsed.warnings.append("Could not confidently identify transaction/invoice date.")
    if parsed.total_cents is None:
        parsed.warnings.append("Could not confidently identify total amount.")
    if (
        parsed.subtotal_cents is not None
        and parsed.tax_cents is not None
        and parsed.total_cents is not None
    ):
        if abs((parsed.subtotal_cents + parsed.tax_cents) - parsed.total_cents) > 2:
            parsed.warnings.append(
                "Subtotal + tax does not reconcile to total; discounts/fees/tips may exist."
            )
    if avg_conf is not None and avg_conf < 0.80:
        parsed.warnings.append(
            f"OCR confidence is low ({avg_conf:.0%}). Review raw text carefully."
        )

    return parsed

