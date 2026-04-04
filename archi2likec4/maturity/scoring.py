"""Maturity scoring engine: compute system and repo scores from gaps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .gaps import PENALTY_TABLE, Gap, Severity

if TYPE_CHECKING:
    from ..builders._result import BuildResult


@dataclass(frozen=True)
class SystemScore:
    """Maturity score for a single system."""

    system_id: str
    system_name: str
    score: int
    tier: str
    gaps: list[Gap] = field(default_factory=list)


@dataclass(frozen=True)
class RepoScore:
    """Aggregate maturity score for the entire repository."""

    score: int
    tier: str
    system_scores: list[SystemScore] = field(default_factory=list)
    total_gaps: int = 0
    blocker_count: int = 0


def score_to_tier(score: int) -> str:
    """Map numeric score (0-100) to maturity tier name."""
    if score >= 90:
        return 'complete'
    if score >= 70:
        return 'partial'
    if score >= 40:
        return 'skeletal'
    return 'stub'


def tier_emoji(tier: str) -> str:
    """Map tier to status emoji."""
    return {
        'complete': '\U0001f7e2',   # 🟢
        'partial': '\U0001f7e1',    # 🟡
        'skeletal': '\U0001f7e0',   # 🟠
        'stub': '\U0001f534',       # 🔴
    }.get(tier, '\u2753')           # ❓


def compute_system_score(system_id: str, system_name: str, gaps: list[Gap]) -> SystemScore:
    """Compute maturity score for a single system.

    score = max(0, 100 - sum of penalties for all gaps)
    """
    penalty = sum(PENALTY_TABLE.get(g.code, 0) for g in gaps)
    score = max(0, 100 - penalty)
    return SystemScore(
        system_id=system_id,
        system_name=system_name,
        score=score,
        tier=score_to_tier(score),
        gaps=gaps,
    )


def compute_repo_score(built: BuildResult, gaps: list[Gap]) -> RepoScore:
    """Compute repo-wide maturity score from all gaps.

    Groups gaps by system, computes per-system scores, then averages.
    Systems with no gaps get score=100.
    """
    # Group gaps by system
    sys_gaps: dict[str, list[Gap]] = {}
    non_system_gaps: list[Gap] = []
    for gap in gaps:
        # Orphan VMs and broken refs are not system-specific
        if gap.code in ('GAP-ORPHAN', 'GAP-REF', 'GAP-ENV'):
            non_system_gaps.append(gap)
        else:
            sys_gaps.setdefault(gap.element_id, []).append(gap)

    # Build system scores
    system_scores: list[SystemScore] = []
    for sys in built.systems:
        s_gaps = sys_gaps.get(sys.c4_id, [])
        system_scores.append(compute_system_score(sys.c4_id, sys.name, s_gaps))

    # Compute average
    avg_score = sum(s.score for s in system_scores) // len(system_scores) if system_scores else 100

    # Non-system gaps apply a global penalty
    global_penalty = sum(PENALTY_TABLE.get(g.code, 0) for g in non_system_gaps)
    # Cap global penalty influence to avoid overwhelming the score
    global_penalty = min(global_penalty, 30)
    final_score = max(0, avg_score - global_penalty)

    blocker_count = sum(1 for g in gaps if g.severity == Severity.BLOCKER)

    system_scores.sort(key=lambda s: (s.score, s.system_id))

    return RepoScore(
        score=final_score,
        tier=score_to_tier(final_score),
        system_scores=system_scores,
        total_gaps=len(gaps),
        blocker_count=blocker_count,
    )
