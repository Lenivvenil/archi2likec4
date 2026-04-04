"""Flask web UI for quality audit dashboard."""

from __future__ import annotations

import argparse
import html
import logging
import os
import secrets
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from flask import Flask

from .exceptions import Archi2LikeC4Error, ConfigError

logger = logging.getLogger(__name__)

_HEALTH_DOMAIN_OK = 0.8
_HEALTH_DOMAIN_WARN = 0.5
_HEALTH_META_OK = 50
_HEALTH_META_WARN = 20


def _ui(lang: str = 'ru') -> dict[str, str]:
    """Build a flat dict of UI strings for the given language."""
    from .i18n import WEB_MESSAGES
    return {k: v.get(lang, v.get('ru', k)) for k, v in WEB_MESSAGES.items()}


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
        from flask import Flask, abort, request, session
    except ImportError as err:
        raise SystemExit(
            'Flask is required for web UI: pip install "archi2likec4[web]"'
        ) from err

    from . import __version__
    from .audit_data import compute_audit_incidents
    from .config import _VALID_C4_ID, load_config, save_suppress, update_config_field
    from .web_routes import init_routes

    if config_path is not None and not config_path.exists():
        raise SystemExit(f'Config file not found: {config_path}')
    if not model_root.is_dir():
        raise SystemExit(f'Model root directory not found: {model_root}')

    resolved_config_path = config_path
    if resolved_config_path is None:
        resolved_config_path = Path('.archi2likec4.yaml')

    template_dir = Path(__file__).parent / 'templates'
    app = Flask(__name__, template_folder=str(template_dir))
    explicit_key = os.environ.get('FLASK_SECRET_KEY')
    if explicit_key:
        app.secret_key = explicit_key
    else:
        logger.warning('FLASK_SECRET_KEY not set — using random secret; '
                       'sessions will not survive restarts or multi-worker deployments')
        app.secret_key = secrets.token_hex(32)

    def _safe_redirect(url: str) -> str:
        """Validate redirect URL to prevent open redirect attacks."""
        if not url or not url.startswith('/') or url.startswith('//'):
            return '/'
        return url

    # ── CSRF middleware ──────────────────────────────────────────────────

    @app.context_processor
    def inject_csrf():
        """Inject CSRF token into all templates and provide csrf_field() helper."""
        if '_csrf' not in session:
            session['_csrf'] = secrets.token_hex(32)
        token = session['_csrf']

        from markupsafe import Markup
        def csrf_field():
            return Markup(f'<input type="hidden" name="_csrf_token" value="{html.escape(token)}">')

        return {'csrf_token': token, 'csrf_field': csrf_field}

    @app.before_request
    def _csrf_check():
        """Reject POST requests without valid CSRF token, with Origin/Referer as secondary check."""
        if request.method != 'POST':
            return None
        form_token = request.form.get('_csrf_token', '')
        session_token = session.get('_csrf', '')
        if not session_token or not form_token or form_token != session_token:
            abort(403)
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

    # ── Data loading with cache ─────────────────────────────────────────

    _cache: dict[str, object] = {}
    _CACHE_TTL = 30  # seconds

    def _load_data():
        """Parse -> build -> validate -> compute audit incidents (cached for _CACHE_TTL seconds)."""
        import time
        now = time.monotonic()
        if '_data' in _cache and now - _cache.get('_ts', 0) < _CACHE_TTL:
            return _cache['_data']

        from .pipeline import _build, _parse, _validate
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
        warnings, errors = _validate(built, config)
        summary, incidents = compute_audit_incidents(built, 0, 0, config)
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

    def _load_config_safe():
        """Load config with error handling for web routes."""
        try:
            return load_config(config_path)
        except (FileNotFoundError, ConfigError, OSError) as e:
            raise ConfigError(str(e)) from e

    # ── After-request and error handlers ────────────────────────────────

    @app.after_request
    def _after_request(response):
        """Invalidate cache after any POST (config-modifying) request."""
        if request.method == 'POST':
            _invalidate_cache()
        return response

    @app.errorhandler(Archi2LikeC4Error)
    def _handle_runtime_error(error):
        return f'<h1>Configuration Error</h1><pre>{html.escape(str(error))}</pre>', 500

    # ── Register route blueprint ────────────────────────────────────────

    init_routes(
        app,
        load_data=_load_data,
        load_config_safe=_load_config_safe,
        safe_redirect=_safe_redirect,
        resolved_config_path=resolved_config_path,
        metric_health=_metric_health,
        ui_func=_ui,
        version=__version__,
        save_suppress=save_suppress,
        update_config_field=update_config_field,
        valid_c4_id=_VALID_C4_ID,
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
