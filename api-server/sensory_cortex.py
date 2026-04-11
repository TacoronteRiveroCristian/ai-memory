"""Layer 0 — Multi-Modal Sensory Cortex.

Keyphrase extraction, tag canonicalization, multi-signal cascade scoring.
"""

import json
import math
import os
import re
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("ai-memory-brain")

AI_MEMORY_TEST_MODE = os.environ.get("AI_MEMORY_TEST_MODE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# ---------------------------------------------------------------------------
# Tag Canonicalization
# ---------------------------------------------------------------------------

TAG_NORMALIZE_RE = re.compile(r"[^a-z0-9/_-]+")
_TAG_ALIASES: dict[str, str] = {}


def _load_tag_aliases() -> dict[str, str]:
    global _TAG_ALIASES
    if _TAG_ALIASES:
        return _TAG_ALIASES
    alias_path = Path(__file__).resolve().parent.parent / "config" / "tag_aliases.json"
    if alias_path.exists():
        with open(alias_path) as f:
            _TAG_ALIASES = json.load(f)
    return _TAG_ALIASES


def singularize(tag: str) -> str:
    if len(tag) > 3 and tag.endswith("ies"):
        return tag[:-3] + "y"
    if len(tag) > 3 and tag.endswith("ses"):
        return tag[:-2]
    if len(tag) > 2 and tag.endswith("s") and not tag.endswith("ss"):
        return tag[:-1]
    return tag


def canonicalize_tag(tag: str) -> list[str]:
    """Canonicalize a single tag: apply alias, extract leaf, singularize."""
    tag = tag.lower().strip()
    tag = TAG_NORMALIZE_RE.sub("", tag)
    if not tag:
        return []
    aliases = _load_tag_aliases()
    canonical = aliases.get(tag, tag)
    canonical = singularize(canonical)
    results = [canonical]
    if "/" in canonical:
        leaf = canonical.rsplit("/", 1)[-1]
        leaf = singularize(leaf)
        if leaf != canonical:
            results.append(leaf)
    return results


def canonicalize_tags(tags: list[str]) -> list[str]:
    """Canonicalize a list of tags, deduplicate, preserve order."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        for canonical in canonicalize_tag(tag):
            if canonical and canonical not in seen:
                seen.add(canonical)
                result.append(canonical)
    return result


# ---------------------------------------------------------------------------
# KeyBERT Keyphrase Extraction
# ---------------------------------------------------------------------------

_kw_model = None


def _get_keybert_model():
    global _kw_model
    if _kw_model is None:
        from keybert import KeyBERT

        _kw_model = KeyBERT(model="all-MiniLM-L6-v2")
    return _kw_model


def extract_keyphrases_deterministic(content: str, user_tags: list[str]) -> list[str]:
    """Deterministic keyphrase extraction for test mode - no ML model needed."""
    words = re.findall(r"[a-z][a-z0-9_-]+", content.lower())
    counts = Counter(w for w in words if len(w) > 3)
    keyphrases = [w for w, _ in counts.most_common(8)]
    for tag in canonicalize_tags(user_tags):
        if tag not in keyphrases:
            keyphrases.append(tag)
    return keyphrases


def extract_keyphrases(content: str, user_tags: list[str]) -> list[str]:
    """Extract keyphrases from content using KeyBERT + append canonicalized user tags."""
    if AI_MEMORY_TEST_MODE:
        return extract_keyphrases_deterministic(content, user_tags)
    try:
        kw_model = _get_keybert_model()
        keywords = kw_model.extract_keywords(
            content,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            top_n=8,
            use_mmr=True,
            diversity=0.5,
        )
        keyphrases = [kw for kw, score in keywords if score > 0.25]
    except Exception as exc:
        logger.warning(
            "KeyBERT extraction failed, using deterministic fallback: %s", exc
        )
        keyphrases = extract_keyphrases_deterministic(content, [])

    for tag in canonicalize_tags(user_tags):
        if tag not in keyphrases:
            keyphrases.append(tag)
    return keyphrases


# ---------------------------------------------------------------------------
# Signal Computation (7 signals for cascade)
# ---------------------------------------------------------------------------


def emotional_proximity(mem_a: dict[str, Any], mem_b: dict[str, Any]) -> float:
    va = float(mem_a.get("valence", 0.0) or 0.0)
    aa = float(mem_a.get("arousal", 0.5) or 0.5)
    vb = float(mem_b.get("valence", 0.0) or 0.0)
    ab = float(mem_b.get("arousal", 0.5) or 0.5)
    dv = (va - vb) ** 2
    da = (aa - ab) ** 2
    distance = math.sqrt(dv + da)
    max_distance = math.sqrt(4 + 1)  # valence [-1,1], arousal [0,1]
    return round(1.0 - min(distance / max_distance, 1.0), 4)


def importance_attraction(mem_a: dict[str, Any], mem_b: dict[str, Any]) -> float:
    ia = float(mem_a.get("importance", 0.5) or 0.5)
    ib = float(mem_b.get("importance", 0.5) or 0.5)
    return round((ia + ib) / 2.0, 4)


def temporal_proximity(mem_a: dict[str, Any], mem_b: dict[str, Any]) -> float:
    ca = mem_a.get("created_at")
    cb = mem_b.get("created_at")
    if not ca or not cb:
        return 0.0
    if isinstance(ca, str):
        try:
            ca = datetime.fromisoformat(ca.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    if isinstance(cb, str):
        try:
            cb = datetime.fromisoformat(cb.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    hours_apart = abs((ca - cb).total_seconds()) / 3600.0
    return round(math.exp(-hours_apart / 48.0), 4)


# Type compatibility matrix
_TYPE_COMPAT: dict[tuple[str, str], float] = {
    ("observation", "observation"): 1.0,
    ("observation", "decision"): 0.5,
    ("observation", "schema"): 0.5,
    ("observation", "insight"): 0.7,
    ("observation", "error"): 0.7,
    ("observation", "pattern"): 0.5,
    ("decision", "decision"): 1.0,
    ("decision", "schema"): 0.7,
    ("decision", "insight"): 0.7,
    ("decision", "error"): 0.3,
    ("decision", "pattern"): 0.5,
    ("schema", "schema"): 1.0,
    ("schema", "insight"): 0.8,
    ("schema", "error"): 0.3,
    ("schema", "pattern"): 0.9,
    ("insight", "insight"): 1.0,
    ("insight", "error"): 0.5,
    ("insight", "pattern"): 0.8,
    ("error", "error"): 1.0,
    ("error", "pattern"): 0.3,
    ("pattern", "pattern"): 1.0,
    ("general", "general"): 0.7,
}


def type_compatibility(mem_a: dict[str, Any], mem_b: dict[str, Any]) -> float:
    ta = str(mem_a.get("memory_type", "general")).lower()
    tb = str(mem_b.get("memory_type", "general")).lower()
    key = (ta, tb) if (ta, tb) in _TYPE_COMPAT else (tb, ta)
    return _TYPE_COMPAT.get(key, 0.5)


# ---------------------------------------------------------------------------
# Multi-Signal Cascade (Tiers 1-3)
# ---------------------------------------------------------------------------


def compute_combined_score(signals: dict[str, float]) -> float:
    """Weighted combination of all 7 signals."""
    return round(
        0.40 * signals.get("semantic_score", 0.0)
        + 0.20 * signals.get("domain_score", 0.0)
        + 0.12 * signals.get("lexical_overlap", 0.0)
        + 0.10 * signals.get("emotional_proximity", 0.0)
        + 0.08 * signals.get("importance_attraction", 0.0)
        + 0.05 * signals.get("temporal_proximity", 0.0)
        + 0.05 * signals.get("type_compatibility", 0.0),
        4,
    )


def infer_relation_type(signals: dict[str, float], cross_project: bool) -> str:
    """Infer relation type from dominant signal."""
    sem = signals.get("semantic_score", 0.0)
    dom = signals.get("domain_score", 0.0)
    lex = signals.get("lexical_overlap", 0.0)
    emo = signals.get("emotional_proximity", 0.0)

    if cross_project and dom > 0.5:
        return "derived_from"
    if sem >= dom and sem >= lex and sem >= emo:
        return "same_concept"
    if dom >= sem and dom >= lex:
        return "supports"
    if lex >= sem and lex >= dom:
        return "extends"
    if emo >= 0.7:
        return "applies_to"
    return "supports"


def classify_synapse_cascade(
    signals: dict[str, float],
    cross_project: bool = False,
) -> Optional[dict[str, Any]]:
    """Multi-signal cascade: Tiers 1-3.

    Returns dict with keys: tier, relation_type, weight, combined_score, reason
    or None if no tier matches.
    """
    sem = signals.get("semantic_score", 0.0)
    dom = signals.get("domain_score", 0.0)
    lex = signals.get("lexical_overlap", 0.0)
    emo = signals.get("emotional_proximity", 0.0)
    temp = signals.get("temporal_proximity", 0.0)

    # In test mode, RRF fusion compresses scores (~0.667 max for top hit),
    # so we lower semantic thresholds to maintain cascade behavior.
    tier1_sem = 0.68 if AI_MEMORY_TEST_MODE else 0.92
    tier2_sem = 0.55 if AI_MEMORY_TEST_MODE else 0.75

    # Tier 1 - INSTINCT: dominant semantic signal
    if sem > tier1_sem:
        return {
            "tier": 1,
            "relation_type": "same_concept",
            "weight": round(sem, 4),
            "combined_score": compute_combined_score(signals),
            "reason": "tier1_instinct_high_semantic",
        }

    # Tier 2 - PERCEPTION: strong semantic + one confirmation
    if sem > tier2_sem:
        confirmed = dom > 0.70 or lex > 0.40 or (emo > 0.80 and temp > 0.50)
        if AI_MEMORY_TEST_MODE:
            # RRF fusion compresses domain scores too; relax thresholds but
            # require lexical overlap to avoid false links between unrelated content
            confirmed = (dom > 0.50 and lex > 0.15) or lex > 0.30 or (emo > 0.70 and temp > 0.40 and lex > 0.10)
        if confirmed:
            rel_type = infer_relation_type(signals, cross_project)
            return {
                "tier": 2,
                "relation_type": rel_type,
                "weight": round(max(sem, dom) * 0.95, 4),
                "combined_score": compute_combined_score(signals),
                "reason": "tier2_perception_confirmed",
            }

    # Tier 3 - REASONING: multiple weak signals converge
    combined = compute_combined_score(signals)
    if combined > 0.55:
        rel_type = infer_relation_type(signals, cross_project)
        return {
            "tier": 3,
            "relation_type": rel_type,
            "weight": round(combined * 0.85, 4),
            "combined_score": combined,
            "reason": "tier3_reasoning_converging_signals",
        }

    return None


# ---------------------------------------------------------------------------
# Contradiction Detection
# ---------------------------------------------------------------------------

CONTRADICTION_PATTERNS: list[tuple[str, str]] = [
    (r"\bno\s+usar\b", r"\busar\b"),
    (r"\bevitar\b", r"\bpreferir\b"),
    (r"\bdeprecated?\b", r"\brecomend(?:ado|ed)\b"),
    (r"\bremove[dr]?\b", r"\badd(?:ed)?\b"),
    (r"\bdisable[dr]?\b", r"\benable[dr]?\b"),
    (r"\bnot?\s+recommend", r"\brecommend"),
    (r"\banti[_-]?pattern\b", r"\bbest[_-]?practice\b"),
]


def compute_contradiction_score(
    signals: dict[str, float],
    content_a: str,
    content_b: str,
    valence_a: float = 0.0,
    valence_b: float = 0.0,
    keyphrases_a: Optional[list[str]] = None,
    keyphrases_b: Optional[list[str]] = None,
    days_apart: float = 0.0,
) -> float:
    """Score how likely two memories contradict each other. Returns [0, 1]."""
    score = 0.0

    sem = signals.get("semantic_score", 0.0)
    lex = signals.get("lexical_overlap", 0.0)

    # 1. Semantic high + lexical low → content diverges despite topic overlap
    if sem > 0.7 and lex < 0.3:
        score += 0.30
    elif sem > 0.5 and lex < 0.2:
        score += 0.15

    # 2. Valence opposition
    if valence_a * valence_b < 0:
        score += 0.25

    # 3. Negation patterns — check both directions
    pattern_score = 0.0
    lower_a = content_a.lower()
    lower_b = content_b.lower()
    for pat_a, pat_b in CONTRADICTION_PATTERNS:
        if (re.search(pat_a, lower_a) and re.search(pat_b, lower_b)) or \
           (re.search(pat_b, lower_a) and re.search(pat_a, lower_b)):
            pattern_score += 0.10
    score += min(pattern_score, 0.25)

    # 4. Temporal supersession — same topic revisited much later
    kp_a = set(keyphrases_a or [])
    kp_b = set(keyphrases_b or [])
    if len(kp_a & kp_b) >= 2 and days_apart > 30:
        score += 0.20

    return min(max(score, 0.0), 1.0)
