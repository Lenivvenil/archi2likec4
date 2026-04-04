"""Scaffold generator: commented-out deployment.c4 for unmapped systems."""

from __future__ import annotations

import logging

from .gaps import GapCode
from .scoring import SystemScore

logger = logging.getLogger(__name__)


def generate_scaffold_deployment(
    system_id: str,
    system_name: str,
    system_score: SystemScore,
    subsystems: list[str],
    env: str = 'prod',
) -> str:
    """Generate deployment.c4 with TODO comments for unmapped systems.

    Returns a syntactically valid LikeC4 file with commented-out blocks
    and maturity metadata in the header.
    """
    tier_upper = system_score.tier.upper()
    gap_lines = []
    for gap in system_score.gaps:
        gap_lines.append(f'// {gap.code}: {gap.remediation}')

    header = f"""\
// {'=' * 60}
// MATURITY: {system_score.score}/100 ({tier_upper})
// {'=' * 60}
//"""

    if gap_lines:
        header += '\n' + '\n'.join(gap_lines) + '\n//'

    has_deploy_gap = any(g.code == GapCode.DEPLOY for g in system_score.gaps)

    if has_deploy_gap:
        # Generate commented-out scaffold
        subsystem_lines = []
        for sub_id in subsystems:
            subsystem_lines.append(f'  //   instanceOf {system_id}.{sub_id}')

        sub_block = '\n'.join(subsystem_lines) if subsystem_lines else f'  //   instanceOf {system_id}'

        return f"""\
{header}

deployment {{
  // TODO [GAP-DEPLOY]: uncomment and fill in the actual VM path
  //
  // extend {env}.{{dc}}.{{zone}}.{{vm}} {{
{sub_block}
  // }}
}}

views {{
  // Deployment view will appear after instanceOf is configured
  //
  // deployment view {system_id}_{env} {{
  //   title '{system_name} — Production'
  //   include {env}.{{dc}}.{{zone}}.{{vm}}.**
  // }}
}}
"""
    else:
        # System has deployment but low score for other reasons — header only
        return f"""\
{header}

// This system has deployment data but other gaps reduce its maturity score.
// See MATURITY.md for details.
"""
