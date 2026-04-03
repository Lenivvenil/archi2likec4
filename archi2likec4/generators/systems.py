"""Generate system detail .c4 files."""

from __future__ import annotations

from ..models import AppFunction, Integration, Subsystem, System
from ..utils import escape_str, validate_c4_id
from ._common import render_metadata, truncate_desc

_MAX_FN_DESC_LEN = 300


def _render_appfunction(fn: AppFunction, lines: list[str], indent: int = 6,
                        sys_c4_id: str = '') -> None:
    pad = ' ' * indent
    title = escape_str(fn.name)
    lines.append(f"{pad}{fn.c4_id} = appFunction '{title}' {{")
    if sys_c4_id:
        lines.append(f"{pad}  #system_{sys_c4_id.replace('-', '_')}")
    if fn.documentation:
        desc = truncate_desc(escape_str(fn.documentation), max_len=_MAX_FN_DESC_LEN)
        lines.append(f"{pad}  description '{desc}'")
    render_metadata(lines, fn.archi_id, pad)
    lines.append(f'{pad}}}')


def _render_subsystem(sub: Subsystem, lines: list[str], indent: int = 4,
                      sys_c4_id: str = '') -> None:
    pad = ' ' * indent
    title = escape_str(sub.name)
    lines.append(f"{pad}{sub.c4_id} = subsystem '{title}' {{")
    if sys_c4_id:
        lines.append(f"{pad}  #system_{sys_c4_id.replace('-', '_')}")
    for tag in sub.tags:
        lines.append(f'{pad}  #{tag}')
    if sub.documentation:
        desc = truncate_desc(escape_str(sub.documentation))
        lines.append(f"{pad}  description '{desc}'")
    for url, link_title in sub.links:
        lines.append(f"{pad}  link {url} '{escape_str(link_title)}'")
    extra: dict[str, str] = {key: escape_str(value) for key, value in sub.metadata.items()}
    render_metadata(lines, sub.archi_id, pad, extra=extra or None)
    # Render nested appFunctions
    if sub.functions:
        lines.append('')
        for fn in sorted(sub.functions, key=lambda f: f.name):
            _render_appfunction(fn, lines, indent=indent + 2, sys_c4_id=sys_c4_id)
    lines.append(f'{pad}}}')


def generate_system_detail_c4(
    domain_c4_id: str,
    sys: System,
    outgoing: list[Integration] | None = None,
) -> str:
    """Generate systems/{c4_id}/model.c4 with extend block + relationships + detail view.

    The detail view (``view {sys_id}_detail of {domain}.{sys_id}``) enables
    drill-down navigation: clicking a system on the domain-level functional
    view opens this view showing its subsystems and appFunctions.

    If *outgoing* integrations are provided, they are rendered after the
    extend block as ``source -> target 'label'`` lines.

    If the system belongs to a subdomain, the path is
    ``{domain}.{subdomain}.{system}`` instead of ``{domain}.{system}``.
    """
    validate_c4_id(domain_c4_id)
    validate_c4_id(sys.c4_id)
    full_path = f'{domain_c4_id}.{sys.subdomain}.{sys.c4_id}' if sys.subdomain else f'{domain_c4_id}.{sys.c4_id}'
    lines = [
        f'// ── {sys.name} (detail) ──────────────────────────────────',
        'model {',
        '',
        f'  extend {full_path} {{',
        '',
    ]

    for sub in sorted(sys.subsystems, key=lambda s: s.name):
        _render_subsystem(sub, lines, indent=4, sys_c4_id=sys.c4_id)
        lines.append('')

    # Functions directly on system (no subsystem parent)
    for fn in sorted(sys.functions, key=lambda f: f.name):
        _render_appfunction(fn, lines, indent=4, sys_c4_id=sys.c4_id)

    lines.append('  }')

    # ── Outgoing relationships (integrations from this system) ──
    if outgoing:
        lines.append('')
        for intg in outgoing:
            if intg.name:
                label = escape_str(intg.name)
                lines.append(f"  {intg.source_path} -> {intg.target_path} '{label}'")
            else:
                lines.append(f'  {intg.source_path} -> {intg.target_path}')

    lines.append('')
    lines.append('}')
    lines.append('')

    # ── Scoped detail view for drill-down navigation ──
    lines.append('views {')
    lines.append('')
    lines.append(f'  view {sys.c4_id}_detail of {full_path} {{')
    lines.append(f"    title '{escape_str(sys.name)}'")
    lines.append('    include *')
    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)
