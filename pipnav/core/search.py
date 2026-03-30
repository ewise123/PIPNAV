"""Fuzzy search — filter projects by subsequence matching."""

from pipnav.core.projects import ProjectInfo


def fuzzy_match(query: str, text: str) -> tuple[bool, int]:
    """Return (matches, score). Higher score = better match.

    Scoring:
    - Each matched character: +1
    - Consecutive matched characters: +2 bonus each
    - Match at start of word: +3 bonus
    """
    query_lower = query.lower()
    text_lower = text.lower()

    if not query_lower:
        return True, 0

    score = 0
    query_idx = 0
    prev_match_idx = -2  # Track consecutive matches

    for text_idx, char in enumerate(text_lower):
        if query_idx < len(query_lower) and char == query_lower[query_idx]:
            score += 1

            # Consecutive match bonus
            if text_idx == prev_match_idx + 1:
                score += 2

            # Word boundary bonus
            if text_idx == 0 or text_lower[text_idx - 1] in "-_ /":
                score += 3

            prev_match_idx = text_idx
            query_idx += 1

    matched = query_idx == len(query_lower)
    return matched, score if matched else 0


def filter_projects(
    query: str, projects: tuple[ProjectInfo, ...]
) -> tuple[ProjectInfo, ...]:
    """Return projects matching query, sorted by match score (best first)."""
    if not query.strip():
        return projects

    scored: list[tuple[int, ProjectInfo]] = []
    for project in projects:
        matched, score = fuzzy_match(query, project.name)
        if matched:
            scored.append((score, project))

    scored.sort(key=lambda x: x[0], reverse=True)
    return tuple(p for _, p in scored)
