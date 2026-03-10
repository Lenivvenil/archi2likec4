"""Flask web UI for quality audit dashboard."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logger = logging.getLogger('archi2likec4.web')

# ── Web UI i18n ─────────────────────────────────────────────────────────

_UI_STRINGS: dict[str, dict[str, str]] = {
    'title': {'ru': 'Аудит качества', 'en': 'Quality Audit'},
    'dashboard': {'ru': 'Панель аудита качества', 'en': 'Quality Audit Dashboard'},
    'systems': {'ru': 'Системы', 'en': 'Systems'},
    'subsystems': {'ru': 'Подсистемы', 'en': 'Subsystems'},
    'metadata': {'ru': 'Метаданные', 'en': 'Metadata'},
    'with_domain': {'ru': 'С доменом', 'en': 'With Domain'},
    'integrations': {'ru': 'Интеграции', 'en': 'Integrations'},
    'deploy_maps': {'ru': 'Deploy-маппинги', 'en': 'Deploy Maps'},
    'suppressed': {'ru': 'Скрыто', 'en': 'Suppressed'},
    'remediations': {'ru': 'Ремедиации', 'en': 'Remediations'},
    'review_all': {'ru': 'Обзор всех', 'en': 'Review all'},
    'incidents': {'ru': 'Инциденты', 'en': 'Incidents'},
    'severity': {'ru': 'Серьёзность', 'en': 'Severity'},
    'incident': {'ru': 'Инцидент', 'en': 'Incident'},
    'count': {'ru': 'Кол-во', 'en': 'Count'},
    'actions': {'ru': 'Действия', 'en': 'Actions'},
    'details': {'ru': 'Подробнее', 'en': 'Details'},
    'suppress': {'ru': 'Скрыть', 'en': 'Suppress'},
    'unsuppress': {'ru': 'Показать', 'en': 'Unsuppress'},
    'no_incidents': {'ru': 'Инцидентов качества не найдено.', 'en': 'No quality incidents found.'},
    'hierarchy': {'ru': 'Иерархия', 'en': 'Hierarchy'},
    'refresh': {'ru': 'Обновить', 'en': 'Refresh'},
    'back': {'ru': 'Назад к панели', 'en': 'Back to dashboard'},
    'problem': {'ru': 'Проблема', 'en': 'Problem'},
    'impact': {'ru': 'Влияние', 'en': 'Impact'},
    'remediation': {'ru': 'Рекомендация', 'en': 'Remediation'},
    'affected': {'ru': 'Затронутые элементы', 'en': 'Affected Elements'},
    'action': {'ru': 'Действие', 'en': 'Action'},
    'assign': {'ru': 'Назначить', 'en': 'Assign'},
    'mark_reviewed': {'ru': 'Проверено', 'en': 'Mark reviewed'},
    'promote': {'ru': 'Промоутить', 'en': 'Promote'},
    'undo': {'ru': 'Отменить', 'en': 'Undo'},
    'hidden_by_suppress': {'ru': 'элемент(ов) скрыто через audit_suppress.', 'en': 'element(s) hidden by audit_suppress.'},
    'remed_review': {'ru': 'Обзор ремедиаций', 'en': 'Remediations Review'},
    'remed_subtitle': {'ru': 'Все конфиг-решения для этой конвертации', 'en': 'All config-driven decisions for this conversion'},
    'domain_overrides': {'ru': 'Назначения доменов', 'en': 'Domain Overrides'},
    'reviewed_systems': {'ru': 'Проверенные системы', 'en': 'Reviewed Systems'},
    'promoted_children': {'ru': 'Промоутированные', 'en': 'Promoted Children'},
    'suppressed_systems': {'ru': 'Скрытые системы', 'en': 'Suppressed Systems'},
    'suppressed_incidents': {'ru': 'Скрытые инциденты', 'en': 'Suppressed Incidents'},
    'no_remed': {'ru': 'Ремедиации ещё не настроены.', 'en': 'No remediations configured yet.'},
    'system_hierarchy': {'ru': 'Иерархия систем', 'en': 'System Hierarchy'},
    'system': {'ru': 'Система', 'en': 'System'},
    'domain': {'ru': 'Домен', 'en': 'Domain'},
    'parent': {'ru': 'Родитель', 'en': 'Parent'},
    'dark_mode': {'ru': 'Тёмная тема', 'en': 'Dark mode'},
    'light_mode': {'ru': 'Светлая тема', 'en': 'Light mode'},
}


def _ui(lang: str = 'ru') -> dict[str, str]:
    """Build a flat dict of UI strings for the given language."""
    return {k: v.get(lang, v.get('ru', k)) for k, v in _UI_STRINGS.items()}


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
.theme-toggle { position: fixed; top: 12px; right: 16px; cursor: pointer;
                background: #e9ecef; border: 1px solid #dee2e6; border-radius: 6px;
                padding: 4px 10px; font-size: 0.8em; z-index: 100; }
/* Dark theme */
[data-theme="dark"] { color-scheme: dark; }
[data-theme="dark"] body { background: #1a1a2e; color: #e0e0e0; }
[data-theme="dark"] .metric { background: #16213e; border-color: #334155; }
[data-theme="dark"] table { background: #16213e; border-color: #334155; }
[data-theme="dark"] th { background: #0f3460; color: #e0e0e0; }
[data-theme="dark"] td { border-color: #334155; }
[data-theme="dark"] tr:hover { background: #1a1a3e; }
[data-theme="dark"] .suppress-bar { background: #332b00; border-color: #665600; color: #e0e0e0; }
[data-theme="dark"] .remed-bar { background: #003320; border-color: #006644; color: #e0e0e0; }
[data-theme="dark"] .suppress-item { background: #334155; color: #e0e0e0; }
[data-theme="dark"] .btn { background: #16213e; border-color: #334155; color: #e0e0e0; }
[data-theme="dark"] .btn:hover { background: #0f3460; }
[data-theme="dark"] a { color: #5dadec; }
[data-theme="dark"] .subtitle { color: #999; }
[data-theme="dark"] .metric-label { color: #999; }
[data-theme="dark"] .detail-block { background: #16213e; border-color: #334155; }
[data-theme="dark"] .detail-block strong { color: #bbb; }
[data-theme="dark"] pre { color: #bbb; }
[data-theme="dark"] .section-block { background: #16213e; border-color: #334155; }
[data-theme="dark"] .hier-domain h3 { background: #0f3460; color: #e0e0e0; }
[data-theme="dark"] .hier-sys { border-color: #334155; background: #16213e !important; }
[data-theme="dark"] .hier-sub { color: #999; }
[data-theme="dark"] .theme-toggle { background: #16213e; border-color: #334155; color: #e0e0e0; }
"""

_THEME_JS = """\
<script>
(function() {
  var t = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.addEventListener('DOMContentLoaded', function() {
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.textContent = t === 'dark' ? '☀️' : '🌙';
      btn.addEventListener('click', function() {
        t = t === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', t);
        localStorage.setItem('theme', t);
        btn.textContent = t === 'dark' ? '☀️' : '🌙';
      });
    }
  });
})();
</script>
"""

_DASHBOARD_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>archi2likec4 — {{ t.title }}</title>
  <style>""" + _BASE_CSS + """</style>
  """ + _THEME_JS + """
</head>
<body>
  <button id="theme-toggle" class="theme-toggle"></button>
  <h1>archi2likec4 — {{ t.dashboard }}</h1>
  <div class="subtitle">v{{ version }}</div>

  <div class="metrics">
    <div class="metric {{ health.systems }}">
      <div class="metric-value">{{ summary.total_systems }}</div>
      <div class="metric-label">{{ t.systems }}</div>
    </div>
    <div class="metric {{ health.subsystems }}">
      <div class="metric-value">{{ summary.total_subsystems }}</div>
      <div class="metric-label">{{ t.subsystems }}</div>
    </div>
    <div class="metric {{ health.meta }}">
      <div class="metric-value">{{ summary.meta_completeness_pct }}%</div>
      <div class="metric-label">{{ t.metadata }}</div>
    </div>
    <div class="metric {{ health.domain }}">
      <div class="metric-value">{{ summary.assigned_count }}/{{ summary.total_systems }}</div>
      <div class="metric-label">{{ t.with_domain }}</div>
    </div>
    <div class="metric {{ health.intg }}">
      <div class="metric-value">{{ summary.total_integrations }}</div>
      <div class="metric-label">{{ t.integrations }}</div>
    </div>
    <div class="metric {{ health.deploy }}">
      <div class="metric-value">{{ summary.deployment_mappings }}</div>
      <div class="metric-label">{{ t.deploy_maps }}</div>
    </div>
  </div>

  {% if suppress_names or suppress_incidents_list %}
  <div class="suppress-bar">
    <strong>{{ t.suppressed }}:</strong>
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
    <strong>{{ t.remediations }}:</strong>
    {% if remed_domain > 0 %}{{ remed_domain }} domain override{{ 's' if remed_domain != 1 }}{% endif %}
    {% if remed_reviewed > 0 %}{% if remed_domain > 0 %}, {% endif %}{{ remed_reviewed }} reviewed{% endif %}
    &rarr; <a href="/remediations">{{ t.review_all }}</a>
  </div>
  {% endif %}

  <h2>{{ t.incidents }} ({{ active_count }}{% if suppressed_count > 0 %}, {{ suppressed_count }} {{ t.suppressed|lower }}{% endif %})</h2>
  {% if incidents %}
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>{{ t.severity }}</th>
        <th>{{ t.incident }}</th>
        <th style="text-align:right">{{ t.count }}</th>
        <th>{{ t.actions }}</th>
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
          {% if inc.suppressed %}</s> <small>({{ t.suppressed|lower }})</small>{% endif %}
        </td>
        <td style="text-align:right">{{ inc.count }}</td>
        <td>
          {% if inc.suppressed %}
            <form method="post" action="/unsuppress/incident" style="display:inline">
              <input type="hidden" name="qa_id" value="{{ inc.qa_id }}">
              <button type="submit" class="btn btn-success">{{ t.unsuppress }}</button>
            </form>
          {% else %}
            <a href="/incident/{{ inc.qa_id }}" class="btn">{{ t.details }}</a>
            <form method="post" action="/suppress/incident" style="display:inline">
              <input type="hidden" name="qa_id" value="{{ inc.qa_id }}">
              <button type="submit" class="btn">{{ t.suppress }}</button>
            </form>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>{{ t.no_incidents }}</p>
  {% endif %}

  <div class="subtitle" style="margin-top:20px">
    Config: {{ config_path }} |
    <a href="/hierarchy">{{ t.hierarchy }}</a> |
    <a href="/">{{ t.refresh }}</a>
  </div>
</body>
</html>
"""

_DETAIL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ incident.qa_id }} — {{ incident.title }}</title>
  <style>""" + _BASE_CSS + """</style>
  """ + _THEME_JS + """
</head>
<body>
  <button id="theme-toggle" class="theme-toggle"></button>
  <div class="back"><a href="/">&larr; {{ t.back }}</a></div>

  <h1>
    {{ incident.qa_id }}
    <span class="badge" style="background:{{ severity_colors[incident.severity] }}">{{ incident.severity }}</span>
    {{ incident.title }}
    ({{ incident.count }})
    {% if incident.suppressed %}<small style="color:#999">(suppressed)</small>{% endif %}
  </h1>

  <div class="detail-block">
    <p><strong>{{ t.problem }}:</strong> {{ incident.description }}</p>
    <p><strong>{{ t.impact }}:</strong> {{ incident.impact }}</p>
    <p><strong>{{ t.remediation }}:</strong></p>
    <pre>{{ incident.remediation }}</pre>
  </div>

  {% if incident.affected %}
  <h2>{{ t.affected }} ({{ incident.affected|length }}{% if incident.count > incident.affected|length %} of {{ incident.count }}{% endif %})</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        {% for key in columns %}
        <th>{{ key }}</th>
        {% endfor %}
        <th>{{ t.action }}</th>
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
            <button type="submit" class="btn btn-success">{{ t.assign }}</button>
          </form>
          {% elif incident.qa_id == 'QA-3' and 'name' in item %}
          <form method="post" action="/mark-reviewed" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/QA-3">
            <button type="submit" class="btn btn-success">{{ t.mark_reviewed }}</button>
          </form>
          {% elif incident.qa_id == 'QA-4' and 'name' in item %}
          <form method="post" action="/promote-system" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/QA-4">
            <select name="domain" class="btn">
              {% for d in available_domains %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
            </select>
            <button type="submit" class="btn btn-success">{{ t.promote }}</button>
          </form>
          {% endif %}
          {% if 'name' in item %}
          <form method="post" action="/suppress/system" style="display:inline">
            <input type="hidden" name="name" value="{{ item['name'] }}">
            <input type="hidden" name="redirect" value="/incident/{{ incident.qa_id }}">
            <button type="submit" class="btn">{{ t.suppress }}</button>
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
    {{ incident.suppressed_count }} {{ t.hidden_by_suppress }}
  </p>
  {% endif %}

  <div class="subtitle" style="margin-top:20px">
    <a href="/">&larr; {{ t.back }}</a>
  </div>
</body>
</html>
"""

_REMEDIATIONS_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>archi2likec4 — {{ t.remed_review }}</title>
  <style>""" + _BASE_CSS + """</style>
  """ + _THEME_JS + """
</head>
<body>
  <button id="theme-toggle" class="theme-toggle"></button>
  <div class="back"><a href="/">&larr; {{ t.back }}</a></div>
  <h1>{{ t.remed_review }}</h1>
  <div class="subtitle">{{ t.remed_subtitle }}</div>

  {% if domain_overrides %}
  <div class="section-block">
    <h2>{{ t.domain_overrides }} ({{ domain_overrides|length }}) <small style="color:#999">QA-1</small></h2>
    <table>
      <thead><tr><th>#</th><th>{{ t.system }}</th><th>&rarr; {{ t.domain }}</th><th>{{ t.action }}</th></tr></thead>
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
              <button type="submit" class="btn btn-danger">{{ t.undo }}</button>
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
    <h2>{{ t.reviewed_systems }} ({{ reviewed_systems|length }}) <small style="color:#999">QA-3</small></h2>
    <table>
      <thead><tr><th>#</th><th>{{ t.system }}</th><th>{{ t.action }}</th></tr></thead>
      <tbody>
        {% for name in reviewed_systems %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ name }}</td>
          <td>
            <form method="post" action="/undo-mark-reviewed" style="display:inline">
              <input type="hidden" name="name" value="{{ name }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">{{ t.undo }}</button>
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
    <h2>{{ t.promoted_children }} ({{ promote_children|length }}) <small style="color:#999">QA-4</small></h2>
    <table>
      <thead><tr><th>#</th><th>{{ t.parent }}</th><th>&rarr; {{ t.domain }}</th><th>{{ t.action }}</th></tr></thead>
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
              <button type="submit" class="btn btn-danger">{{ t.undo }}</button>
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
    <h2>{{ t.suppressed_systems }} ({{ suppress_names|length }}) <small style="color:#999">All QA</small></h2>
    <table>
      <thead><tr><th>#</th><th>{{ t.system }}</th><th>{{ t.action }}</th></tr></thead>
      <tbody>
        {% for name in suppress_names %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ name }}</td>
          <td>
            <form method="post" action="/unsuppress/system" style="display:inline">
              <input type="hidden" name="name" value="{{ name }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">{{ t.unsuppress }}</button>
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
    <h2>{{ t.suppressed_incidents }} ({{ suppress_incidents_list|length }})</h2>
    <table>
      <thead><tr><th>#</th><th>QA-ID</th><th>{{ t.action }}</th></tr></thead>
      <tbody>
        {% for qid in suppress_incidents_list %}
        <tr>
          <td>{{ loop.index }}</td>
          <td>{{ qid }}</td>
          <td>
            <form method="post" action="/unsuppress/incident" style="display:inline">
              <input type="hidden" name="qa_id" value="{{ qid }}">
              <input type="hidden" name="redirect" value="/remediations">
              <button type="submit" class="btn btn-danger">{{ t.unsuppress }}</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  {% if not domain_overrides and not reviewed_systems and not promote_children and not suppress_names and not suppress_incidents_list %}
  <p>{{ t.no_remed }}</p>
  {% endif %}

  <div class="subtitle" style="margin-top:20px">
    <a href="/">&larr; {{ t.back }}</a>
  </div>
</body>
</html>
"""


_HIERARCHY_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>archi2likec4 — {{ t.system_hierarchy }}</title>
  <style>""" + _BASE_CSS + """
  .hier-domain { margin-bottom: 20px; }
  .hier-domain h3 { background: #e9ecef; padding: 8px 12px; border-radius: 6px 6px 0 0;
                     margin: 0; font-size: 0.95em; }
  .hier-sys { padding: 6px 12px; border: 1px solid #dee2e6; border-top: none; font-size: 0.9em; }
  .hier-sys:last-child { border-radius: 0 0 6px 6px; }
  .hier-sub { margin-left: 24px; color: #555; font-size: 0.85em; }
  .hier-fn-count { color: #999; font-size: 0.8em; }
  .hier-tag { font-size: 0.7em; padding: 1px 6px; border-radius: 3px; color: #fff; margin-left: 4px; }
  .tag-promoted { background: #6f42c1; }
  .tag-to_review { background: #fd7e14; }
  .tag-external { background: #6c757d; }
  </style>
  """ + _THEME_JS + """
</head>
<body>
  <button id="theme-toggle" class="theme-toggle"></button>
  <div class="back"><a href="/">&larr; {{ t.back }}</a></div>
  <h1>{{ t.system_hierarchy }}</h1>
  <div class="subtitle">{{ total_systems }} {{ t.systems|lower }}, {{ total_subsystems }} {{ t.subsystems|lower }}</div>

  {% for domain_id, systems in domain_groups.items() %}
  <div class="hier-domain">
    <h3>{{ domain_id }} ({{ systems|length }})</h3>
    {% for sys in systems %}
    <div class="hier-sys" style="background:#fff">
      <strong>{{ sys.name }}</strong>
      <code style="color:#999;font-size:0.8em">{{ sys.c4_id }}</code>
      {% if sys.name.split('.')[0] in promoted_parents %}
        <span class="hier-tag tag-promoted">promoted</span>
      {% endif %}
      {% for tag in sys.tags %}
        <span class="hier-tag tag-{{ tag }}">{{ tag }}</span>
      {% endfor %}
      {% if sys.functions %}
        <span class="hier-fn-count">{{ sys.functions|length }} fn</span>
      {% endif %}
      {% if sys.subsystems %}
      {% for sub in sys.subsystems|sort(attribute='name') %}
        <div class="hier-sub">
          &#x2514; {{ sub.name }} <code style="color:#bbb;font-size:0.8em">{{ sub.c4_id }}</code>
          {% if sub.functions %}
            <span class="hier-fn-count">{{ sub.functions|length }} fn</span>
          {% endif %}
        </div>
      {% endfor %}
      {% endif %}
    </div>
    {% endfor %}
  </div>
  {% endfor %}

  <div class="subtitle" style="margin-top:20px">
    <a href="/">&larr; {{ t.back }}</a>
  </div>
</body>
</html>
"""


def _get_columns(incident) -> list[str]:
    """Determine table columns from affected items."""
    if not incident.affected:
        return []
    return list(incident.affected[0].keys())


_HEALTH_DOMAIN_OK = 0.8
_HEALTH_DOMAIN_WARN = 0.5
_HEALTH_META_OK = 50
_HEALTH_META_WARN = 20


def _metric_health(summary) -> dict[str, str]:
    """Compute CSS classes for metric cards based on risk thresholds."""
    h: dict[str, str] = {}
    # With Domain
    ratio = summary.assigned_count / summary.total_systems if summary.total_systems else 1
    h['domain'] = 'metric-ok' if ratio >= _HEALTH_DOMAIN_OK else (
        'metric-warn' if ratio >= _HEALTH_DOMAIN_WARN else 'metric-crit')
    # Metadata
    h['meta'] = 'metric-ok' if summary.meta_completeness_pct >= _HEALTH_META_OK else (
        'metric-warn' if summary.meta_completeness_pct >= _HEALTH_META_WARN else 'metric-crit')
    # Integrations
    h['intg'] = 'metric-ok' if summary.total_integrations > 0 else 'metric-crit'
    # Deploy Maps
    h['deploy'] = 'metric-ok' if summary.deployment_mappings > 0 else 'metric-crit'
    # Systems, Subsystems — neutral info
    h['systems'] = 'metric-info'
    h['subsystems'] = 'metric-info'
    return h


def create_app(
    config_path: Path | None,
    model_root: Path,
    output_dir: Path,
) -> 'Flask':
    """Create Flask app for quality audit dashboard (without starting the server)."""
    try:
        from flask import Flask, render_template_string, request, redirect
    except ImportError:
        raise SystemExit(
            'Flask is required for web UI: pip install "archi2likec4[web]"'
        )

    from . import __version__
    from .config import load_config, save_suppress, update_config_field
    from .audit_data import compute_audit_incidents

    # Fail-fast: validate paths at startup, not on first request
    if config_path is not None and not config_path.exists():
        raise SystemExit(f'Config file not found: {config_path}')
    if not model_root.is_dir():
        raise SystemExit(f'Model root directory not found: {model_root}')

    # Resolve config path for save operations
    resolved_config_path = config_path
    if resolved_config_path is None:
        resolved_config_path = Path('.archi2likec4.yaml')

    app = Flask(__name__)
    app.secret_key = __import__('secrets').token_hex(32)

    @app.before_request
    def _csrf_check():
        """Reject cross-origin POST requests (Origin/Referer check)."""
        if request.method != 'POST':
            return None
        origin = request.headers.get('Origin') or ''
        referer = request.headers.get('Referer') or ''
        host = request.host_url.rstrip('/')
        if origin:
            if not origin.startswith(host):
                from flask import abort
                abort(403, 'Cross-origin POST rejected')
        elif referer:
            if not referer.startswith(host):
                from flask import abort
                abort(403, 'Cross-origin POST rejected')
        else:
            # No Origin or Referer — reject to prevent blind CSRF
            from flask import abort
            abort(403, 'POST without Origin/Referer header rejected')
        return None

    def _safe_redirect(url: str) -> str:
        """Validate redirect URL to prevent open redirect attacks."""
        if not url or not url.startswith('/') or url.startswith('//'):
            return '/'
        return url

    _cache: dict[str, object] = {}
    _CACHE_TTL = 30  # seconds

    def _load_data():
        """Parse -> build -> validate -> compute audit incidents (cached for _CACHE_TTL seconds)."""
        import time
        now = time.monotonic()
        if '_data' in _cache and now - _cache.get('_ts', 0) < _CACHE_TTL:
            return _cache['_data']

        from .pipeline import _parse, _build, _validate
        try:
            config = load_config(config_path)
        except (FileNotFoundError, ValueError, OSError) as e:
            raise RuntimeError(f'Configuration error: {e}') from e
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
        result = config, summary, incidents, available_domains, built
        _cache['_data'] = result
        _cache['_ts'] = now
        return result

    def _invalidate_cache():
        """Clear cached data (called after config modifications)."""
        _cache.clear()

    @app.after_request
    def _after_request(response):
        """Invalidate cache after any POST (config-modifying) request."""
        if request.method == 'POST':
            _invalidate_cache()
        return response

    @app.errorhandler(RuntimeError)
    def _handle_runtime_error(error):
        return f'<h1>Configuration Error</h1><pre>{error}</pre>', 500

    @app.route('/')
    def dashboard():
        config, summary, incidents, available_domains, built = _load_data()
        lang = getattr(config, 'language', 'ru')
        active_count = sum(1 for i in incidents if not i.suppressed)
        suppressed_count = sum(1 for i in incidents if i.suppressed)
        remed_domain = len(config.domain_overrides)
        remed_reviewed = len(config.reviewed_systems)
        remed_total = remed_domain + remed_reviewed
        return render_template_string(
            _DASHBOARD_TEMPLATE,
            t=_ui(lang), lang=lang,
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
        config, summary, incidents, available_domains, built = _load_data()
        lang = getattr(config, 'language', 'ru')
        incident = next((i for i in incidents if i.qa_id == qa_id), None)
        if incident is None:
            return redirect('/')
        columns = _get_columns(incident)
        return render_template_string(
            _DETAIL_TEMPLATE,
            t=_ui(lang), lang=lang,
            incident=incident,
            columns=columns,
            severity_colors=_SEVERITY_COLORS,
            available_domains=available_domains,
        )

    def _load_config_safe():
        """Load config with error handling for web routes."""
        try:
            return load_config(config_path)
        except (FileNotFoundError, ValueError, OSError) as e:
            raise RuntimeError(f'Configuration error: {e}') from e

    @app.route('/remediations')
    def remediations():
        config = _load_config_safe()
        lang = getattr(config, 'language', 'ru')
        return render_template_string(
            _REMEDIATIONS_TEMPLATE,
            t=_ui(lang), lang=lang,
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
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name:
            config = _load_config_safe()
            names = list(set(config.audit_suppress + [name]))
            save_suppress(resolved_config_path, names, config.audit_suppress_incidents)
            logger.info('Suppressed system: %s', name)
        return redirect(redirect_to)

    @app.route('/unsuppress/system', methods=['POST'])
    def unsuppress_system():
        name = request.form.get('name', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name:
            config = _load_config_safe()
            names = [n for n in config.audit_suppress if n != name]
            save_suppress(resolved_config_path, names, config.audit_suppress_incidents)
            logger.info('Unsuppressed system: %s', name)
        return redirect(redirect_to)

    @app.route('/suppress/incident', methods=['POST'])
    def suppress_incident():
        qa_id = request.form.get('qa_id', '').strip()
        if qa_id:
            config = _load_config_safe()
            ids = list(set(config.audit_suppress_incidents + [qa_id]))
            save_suppress(resolved_config_path, config.audit_suppress, ids)
            logger.info('Suppressed incident: %s', qa_id)
        return redirect('/')

    @app.route('/unsuppress/incident', methods=['POST'])
    def unsuppress_incident():
        qa_id = request.form.get('qa_id', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if qa_id:
            config = _load_config_safe()
            ids = [i for i in config.audit_suppress_incidents if i != qa_id]
            save_suppress(resolved_config_path, config.audit_suppress, ids)
            logger.info('Unsuppressed incident: %s', qa_id)
        return redirect(redirect_to)

    # ── Remediation routes ────────────────────────────────────────────

    @app.route('/assign-domain', methods=['POST'])
    def assign_domain():
        from .utils import sanitize_path_segment
        name = request.form.get('name', '').strip()
        domain = sanitize_path_segment(request.form.get('domain', '').strip())
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name and domain:
            config = _load_config_safe()
            overrides = dict(config.domain_overrides)
            overrides[name] = domain
            update_config_field(resolved_config_path, 'domain_overrides', overrides)
            logger.info('Assigned domain %s to system %s', domain, name)
        return redirect(redirect_to)

    @app.route('/undo-assign-domain', methods=['POST'])
    def undo_assign_domain():
        name = request.form.get('name', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name:
            config = _load_config_safe()
            overrides = dict(config.domain_overrides)
            overrides.pop(name, None)
            update_config_field(resolved_config_path, 'domain_overrides', overrides)
            logger.info('Undone domain override for %s', name)
        return redirect(redirect_to)

    @app.route('/mark-reviewed', methods=['POST'])
    def mark_reviewed():
        name = request.form.get('name', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name:
            config = _load_config_safe()
            reviewed = list(set(config.reviewed_systems + [name]))
            update_config_field(resolved_config_path, 'reviewed_systems', sorted(reviewed))
            logger.info('Marked system as reviewed: %s', name)
        return redirect(redirect_to)

    @app.route('/undo-mark-reviewed', methods=['POST'])
    def undo_mark_reviewed():
        name = request.form.get('name', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name:
            config = _load_config_safe()
            reviewed = [s for s in config.reviewed_systems if s != name]
            update_config_field(resolved_config_path, 'reviewed_systems', reviewed)
            logger.info('Undone reviewed mark for %s', name)
        return redirect(redirect_to)

    @app.route('/promote-system', methods=['POST'])
    def promote_system():
        from .utils import sanitize_path_segment
        name = request.form.get('name', '').strip()
        domain = sanitize_path_segment(request.form.get('domain', '').strip())
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name and domain:
            config = _load_config_safe()
            promote = dict(config.promote_children)
            promote[name] = domain
            update_config_field(resolved_config_path, 'promote_children', promote)
            logger.info('Promoted system %s with fallback domain %s', name, domain)
        return redirect(redirect_to)

    @app.route('/undo-promote', methods=['POST'])
    def undo_promote():
        name = request.form.get('name', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name:
            config = _load_config_safe()
            promote = dict(config.promote_children)
            promote.pop(name, None)
            update_config_field(resolved_config_path, 'promote_children', promote)
            logger.info('Undone promote for %s', name)
        return redirect(redirect_to)

    @app.route('/hierarchy')
    def hierarchy():
        config, summary, incidents, available_domains, built = _load_data()
        lang = getattr(config, 'language', 'ru')

        # Group systems by domain
        domain_groups: dict[str, list] = {}
        for domain_id, sys_list in sorted(built.domain_systems.items()):
            if sys_list:
                domain_groups[domain_id] = sorted(sys_list, key=lambda s: s.name)

        # Promoted info
        promoted_parents = set(config.promote_children.keys())

        return render_template_string(
            _HIERARCHY_TEMPLATE,
            t=_ui(lang), lang=lang,
            version=__version__,
            domain_groups=domain_groups,
            promoted_parents=promoted_parents,
            total_systems=summary.total_systems,
            total_subsystems=summary.total_subsystems,
        )

    return app


def run_web(
    config_path: Path | None,
    model_root: Path,
    output_dir: Path,
    port: int = 8090,
) -> None:
    """Create and start Flask web UI for quality audit dashboard."""
    app = create_app(config_path, model_root, output_dir)
    logger.info('archi2likec4 web UI: http://127.0.0.1:%d', port)
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
