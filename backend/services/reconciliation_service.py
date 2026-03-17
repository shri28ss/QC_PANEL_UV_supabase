"""
Symmetric Order-Independent Transaction Reconciliation Service.

Neither code nor LLM extraction is treated as the source of truth.
Both are compared symmetrically with field-level mismatch flags.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from rapidfuzz import fuzz


def normalize_date(date_str: Any) -> str:
    """Normalize date string to YYYY-MM-DD."""
    if not date_str or not isinstance(date_str, str):
        return ""
    date_str = date_str.strip()
    for fmt in (
        "%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d",
        "%d/%m/%y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y",
        "%d %b %Y", "%d %B %Y",           # 25 Aug 2025, 25 August 2025
        "%d-%b-%Y", "%d-%B-%Y",           # 25-Aug-2025, 25-August-2025
        "%d/%b/%Y", "%d/%B/%Y",           # 25/Aug/2025
        "%b %d, %Y", "%B %d, %Y",         # Aug 25, 2025
        "%d %b %y", "%d %B %y",           # 25 Aug 25
    ):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str  # return as-is if no format works


def normalize_amount(val) -> float:
    """Normalize amount to round(float, 2)."""
    if val is None:
        return 0.0
    try:
        # Handle string amounts with commas
        if isinstance(val, str):
            val = val.replace(",", "")
        # Use a more explicit rounding to satisfy strict type checkers
        f_val = float(val)
        return float(f"{f_val:.2f}")
    except (ValueError, TypeError):
        return 0.0


def get_effective_amount(txn: Dict[str, Any]) -> float:
    """Get a signed effective amount: positive for credit, negative for debit."""
    credit = normalize_amount(txn.get("credit"))
    debit = normalize_amount(txn.get("debit"))
    if credit:
        return credit
    if debit:
        return -debit
    return 0.0


def normalize_details(details: str) -> str:
    """Normalize details: lowercase, strip, collapse whitespace."""
    if not details or not isinstance(details, str):
        return ""
    return re.sub(r"\s+", " ", details.lower().strip())


def _prepare(txn: Dict[str, Any], idx: int, source: str) -> Dict[str, Any]:
    """Prepare a single transaction for matching."""
    norm_date = normalize_date(txn.get("date", ""))
    eff_amount = get_effective_amount(txn)
    norm_desc = normalize_details(txn.get("details", ""))
    return {
        "original": txn,
        "index": idx,
        "source": source,
        "norm_date": norm_date,
        "eff_amount": eff_amount,
        "abs_amount": abs(eff_amount),
        "norm_desc": norm_desc,
        "primary_key": (norm_date, eff_amount),
    }


def _compute_score(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[float, Dict[str, bool], float]:
    """
    Compute weighted similarity score between two prepared transactions.
    score = 0.5 * amount_match + 0.3 * date_match + 0.2 * desc_similarity
    Returns (score, field_flags dict, desc_ratio)
    """
    # Amount match (exact after normalization)
    amount_match = 1.0 if a["eff_amount"] == b["eff_amount"] else 0.0

    # Date match (exact after normalization)
    date_match = 1.0 if a["norm_date"] == b["norm_date"] else 0.0

    # Description similarity via RapidFuzz
    if a["norm_desc"] and b["norm_desc"]:
        desc_ratio = float(fuzz.token_sort_ratio(a["norm_desc"], b["norm_desc"])) / 100.0
    elif not a["norm_desc"] and not b["norm_desc"]:
        desc_ratio = 1.0  # both empty
    else:
        desc_ratio = 0.0

    score = 0.5 * amount_match + 0.3 * date_match + 0.2 * desc_ratio

    # Field-level flags
    flags: Dict[str, bool] = {}
    if amount_match < 1.0:
        flags["amount_mismatch"] = True
    if date_match < 1.0:
        flags["date_mismatch"] = True
    if desc_ratio < 0.80:
        flags["detail_mismatch"] = True

    return score, flags, desc_ratio


def reconcile_transactions(code_txns: List[Dict[str, Any]], llm_txns: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Symmetric order-independent reconciliation.

    1. Normalize all transactions.
    2. Primary grouping by (date, amount); fallback by amount only.
    3. Compute weighted scores for candidate pairs.
    4. Greedy best-match pairing (each txn matched at most once).
    5. Return matched_pairs, field_flags, unmatched_code, unmatched_llm.
    """
    code_prepared = [_prepare(t, i, "code") for i, t in enumerate(code_txns)]
    llm_prepared = [_prepare(t, i, "llm") for i, t in enumerate(llm_txns)]

    # Build candidate pairs with scores
    # For each (code, llm) combination, compute score only if they share
    # either a primary key or a fallback (amount-only) key.
    candidate_pairs: List[Tuple[float, Dict[str, bool], float, Dict[str, Any], Dict[str, Any]]] = []

    # Primary: group code transactions by (date, amount)
    code_by_primary: Dict[Tuple[str, float], List[Dict[str, Any]]] = {}
    for cp in code_prepared:
        code_by_primary.setdefault(cp["primary_key"], []).append(cp)

    # Fallback: group code transactions by amount only
    code_by_amount: Dict[float, List[Dict[str, Any]]] = {}
    for cp in code_prepared:
        code_by_amount.setdefault(cp["eff_amount"], []).append(cp)

    for lp in llm_prepared:
        # Primary candidates: same (date, amount)
        primary_candidates = code_by_primary.get(lp["primary_key"], [])
        # Fallback candidates: same amount but different date (OCR date errors)
        fallback_candidates = [
            c for c in code_by_amount.get(lp["eff_amount"], [])
            if c not in primary_candidates
        ]

        seen = set()
        for cp in primary_candidates:
            if id(cp) not in seen:
                score, flags, desc_ratio = _compute_score(cp, lp)
                candidate_pairs.append((score, flags, desc_ratio, cp, lp))
                seen.add(id(cp))

        for cp in fallback_candidates:
            if id(cp) not in seen:
                # Type hint for the checker
                score, flags, desc_ratio = _compute_score(cp, lp)
                candidate_pairs.append((score, flags, desc_ratio, cp, lp))
                seen.add(id(cp))

    # Sort by score descending (greedy best-first matching)
    candidate_pairs.sort(key=lambda x: x[0], reverse=True)

    matched_code_ids = set()
    matched_llm_ids = set()
    matched_pairs = []
    field_flags = []

    for score, flags, desc_ratio, cp, lp in candidate_pairs:
        if id(cp) in matched_code_ids or id(lp) in matched_llm_ids:
            continue
        if score < 0.75:
            continue

        matched_code_ids.add(id(cp))
        matched_llm_ids.add(id(lp))

        matched_pairs.append({
            "code": cp["original"],
            "llm": lp["original"],
            "score": float(f"{score:.3f}"),
            "desc_similarity": float(f"{(desc_ratio * 100):.1f}"),
        })
        field_flags.append(flags)

    # Unmatched
    unmatched_code = [cp["original"] for cp in code_prepared if id(cp) not in matched_code_ids]
    unmatched_llm = [lp["original"] for lp in llm_prepared if id(lp) not in matched_llm_ids]

    # ---- Overall Similarity ----
    total_code = len(code_prepared)
    total_llm = len(llm_prepared)
    total_txns = max(total_code, total_llm, 1)  # avoid /0

    # Sum of individual match scores
    sum_scores = sum(p["score"] for p in matched_pairs)

    # Overall = (sum of matched scores) / max(total_code, total_llm) * 100
    overall_similarity = float(f"{(sum_scores / total_txns * 100):.1f}")

    return {
        "matched_pairs": matched_pairs,
        "field_flags": field_flags,
        "unmatched_code": unmatched_code,
        "unmatched_llm": unmatched_llm,
        "overall_similarity": overall_similarity,
        "summary": {
            "total_code": total_code,
            "total_llm": total_llm,
            "matched_count": len(matched_pairs),
            "unmatched_code_count": len(unmatched_code),
            "unmatched_llm_count": len(unmatched_llm),
        },
    }
