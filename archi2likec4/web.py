"""Flask web UI for quality audit dashboard."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logger = logging.getLogger('archi2likec4.web')

# ── Jinja2 templates (inline) ──────────────────────────────────────────

_SEVERITY_COLORS = {
    'Critical': '#dc3545',
    'High': '#fd7e14',
    'Medium': '#ffc107',
    'Low': '#28a745',
}

_BASE_CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       max-width: 960px; margin: 0 auto; padding: 20px; color: #333; background: #f8f9fa; }
h1 { margin-bottom: 4px; font-size: 1.4em; }
h2 { margin-top: 20px; margin-bottom: 8px; font-size: 1.1em; }
.subtitle { color: #666; font-size: 0.85em; margin-bottom: 16px; }
.metrics { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }
.metric { background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
          padding: 10px 16px; min-width: 120px; }
.metric-ok   { border-left: 4px solid #28a745; }
.metric-warn { border-left: 4px solid #ffc107; }
.metric-crit { border-left: 4px solid #dc3545; }
.metric-info { border-left: 4px solid #6c757d; }
.metric-value { font-size: 1.4em; font-weight: 700; }
.metric-label { font-size: 0.75em; color: #666; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border: 1px solid #dee2e6; border-radius: 6px; overflow: hidden; }
th { background: #e9ecef; text-align: left; padding: 8px 12px; font-size: 0.8em;
     text-transform: uppercase; color: #555; }
td { padding: 8px 12px; border-top: 1px solid #dee2e6; font-size: 0.9em; }
tr:hover { background: #f1f3f5; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
         font-size: 0.75em; font-weight: 600; color: #fff; }
a { color: #0d6efd; text-decoration: none; }
a:hover { text-decoration: underline; }
.btn { display: inline-block; padding: 4px 10px; border: 1px solid #dee2e6;
       border-radius: 4px; font-size: 0.8em; cursor: pointer; background: #fff; }
.btn:hover { background: #e9ecef; }
.btn-danger { color: #dc3545; border-color: #dc3545; }
.btn-danger:hover { background: #dc3545; color: #fff; }
.btn-success { color: #28a745; border-color: #28a745; }
.btn-success:hover { background: #28a745; color: #fff; }
select.btn { appearance: auto; padding: 3px 6px; }
.suppress-bar { background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px;
                padding: 10px 16px; margin-bottom: 16px; font-size: 0.85em; }
.suppress-bar form { display: inline; }
.suppress-item { display: inline-block; background: #e9ecef; border-radius: 4px;
                 padding: 2px 8px; margin: 2px; font-size: 0.8em; }
.remed-bar { background: #d4edda; border: 1px solid #28a745; border-radius: 6px;
             padding: 10px 16px; margin-bottom: 16px; font-size: 0.85em; }
.back { margin-bottom: 12px; font-size: 0.9em; }
.detail-block { background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
                padding: 16px; margin-bottom: 16px; }
.detail-block p { margin-bottom: 8px; line-height: 1.5; }
.detail-block strong { color: #555; }
pre { white-space: pre-wrap; font-size: 0.85em; color: #555; }
.suppressed-row { opacity: 0.45; }
.section-block { background: #fff; border: 1px solid #dee2e6; border-radius: 6px;
                 padding: 16px; margin-bottom: 16px; }
"""

_DASHBOARD_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>archi2likec4 — Quality Audit</title>
  <style>""" + _BASE_CSS + """</style>
</head>
<body>
  <h1>archi2likec4 — Quality Audit Dashboard</h1>
  <div class="subtitle">v{{ version }}</div>

  <div class="metrics">
    <div class="metric {{ health.systems }}">
      <div class="metric-value">{{ summary.total_systems }}</div>
      <div class="metric-label">Systems</div>
    </div>
    <div class="metric {{ health.subsystems }}">
      <div class="metric-value">{{ summary.total_subsystems }}</div>
      <div class="metric-label">Subsystems</div>
    </div>
    <div class="metric {{ health.meta }}">
      <div class="metric-value">{{ summary.meta_completeness_pct }}%</div>
      <div class="metric-label">Metadata</div>
    </div>
    <div class="metric {{ health.domain }}">
      <div class="metric-value">{{ summary.assigned_count }}/{{ summary.total_systems }}</div>
      <div class="metric-label">With Domain</div>
    </div>
    <div class="metric {{ health.intg }}">
      <div class="metric-value">{{ summary.total_integrations }}</div>
      <div class="metric-label">Integrations</div>
    </div>
    <div class="metric {{ health.deploy }}">
      <div class="metric-value">{{ summary.deployment_mappings }}</div>
      <div class="metric-label">Deploy Maps</div>
    </div>
  </div>

  {% if suppress_names or suppress_incidents_list %}
  <div class="suppress-bar">
    <strong>Suppressed:</strong>
    {% for name in suppress_names %}
      <span class="suppress-item">
        {{ name }}
        <form method="post" action="/unsuppress/system">
          <input type="hidden" name="name" value="{{ name }}">
          <button type="submit" class="btn btn-danger" style="padding:0 4px;border:0;font-size:0.7em;">&times;</button>
        </form>
      </span>
    {% endfor %}
    {% for qid in suppress_incidents_list %}
      <span class="suppress-item">
        {{ qid }}
        <form method="post" action="/unsuppress/incident">
          <input type="hidden" name="qa_id" value="{{ qid }}">
          <button type="submit" class="btn btn-danger" style="padding:0 4px;border:0;font-size:0.7em;">&times;</button>
        </form>
      </span>
    {% endfor %}
  </div>
  {% endif %}

  {% if remed_total > 0 %}
  <div class="remed-bar">
    <strong>Remediations:</strong>
    {% if remed_domain > 0 %}{{ remed_domain }} domain override{{ 's' if remed_domain != 1 }}{% endif %}
    {% if remed_reviewed > 0 %}{% if remed_domain > 0 %}, {% endif %}{{ remed_reviewed }} reviewed{% endif %}
    &rarr; <a href="/remediations">Review all</a>
  </div>
  {% endif %}

  <h2>Incidents ({{ active_count }}{% if suppressed_count > 0 %}, {{ suppressed_count }} suppressed{% endif %})</h2>
  {% if incidents %}
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>Severity</th>
        <th>Incident</th>
        <th style="text-align:right">Count</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for inc in incidents %}
      <tr{% if inc.suppressed %} class="suppressed-row"{% endif %}>
        <td>{{ inc.qa_id }}</td>
        <td><span class="badge" style="background:{{ severity_colors[inc.severity] }}">{{ inc.severity }}</span></td>
        <td>
          {% if inc.suppressed %}<s>{% endif %}
          <a href="/incident/{{ inc.qa_id }}">{{ inc.title }}</a>
          {% if inc.suppressed %}</s> <small>(suppressed)</small>{% endif %}
        </td>
        <td style="text-align:right">{{ inc.count }}</td>
        <td>
          {% if inc.suppressed %}
            <form method="post" action="/unsuppress/incident" style="display:inline">
              <input type="hidden" name="qa_id" value="{{ inc.qa_id }}">
              <button type="submit" class="btn btn-success">Unsuppress</button>
            </form>
          {% else %}
            <a href="/incident/{{ inc.qa_id }}" class="btn">Details</a>
            <form method="post" action="/suppress/incident" style="display:inline">
              <input type="hidden" name="qa_id" value="{{ inc.qa_id }}">
              <button type="submit" class="btn">Suppress</button>
            </form>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No quality incidents found.</p>
  {% endif %}

  <div class="subtitle" style="margin-top:20px">
    Config: {{ config_path }} |
    <a href="/">Refresh</a>
  </div>
</body>
</html>
"""

_DETAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ incident.qa_id }} — {{ incident.title }}</title>
  <style>""" + _BASE_CSS + """</style>
</head>
<body>
  <div class="back"><a href="/">&larr; Back to dashboard</a></div>

  <h1>
    {{ incident.qa_id }}
    <span class="badge" style="background:{{ severity_colors[incident.severity] }}">{{ incident.severity }}</span>
    {{ incident.title }}
    ({{ incident.count }})
    {% if incident.suppressed %}<small style="color:#999">(suppressed)</small>{% endif %}
  </h1>

  <div class="detail-block">
    <p><strong>Problem:</strong> {{ incident.description }}</p>
    <p><strong>Impact:</strong> {{ incident.impact }}</p>
    <p><strong>Remediation:</strong></p>
    <pre>{{ incident.remediation }}</pre>
  </div>

  {% if incident.affected %}
  <h2>Affected Elements ({{ incident.affected|length }}{% if incident.count > incident.affected|length %} of {{ incident.count }}{% endif %})</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        {% for key in columns %}
        <th>{{ key }}</th>
        {% endfor %}
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
      {% for item in incident.affected %}
      <tr>
        <td>{{ loop.index }}</td>
        {% for key in columns %}
        <td>{{ item.get(key, '') }}</td>
        {% endfor %}
        <td>
          {% if incident.qa_id == 'QA-1' and 'name' in item %}
          <form method="post" action="/assign-domain" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/QA-1">
            <select name="domain" class="btn">
              {% for d in available_domains %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
            </select>
            <button type="submit" class="btn btn-success">Assign</button>
          </form>
          {% elif incident.qa_id == 'QA-3' and 'name' in item %}
          <form method="post" action="/mark-reviewed" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/QA-3">
            <button type="submit" class="btn btn-success">Mark reviewed</button>
          </form>
          {% elif incident.qa_id == 'QA-4' and 'name' in item %}
          <form method="post" action="/promote-system" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/QA-4">
            <select name="domain" class="btn">
              {% for d in available_domains %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
            </select>
            <button type="submit" class="btn btn-success">Promote</button>
          </form>
          {% endif %}
          {% if 'name' in item %}
          <form method="post" action="/suppress/system" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/{{ incident.qa_id }}">
            <button type="submit" class="btn">Suppress</button>
          </form>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if incident.suppressed_count > 0 %}
  <p style="margin-top:12px;color:#666;font-size:0.85em">
    {{ incident.suppressed_count }} element(s) hidden by audit_suppress.
  </p>
  {% endif %}

  <div class="subtitle" style="margin-top:20px">
    <a href="/">&larr; Back to dashboard</a>
  </div>
</body>
</html>
"""

_REMEDIATIONS_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>archi2likec4 — Remediations Review</title>
  <style>""" + _BASE_CSS + """</style>
</head>
<body>
  <div class="back"><a href="/">&larr; Back to dashboard</a></div>
  <h1>Remediations Review</h1>
  <div class="subtitle">All config-driven decisions for this conversion</div>

  {% if domain_overrides %}
  <div class="section-block">
    <h2>Domain Overrides ({{ domain_overrides|length }}) <small style="color:#999">QA-1</small></h2>
    <table>
      <thead><tr><th>#</th><th>System</th><th>&rarr; Domain</th><th>Action</th></tr></thead>
      <tbody>
        {% for name, domain in domain_overrides.items() %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ name }}</td>
          <td>{{ domain }}</td>
          <td>
            <form method="post" action="/undo-assign-domain" style="display:inline">
              <input type="hidden" name="name" value="{{ name }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">Undo</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if reviewed_systems %}
  <div class="section-block">
    <h2>Reviewed Systems ({{ reviewed_systems|length }}) <small style="color:#999">QA-3</small></h2>
    <table>
      <thead><tr><th>#</th><th>System</th><th>Action</th></tr></thead>
      <tbody>
        {% for name in reviewed_systems %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ name }}</td>
          <td>
            <form method="post" action="/undo-mark-reviewed" style="display:inline">
              <input type="hidden" name="name" value="{{ name }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">Undo</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if promote_children %}
  <div class="section-block">
    <h2>Promoted Children ({{ promote_children|length }}) <small style="color:#999">QA-4</small></h2>
    <table>
      <thead><tr><th>#</th><th>Parent</th><th>&rarr; Domain</th><th>Action</th></tr></thead>
      <tbody>
        {% for name, domain in promote_children.items() %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ name }}</td>
          <td>{{ domain }}</td>
          <td>
            <form method="post" action="/undo-promote" style="display:inline">
              <input type="hidden" name="name" value="{{ name }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">Undo</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if suppress_names %}
  <div class="section-block">
    <h2>Suppressed Systems ({{ suppress_names|length }}) <small style="color:#999">All QA</small></h2>
    <table>
      <thead><tr><th>#</th><th>System</th><th>Action</th></tr></thead>
      <tbody>
        {% for name in suppress_names %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ name }}</td>
          <td>
            <form method="post" action="/unsuppress/system" style="display:inline">
              <input type="hidden" name="name" value="{{ name }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">Unsuppress</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if suppress_incidents_list %}
  <div class="section-block">
    <h2>Suppressed Incidents ({{ suppress_incidents_list|length }})</h2>
    <table>
      <thead><tr><th>#</th><th>QA-ID</th><th>Action</th></tr></thead>
      <tbody>
        {% for qid in suppress_incidents_list %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ qid }}</td>
          <td>
            <form method="post" action="/unsuppress/incident" style="display:inline">
              <input type="hidden" name="qa_id" value="{{ qid }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">Unsuppress</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if not domain_overrides and not reviewed_systems and not promote_children and not suppress_names and not suppress_incidents_list %}
  <p>No remediations configured yet.</p>
  {% endif %}

  <div class="subtitle" style="margin-top:20px">
    <a href="/">&larr; Back to dashboard</a>
  </div>
</body>
</html>
"""


def _get_columns(incident) -> list[str]:
    """Determine table columns from affected items."""
    if not incident.affected:
        return []
    return list(incident.affected[0].keys())


def _metric_health(summary) -> dict[str, str]:
    """Compute CSS classes for metric cards based on risk thresholds."""
    h: dict[str, str] = {}
    # With Domain
    ratio = summary.assigned_count / summary.total_systems if summary.total_systems else 1
    h['domain'] = 'metric-ok' if ratio >= 0.8 else ('metric-warn' if ratio >= 0.5 else 'metric-crit')
    # Metadata
    h['meta'] = 'metric-ok' if summary.meta_completeness_pct >= 50 else (
        'metric-warn' if summary.meta_completeness_pct >= 20 else 'metric-crit')
    # Integrations
    h['intg'] = 'metric-ok' if summary.total_integrations > 0 else 'metric-crit'
    # Deploy Maps
    h['deploy'] = 'metric-ok' if summary.deployment_mappings > 0 else 'metric-crit'
    # Systems, Subsystems — neutral info
    h['systems'] = 'metric-info'
    h['subsystems'] = 'metric-info'
    return h


def run_web(
    config_path: Path | None,
    model_root: Path,
    output_dir: Path,
    port: int = 8090,
) -> None:
    """Start Flask web UI for quality audit dashboard."""
    try:
        from flask import Flask, render_template_string, request, redirect
    except ImportError:
        raise SystemExit(
            'Flask is required for web UI: pip install "archi2likec4[web]"'
        )

    from . import __version__
    from .config import load_config, save_suppress, update_config_field
    from .audit_data import compute_audit_incidents

    # Resolve config path for save operations
    resolved_config_path = config_path
    if resolved_config_path is None:
        resolved_config_path = Path('.archi2likec4.yaml')

    app = Flask(__name__)

    def _load_data():
        """Parse -> build -> validate -> compute audit incidents."""
        from .pipeline import _parse, _build, _validate
        config = load_config(config_path)
        config.model_root = model_root
        config.output_dir = output_dir
        parsed = _parse(model_root, config)
        built = _build(parsed, config)
        _, _, _, sv_unresolved, sv_total = _validate(built, config)
        summary, incidents = compute_audit_incidents(built, sv_unresolved, sv_total, config)
        available_domains = sorted(
            d for d in built.domain_systems.keys()
            if d != 'unassigned' and built.domain_systems[d]
        )
        return config, summary, incidents, available_domains

    @app.route('/')
    def dashboard():
        config, summary, incidents, available_domains = _load_data()
        active_count = sum(1 for i in incidents if not i.suppressed)
        suppressed_count = sum(1 for i in incidents if i.suppressed)
        remed_domain = len(config.domain_overrides)
        remed_reviewed = len(config.reviewed_systems)
        remed_total = remed_domain + remed_reviewed
        return render_template_string(
            _DASHBOARD_TEMPLATE,
            version=__version__,
            summary=summary,
            incidents=incidents,
            severity_colors=_SEVERITY_COLORS,
            health=_metric_health(summary),
            suppress_names=sorted(config.audit_suppress),
            suppress_incidents_list=sorted(config.audit_suppress_incidents),
            config_path=str(resolved_config_path),
            active_count=active_count,
            suppressed_count=suppressed_count,
            remed_domain=remed_domain,
            remed_reviewed=remed_reviewed,
            remed_total=remed_total,
        )

    @app.route('/incident/<qa_id>')
    def incident_detail(qa_id):
        config, summary, incidents, available_domains = _load_data()
        incident = next((i for i in incidents if i.qa_id == qa_id), None)
        if incident is None:
            return redirect('/')
        columns = _get_columns(incident)
        return render_template_string(
            _DETAIL_TEMPLATE,
            incident=incident,
            columns=columns,
            severity_colors=_SEVERITY_COLORS,
            available_domains=available_domains,
        )

    @app.route('/remediations')
    def remediations():
        config = load_config(config_path)
        return render_template_string(
            _REMEDIATIONS_TEMPLATE,
            domain_overrides=config.domain_overrides,
            reviewed_systems=sorted(config.reviewed_systems),
            promote_children=config.promote_children,
            suppress_names=sorted(config.audit_suppress),
            suppress_incidents_list=sorted(config.audit_suppress_incidents),
        )

    # ── Suppress / Unsuppress routes ──────────────────────────────────

    @app.route('/suppress/system', methods=['POST'])
    def suppress_system():
        name = request.form.get('name', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name:
            config = load_config(config_path)
            names = list(set(config.audit_suppress + [name]))
            save_suppress(resolved_config_path, names, config.audit_suppress_incidents)
            logger.info('Suppressed system: %s', name)
        return redirect(redirect_to)

    @app.route('/unsuppress/system', methods=['POST'])
    def unsuppress_system():
        name = request.form.get('name', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name:
            config = load_config(config_path)
            names = [n for n in config.audit_suppress if n != name]
            save_suppress(resolved_config_path, names, config.audit_suppress_incidents)
            logger.info('Unsuppressed system: %s', name)
        return redirect(redirect_to)

    @app.route('/suppress/incident', methods=['POST'])
    def suppress_incident():
        qa_id = request.form.get('qa_id', '').strip()
        if qa_id:
            config = load_config(config_path)
            ids = list(set(config.audit_suppress_incidents + [qa_id]))
            save_suppress(resolved_config_path, config.audit_suppress, ids)
            logger.info('Suppressed incident: %s', qa_id)
        return redirect('/')

    @app.route('/unsuppress/incident', methods=['POST'])
    def unsuppress_incident():
        qa_id = request.form.get('qa_id', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if qa_id:
            config = load_config(config_path)
            ids = [i for i in config.audit_suppress_incidents if i != qa_id]
            save_suppress(resolved_config_path, config.audit_suppress, ids)
            logger.info('Unsuppressed incident: %s', qa_id)
        return redirect(redirect_to)

    # ── Remediation routes ────────────────────────────────────────────

    @app.route('/assign-domain', methods=['POST'])
    def assign_domain():
        name = request.form.get('name', '').strip()
        domain = request.form.get('domain', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name and domain:
            config = load_config(config_path)
            overrides = dict(config.domain_overrides)
            overrides[name] = domain
            update_config_field(resolved_config_path, 'domain_overrides', overrides)
            logger.info('Assigned domain %s to system %s', domain, name)
        return redirect(redirect_to)

    @app.route('/undo-assign-domain', methods=['POST'])
    def undo_assign_domain():
        name = request.form.get('name', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name:
            config = load_config(config_path)
            overrides = dict(config.domain_overrides)
            overrides.pop(name, None)
            update_config_field(resolved_config_path, 'domain_overrides', overrides)
            logger.info('Undone domain override for %s', name)
        return redirect(redirect_to)

    @app.route('/mark-reviewed', methods=['POST'])
    def mark_reviewed():
        name = request.form.get('name', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name:
            config = load_config(config_path)
            reviewed = list(set(config.reviewed_systems + [name]))
            update_config_field(resolved_config_path, 'reviewed_systems', sorted(reviewed))
            logger.info('Marked system as reviewed: %s', name)
        return redirect(redirect_to)

    @app.route('/undo-mark-reviewed', methods=['POST'])
    def undo_mark_reviewed():
        name = request.form.get('name', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name:
            config = load_config(config_path)
            reviewed = [s for s in config.reviewed_systems if s != name]
            update_config_field(resolved_config_path, 'reviewed_systems', reviewed)
            logger.info('Undone reviewed mark for %s', name)
        return redirect(redirect_to)

    @app.route('/promote-system', methods=['POST'])
    def promote_system():
        name = request.form.get('name', '').strip()
        domain = request.form.get('domain', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name and domain:
            config = load_config(config_path)
            promote = dict(config.promote_children)
            promote[name] = domain
            update_config_field(resolved_config_path, 'promote_children', promote)
            logger.info('Promoted system %s with fallback domain %s', name, domain)
        return redirect(redirect_to)

    @app.route('/undo-promote', methods=['POST'])
    def undo_promote():
        name = request.form.get('name', '').strip()
        redirect_to = request.form.get('redirect', '/')
        if name:
            config = load_config(config_path)
            promote = dict(config.promote_children)
            promote.pop(name, None)
            update_config_field(resolved_config_path, 'promote_children', promote)
            logger.info('Undone promote for %s', name)
        return redirect(redirect_to)

    print(f'archi2likec4 web UI: http://127.0.0.1:{port}')
    app.run(host='127.0.0.1', port=port, debug=False)


def run_web_cli() -> None:
    """CLI entry point for: archi2likec4 web [--port PORT] [--config PATH] [model_root]"""
    parser = argparse.ArgumentParser(
        prog='archi2likec4 web',
        description='Start Flask web UI for quality audit dashboard',
    )
    parser.add_argument('model_root', nargs='?', default='architectural_repository/model',
                        help='Path to coArchi model directory')
    parser.add_argument('--output-dir', default='output',
                        help='Output directory (default: output)')
    parser.add_argument('--port', type=int, default=8090,
                        help='Port to listen on (default: 8090)')
    parser.add_argument('--config', type=Path, default=None, dest='config_file',
                        help='Config YAML file')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    run_web(
        config_path=args.config_file,
        model_root=Path(args.model_root),
        output_dir=Path(args.output_dir),
        port=args.port,
    )
