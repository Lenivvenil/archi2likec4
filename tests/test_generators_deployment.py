"""Tests for deployment-related generation in archi2likec4.generators."""

from archi2likec4.generators import (
    generate_deployment_overview_view,
)
from archi2likec4.generators.deployment import generate_infrastructure_files, generate_system_deployment_c4
from archi2likec4.models import DeploymentNode

# ── kind resolution (builders) ──────────────────────────────────────────

class TestKindResolution:
    """Test ArchiMate type → LikeC4 kind mapping via builders."""

    def test_location_becomes_site(self):
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='DC-1', tech_type='Location')], [])
        assert nodes[0].kind == 'site'

    def test_path_becomes_segment(self):
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='WAN', tech_type='Path')], [])
        assert nodes[0].kind == 'segment'

    def test_communication_network_becomes_segment(self):
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='LAN', tech_type='CommunicationNetwork')], [])
        assert nodes[0].kind == 'segment'

    def test_technology_collaboration_becomes_cluster(self):
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='K8s-Prod', tech_type='TechnologyCollaboration')], [])
        assert nodes[0].kind == 'cluster'

    def test_device_becomes_server(self):
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='Lenovo SN550', tech_type='Device')], [])
        assert nodes[0].kind == 'server'

    def test_node_at_top_level_becomes_server(self):
        """Top-level Node (no parent) becomes server."""
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='SRV-1', tech_type='Node')], [])
        assert nodes[0].kind == 'server'

    def test_node_inside_cluster_becomes_vm(self):
        """Node inside TechnologyCollaboration (cluster) becomes vm."""
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import RawRelationship, TechElement
        elements = [
            TechElement(archi_id='t-1', name='K8s', tech_type='TechnologyCollaboration'),
            TechElement(archi_id='t-2', name='Worker-1', tech_type='Node'),
        ]
        rels = [RawRelationship(
            rel_id='r-1', rel_type='AggregationRelationship', name='',
            source_id='t-1', target_id='t-2',
            source_type='TechnologyCollaboration', target_type='Node',
        )]
        nodes = build_deployment_topology(elements, rels)
        cluster = nodes[0]
        assert cluster.kind == 'cluster'
        assert cluster.children[0].kind == 'vm'

    def test_system_software_with_node_children_becomes_cluster(self):
        """Hypervisor pattern: SystemSoftware containing Nodes → cluster."""
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import RawRelationship, TechElement
        elements = [
            TechElement(archi_id='t-1', name='ESXi 7.0', tech_type='SystemSoftware'),
            TechElement(archi_id='t-2', name='VM-1', tech_type='Node'),
        ]
        rels = [RawRelationship(
            rel_id='r-1', rel_type='AggregationRelationship', name='',
            source_id='t-1', target_id='t-2',
            source_type='SystemSoftware', target_type='Node',
        )]
        nodes = build_deployment_topology(elements, rels)
        hypervisor = nodes[0]
        assert hypervisor.kind == 'cluster'
        assert hypervisor.children[0].kind == 'vm'

    def test_system_software_with_software_children_becomes_cluster(self):
        """Container host: SystemSoftware containing other SystemSoftware → cluster."""
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import RawRelationship, TechElement
        elements = [
            TechElement(archi_id='t-1', name='Linux', tech_type='SystemSoftware'),
            TechElement(archi_id='t-2', name='nginx', tech_type='SystemSoftware'),
        ]
        rels = [RawRelationship(
            rel_id='r-1', rel_type='AggregationRelationship', name='',
            source_id='t-1', target_id='t-2',
            source_type='SystemSoftware', target_type='SystemSoftware',
        )]
        nodes = build_deployment_topology(elements, rels)
        container = nodes[0]
        assert container.kind == 'cluster'
        assert container.children[0].kind == 'infraSoftware'

    def test_system_software_without_children_stays_infra_software(self):
        """Plain SystemSoftware stays infraSoftware."""
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import TechElement
        nodes = build_deployment_topology(
            [TechElement(archi_id='t-1', name='PostgreSQL', tech_type='SystemSoftware')], [])
        assert nodes[0].kind == 'infraSoftware'

    def test_nested_collaboration_with_namespace_keyword(self):
        """TechnologyCollaboration inside cluster with 'namespace' in name → namespace."""
        from archi2likec4.builders.deployment import build_deployment_topology
        from archi2likec4.models import RawRelationship, TechElement
        elements = [
            TechElement(archi_id='t-1', name='K8s', tech_type='TechnologyCollaboration'),
            TechElement(archi_id='t-2', name='namespace-prod', tech_type='TechnologyCollaboration'),
        ]
        rels = [RawRelationship(
            rel_id='r-1', rel_type='AggregationRelationship', name='',
            source_id='t-1', target_id='t-2',
            source_type='TechnologyCollaboration', target_type='TechnologyCollaboration',
        )]
        nodes = build_deployment_topology(elements, rels)
        cluster = nodes[0]
        assert cluster.kind == 'cluster'
        assert cluster.children[0].kind == 'namespace'


# ── generate_deployment_overview_view ────────────────────────────────────

class TestGenerateDeploymentOverviewView:
    def test_view_content_no_nodes(self):
        content = generate_deployment_overview_view()
        assert 'deployment view deployment_architecture' in content
        assert 'include prod' in content

    def test_star_chain_with_nodes(self):
        vm = DeploymentNode(c4_id='vm1', name='VM-1', archi_id='n-2', tech_type='Node', kind='vm')
        site = DeploymentNode(
            c4_id='dc1', name='DC-1', archi_id='n-1', tech_type='Location', kind='site', children=[vm]
        )
        content = generate_deployment_overview_view(nodes=[site])
        assert 'include prod' in content
        assert 'include prod.*' in content
        assert 'include prod.dc1.*' in content
        assert 'include prod.dc1.vm1.*' in content
        assert '.**' not in content

    def test_custom_env(self):
        content = generate_deployment_overview_view(env='staging')
        assert 'include staging' in content


# ── generate_infrastructure_files ──���───────────────────────────────────


class TestGenerateInfrastructureFiles:
    def test_environments_file_always_present(self):
        files = generate_infrastructure_files([])
        assert 'environments.c4' in files
        assert 'environment prod {' in files['environments.c4']

    def test_one_file_per_top_level_node(self):
        nodes = [
            DeploymentNode(c4_id='dc_primary', name='Primary DC', archi_id='n-1',
                           tech_type='Location', kind='site'),
            DeploymentNode(c4_id='dc_secondary', name='Secondary DC', archi_id='n-2',
                           tech_type='Location', kind='site'),
        ]
        files = generate_infrastructure_files(nodes)
        assert 'environments.c4' in files
        assert 'dc_primary.c4' in files
        assert 'dc_secondary.c4' in files
        assert len(files) == 3

    def test_site_file_uses_extend(self):
        child_vm = DeploymentNode(c4_id='vm01', name='VM-01', archi_id='n-2',
                                  tech_type='Node', kind='vm')
        nodes = [
            DeploymentNode(c4_id='dc1', name='DC 1', archi_id='n-1',
                           tech_type='Location', kind='site', children=[child_vm]),
        ]
        files = generate_infrastructure_files(nodes)
        content = files['dc1.c4']
        assert 'extend prod {' in content
        assert "dc1 = site 'DC 1'" in content
        assert "vm01 = vm 'VM-01'" in content
        # No instanceOf in infrastructure files
        assert 'instanceOf' not in content

    def test_custom_env(self):
        nodes = [
            DeploymentNode(c4_id='dc1', name='DC 1', archi_id='n-1',
                           tech_type='Location', kind='site'),
        ]
        files = generate_infrastructure_files(nodes, env='staging')
        assert 'environment staging {' in files['environments.c4']
        assert 'extend staging {' in files['dc1.c4']

    def test_no_instance_of_in_infra(self):
        """Infrastructure files must NOT contain instanceOf — those go to per-system files."""
        vm = DeploymentNode(c4_id='vm01', name='VM-01', archi_id='n-2',
                            tech_type='Node', kind='vm')
        nodes = [
            DeploymentNode(c4_id='dc1', name='DC 1', archi_id='n-1',
                           tech_type='Location', kind='site', children=[vm]),
        ]
        files = generate_infrastructure_files(nodes)
        for content in files.values():
            assert 'instanceOf' not in content


# ── generate_system_deployment_c4 ───────────────────────────────────────


class TestGenerateSystemDeploymentC4:
    def test_basic_deployment(self):
        entries = [('channels.efs', 'dc1.app_zone.vm01')]
        content = generate_system_deployment_c4('efs', 'EFS', entries)
        assert 'extend prod.dc1.app_zone.vm01 {' in content
        assert 'instanceOf channels.efs' in content
        assert 'deployment view efs_deployment' in content
        assert "title 'EFS — prod'" in content
        assert 'include prod.dc1.app_zone.vm01.*' in content

    def test_multiple_vms(self):
        entries = [
            ('channels.efs.api', 'dc1.app.vm01'),
            ('channels.efs.db', 'dc1.db.vm02'),
        ]
        content = generate_system_deployment_c4('efs', 'EFS', entries)
        assert 'extend prod.dc1.app.vm01 {' in content
        assert 'extend prod.dc1.db.vm02 {' in content
        assert 'include prod.dc1.app.vm01.*' in content
        assert 'include prod.dc1.db.vm02.*' in content

    def test_multiple_instances_same_vm(self):
        entries = [
            ('channels.efs.api', 'dc1.app.vm01'),
            ('channels.efs.mq', 'dc1.app.vm01'),
        ]
        content = generate_system_deployment_c4('efs', 'EFS', entries)
        assert 'instanceOf channels.efs.api' in content
        assert 'instanceOf channels.efs.mq' in content
        # Only one extend block for the same VM
        assert content.count('extend prod.dc1.app.vm01 {') == 1

    def test_empty_entries_returns_empty(self):
        content = generate_system_deployment_c4('efs', 'EFS', [])
        assert content == ''

    def test_custom_env(self):
        entries = [('channels.efs', 'dc1.vm01')]
        content = generate_system_deployment_c4('efs', 'EFS', entries, env='staging')
        assert 'extend staging.dc1.vm01 {' in content
        assert 'include staging.dc1.vm01.*' in content
        assert "title 'EFS — staging'" in content

    def test_duplicate_base_name_aliased(self):
        entries = [
            ('channels.efs.mib', 'dc1.app.vm01'),
            ('platform.esb.mib', 'dc1.app.vm01'),
        ]
        content = generate_system_deployment_c4('efs', 'EFS', entries)
        assert 'instanceOf channels.efs.mib' in content
        assert 'mib_2 = instanceOf platform.esb.mib' in content

    def test_no_tags_in_deployment(self):
        """Per-system deployment files must NOT use tag-based filtering."""
        entries = [('channels.efs', 'dc1.vm01')]
        content = generate_system_deployment_c4('efs', 'EFS', entries)
        assert '#system_' not in content
        assert 'exclude' not in content

    def test_view_uses_targeted_includes(self):
        """Deployment view uses targeted VM-path includes, not star-chain over all paths."""
        entries = [
            ('channels.efs.api', 'dc1.app.vm01'),
            ('channels.efs.db', 'dc2.db.vm05'),
        ]
        content = generate_system_deployment_c4('efs', 'EFS', entries)
        # Only includes for VMs where this system is deployed
        assert 'include prod.dc1.app.vm01.*' in content
        assert 'include prod.dc2.db.vm05.*' in content
        # NOT a star-chain over all infrastructure
        assert 'include prod.*' not in content
