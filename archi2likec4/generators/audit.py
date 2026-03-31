"""Generate AUDIT.md quality report."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from ..i18n import get_audit_label

if TYPE_CHECKING:
    from ..audit_data import AuditIncident
    from ..builders._result import BuildResult
    from ..config import ConvertConfig


def generate_audit_md(
    built: BuildResult,
    sv_unresolved: int,
    sv_total: int,
    config: ConvertConfig,
) -> str:
    """Generate AUDIT.md — quality incident register for ArchiMate repository owners.

    Delegates all logic to compute_audit_incidents() (audit_data.py) as the
    single source of truth, then renders results as markdown. Respects
    config.audit_suppress_incidents to skip entire QA categories.
    Fully bilingual (ru/en) via config.language.
    """
    from .. import __version__
    from ..audit_data import compute_audit_incidents

    lang: str = config.language
    summary, all_incidents = compute_audit_incidents(built, sv_unresolved, sv_total, config)

    # Filter out suppressed and zero-count incidents (keep for suppressed_count tracking)
    incidents = [inc for inc in all_incidents if not inc.suppressed and inc.count > 0]

    def _L(k: str, **kw: object) -> str:
        return get_audit_label(k, lang, **kw)

    # ── Header ────────────────────────────────────────────────────────
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    header = (
        f'# {_L("title")}\n\n'
        f'> {_L("auto_generated", version=__version__, date=now)}\n'
        f'> {_L("fix_prompt")}\n'
    )

    # ── Summary table ─────────────────────────────────────────────────
    total_sys = summary.total_systems
    assigned_pct = round(summary.assigned_count / total_sys * 100) if total_sys else 0
    summary_md = (
        f'## {_L("summary_heading")}\n\n'
        f'| {_L("metric")} | {_L("value")} |\n'
        '|---------|----------|\n'
        f'| {_L("systems")} | {total_sys} |\n'
        f'| {_L("subsystems")} | {summary.total_subsystems} |\n'
        f'| {_L("meta_completeness")} | {summary.meta_completeness_pct}% |\n'
        f'| {_L("domain_assigned")} | {summary.assigned_count} / {total_sys} ({assigned_pct}%) |\n'
        f'| {_L("integrations")} | {summary.total_integrations} |\n'
        f'| {_L("data_entities")} | {summary.total_entities} |\n'
        f'| {_L("deploy_mappings")} | {summary.deployment_mappings} |\n'
    )

    # ── Render incident sections ──────────────────────────────────────
    sections: list[str] = []
    suppressed_total = sum(inc.suppressed_count for inc in all_incidents)

    for inc in incidents:
        section = f'## {inc.qa_id}. [{inc.severity}] {inc.title} ({inc.count})\n\n'
        section += f'**{_L("problem")}:** {inc.description}\n\n'
        section += f'**{_L("impact_label")}:** {inc.impact}\n\n'
        section += f'**{_L("recommendation")}:**\n{inc.remediation}\n'

        if inc.affected:
            section += '\n'
            section += _render_affected_table(inc, lang)

        sections.append(section)

    # ── Assemble ──────────────────────────────────────────────────────
    suppressed_qa_ids = [inc.qa_id for inc in all_incidents if inc.suppressed]
    suppress_note = ''
    if suppressed_total > 0:
        suppress_note = _L('suppressed_note', count=suppressed_total)
    if suppressed_qa_ids:
        suppress_note += _L('suppressed_qa_note', ids=', '.join(suppressed_qa_ids))
    if not sections:
        return (
            header + '\n'
            + summary_md + '\n'
            + f'{_L("no_incidents")}{suppress_note}\n'
        )

    body = '\n---\n\n'.join(sections)
    footer_text = _L('footer', qa_num=len(incidents),
                      suppress_note=suppress_note, version=__version__)
    footer = f'\n---\n\n*{footer_text}*\n'
    return header + '\n' + summary_md + '\n---\n\n' + body + footer


def _render_affected_table(inc: AuditIncident, lang: str) -> str:
    """Render incident's affected items as a markdown table."""
    def _L(k: str, **kw: object) -> str:
        return get_audit_label(k, lang, **kw)

    if not inc.affected:
        return ''

    # Determine columns from first affected item
    keys = list(inc.affected[0].keys())

    # QA-2 has special rendering with field_stats sub-tables
    if inc.qa_id == 'QA-2':
        return _render_qa2_table(inc, lang)

    # QA-10 has element/kind/issue columns
    if inc.qa_id == 'QA-10':
        header = f'| {_L("col_num")} | {_L("col_element")} | {_L("col_kind")} | {_L("col_issue")} |\n'
        header += '|---|---------|------|----------|\n'
        rows = []
        for i, item in enumerate(inc.affected, 1):
            rows.append(f'| {i} | {item.get("name", "")} | {item.get("kind", "")} | {item.get("issue", "")} |')
        return header + '\n'.join(rows) + '\n'

    # Generic table based on keys
    col_map = {
        'name': _L('col_system'),
        'tags': _L('col_tags'),
        'domain': _L('col_domain'),
        'subsystem_count': _L('col_subsystems'),
    }
    col_headers = [_L('col_num')] + [col_map.get(k, k) for k in keys]
    header = '| ' + ' | '.join(col_headers) + ' |\n'
    header += '|' + '|'.join('---' for _ in col_headers) + '|\n'

    shown = inc.affected
    suffix = ''
    if inc.count > len(shown):
        suffix = _L('shown_first', n=len(shown), total=inc.count)

    rows = []
    for i, item in enumerate(shown, 1):
        vals = [str(i)] + [str(item.get(k, '')) for k in keys]
        rows.append('| ' + ' | '.join(vals) + ' |')

    return header + '\n'.join(rows) + suffix + '\n'


def _render_qa2_table(inc: AuditIncident, lang: str) -> str:
    """Render QA-2 metadata gap tables (field completeness + top systems)."""
    def _L(k: str, **kw: object) -> str:
        return get_audit_label(k, lang, **kw)

    # Top-N systems with most empty fields
    top_n = min(20, len(inc.affected))
    top_header = f'| {_L("col_num")} | {_L("col_system")} | {_L("col_domain")} | {_L("col_empty_fields")} |\n'
    top_header += '|---|---------|-------|--------------|\n'
    rows = []
    for i, item in enumerate(inc.affected[:top_n], 1):
        rows.append(f'| {i} | {item["name"]} | {item.get("domain", "")} '
                    f'| {item["tbd_count"]} / {item.get("total_fields", "")} |')

    return (
        f'\n**{_L("top_systems", n=top_n)}:**\n\n'
        + top_header + '\n'.join(rows) + '\n'
    )
