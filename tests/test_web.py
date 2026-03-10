"""Tests for archi2likec4.web module — Flask routes via create_app + test client."""

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


def _mock_load_data():
    """Return mock data matching what _load_data() produces."""
    summary = _make_summary()
    incidents = [
        _make_incident('QA-1', 'Critical', 'Системы без домена', 2,
                       affected=[{'name': 'AD'}, {'name': 'Legacy'}]),
        _make_incident('QA-5', 'Medium', 'Системы без документации', 1,
                       affected=[{'name': 'EFS', 'domain': 'channels'}]),
    ]
    config = _make_config()
    available_domains = ['channels', 'products', 'platform']

    # Mock built object for hierarchy page
    from archi2likec4.models import System, Subsystem
    sys1 = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels',
                  subsystems=[Subsystem(c4_id='core', name='EFS.Core', archi_id='sub1', metadata={})])
    sys2 = System(c4_id='crm', name='CRM', archi_id='s2', metadata={}, domain='products')

    mock_built = MagicMock()
    mock_built.domain_systems = {'channels': [sys1], 'products': [sys2]}
    mock_built.systems = [sys1, sys2]
    mock_built.deployment_map = []
    mock_built.integrations = []
    mock_built.entities = []
    mock_built.deployment_nodes = []
    mock_built.relationships = []
    mock_built.orphan_fns = 0

    return config, summary, incidents, available_domains, mock_built


@pytest.fixture
def app_client(tmp_path):
    """Create Flask test client via create_app with mocked pipeline."""
    from archi2likec4 import web

    config, summary, incidents, available_domains, mock_built = _mock_load_data()

    model_dir = tmp_path / 'model'
    model_dir.mkdir()

    # Patch the pipeline functions called by _load_data inside create_app
    with patch('archi2likec4.config.load_config', return_value=config), \
         patch('archi2likec4.pipeline._parse', return_value=MagicMock()), \
         patch('archi2likec4.pipeline._build', return_value=mock_built), \
         patch('archi2likec4.pipeline._validate', return_value=(0, 0, {}, 0, 0)), \
         patch('archi2likec4.audit_data.compute_audit_incidents',
               return_value=(summary, incidents)):
        app = web.create_app(
            config_path=None,
            model_root=model_dir,
            output_dir=tmp_path / 'output',
        )
        yield app.test_client()


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

    def test_empty_remediations_shows_placeholder(self, app_client):
        """Default ConvertConfig has no remediations, page shows empty state."""
        resp = app_client.get('/remediations')
        html = resp.data.decode()
        assert resp.status_code == 200


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


# ── Open redirect prevention ──────────────────────────────────────────

class TestOpenRedirect:
    def test_safe_redirect_rejects_absolute_url(self, app_client):
        """POST with absolute redirect URL should redirect to / instead."""
        resp = app_client.post('/suppress/system', data={
            'name': 'TestSys',
            'redirect': 'https://evil.com/steal',
        })
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/')

    def test_safe_redirect_allows_relative(self, app_client):
        """POST with relative redirect URL should be allowed."""
        resp = app_client.post('/suppress/system', data={
            'name': 'TestSys',
            'redirect': '/incident/QA-1',
        })
        assert resp.status_code == 302
        assert '/incident/QA-1' in resp.headers['Location']

    def test_safe_redirect_rejects_protocol_relative(self, app_client):
        """POST with protocol-relative redirect URL (//evil.com) should redirect to /."""
        resp = app_client.post('/suppress/system', data={
            'name': 'TestSys',
            'redirect': '//evil.example/steal',
        })
        assert resp.status_code == 302
        assert resp.headers['Location'].endswith('/')


# ── CSRF protection ──────────────────────────────────────────────────

class TestCSRF:
    def test_cross_origin_post_rejected(self, app_client):
        """POST with foreign Origin header should return 403."""
        resp = app_client.post('/suppress/system',
                               data={'name': 'Sys', 'redirect': '/'},
                               headers={'Origin': 'https://evil.com'})
        assert resp.status_code == 403

    def test_same_origin_post_allowed(self, app_client):
        """POST with same-origin Origin header should succeed."""
        resp = app_client.post('/suppress/system',
                               data={'name': 'Sys', 'redirect': '/'},
                               headers={'Origin': 'http://localhost'})
        assert resp.status_code == 302

    def test_cross_origin_referer_rejected(self, app_client):
        """POST with foreign Referer (no Origin) should return 403."""
        resp = app_client.post('/suppress/system',
                               data={'name': 'Sys', 'redirect': '/'},
                               headers={'Referer': 'https://evil.com/page'})
        assert resp.status_code == 403
