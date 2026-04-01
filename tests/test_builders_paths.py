"""Tests for builders/_paths.py module."""

from archi2likec4.builders._paths import build_comp_c4_path, build_deployment_path_index
from archi2likec4.models import (
    DeploymentNode,
    Subsystem,
    System,
)


class TestBuildCompC4Path:
    def test_simple_system(self):
        sys = System(c4_id='billing', name='Billing', archi_id='id-1')
        result = build_comp_c4_path([sys])
        assert result == {'id-1': 'billing'}

    def test_system_with_subsystem(self):
        sub = Subsystem(c4_id='invoices', name='Invoices', archi_id='id-sub')
        sys = System(c4_id='billing', name='Billing', archi_id='id-1', subsystems=[sub])
        result = build_comp_c4_path([sys])
        assert result['id-1'] == 'billing'
        assert result['id-sub'] == 'billing.invoices'

    def test_extra_archi_ids(self):
        sys = System(c4_id='billing', name='Billing', archi_id='id-1', extra_archi_ids=['id-dup'])
        result = build_comp_c4_path([sys])
        assert result['id-dup'] == 'billing'

    def test_empty_list(self):
        assert build_comp_c4_path([]) == {}

    def test_system_without_archi_id(self):
        sys = System(c4_id='billing', name='Billing', archi_id='')
        result = build_comp_c4_path([sys])
        assert 'billing' not in result  # no archi_id, no entry keyed by c4_id


# ── build_deployment_path_index ──────────────────────────────────────────

class TestBuildDeploymentPathIndex:
    def test_empty_nodes(self):
        assert build_deployment_path_index([]) == {}

    def test_single_root_node(self):
        node = DeploymentNode(c4_id='prod', name='Prod', archi_id='n-1', tech_type='Node')
        result = build_deployment_path_index([node])
        assert result == {'n-1': 'prod'}

    def test_nested_hierarchy(self):
        child = DeploymentNode(c4_id='app', name='App', archi_id='n-2', tech_type='Node')
        root = DeploymentNode(c4_id='prod', name='Prod', archi_id='n-1', tech_type='Node', children=[child])
        result = build_deployment_path_index([root])
        assert result['n-1'] == 'prod'
        assert result['n-2'] == 'prod.app'

    def test_deeply_nested(self):
        leaf = DeploymentNode(c4_id='jvm', name='JVM', archi_id='n-3', tech_type='SystemSoftware')
        mid = DeploymentNode(c4_id='app', name='App', archi_id='n-2', tech_type='Node', children=[leaf])
        root = DeploymentNode(c4_id='dc1', name='DC1', archi_id='n-1', tech_type='Node', children=[mid])
        result = build_deployment_path_index([root])
        assert result['n-3'] == 'dc1.app.jvm'
