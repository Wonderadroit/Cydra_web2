"""Deterministic, evidence-grounded browser test candidate generation.

This is a heuristic baseline, not an LLM. Candidates are derived only from
observable DOM semantics and carry the evidence that caused each proposal.
"""
from __future__ import annotations

from typing import Any


def generate_test_candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Propose bounded behavioral checks from a normalized DOM snapshot."""
    candidates: list[dict[str, Any]] = []
    checkbox_count = int(snapshot.get("checkbox_count", 0) or 0)
    if checkbox_count > 0:
        candidates.append({
            "id": "checkbox_toggle_restore",
            "kind": "interaction_invariant",
            "title": "Checkbox activation changes state and a second activation restores it",
            "evidence": {"checkbox_count": checkbox_count},
            "confidence": "high",
        })

    controls = snapshot.get("form_controls", [])
    for index, control in enumerate(controls):
        label = str(control.get("label", "")).strip()
        required_attr = bool(control.get("required"))
        required_hint = bool(control.get("required_hint"))
        if required_attr or required_hint:
            candidates.append({
                "id": f"required_validation_{index}",
                "kind": "form_constraint",
                "title": f"Required control is enforced: {label or control.get('type', 'input')}",
                "evidence": {
                    "control_index": index,
                    "label": label,
                    "required_attribute": required_attr,
                    "required_label_hint": required_hint,
                    "input_type": str(control.get("type", "text")),
                },
                "confidence": "high" if required_attr and required_hint else "medium",
            })

    return candidates
