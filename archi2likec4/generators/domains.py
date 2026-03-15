"""Generate domain .c4 files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import Subdomain, System
from ..utils import escape_str

if TYPE_CHECKING:
    pass

_MAX_DESC_LEN = 500


def _render_system(sys: System, lines: list[str], indent: int = 2) -> None:
    pad = ' ' * indent
    title = escape_str(sys.name)
    lines.append(f"{pad}{sys.c4_id} = system '{title}' {{")
    for tag in sys.tags:
        lines.append(f'{pad}  #{tag}')
    if sys.documentation:
        desc = escape_str(sys.documentation)
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
        lines.append(f"{pad}  description '{desc}'")
    for url, link_title in sys.links:
        lines.append(f"{pad}  link {url} '{escape_str(link_title)}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{sys.archi_id}'")
    for key, value in sys.metadata.items():
        lines.append(f"{pad}    {key} '{escape_str(value)}'")
    if sys.api_interfaces:
        ifaces_str = '; '.join(sys.api_interfaces)
        lines.append(f"{pad}    api_interfaces '{escape_str(ifaces_str)}'")
    lines.append(f'{pad}  }}')
    # Subsystems and functions are rendered in systems/{c4_id}.c4 via extend
    lines.append(f'{pad}}}')


def generate_domain_c4(
    domain_c4_id: str,
    domain_name: str,
    systems: list[System],
    subdomains: list[Subdomain] | None = None,
) -> str:
    """Generate a domain .c4 file: domain element with nested systems.

    If subdomains are provided, systems assigned to a subdomain are wrapped
    in a ``subdomain`` block; remaining systems are placed directly under the
    domain (fallback).
    """
    lines = [
        f'// ── {domain_name} ──────────────────────────────────────',
        'model {',
        '',
        f"  {domain_c4_id} = domain '{escape_str(domain_name)}' {{",
        '',
    ]

    domain_subdomains = [sd for sd in (subdomains or []) if sd.domain_id == domain_c4_id]
    if domain_subdomains:
        # Build lookup: subdomain c4_id → system c4_id set
        sd_system_sets: dict[str, set[str]] = {
            sd.c4_id: set(sd.system_ids) for sd in domain_subdomains
        }
        # Map each system to its subdomain (if any)
        sys_by_subdomain: dict[str, list[System]] = {}
        ungrouped: list[System] = []
        for sys in sorted(systems, key=lambda s: s.name):
            if sys.subdomain and sys.subdomain in sd_system_sets:
                sys_by_subdomain.setdefault(sys.subdomain, []).append(sys)
            else:
                ungrouped.append(sys)

        # Render subdomain blocks
        for sd in sorted(domain_subdomains, key=lambda s: s.name):
            sd_systems = sys_by_subdomain.get(sd.c4_id, [])
            if not sd_systems:
                continue
            lines.append(f"    {sd.c4_id} = subdomain '{escape_str(sd.name)}' {{")
            lines.append('')
            for sys in sd_systems:
                _render_system(sys, lines, indent=6)
                lines.append('')
            lines.append('    }')
            lines.append('')

        # Render ungrouped systems directly under domain
        for sys in ungrouped:
            _render_system(sys, lines, indent=4)
            lines.append('')
    else:
        for sys in sorted(systems, key=lambda s: s.name):
            _render_system(sys, lines, indent=4)
            lines.append('')

    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
