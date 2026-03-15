"""Generate cross-domain relationships .c4 file."""

from __future__ import annotations

from ..models import Integration
from ..utils import escape_str


def generate_relationships(integrations: list[Integration]) -> str:
    """Generate relationships.c4: cross-domain integrations model block."""
    lines = [
        '// ── Cross-domain integrations ──────────────────────────',
        'model {',
        '',
    ]
    if not integrations:
        lines.append('  // No integrations found')
    else:
        for intg in integrations:
            if intg.name:
                label = escape_str(intg.name)
                lines.append(f"  {intg.source_path} -> {intg.target_path} '{label}'")
            else:
                lines.append(f"  {intg.source_path} -> {intg.target_path}")
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
