from __future__ import annotations

import re


LEADING_ACTION_PATTERN = re.compile(
    r"^(?P<action>(?:\s*[（(][^（）()]+[）)]\s*)+)(?P<dialogue>.*)$",
    re.DOTALL,
)

ACTION_SEGMENT_PATTERN = re.compile(r"([（(])([^（）()]+)([）)])")


def parse_content(text: str) -> tuple[str, str]:
    content = text.strip()
    if not content:
        return "", ""
    match = LEADING_ACTION_PATTERN.match(content)
    if not match:
        return "", content
    action = re.sub(r"\s+", " ", match.group("action")).strip()
    dialogue = match.group("dialogue").strip()
    return action, dialogue


def format_action_text(action: str) -> str:
    return action.strip()


def convert_action_to_third_person(action: str, subject: str) -> str:
    normalized_subject = subject.strip() or "AURA"
    normalized_action = action.strip()
    if not normalized_action:
        return normalized_action
    normalized_action = normalized_action.replace("我自己", f"{normalized_subject}自己")
    normalized_action = normalized_action.replace("我的", f"{normalized_subject}的")
    normalized_action = normalized_action.replace("我", normalized_subject)
    return re.sub(r"\s+", " ", normalized_action).strip()


def normalize_action_perspective(text: str, subject: str) -> str:
    normalized_subject = subject.strip() or "AURA"
    if not text.strip():
        return text

    def _replace(match: re.Match[str]) -> str:
        open_bracket, inner, close_bracket = match.groups()
        return f"{open_bracket}{convert_action_to_third_person(inner, normalized_subject)}{close_bracket}"

    return ACTION_SEGMENT_PATTERN.sub(_replace, text)


def extract_first_sentence(text: str, max_length: int = 80) -> str:
    content = re.sub(r"\s+", " ", text.strip())
    if not content:
        return ""
    sentence_match = re.search(r"[。！？!?\.]", content)
    if sentence_match:
        content = content[: sentence_match.end()]
    if len(content) <= max_length:
        return content
    return content[: max_length - 1].rstrip() + "…"
