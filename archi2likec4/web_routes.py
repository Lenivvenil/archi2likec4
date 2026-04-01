"""Flask Blueprint with route handlers for the quality audit dashboard."""

from __future__ import annotations

import html
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask

from flask import Blueprint, redirect, render_template, request

logger = logging.getLogger(__name__)

_SEVERITY_COLORS = {
    'Critical': '#dc3545',
    'High': '#fd7e14',
    'Medium': '#ffc107',
    'Low': '#28a745',
}

def _get_columns(incident) -> list[str]:
    """Determine table columns from affected items."""
    if not incident.affected:
        return []
    return list(incident.affected[0].keys())


audit_bp = Blueprint('audit', __name__)


def init_routes(
    app: Flask,
    *,
    load_data: Callable[[], Any],
    load_config_safe: Callable[[], Any],
    safe_redirect: Callable[[str], str],
    resolved_config_path: Any,
    metric_health: Callable[..., dict[str, str]],
    ui_func: Callable[[str], dict[str, str]],
    version: str,
    save_suppress: Callable[..., None],
    update_config_field: Callable[..., None],
    valid_c4_id: Any,
) -> None:
    """Register audit blueprint routes on the app.

    All dependencies are injected to keep routes decoupled from app creation.
    """
    # Store dependencies in app config for access from route handlers
    app.config['_audit'] = {
        'load_data': load_data,
        'load_config_safe': load_config_safe,
        'safe_redirect': safe_redirect,
        'resolved_config_path': resolved_config_path,
        'metric_health': metric_health,
        'ui': ui_func,
        'version': version,
        'save_suppress': save_suppress,
        'update_config_field': update_config_field,
        'valid_c4_id': valid_c4_id,
    }
    app.register_blueprint(audit_bp)


def _ctx() -> dict[str, Any]:
    """Shortcut to access injected dependencies from app config."""
    from flask import current_app
    result: dict[str, Any] = current_app.config['_audit']
    return result


# ── Dashboard ────────────────────────────────────────────────────────────

@audit_bp.route('/')
def dashboard():
    ctx = _ctx()
    config, summary, incidents, available_domains, built = ctx['load_data']()
    lang = config.language
    active_count = sum(1 for i in incidents if not i.suppressed)
    suppressed_count = sum(1 for i in incidents if i.suppressed)
    remed_domain = len(config.domain_overrides)
    remed_reviewed = len(config.reviewed_systems)
    remed_total = remed_domain + remed_reviewed
    return render_template(
        'dashboard.html',
        t=ctx['ui'](lang), lang=lang,
        version=ctx['version'],
        summary=summary,
        incidents=incidents,
        severity_colors=_SEVERITY_COLORS,
        health=ctx['metric_health'](summary),
        suppress_names=sorted(config.audit_suppress),
        suppress_incidents_list=sorted(config.audit_suppress_incidents),
        config_path=str(ctx['resolved_config_path']),
        active_count=active_count,
        suppressed_count=suppressed_count,
        remed_domain=remed_domain,
        remed_reviewed=remed_reviewed,
        remed_total=remed_total,
    )


# ── Incident detail ─────────────────────────────────────────────────────

@audit_bp.route('/incident/<qa_id>')
def incident_detail(qa_id):
    ctx = _ctx()
    config, summary, incidents, available_domains, built = ctx['load_data']()
    lang = config.language
    incident = next((i for i in incidents if i.qa_id == qa_id), None)
    if incident is None:
        return redirect('/')
    columns = _get_columns(incident)
    return render_template(
        'detail.html',
        t=ctx['ui'](lang), lang=lang,
        incident=incident,
        columns=columns,
        severity_colors=_SEVERITY_COLORS,
        available_domains=available_domains,
    )


# ── Remediations page ───────────────────────────────────────────────────

@audit_bp.route('/remediations')
def remediations():
    ctx = _ctx()
    config = ctx['load_config_safe']()
    lang = config.language
    return render_template(
        'remediations.html',
        t=ctx['ui'](lang), lang=lang,
        domain_overrides=config.domain_overrides,
        reviewed_systems=sorted(config.reviewed_systems),
        promote_children=config.promote_children,
        suppress_names=sorted(config.audit_suppress),
        suppress_incidents_list=sorted(config.audit_suppress_incidents),
    )


# ── Suppress / Unsuppress routes ────────────────────────────────────────

@audit_bp.route('/suppress/system', methods=['POST'])
def suppress_system():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name:
        config = ctx['load_config_safe']()
        names = list(set(config.audit_suppress + [name]))
        ctx['save_suppress'](ctx['resolved_config_path'], names, config.audit_suppress_incidents)
        logger.info('Suppressed system: %s', name)
    return redirect(redirect_to)


@audit_bp.route('/unsuppress/system', methods=['POST'])
def unsuppress_system():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name:
        config = ctx['load_config_safe']()
        names = [n for n in config.audit_suppress if n != name]
        ctx['save_suppress'](ctx['resolved_config_path'], names, config.audit_suppress_incidents)
        logger.info('Unsuppressed system: %s', name)
    return redirect(redirect_to)


@audit_bp.route('/suppress/incident', methods=['POST'])
def suppress_incident():
    ctx = _ctx()
    qa_id = request.form.get('qa_id', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if qa_id:
        config = ctx['load_config_safe']()
        ids = list(set(config.audit_suppress_incidents + [qa_id]))
        ctx['save_suppress'](ctx['resolved_config_path'], config.audit_suppress, ids)
        logger.info('Suppressed incident: %s', qa_id)
    return redirect(redirect_to)


@audit_bp.route('/unsuppress/incident', methods=['POST'])
def unsuppress_incident():
    ctx = _ctx()
    qa_id = request.form.get('qa_id', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if qa_id:
        config = ctx['load_config_safe']()
        ids = [i for i in config.audit_suppress_incidents if i != qa_id]
        ctx['save_suppress'](ctx['resolved_config_path'], config.audit_suppress, ids)
        logger.info('Unsuppressed incident: %s', qa_id)
    return redirect(redirect_to)


# ── Remediation routes ──────────────────────────────────────────────────

@audit_bp.route('/assign-domain', methods=['POST'])
def assign_domain():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    domain = request.form.get('domain', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name and domain:
        if not ctx['valid_c4_id'].match(domain):
            return f'Invalid domain identifier: {html.escape(domain)}', 400
        config = ctx['load_config_safe']()
        overrides = dict(config.domain_overrides)
        overrides[name] = domain
        ctx['update_config_field'](ctx['resolved_config_path'], 'domain_overrides', overrides)
        logger.info('Assigned domain %s to system %s', domain, name)
    return redirect(redirect_to)


@audit_bp.route('/undo-assign-domain', methods=['POST'])
def undo_assign_domain():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name:
        config = ctx['load_config_safe']()
        overrides = dict(config.domain_overrides)
        overrides.pop(name, None)
        ctx['update_config_field'](ctx['resolved_config_path'], 'domain_overrides', overrides)
        logger.info('Undone domain override for %s', name)
    return redirect(redirect_to)


@audit_bp.route('/mark-reviewed', methods=['POST'])
def mark_reviewed():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name:
        config = ctx['load_config_safe']()
        reviewed = list(set(config.reviewed_systems + [name]))
        ctx['update_config_field'](ctx['resolved_config_path'], 'reviewed_systems', sorted(reviewed))
        logger.info('Marked system as reviewed: %s', name)
    return redirect(redirect_to)


@audit_bp.route('/undo-mark-reviewed', methods=['POST'])
def undo_mark_reviewed():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name:
        config = ctx['load_config_safe']()
        reviewed = [s for s in config.reviewed_systems if s != name]
        ctx['update_config_field'](ctx['resolved_config_path'], 'reviewed_systems', reviewed)
        logger.info('Undone reviewed mark for %s', name)
    return redirect(redirect_to)


@audit_bp.route('/promote-system', methods=['POST'])
def promote_system():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    domain = request.form.get('domain', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name and domain:
        if not ctx['valid_c4_id'].match(domain):
            return f'Invalid domain identifier: {html.escape(domain)}', 400
        config = ctx['load_config_safe']()
        promote = dict(config.promote_children)
        promote[name] = domain
        ctx['update_config_field'](ctx['resolved_config_path'], 'promote_children', promote)
        logger.info('Promoted system %s with fallback domain %s', name, domain)
    return redirect(redirect_to)


@audit_bp.route('/undo-promote', methods=['POST'])
def undo_promote():
    ctx = _ctx()
    name = request.form.get('name', '').strip()
    redirect_to = ctx['safe_redirect'](request.form.get('redirect', '/'))
    if name:
        config = ctx['load_config_safe']()
        promote = dict(config.promote_children)
        promote.pop(name, None)
        ctx['update_config_field'](ctx['resolved_config_path'], 'promote_children', promote)
        logger.info('Undone promote for %s', name)
    return redirect(redirect_to)


# ── Hierarchy page ──────────────────────────────────────────────────────

@audit_bp.route('/hierarchy')
def hierarchy():
    ctx = _ctx()
    config, summary, incidents, available_domains, built = ctx['load_data']()
    lang = config.language

    subdomain_names: dict[str, str] = {}
    for sd in built.subdomains:
        subdomain_names[sd.c4_id] = sd.name

    domain_groups: dict[str, dict[str, list]] = {}
    domain_totals: dict[str, int] = {}
    for domain_id, sys_list in sorted(built.domain_systems.items()):
        if sys_list:
            sd_map: dict[str, list] = {}
            for sys in sorted(sys_list, key=lambda s: s.name):
                sd_key = sys.subdomain or ''
                sd_map.setdefault(sd_key, []).append(sys)
            ordered: dict[str, list] = {}
            if '' in sd_map:
                ordered[''] = sd_map['']
            for k in sorted(k for k in sd_map if k):
                ordered[k] = sd_map[k]
            domain_groups[domain_id] = ordered
            domain_totals[domain_id] = len(sys_list)

    promoted_parents = set(config.promote_children.keys())

    return render_template(
        'hierarchy.html',
        t=ctx['ui'](lang), lang=lang,
        version=ctx['version'],
        domain_groups=domain_groups,
        domain_totals=domain_totals,
        subdomain_names=subdomain_names,
        promoted_parents=promoted_parents,
        total_systems=summary.total_systems,
        total_subsystems=summary.total_subsystems,
    )
