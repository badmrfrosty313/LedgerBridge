"""Deterministic extraction adapted from Kyle Hawkins's earlier prototype."""

from .classifier import classify_document
from .parser import ParsedDocument, parse_document

__all__ = ["ParsedDocument", "classify_document", "parse_document"]

