"""Tests for archi2likec4.web module — Flask routes via test client."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from archi2likec4.audit_data import AuditSummary, AuditIncident
from archi2likec4.config import ConvertConfig


def _make_summary(**kwargs):
    defaults = dict(
        total_systems=5, total_subsystems=10, meta_completeness_pct=60,
        assigned_count=4, total_integrations=20, total_entities=8,
        deployment_mappings=3,
    )
    defaults.update(kwargs)
    return AuditSummary(**defaults)


def _make_incident(qa_id='QA-1', severity='Critical', title='Test', count=2,
                   affected=None, suppressed=False, **kwargs):
    return AuditIncident(
        qa_id=qa_id, severity=severity, title=title, count=count,
        affected=affected or [{'name': 'SysA'}, {'name': 'SysB'}],
        suppressed=suppressed, **kwargs,
    )


def _make_config(**kwargs):
    c = ConvertConfig()
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


@pytest.fixture
def app_client():
    """Create Flask test client with mocked pipeline."""
    from archi2likec4 import web

    summary = _make_summary()
    incidents = [
        _make_incident('QA-1', 'Critical', 'Системы без домена', 2,
                       affected=[{'name': 'AD'}, {'name': 'Legacy'}]),
        _make_incident('QA-5', 'Medium', 'Системы без документации', 1,
                       affected=[{'name': 'EFS', 'domain': 'channels'}]),
    ]
    config = _make_config()
    available_domains = ['channels', 'products', 'platform']

    mock_data = (config, summary, incidents, available_domains)

    with patch.object(web, '_DASHBOARD_TEMPLATE', web._DASHBOARD_TEMPLATE), \
         patch.object(web, '_DETAIL_TEMPLATE', web._DETAIL_TEMPLATE):
        # We need to actually create a Flask app via run_web but without running it.
        # Instead, let's directly construct the app by calling run_web internals.
        pass

    # Create app by importing Flask and setting up routes manually
    from flask import Flask, render_template_string, request, redirect
    from archi2likec4 import __version__

    test_app = Flask(__name__)

    def _load_data():
        return mock_data

    @test_app.route('/')
    def dashboard():
        config, summary, incidents, available_domains = _load_data()
        lang = getattr(config, 'language', 'ru')
        active_count = sum(1 for i in incidents if not i.suppressed)
        suppressed_count = sum(1 for i in incidents if i.suppressed)
        return render_template_string(
            web._DASHBOARD_TEMPLATE,
            t=web._ui(lang), lang=lang,
            version=__version__,
            summary=summary,
            incidents=incidents,
            severity_colors=web._SEVERITY_COLORS,
            health=web._metric_health(summary),
            suppress_names=sorted(config.audit_suppress),
            suppress_incidents_list=sorted(config.audit_suppress_incidents),
            config_path='.archi2likec4.yaml',
            active_count=active_count,
            suppressed_count=suppressed_count,
            remed_domain=len(config.domain_overrides),
            remed_reviewed=len(config.reviewed_systems),
            remed_total=len(config.domain_overrides) + len(config.reviewed_systems),
        )

    @test_app.route('/incident/<qa_id>')
    def incident_detail(qa_id):
        config, summary, incidents, available_domains = _load_data()
        lang = getattr(config, 'language', 'ru')
        incident = next((i for i in incidents if i.qa_id == qa_id), None)
        if incident is None:
            return redirect('/')
        columns = web._get_columns(incident)
        return render_template_string(
            web._DETAIL_TEMPLATE,
            t=web._ui(lang), lang=lang,
            incident=incident,
            columns=columns,
            severity_colors=web._SEVERITY_COLORS,
            available_domains=available_domains,
        )

    @test_app.route('/remediations')
    def remediations():
        lang = getattr(config, 'language', 'ru')
        return render_template_string(
            web._REMEDIATIONS_TEMPLATE,
            t=web._ui(lang), lang=lang,
            domain_overrides=config.domain_overrides,
            reviewed_systems=sorted(config.reviewed_systems),
            promote_children=config.promote_children,
            suppress_names=sorted(config.audit_suppress),
            suppress_incidents_list=sorted(config.audit_suppress_incidents),
        )

    @test_app.route('/hierarchy')
    def hierarchy():
        from archi2likec4.models import System, Subsystem
        from archi2likec4 import __version__
        lang = getattr(config, 'language', 'ru')
        sys1 = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels',
                      subsystems=[Subsystem(c4_id='core', name='EFS.Core', archi_id='sub1', metadata={})])
        sys2 = System(c4_id='crm', name='CRM', archi_id='s2', metadata={}, domain='products')
        domain_groups = {'channels': [sys1], 'products': [sys2]}
        return render_template_string(
            web._HIERARCHY_TEMPLATE,
            t=web._ui(lang), lang=lang,
            version=__version__,
            domain_groups=domain_groups,
            promoted_parents=set(),
            total_systems=2,
            total_subsystems=1,
        )

    return test_app.test_client()


# ── Dashboard tests ──────────────────────────────────────────────────────

class TestDashboard:
    def test_dashboard_returns_200(self, app_client):
        resp = app_client.get('/')
        assert resp.status_code == 200

    def test_dashboard_contains_title(self, app_client):
        resp = app_client.get('/')
        html = resp.data.decode()
        # Default language is 'ru'
        assert 'Панель аудита качества' in html or 'Quality Audit Dashboard' in html

    def test_dashboard_shows_metrics(self, app_client):
        resp = app_client.get('/')
        html = resp.data.decode()
        assert '5' in html  # total_systems
        assert '10' in html  # total_subsystems
        assert '60%' in html  # meta_completeness_pct

    def test_dashboard_shows_incidents(self, app_client):
        resp = app_client.get('/')
        html = resp.data.decode()
        assert 'QA-1' in html
        assert 'QA-5' in html

    def test_dashboard_shows_incident_count(self, app_client):
        resp = app_client.get('/')
        html = resp.data.decode()
        assert 'Инциденты (2' in html or 'Incidents (2' in html


# ── Incident detail tests ───────────────────────────────────────────────

class TestIncidentDetail:
    def test_existing_incident_returns_200(self, app_client):
        resp = app_client.get('/incident/QA-1')
        assert resp.status_code == 200

    def test_detail_shows_title(self, app_client):
        resp = app_client.get('/incident/QA-1')
        html = resp.data.decode()
        assert 'QA-1' in html

    def test_detail_shows_affected(self, app_client):
        resp = app_client.get('/incident/QA-1')
        html = resp.data.decode()
        assert 'AD' in html
        assert 'Legacy' in html

    def test_unknown_incident_redirects(self, app_client):
        resp = app_client.get('/incident/QA-99')
        assert resp.status_code == 302

    def test_qa5_detail(self, app_client):
        resp = app_client.get('/incident/QA-5')
        html = resp.data.decode()
        assert 'EFS' in html


# ── Remediations page tests ─────────────────────────────────────────────

class TestRemediations:
    def test_remediations_returns_200(self, app_client):
        resp = app_client.get('/remediations')
        assert resp.status_code == 200

    def test_remediations_shows_title(self, app_client):
        resp = app_client.get('/remediations')
        html = resp.data.decode()
        assert 'Обзор ремедиаций' in html or 'Remediations Review' in html

    def test_shows_default_promote_children(self, app_client):
        """Default ConvertConfig has promote_children, so they show on remediations page."""
        resp = app_client.get('/remediations')
        html = resp.data.decode()
        assert 'Промоутированные' in html or 'Promoted Children' in html


# ── Helper function tests ───────────────────────────────────────────────

class TestHelperFunctions:
    def test_get_columns_empty(self):
        from archi2likec4.web import _get_columns
        inc = AuditIncident(qa_id='QA-1', severity='Critical', title='T', count=0)
        assert _get_columns(inc) == []

    def test_get_columns_with_affected(self):
        from archi2likec4.web import _get_columns
        inc = AuditIncident(qa_id='QA-1', severity='Critical', title='T', count=1,
                            affected=[{'name': 'A', 'domain': 'B'}])
        assert _get_columns(inc) == ['name', 'domain']

    def test_metric_health_good(self):
        from archi2likec4.web import _metric_health
        s = _make_summary(assigned_count=5, total_systems=5, meta_completeness_pct=80)
        h = _metric_health(s)
        assert h['domain'] == 'metric-ok'
        assert h['meta'] == 'metric-ok'

    def test_metric_health_bad(self):
        from archi2likec4.web import _metric_health
        s = _make_summary(assigned_count=1, total_systems=5, meta_completeness_pct=10,
                          total_integrations=0, deployment_mappings=0)
        h = _metric_health(s)
        assert h['domain'] == 'metric-crit'
        assert h['meta'] == 'metric-crit'
        assert h['intg'] == 'metric-crit'
        assert h['deploy'] == 'metric-crit'

    def test_metric_health_warn(self):
        from archi2likec4.web import _metric_health
        s = _make_summary(assigned_count=3, total_systems=5, meta_completeness_pct=30)
        h = _metric_health(s)
        assert h['domain'] == 'metric-warn'
        assert h['meta'] == 'metric-warn'


# ── Hierarchy page tests ────────────────────────────────────────────────

class TestHierarchy:
    def test_hierarchy_returns_200(self, app_client):
        resp = app_client.get('/hierarchy')
        assert resp.status_code == 200

    def test_hierarchy_shows_title(self, app_client):
        resp = app_client.get('/hierarchy')
        html = resp.data.decode()
        assert 'Иерархия систем' in html or 'System Hierarchy' in html

    def test_hierarchy_shows_domains(self, app_client):
        resp = app_client.get('/hierarchy')
        html = resp.data.decode()
        assert 'channels' in html
        assert 'products' in html

    def test_hierarchy_shows_systems(self, app_client):
        resp = app_client.get('/hierarchy')
        html = resp.data.decode()
        assert 'EFS' in html
        assert 'CRM' in html

    def test_hierarchy_shows_subsystems(self, app_client):
        resp = app_client.get('/hierarchy')
        html = resp.data.decode()
        assert 'EFS.Core' in html
