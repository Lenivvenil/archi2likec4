"""Flask web UI for quality audit dashboard."""

from __future__ import annotations

import argparse
import html
import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from flask import Flask

from .exceptions import Archi2LikeC4Error, ConfigError

logger = logging.getLogger('archi2likec4.web')

_SEVERITY_COLORS = {
    'Critical': '#dc3545',
    'High': '#fd7e14',
    'Medium': '#ffc107',
    'Low': '#28a745',
}

_HEALTH_DOMAIN_OK = 0.8
_HEALTH_DOMAIN_WARN = 0.5
_HEALTH_META_OK = 50
_HEALTH_META_WARN = 20


def _ui(lang: str = 'ru') -> dict[str, str]:
    """Build a flat dict of UI strings for the given language."""
    from .i18n import WEB_MESSAGES
    return {k: v.get(lang, v.get('ru', k)) for k, v in WEB_MESSAGES.items()}


def _get_columns(incident) -> list[str]:
    """Determine table columns from affected items."""
    if not incident.affected:
        return []
    return list(incident.affected[0].keys())


def _metric_health(summary) -> dict[str, str]:
    """Compute CSS classes for metric cards based on risk thresholds."""
    h: dict[str, str] = {}
    ratio = summary.assigned_count / summary.total_systems if summary.total_systems else 1
    h['domain'] = 'metric-ok' if ratio >= _HEALTH_DOMAIN_OK else (
        'metric-warn' if ratio >= _HEALTH_DOMAIN_WARN else 'metric-crit')
    h['meta'] = 'metric-ok' if summary.meta_completeness_pct >= _HEALTH_META_OK else (
        'metric-warn' if summary.meta_completeness_pct >= _HEALTH_META_WARN else 'metric-crit')
    h['intg'] = 'metric-ok' if summary.total_integrations > 0 else 'metric-crit'
    h['deploy'] = 'metric-ok' if summary.deployment_mappings > 0 else 'metric-crit'
    h['systems'] = 'metric-info'
    h['subsystems'] = 'metric-info'
    return h


def create_app(
    config_path: Path | None,
    model_root: Path,
    output_dir: Path,
) -> Flask:
    """Create Flask app for quality audit dashboard (without starting the server)."""
    try:
        from flask import Flask, abort, redirect, render_template, request, session
    except ImportError as err:
        raise SystemExit(
            'Flask is required for web UI: pip install "archi2likec4[web]"'
        ) from err

    from . import __version__
    from .audit_data import compute_audit_incidents
    from .config import _VALID_C4_ID, load_config, save_suppress, update_config_field

    if config_path is not None and not config_path.exists():
        raise SystemExit(f'Config file not found: {config_path}')
    if not model_root.is_dir():
        raise SystemExit(f'Model root directory not found: {model_root}')

    resolved_config_path = config_path
    if resolved_config_path is None:
        resolved_config_path = Path('.archi2likec4.yaml')

    template_dir = Path(__file__).parent / 'templates'
    app = Flask(__name__, template_folder=str(template_dir))
    app.secret_key = secrets.token_hex(32)

    def _safe_redirect(url: str) -> str:
        """Validate redirect URL to prevent open redirect attacks."""
        if not url or not url.startswith('/') or url.startswith('//'):
            return '/'
        return url

    @app.context_processor
    def inject_csrf():
        """Inject CSRF token into all templates and provide csrf_field() helper."""
        if '_csrf' not in session:
            session['_csrf'] = secrets.token_hex(32)
        token = session['_csrf']

        from markupsafe import Markup
        def csrf_field():
            return Markup(f'<input type="hidden" name="_csrf_token" value="{token}">')

        return {'csrf_token': token, 'csrf_field': csrf_field}

    @app.before_request
    def _csrf_check():
        """Reject POST requests without valid CSRF token, with Origin/Referer as secondary check."""
        if request.method != 'POST':
            return None
        # Primary: session-based CSRF token check
        form_token = request.form.get('_csrf_token', '')
        session_token = session.get('_csrf', '')
        if not session_token or not form_token or form_token != session_token:
            abort(403)
        # Secondary: Origin/Referer cross-origin check
        host_parsed = urlparse(request.host_url)
        host_netloc = host_parsed.netloc
        origin = request.headers.get('Origin') or ''
        referer = request.headers.get('Referer') or ''
        if origin:
            origin_parsed = urlparse(origin)
            if origin_parsed.netloc != host_netloc:
                abort(403)
        elif referer:
            referer_parsed = urlparse(referer)
            if referer_parsed.netloc != host_netloc:
                abort(403)
        return None

    _cache: dict[str, object] = {}
    _CACHE_TTL = 30  # seconds

    def _load_data():
        """Parse -> build -> validate -> compute audit incidents (cached for _CACHE_TTL seconds)."""
        import time
        now = time.monotonic()
        if '_data' in _cache and now - _cache.get('_ts', 0) < _CACHE_TTL:
            return _cache['_data']

        from .generators.views import generate_solution_views
        from .pipeline import _build, _build_solution_view_index, _parse, _validate
        try:
            config = load_config(config_path)
        except (FileNotFoundError, ConfigError, OSError) as e:
            raise ConfigError(str(e)) from e
        config.model_root = model_root
        config.output_dir = output_dir
        try:
            parsed = _parse(model_root, config)
            built = _build(parsed, config)
        except Archi2LikeC4Error:
            raise
        except Exception as e:
            raise Archi2LikeC4Error(f'Pipeline error: {e}') from e
        sys_subdomain = _build_solution_view_index(built)
        _, sv_unresolved, sv_total = generate_solution_views(
            built.solution_views, built.archi_to_c4, built.sys_domain,
            built.relationships,
            promoted_archi_to_c4=built.promoted_archi_to_c4,
            tech_archi_to_c4=built.tech_archi_to_c4,
            entity_archi_ids={e.archi_id for e in built.entities},
            deployment_map=built.deployment_map,
            sys_subdomain=sys_subdomain or None,
            deployment_env=config.deployment_env,
        )
        warnings, errors = _validate(built, config, sv_unresolved=sv_unresolved, sv_total=sv_total)
        summary, incidents = compute_audit_incidents(built, sv_unresolved, sv_total, config)
        available_domains = sorted(
            d for d in built.domain_systems
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

    @app.errorhandler(Archi2LikeC4Error)
    def _handle_runtime_error(error):
        return f'<h1>Configuration Error</h1><pre>{html.escape(str(error))}</pre>', 500

    @app.route('/')
    def dashboard():
        config, summary, incidents, available_domains, built = _load_data()
        lang = getattr(config, 'language', 'ru')
        active_count = sum(1 for i in incidents if not i.suppressed)
        suppressed_count = sum(1 for i in incidents if i.suppressed)
        remed_domain = len(config.domain_overrides)
        remed_reviewed = len(config.reviewed_systems)
        remed_total = remed_domain + remed_reviewed
        return render_template(
            'dashboard.html',
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
        return render_template(
            'detail.html',
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
        except (FileNotFoundError, ConfigError, OSError) as e:
            raise ConfigError(str(e)) from e

    @app.route('/remediations')
    def remediations():
        config = _load_config_safe()
        lang = getattr(config, 'language', 'ru')
        return render_template(
            'remediations.html',
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
        name = request.form.get('name', '').strip()
        domain = request.form.get('domain', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name and domain:
            if not _VALID_C4_ID.match(domain):
                return f'Invalid domain identifier: {html.escape(domain)}', 400
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
        name = request.form.get('name', '').strip()
        domain = request.form.get('domain', '').strip()
        redirect_to = _safe_redirect(request.form.get('redirect', '/'))
        if name and domain:
            if not _VALID_C4_ID.match(domain):
                return f'Invalid domain identifier: {html.escape(domain)}', 400
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

        subdomain_names: dict[str, str] = {}
        for sd in getattr(built, 'subdomains', []):
            subdomain_names[sd.c4_id] = sd.name

        domain_groups: dict[str, dict[str, list]] = {}
        domain_totals: dict[str, int] = {}
        for domain_id, sys_list in sorted(built.domain_systems.items()):
            if sys_list:
                sd_map: dict[str, list] = {}
                for sys in sorted(sys_list, key=lambda s: s.name):
                    sd_key = getattr(sys, 'subdomain', '') or ''
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
            t=_ui(lang), lang=lang,
            version=__version__,
            domain_groups=domain_groups,
            domain_totals=domain_totals,
            subdomain_names=subdomain_names,
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
