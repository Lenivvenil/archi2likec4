"""Tests for deployment-related generation in archi2likec4.generators."""

from archi2likec4.generators import (
    generate_deployment_c4,
    generate_deployment_overview_view,
)
from archi2likec4.models import DeploymentNode

# ── generate_deployment_c4 ───────────────────────────────────────────────

class TestGenerateDeploymentC4:
    def test_basic_node(self):
        nodes = [
            DeploymentNode(
                c4_id='srv_1', name='Server 1', archi_id='n-1',
                tech_type='Node', kind='infraNode',
                documentation='vCPU: 8',
            ),
        ]
        content = generate_deployment_c4(nodes)
        assert "srv_1 = infraNode 'Server 1'" in content
        assert "archi_id 'n-1'" in content
        assert "tech_type 'Node'" in content
        assert "description 'vCPU: 8'" in content
        assert 'deployment {' in content
        assert 'environment prod {' in content

    def test_nested_nodes(self):
        child = DeploymentNode(
            c4_id='pg', name='PostgreSQL', archi_id='sw-1',
            tech_type='SystemSoftware', kind='infraSoftware',
        )
        parent = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='infraNode',
            children=[child],
        )
        content = generate_deployment_c4([parent])
        assert "srv_1 = infraNode 'Server 1'" in content
        assert "pg = infraSoftware 'PostgreSQL'" in content
        # Child should be indented more than parent
        lines = content.split('\n')
        parent_line = next(ln for ln in lines if 'srv_1 = infraNode' in ln)
        child_line = next(ln for ln in lines if 'pg = infraSoftware' in ln)
        assert len(child_line) - len(child_line.lstrip()) > len(parent_line) - len(parent_line.lstrip())

    def test_instance_of_inserted(self):
        """instanceOf is added for apps mapped to a node via deployment_map."""
        node = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='infraNode',
        )
        deployment_map = [('channels.efs', 'srv_1'), ('products.mls', 'srv_1')]
        content = generate_deployment_c4([node], deployment_map=deployment_map)
        assert 'instanceOf channels.efs' in content
        assert 'instanceOf products.mls' in content

    def test_instance_of_nested_path(self):
        """instanceOf is placed inside the correct nested node by full path."""
        child = DeploymentNode(
            c4_id='pg', name='PostgreSQL', archi_id='sw-1',
            tech_type='SystemSoftware', kind='infraSoftware',
        )
        parent = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='infraNode',
            children=[child],
        )
        deployment_map = [('channels.aim.aim', 'srv_1.pg')]
        content = generate_deployment_c4([parent], deployment_map=deployment_map)
        assert 'instanceOf channels.aim.aim' in content
        # Should NOT be at root level
        lines = content.split('\n')
        pg_idx = next(i for i, ln in enumerate(lines) if 'pg = infraSoftware' in ln)
        instance_idx = next(i for i, ln in enumerate(lines) if 'instanceOf channels.aim.aim' in ln)
        assert instance_idx > pg_idx


# ── generate_deployment_overview_view ────────────────────────────────────

class TestGenerateDeploymentOverviewView:
    def test_view_content(self):
        content = generate_deployment_overview_view()
        assert 'deployment view deployment_architecture' in content
        assert 'prod.**' in content

    def test_custom_env(self):
        content = generate_deployment_overview_view(env='staging')
        assert 'staging.**' in content
