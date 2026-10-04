"""Deterministic building blocks: action kinds, result status, and text features.

Everything here is a pure function of its inputs so each rule can be tested and
reasoned about in isolation. Feature extraction over a whole context lives in
``features.py``; turning features into a score lives in ``scoring.py``.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Iterable

from suffiss.necessity import lexicon
from suffiss.necessity.models import Action
from suffiss.necessity.similarity import normalize_path, tokenize


class ActionKind(StrEnum):
    READ = "read"
    SEARCH = "search"
    REQUEST = "request"
    EXECUTE = "execute"
    WRITE = "write"
    FINISH = "finish"
    OTHER = "other"


class ResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TRANSIENT_FAILURE = "transient_failure"
    PENDING = "pending"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------- text

def stem(token: str) -> str:
    """Very light suffix stripping so 'logs'/'log' and 'crashed'/'crash' match."""
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and not token.endswith("ss") and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            break
    if token.endswith("e") and len(token) > 3:
        token = token[:-1]
    return token


_STEMMED_STOPWORDS = frozenset(stem(word) for word in lexicon.STOPWORDS)
_STEMMED_CONCEPTS = {name: frozenset(stem(w) for w in words) for name, words in lexicon.CONCEPTS.items()}


def content_stems(text: str) -> set[str]:
    """Informative word stems: no stopwords, no single characters."""
    stems = {stem(token) for token in tokenize(text) if len(token) > 1 and token not in lexicon.STOPWORDS}
    return stems - _STEMMED_STOPWORDS


def concepts_of(stems: Iterable[str]) -> set[str]:
    stems = set(stems)
    return {name for name, words in _STEMMED_CONCEPTS.items() if stems & words}


def overlap_coefficient(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def action_text(action: Action) -> str:
    values = " ".join(_flatten(action.arguments.values()))
    return f"{action.type} {action.tool} {action.description} {values}"


def _flatten(values: Iterable[Any]) -> list[str]:
    flat: list[str] = []
    for value in values:
        if isinstance(value, dict):
            flat.extend(_flatten(value.values()))
        elif isinstance(value, (list, tuple)):
            flat.extend(_flatten(value))
        elif value is not None:
            flat.append(str(value))
    return flat


def sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.!?;\n]+", text) if part.strip()]


# ------------------------------------------------------------ action kinds

_TARGET_KEYS = ("path", "file", "file_path", "filepath", "filename", "url", "uri", "target", "table")
_WRITE_METHODS = frozenset({"post", "put", "patch", "delete"})
_SQL_WRITE = re.compile(r"^\s*(insert|update|delete|drop|alter|create|truncate)\b", re.IGNORECASE)


def classify_action(action: Action) -> ActionKind:
    """Kind from the action's type/tool words, falling back to its description."""
    for words in (tokenize(f"{action.type} {action.tool}"), tokenize(action.description)[:1]):
        for kind_name, keywords in lexicon.KIND_KEYWORDS.items():
            if set(words) & keywords:
                return ActionKind(kind_name)
    return ActionKind.OTHER


def is_mutating(action: Action, kind: ActionKind | None = None) -> bool:
    """Whether executing the action can change the state other actions observe."""
    kind = kind or classify_action(action)
    if kind is ActionKind.WRITE:
        return True
    args = {key.lower(): value for key, value in action.arguments.items()}
    if str(args.get("method", "")).lower() in _WRITE_METHODS:
        return True
    for key in ("sql", "query", "statement"):
        if isinstance(args.get(key), str) and _SQL_WRITE.match(args[key]):
            return True
    if kind is ActionKind.EXECUTE:
        command = str(args.get("command", args.get("cmd", "")))
        return bool(set(tokenize(command)) & lexicon.MUTATING_COMMAND_WORDS)
    return False


def is_test_run(action: Action) -> bool:
    text = f"{action.description} {' '.join(_flatten(action.arguments.values()))}"
    return bool(set(tokenize(text)) & lexicon.TEST_COMMAND_WORDS)


def target_of(action: Action) -> str | None:
    args = {key.lower(): value for key, value in action.arguments.items()}
    for key in _TARGET_KEYS:
        if isinstance(args.get(key), str) and args[key].strip():
            return normalize_path(args[key])
    return None


def targets_related(left: str, right: str) -> bool:
    """Same target, or one is a directory containing the other."""
    if left == right or left == "." or right == ".":
        return True
    return left.startswith(right + "/") or right.startswith(left + "/")


def is_doc_path(path: str) -> bool:
    file = PurePosixPath(path)
    if file.suffix in lexicon.DOC_EXTENSIONS or path.startswith("docs/"):
        return True
    return not file.suffix and file.name in lexicon.DOC_FILENAMES


def is_broad_action(action: Action) -> bool:
    if set(tokenize(f"{action.type} {action.tool}")) & lexicon.BROAD_TOOL_WORDS:
        return True
    description = action.description.lower()
    return any(phrase in description for phrase in lexicon.BROAD_PHRASES)


# ------------------------------------------------------------- result status

_EXIT_CODE = re.compile(r"exit(?:ed)?[ _]?(?:code|status)?\s*(?:with\s+)?(?:code\s+)?[=:]?\s*(-?\d+)", re.I)
_HTTP_STATUS = re.compile(r"\b(?:status|http)(?:[ _]?code)?\"?\s*[=:]?\s*\"?([1-5]\d\d)\b", re.I)
_TRANSIENT = re.compile(
    r"timed? ?out|rate.?limit|too many requests|temporarily unavailable|connection reset|"
    r"service unavailable|try again later|\b(429|502|503|504)\b",
    re.I,
)
_ZERO_FAILURES = re.compile(r"\b(?:0|no|zero)\s+(?:errors?|failures?|failed)\b", re.I)
_FAILURE = re.compile(
    r"^\s*(?:error|fatal|exception|traceback|failed|failure|npm err)\b|\berror:|\b[1-9]\d*\s+(?:failed|errors?)\b|"
    r"no such file|permission denied|not found|command not found",
    re.I | re.M,
)
_PENDING = re.compile(r"\b(?:pending|running|in.progress|queued|processing|not ready|waiting)\b", re.I)


def classify_result(result: str) -> ResultStatus:
    if not result.strip():
        return ResultStatus.UNKNOWN
    if _TRANSIENT.search(result):
        return ResultStatus.TRANSIENT_FAILURE
    exit_code = _EXIT_CODE.search(result)
    if exit_code:
        return ResultStatus.SUCCESS if int(exit_code.group(1)) == 0 else ResultStatus.FAILURE
    http = _HTTP_STATUS.search(result)
    if http:
        code = int(http.group(1))
        return ResultStatus.SUCCESS if code < 400 else ResultStatus.FAILURE
    if _FAILURE.search(_ZERO_FAILURES.sub("", result)):
        return ResultStatus.FAILURE
    if _PENDING.search(result):
        return ResultStatus.PENDING
    return ResultStatus.SUCCESS


_TRUNCATED = re.compile(
    r"\btruncated\b|\bshowing (?:lines|results|items|rows) \d+\s*(?:-|to)\s*\d+ of \d+|\bpage \d+ of \d+\b|"
    r"\bmore results\b|\.\.\. ?and \d+ more\b|\bhas_more\W+true\b|\bnext.?page\b",
    re.I,
)


def is_truncated(result: str) -> bool:
    """Whether a result says explicitly that it is only part of the output."""
    return bool(_TRUNCATED.search(result))


def mentions_target(result: str, target: str) -> bool:
    """Whether an earlier result surfaced this file path or URL as a lead."""
    bare = re.sub(r"^[a-z]+://(?:www\.)?", "", target)
    return len(bare) >= 4 and bare in result.replace("\\", "/").lower()


# ----------------------------------------------------------- state snapshot

_CHANGE_WORDS = re.compile(
    r"\b(modified|changed|updated|edited|rewritten|reverted|deleted|new commits?|has been reset|reloaded)\b", re.I
)
_NEGATION = re.compile(r"\b(no|not|nothing|none|unchanged|without|never)\b|n't\b", re.I)
_KNOWLEDGE_GAP = re.compile(
    r"\bnot (?:yet )?(?:been )?(?:read|inspected|checked|loaded|seen|opened|examined|reviewed|viewed)\b|"
    r"\bno\b.*\b(?:yet|inspected|read|checked)\b|\bunknown\b|\bunread\b|\bmissing\b|\bnot yet\b|"
    r"\bhave(?:n't| not)\b|\bneed(?:s)? to (?:read|check|inspect|know|see)\b",
    re.I,
)


def state_reports_change(state: str) -> bool:
    """True when the snapshot asserts a change, ignoring negated mentions."""
    return any(_CHANGE_WORDS.search(s) and not _NEGATION.search(s) for s in sentences(state))


def knowledge_gaps(state: str) -> list[str]:
    """Sentences in the snapshot saying something is not known yet."""
    return [s for s in sentences(state) if _KNOWLEDGE_GAP.search(s)]
