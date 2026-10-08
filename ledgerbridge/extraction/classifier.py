from __future__ import annotations

import re
from typing import Iterable


PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")


def _normalized_text(lines: Iterable[str]) -> str:
    return " ".join(re.sub(r"\s+", " ", str(line)).strip() for line in lines).lower()


def classify_document(lines: Iterable[str]) -> str:
    """Classify a document into the workflow families currently supported."""

    text = _normalized_text(lines)

    if not text.strip():
        return "unknown"

    if "check request" in text:
        return "check_request"

    if "travel voucher" in text or ("voucher" in text and "travel" in text):
        return "travel_voucher"

    line_detail_signals = (
        "usage details",
        "wireless service",
        "monthly charge",
        "plan charges",
        "line details",
    )
    if (
        PHONE_RE.search(text)
        and sum(signal in text for signal in line_detail_signals) >= 2
    ):
        return "telecom_line_detail"

    statement_signals = (
        "service activity",
        "monthly charges",
        "account details",
        "billing date",
        "previous balance",
        "current charges",
    )
    if sum(signal in text for signal in statement_signals) >= 2:
        return "telecom_statement"

    invoice_signals = (
        "invoice total",
        "balance due",
        "amount due",
        "bill to",
        "ship to",
        "subtotal",
        "total due",
    )
    if "invoice" in text and any(signal in text for signal in invoice_signals):
        return "vendor_invoice"

    if "receipt" in text:
        return "receipt"

    return "unknown"

