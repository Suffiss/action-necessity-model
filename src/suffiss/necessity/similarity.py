"""Local, dependency-free similarity between texts and actions.

``SimilarityProvider`` is the extension point: an embedding-backed provider can
replace ``LexicalSimilarity`` later without touching the rules or scoring code.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Mapping, Protocol

from suffiss.necessity.models import Action

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Argument keys that do not change what an action observes or does.
VOLATILE_KEYS = frozenset({"timeout", "request_id", "trace_id", "timestamp", "nonce", "retry", "attempt"})


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens; splits snake_case, paths and dotted names."""
    return _TOKEN_RE.findall(text.lower())


def normalize_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/").lower() or "."


def _normalize_value(key: str, value: Any) -> Any:
    if isinstance(value, str):
        # Only case and whitespace are cosmetic. Word order and punctuation can
        # carry meaning (e.g. SQL operators), so they are kept.
        if "path" in key or "file" in key:
            return normalize_path(value)
        return normalize_text(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, default=str)
    return value


def normalize_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key.lower(): _normalize_value(key.lower(), value)
        for key, value in arguments.items()
        if key.lower() not in VOLATILE_KEYS
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


class SimilarityProvider(Protocol):
    """Interface for comparing texts and actions. Scores lie in [0, 1]."""

    def text_similarity(self, left: str, right: str) -> float: ...

    def action_similarity(self, left: Action, right: Action) -> float: ...


class LexicalSimilarity:
    """Similarity from normalized strings, token overlap and SequenceMatcher."""

    def text_similarity(self, left: str, right: str) -> float:
        a, b = normalize_text(left), normalize_text(right)
        if not a or not b:
            return 0.0
        token_score = jaccard(set(tokenize(a)), set(tokenize(b)))
        return max(token_score, SequenceMatcher(None, a, b).ratio())

    def action_similarity(self, left: Action, right: Action) -> float:
        if _tool_key(left) != _tool_key(right):
            return 0.0
        left_args = normalize_arguments(left.arguments)
        right_args = normalize_arguments(right.arguments)
        if not left_args and not right_args:
            # Without arguments the description is the only thing distinguishing them.
            return self.text_similarity(left.description, right.description)
        keys = set(left_args) | set(right_args)
        # Argument values are compared exactly: "src/a.py" vs "src/b.py" are
        # different targets even though their strings are nearly identical.
        matching = sum(1 for key in keys if left_args.get(key) == right_args.get(key))
        return matching / len(keys)


def _tool_key(action: Action) -> str:
    return normalize_text(action.tool or action.type)
