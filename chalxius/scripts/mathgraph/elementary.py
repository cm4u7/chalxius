from __future__ import annotations

import re
from typing import Any

from .contracts import require_exact_keys, require_string


ELEMENTARY_CATEGORIES = frozenset(
    {
        "basic_metric_compactness",
        "elementary_limit_series",
        "finite_algebra",
        "finite_linear_algebra",
        "identity_removability",
        "iterated_polydisc_cauchy",
        "local_inverse_implicit",
        "one_variable_cauchy",
        "residue_winding",
    }
)

_ELEMENTARY_REQUIRED_FIELDS = {
    "key",
    "result",
    "category",
    "hypothesis_witnesses",
    "used_conclusion",
    "scope_limitations",
    "reconstruction",
    "proof_anchor",
}
_ELEMENTARY_KEY_RE = re.compile(r"[A-Za-z0-9._-]+")


def _require_nonempty_string_list(
    payload: dict[str, Any],
    key: str,
    *,
    label: str,
) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label}.{key} must be a nonempty list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label}.{key} must be a nonempty list of strings")
    return list(value)


def validate_elementary_uses_for_submission(
    elementary_uses: list[dict[str, Any]],
    proof: str,
) -> None:
    """Validate the controlled elementary-result exemption ledger.

    This checks structure and proof binding, not mathematical eligibility. The
    packet-only verifier remains responsible for rejecting a substantive result
    disguised as an elementary one.
    """

    if not isinstance(elementary_uses, list) or any(
        not isinstance(item, dict) for item in elementary_uses
    ):
        raise ValueError("elementary_uses must be a list of objects")

    seen_keys: set[str] = set()
    seen_anchors: set[str] = set()
    for index, use in enumerate(elementary_uses, 1):
        label = f"elementary_uses[{index}]"
        require_exact_keys(
            use,
            required=_ELEMENTARY_REQUIRED_FIELDS,
            label=label,
        )
        key = require_string(use, "key")
        if _ELEMENTARY_KEY_RE.fullmatch(key) is None:
            raise ValueError(
                f"{label}.key must contain only ASCII letters, digits, dot, _ or -"
            )
        if key in seen_keys:
            raise ValueError(f"duplicate elementary-use key: {key}")
        seen_keys.add(key)

        require_string(use, "result")
        category = require_string(use, "category")
        if category not in ELEMENTARY_CATEGORIES:
            raise ValueError(
                f"{label}.category must be one of: "
                + ", ".join(sorted(ELEMENTARY_CATEGORIES))
            )
        _require_nonempty_string_list(
            use,
            "hypothesis_witnesses",
            label=label,
        )
        require_string(use, "used_conclusion")
        _require_nonempty_string_list(
            use,
            "scope_limitations",
            label=label,
        )
        require_string(use, "reconstruction")

        anchor = require_string(use, "proof_anchor")
        expected = f"[ELM:{key}]"
        if anchor != expected:
            raise ValueError(f"{label}.proof_anchor must be exactly {expected}")
        if anchor in seen_anchors:
            raise ValueError(f"duplicate elementary-use proof anchor: {anchor}")
        seen_anchors.add(anchor)
        occurrences = proof.count(anchor)
        if occurrences != 1:
            raise ValueError(
                f"elementary-use proof anchor {anchor} must occur exactly once in proof; "
                f"found {occurrences}"
            )
