"""Tests for deployment-related generation in archi2likec4.generators."""

from archi2likec4.generators import (
    generate_deployment_c4,
    generate_deployment_overview_view,
    generate_system_deployment_views,
)
from archi2likec4.generators.deployment import generate_infrastructure_files, generate_system_deployment_c4
from archi2likec4.models import DeploymentNode, System

# ── generate_deployment_c4 ───────────────────────────────────────────────

class TestGenerateDeploymentC4:
    def test_basic_node(self):
        nodes = [
            DeploymentNode(
                c4_id='srv_1', name='Server 1', archi_id='n-1',
                tech_type='Node', kind='server',
                documentation='vCPU: 8',
            ),
        ]
        content = generate_deployment_c4(nodes)
        assert "srv_1 = server 'Server 1'" in content
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
            tech_type='Node', kind='server',
            children=[child],
        )
        content = generate_deployment_c4([parent])
        assert "srv_1 = server 'Server 1'" in content
        assert "pg = infraSoftware 'PostgreSQL'" in content
        # Child should be indented more than parent
        lines = content.split('\n')
        parent_line = next(ln for ln in lines if 'srv_1 = server' in ln)
        child_line = next(ln for ln in lines if 'pg = infraSoftware' in ln)
        assert len(child_line) - len(child_line.lstrip()) > len(parent_line) - len(parent_line.lstrip())

    def test_instance_of_inserted(self):
        """instanceOf is added for apps mapped to a node via deployment_map."""
        node = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='server',
        )
        deployment_map = [('channels.efs', 'srv_1'), ('products.mls', 'srv_1')]
        content = generate_deployment_c4([node], deployment_map=deployment_map)
        assert 'instanceOf channels.efs' in content
        assert 'instanceOf products.mls' in content

    def test_instance_of_duplicate_base_name_aliased(self):
        """Two instanceOf with same last segment get unique aliases."""
        node = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-1',
            tech_type='Node', kind='vm',
        )
        deployment_map = [
            ('customer_service.collection.ras.mib', 'vm1'),
            ('products.loan.mib', 'vm1'),
        ]
        content = generate_deployment_c4([node], deployment_map=deployment_map)
        assert 'instanceOf customer_service.collection.ras.mib' in content
        assert 'mib_2 = instanceOf products.loan.mib' in content

    def test_instance_of_conflicts_with_child_node(self):
        """instanceOf whose base name matches a child node c4_id gets aliased."""
        child = DeploymentNode(
            c4_id='nginx', name='Nginx', archi_id='sw-1',
            tech_type='SystemSoftware', kind='infraSoftware',
        )
        parent = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='server',
            children=[child],
        )
        deployment_map = [('channels.donocrm.nginx', 'srv_1')]
        content = generate_deployment_c4([parent], deployment_map=deployment_map)
        # Should be aliased because child node already uses 'nginx'
        assert 'nginx_2 = instanceOf channels.donocrm.nginx' in content
        assert "nginx = infraSoftware 'Nginx'" in content

    def test_instance_of_no_conflict_no_alias(self):
        """instanceOf without name conflicts renders without alias."""
        node = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='server',
        )
        deployment_map = [('channels.efs', 'srv_1')]
        content = generate_deployment_c4([node], deployment_map=deployment_map)
        assert 'instanceOf channels.efs' in content
        assert '= instanceOf channels.efs' not in content

    def test_instance_of_nested_path(self):
        """instanceOf is placed inside the correct nested node by full path."""
        vm_child = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-2',
            tech_type='Node', kind='vm',
        )
        srv = DeploymentNode(
            c4_id='srv_1', name='Server 1', archi_id='n-1',
            tech_type='Node', kind='server',
            children=[vm_child],
        )
        deployment_map = [('channels.aim.aim', 'srv_1.vm1')]
        content = generate_deployment_c4([srv], deployment_map=deployment_map)
        assert 'instanceOf channels.aim.aim' in content
        lines = content.split('\n')
        vm_idx = next(i for i, ln in enumerate(lines) if "vm1 = vm" in ln)
        instance_idx = next(i for i, ln in enumerate(lines) if 'instanceOf channels.aim.aim' in ln)
        assert instance_idx > vm_idx

    def test_host_system_tags(self):
        """Hosts get #system_X tags from their instanceOf app paths."""
        node = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-1',
            tech_type='Node', kind='vm',
        )
        deployment_map = [('channels.efs', 'vm1'), ('products.abs', 'vm1')]
        content = generate_deployment_c4([node], deployment_map=deployment_map)
        assert "#system_abs #system_efs" in content
        assert "vm1 = vm 'VM-1'" in content

    def test_ancestor_tag_propagation(self):
        """Ancestor structural nodes get system tags propagated from descendant hosts."""
        vm = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-3',
            tech_type='Node', kind='vm',
        )
        cluster = DeploymentNode(
            c4_id='cluster1', name='Cluster-1', archi_id='n-2',
            tech_type='TechnologyCollaboration', kind='cluster',
            children=[vm],
        )
        site = DeploymentNode(
            c4_id='site1', name='Site-1', archi_id='n-1',
            tech_type='Location', kind='site',
            children=[cluster],
        )
        deployment_map = [('channels.efs', 'site1.cluster1.vm1')]
        content = generate_deployment_c4([site], deployment_map=deployment_map)
        lines = content.split('\n')
        # Host (vm1) gets system tag
        vm_line = next(i for i, ln in enumerate(lines) if "vm1 = vm" in ln)
        assert '#system_efs' in lines[vm_line + 1]
        # Ancestors (site1, cluster1) also get system tag
        site_line = next(i for i, ln in enumerate(lines) if "site1 = site" in ln)
        assert '#system_efs' in lines[site_line + 1]
        cluster_line = next(i for i, ln in enumerate(lines) if "cluster1 = cluster" in ln)
        assert '#system_efs' in lines[cluster_line + 1]

    def test_orphan_nodes_no_tags(self):
        """Structural nodes without descendant hosts get no system tags."""
        orphan = DeploymentNode(
            c4_id='site2', name='Site-2', archi_id='n-4',
            tech_type='Location', kind='site',
        )
        host = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-3',
            tech_type='Node', kind='vm',
        )
        site1 = DeploymentNode(
            c4_id='site1', name='Site-1', archi_id='n-1',
            tech_type='Location', kind='site',
            children=[host],
        )
        deployment_map = [('channels.efs', 'site1.vm1')]
        content = generate_deployment_c4([site1, orphan], deployment_map=deployment_map)
        lines = content.split('\n')
        # site2 should NOT have any system tags
        site2_idx = next(i for i, ln in enumerate(lines) if "site2 = site" in ln)
        assert '#system' not in lines[site2_idx + 1]


# ── instanceOf filtering ────────────────────────────────────────────────

class TestInstanceOfFiltering:
    """instanceOf is only allowed on leaf compute kinds (vm, server, namespace)."""

    def test_no_instance_on_segment(self):
        """WAN (Path/segment) must not contain instanceOf."""
        wan = DeploymentNode(
            c4_id='wan', name='WAN', archi_id='n-1',
            tech_type='Path', kind='segment',
        )
        deployment_map = [('channels.aim.aim', 'wan')]
        content = generate_deployment_c4([wan], deployment_map=deployment_map)
        assert 'instanceOf' not in content

    def test_no_instance_on_cluster(self):
        """Cluster must not contain instanceOf directly."""
        cluster = DeploymentNode(
            c4_id='k8s', name='K8s', archi_id='n-1',
            tech_type='TechnologyCollaboration', kind='cluster',
        )
        deployment_map = [('channels.aim.aim', 'k8s')]
        content = generate_deployment_c4([cluster], deployment_map=deployment_map)
        assert 'instanceOf' not in content

    def test_no_instance_on_site(self):
        """Site must not contain instanceOf."""
        site = DeploymentNode(
            c4_id='dc1', name='DC-1', archi_id='n-1',
            tech_type='Location', kind='site',
        )
        deployment_map = [('channels.aim.aim', 'dc1')]
        content = generate_deployment_c4([site], deployment_map=deployment_map)
        assert 'instanceOf' not in content

    def test_instance_on_vm(self):
        """VM gets instanceOf."""
        vm = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-1',
            tech_type='Node', kind='vm',
        )
        cluster = DeploymentNode(
            c4_id='cluster1', name='K8s', archi_id='n-2',
            tech_type='TechnologyCollaboration', kind='cluster',
            children=[vm],
        )
        deployment_map = [('channels.aim.aim', 'cluster1.vm1')]
        content = generate_deployment_c4([cluster], deployment_map=deployment_map)
        assert 'instanceOf channels.aim.aim' in content
        assert "vm1 = vm 'VM-1'" in content

    def test_instance_on_server(self):
        """Server (bare-metal) gets instanceOf."""
        srv = DeploymentNode(
            c4_id='srv1', name='Lenovo SN550', archi_id='n-1',
            tech_type='Device', kind='server',
        )
        deployment_map = [('platform.ibm_mq', 'srv1')]
        content = generate_deployment_c4([srv], deployment_map=deployment_map)
        assert 'instanceOf platform.ibm_mq' in content

    def test_instance_on_namespace(self):
        """Namespace gets instanceOf."""
        ns = DeploymentNode(
            c4_id='ns_prod', name='ns-prod', archi_id='n-1',
            tech_type='TechnologyCollaboration', kind='namespace',
        )
        deployment_map = [('channels.efs', 'ns_prod')]
        content = generate_deployment_c4([ns], deployment_map=deployment_map)
        assert 'instanceOf channels.efs' in content

    def test_mixed_filtering(self):
        """Only placements on leaf kinds survive, structural ones are filtered."""
        wan = DeploymentNode(
            c4_id='wan', name='WAN', archi_id='n-1',
            tech_type='Path', kind='segment',
        )
        vm = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-2',
            tech_type='Node', kind='vm',
        )
        deployment_map = [
            ('channels.aim.aim', 'wan'),       # filtered
            ('channels.aim.aim', 'vm1'),        # kept
        ]
        content = generate_deployment_c4([wan, vm], deployment_map=deployment_map)
        assert 'instanceOf channels.aim.aim' in content
        # instanceOf should be inside vm1, not wan
        lines = content.split('\n')
        vm_idx = next(i for i, ln in enumerate(lines) if "vm1 = vm" in ln)
        instance_idx = next(i for i, ln in enumerate(lines) if 'instanceOf channels.aim.aim' in ln)
        assert instance_idx > vm_idx


# ── orphan infraSoftware dropping ────────────────────────────────────────

class TestOrphanDropping:
    """Orphan infraSoftware (top-level, no parent) is not rendered."""

    def test_orphan_infra_software_dropped(self):
        """Top-level infraSoftware without parent is not rendered."""
        orphan = DeploymentNode(
            c4_id='winrar', name='WinRAR 6.02', archi_id='n-1',
            tech_type='SystemSoftware', kind='infraSoftware',
        )
        content = generate_deployment_c4([orphan])
        assert 'winrar' not in content
        assert 'WinRAR' not in content

    def test_nested_infra_software_kept(self):
        """infraSoftware inside a VM is rendered."""
        sw = DeploymentNode(
            c4_id='rhel', name='RHEL 8', archi_id='n-2',
            tech_type='SystemSoftware', kind='infraSoftware',
        )
        vm = DeploymentNode(
            c4_id='vm1', name='VM-1', archi_id='n-1',
            tech_type='Node', kind='vm',
            children=[sw],
        )
        content = generate_deployment_c4([vm])
        assert "rhel = infraSoftware 'RHEL 8'" in content

    def test_orphan_dropped_with_others_kept(self):
        """Orphan is dropped while valid nodes are kept."""
        orphan = DeploymentNode(
            c4_id='gitea', name='gitea-postgresql', archi_id='n-1',
            tech_type='SystemSoftware', kind='infraSoftware',
        )
        server = DeploymentNode(
            c4_id='srv1', name='Server 1', archi_id='n-2',
            tech_type='Device', kind='server',
        )
        content = generate_deployment_c4([orphan, server])
        assert 'gitea' not in content
        assert "srv1 = server 'Server 1'" in content


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
        site = DeploymentNode(c4_id='dc1', name='DC-1', archi_id='n-1', tech_type='Location', kind='site', children=[vm])
        content = generate_deployment_overview_view(nodes=[site])
        assert 'include prod' in content
        assert 'include prod.*' in content
        assert 'include prod.dc1.*' in content
        assert 'include prod.dc1.vm1.*' in content
        assert '.**' not in content

    def test_custom_env(self):
        content = generate_deployment_overview_view(env='staging')
        assert 'include staging' in content


# ── generate_system_deployment_views ─────────────────────────────────

def _make_system(c4_id: str, name: str) -> System:
    return System(c4_id=c4_id, name=name, archi_id=f'a-{c4_id}')


def _simple_nodes() -> list[DeploymentNode]:
    """A minimal deployment tree: site → cluster → vm."""
    vm = DeploymentNode(c4_id='vm1', name='VM-1', archi_id='n-3', tech_type='Node', kind='vm')
    cluster = DeploymentNode(c4_id='esxi', name='ESXi', archi_id='n-2',
                             tech_type='TechnologyCollaboration', kind='cluster', children=[vm])
    site = DeploymentNode(c4_id='dc1', name='DC-1', archi_id='n-1',
                          tech_type='Location', kind='site', children=[cluster])
    return [site]


class TestGenerateSystemDeploymentViews:

    def test_single_system_view(self):
        nodes = _simple_nodes()
        systems = [_make_system('efs', 'EFS')]
        deployment_map = [('channels.efs', 'dc1.esxi.vm1')]
        content = generate_system_deployment_views(
            nodes=nodes, deployment_map=deployment_map, systems=systems,
        )
        assert 'deployment view efs_deploy' in content
        assert "title 'EFS — prod'" in content
        assert 'exclude * where tag is not #system_efs' in content
        # Star-chain includes, no .**
        assert '.**' not in content
        assert 'include prod' in content
        assert 'include prod.*' in content
        assert 'include prod.dc1.*' in content

    def test_multiple_systems(self):
        nodes = _simple_nodes()
        systems = [_make_system('efs', 'EFS'), _make_system('abs', 'ABS')]
        deployment_map = [
            ('channels.efs', 'dc1.esxi.vm1'),
            ('products.abs', 'dc1.esxi.vm1'),
        ]
        content = generate_system_deployment_views(
            nodes=nodes, deployment_map=deployment_map, systems=systems,
        )
        assert 'deployment view abs_deploy' in content
        assert 'deployment view efs_deploy' in content

    def test_system_no_deployments_skipped(self):
        nodes = _simple_nodes()
        systems = [_make_system('efs', 'EFS'), _make_system('abs', 'ABS')]
        deployment_map = [('channels.efs', 'dc1.esxi.vm1')]
        content = generate_system_deployment_views(
            nodes=nodes, deployment_map=deployment_map, systems=systems,
        )
        assert 'efs_deploy' in content
        assert 'abs_deploy' not in content

    def test_empty_map_returns_empty(self):
        nodes = _simple_nodes()
        systems = [_make_system('efs', 'EFS')]
        assert generate_system_deployment_views(nodes=nodes, deployment_map=[], systems=systems) == ''

    def test_no_nodes_returns_empty(self):
        systems = [_make_system('efs', 'EFS')]
        deployment_map = [('channels.efs', 'dc1.vm1')]
        assert generate_system_deployment_views(nodes=None, deployment_map=deployment_map, systems=systems) == ''

    def test_view_id_sanitized(self):
        nodes = _simple_nodes()
        systems = [_make_system('call_center', 'Call Center')]
        deployment_map = [('channels.call_center', 'dc1.esxi.vm1')]
        content = generate_system_deployment_views(
            nodes=nodes, deployment_map=deployment_map, systems=systems,
        )
        assert 'deployment view call_center_deploy' in content
        assert '#system_call_center' in content

    def test_custom_env(self):
        nodes = _simple_nodes()
        systems = [_make_system('efs', 'EFS')]
        deployment_map = [('channels.efs', 'dc1.esxi.vm1')]
        content = generate_system_deployment_views(
            nodes=nodes, deployment_map=deployment_map, systems=systems, env='staging',
        )
        assert 'include staging' in content
        assert "title 'EFS — staging'" in content


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
