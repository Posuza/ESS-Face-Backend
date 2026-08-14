from __future__ import annotations

from typing import Optional

from app.core.mo.config import get_rank_label, get_workflow_ranks


WORKFLOW_WAITING = "WAITING"
WORKFLOW_EDITING = "EDITING"
WORKFLOW_RETURNED_TO = "RETURNED_TO"
WORKFLOW_APPROVED = "APPROVED"


def make_workflow_status(rank_code: str, state: str) -> str:
    rank = rank_code.upper()
    normalized_state = state.upper()
    if normalized_state == WORKFLOW_WAITING:
        return f"WAITING_{rank}"
    if normalized_state == WORKFLOW_EDITING:
        return f"EDITING_{rank}"
    if normalized_state == WORKFLOW_RETURNED_TO:
        return f"RETURNED_TO_{rank}"
    if normalized_state == WORKFLOW_APPROVED:
        return f"APPROVED_{rank}"
    return f"{normalized_state}_{rank}"


def next_workflow_rank(rank_code: str) -> Optional[str]:
    workflow_ranks = get_workflow_ranks()
    try:
        index = workflow_ranks.index(rank_code)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(workflow_ranks):
        return None
    return workflow_ranks[next_index]


def previous_workflow_rank(rank_code: str) -> Optional[str]:
    workflow_ranks = get_workflow_ranks()
    try:
        index = workflow_ranks.index(rank_code)
    except ValueError:
        return None
    if index <= 0:
        return None
    return workflow_ranks[index - 1]


def split_workflow_status(workflow_status: Optional[str]) -> tuple[str, str]:
    value = (workflow_status or "").strip().upper()
    prefixes = (
        ("RETURNED_TO_", WORKFLOW_RETURNED_TO),
        ("WAITING_", WORKFLOW_WAITING),
        ("EDITING_", WORKFLOW_EDITING),
        ("APPROVED_", WORKFLOW_APPROVED),
    )
    for prefix, state in prefixes:
        if value.startswith(prefix):
            return value[len(prefix):], state

    # Backward compatibility for old values such as DIRECTOR_PENDING.
    if "_" not in value:
        return "", ""
    rank_code, state = value.rsplit("_", 1)
    if state == "PENDING":
        state = WORKFLOW_WAITING
    elif state == "REJECTED":
        rank_code = previous_workflow_rank(rank_code) or rank_code
        state = WORKFLOW_RETURNED_TO
    return rank_code, state


def workflow_rank_label(rank_code: str) -> str:
    return get_rank_label(rank_code)


def initial_workflow_status(actor_rank: str) -> str:
    next_rank = next_workflow_rank(actor_rank)
    target_rank = next_rank or actor_rank
    return make_workflow_status(target_rank, WORKFLOW_WAITING)

