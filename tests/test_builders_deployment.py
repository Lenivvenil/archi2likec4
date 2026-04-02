"""Tests for builders/deployment.py module."""

import xml.etree.ElementTree as ET

from archi2likec4.builders import (
    DeploymentMappingContext,
    SystemBuildConfig,
    assign_domains,
    build_deployment_map,
    build_deployment_topology,
    build_systems,
    build_tech_archi_to_c4_map,
    validate_deployment_tree,
)
from archi2likec4.builders.deployment import enrich_deployment_from_visual_nesting
from archi2likec4.models import (
    AppComponent,
    DeploymentNode,
    DomainInfo,
    RawRelationship,
    Subsystem,
    System,
    TechElement,
)
from archi2likec4.parsers import _extract_visual_nesting


class TestDeploymentTopology:
    def test_basic_node_with_software(self):
        """AggregationRelationship Node→SystemSoftware creates nesting."""
        elems = [
            TechElement(archi_id='n-1', name='Server 1', tech_type='Node'),
            TechElement(archi_id='sw-1', name='PostgreSQL', tech_type='SystemSoftware'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AggregationRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
        ]
        roots = build_deployment_topology(elems, rels)
        assert len(roots) == 1
        assert roots[0].name == 'Server 1'
        assert roots[0].kind == 'server'
        assert len(roots[0].children) == 1
        assert roots[0].children[0].name == 'PostgreSQL'
        assert roots[0].children[0].kind == 'infraSoftware'

    def test_cluster_node_software_chain(self):
        """TechnologyCollaboration→Node→SystemSoftware: 2-level tree."""
        elems = [
            TechElement(archi_id='tc-1', name='K8s Cluster', tech_type='TechnologyCollaboration'),
            TechElement(archi_id='n-1', name='Worker 1', tech_type='Node'),
            TechElement(archi_id='sw-1', name='Redis', tech_type='SystemSoftware'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AggregationRelationship', name='',
                source_type='TechnologyCollaboration', source_id='tc-1',
                target_type='Node', target_id='n-1',
            ),
            RawRelationship(
                rel_id='r-2', rel_type='AggregationRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
        ]
        roots = build_deployment_topology(elems, rels)
        assert len(roots) == 1
        assert roots[0].name == 'K8s Cluster'
        assert len(roots[0].children) == 1
        node = roots[0].children[0]
        assert node.name == 'Worker 1'
        assert len(node.children) == 1
        assert node.children[0].name == 'Redis'

    def test_standalone_nodes(self):
        """Nodes without parent remain at top level."""
        elems = [
            TechElement(archi_id='n-1', name='Server A', tech_type='Node'),
            TechElement(archi_id='n-2', name='Server B', tech_type='Node'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 2

    def test_kind_assignment(self):
        """Node→infraNode, non-DB SystemSoftware→infraSoftware, Device→infraNode,
        CommunicationNetwork/Path→infraZone."""
        elems = [
            TechElement(archi_id='n-1', name='Srv', tech_type='Node'),
            TechElement(archi_id='d-1', name='Power', tech_type='Device'),
            TechElement(archi_id='sw-1', name='Nginx', tech_type='SystemSoftware'),
            TechElement(archi_id='ts-1', name='Eureka', tech_type='TechnologyService'),
            TechElement(archi_id='a-1', name='app.war', tech_type='Artifact'),
            TechElement(archi_id='cn-1', name='LAN_Segment', tech_type='CommunicationNetwork'),
            TechElement(archi_id='p-1', name='WAN_Link', tech_type='Path'),
        ]
        roots = build_deployment_topology(elems, [])
        by_name = {r.name: r for r in roots}
        assert by_name['Srv'].kind == 'server'
        assert by_name['Power'].kind == 'server'
        assert by_name['Nginx'].kind == 'infraSoftware'
        assert by_name['Eureka'].kind == 'infraSoftware'
        assert by_name['app.war'].kind == 'infraSoftware'
        assert by_name['LAN_Segment'].kind == 'segment'
        assert by_name['WAN_Link'].kind == 'segment'

    def test_id_collision_resolved(self):
        """Two elements with same name get unique c4_ids."""
        elems = [
            TechElement(archi_id='n-1', name='postgresql', tech_type='SystemSoftware'),
            TechElement(archi_id='n-2', name='postgresql', tech_type='SystemSoftware'),
        ]
        roots = build_deployment_topology(elems, [])
        ids = [r.c4_id for r in roots]
        assert len(set(ids)) == 2  # unique

    def test_empty_input(self):
        """Empty tech_elements → empty result."""
        assert build_deployment_topology([], []) == []

    def test_duplicate_aggregation_no_duplicate_children(self):
        """Duplicate AggregationRelationship should not create duplicate children."""
        elems = [
            TechElement(archi_id='n-1', name='Server', tech_type='Node'),
            TechElement(archi_id='sw-1', name='Postgres', tech_type='SystemSoftware'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AggregationRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
            RawRelationship(
                rel_id='r-2', rel_type='AggregationRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
        ]
        roots = build_deployment_topology(elems, rels)
        assert len(roots) == 1
        assert len(roots[0].children) == 1  # not 2


class TestDeploymentMap:
    def test_realization_app_to_node(self):
        """RealizationRelationship App→Node creates mapping."""
        systems = [
            System(c4_id='efs', name='EFS', archi_id='ac-1'),
        ]
        nodes = [
            DeploymentNode(c4_id='server_1', name='Server 1', archi_id='n-1',
                           tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='RealizationRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='ApplicationComponent', target_id='ac-1',
            ),
        ]
        result = build_deployment_map(systems, nodes, rels, DeploymentMappingContext(sys_domain={'efs': 'channels'}))
        assert len(result) == 1
        assert result[0] == ('channels.efs', 'server_1')

    def test_no_tech_elements(self):
        """Empty deployment_nodes → empty mapping."""
        systems = [System(c4_id='efs', name='EFS', archi_id='ac-1')]
        result = build_deployment_map(systems, [], [], DeploymentMappingContext(sys_domain={'efs': 'channels'}))
        assert result == []

    def test_dedup_pairs(self):
        """Same (app, node) pair from multiple rels → only one mapping."""
        systems = [System(c4_id='efs', name='EFS', archi_id='ac-1')]
        nodes = [
            DeploymentNode(c4_id='srv', name='Srv', archi_id='n-1', tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='RealizationRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='ApplicationComponent', target_id='ac-1',
            ),
            RawRelationship(
                rel_id='r-2', rel_type='RealizationRelationship', name='',
                source_type='ApplicationComponent', source_id='ac-1',
                target_type='Node', target_id='n-1',
            ),
        ]
        result = build_deployment_map(systems, nodes, rels, DeploymentMappingContext(sys_domain={'efs': 'channels'}))
        assert len(result) == 1

    def test_nested_node_qualified_path(self):
        """Nested deployment node gets parent.child path in mapping."""
        systems = [System(c4_id='efs', name='EFS', archi_id='ac-1')]
        child = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                               tech_type='SystemSoftware', kind='infraSoftware')
        parent = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                                tech_type='Node', children=[child])
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='RealizationRelationship', name='',
                source_type='ApplicationComponent', source_id='ac-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
        ]
        result = build_deployment_map(systems, [parent], rels, DeploymentMappingContext(sys_domain={'efs': 'channels'}))
        assert len(result) == 1
        assert result[0] == ('channels.efs', 'srv.pg')

    def test_system_with_subdomain_includes_subdomain_in_path(self):
        """System assigned to subdomain gets domain.subdomain.system path."""
        systems = [
            System(c4_id='efs', name='EFS', archi_id='ac-1'),
        ]
        nodes = [
            DeploymentNode(c4_id='srv', name='Server', archi_id='n-1', tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='RealizationRelationship', name='',
                source_type='ApplicationComponent', source_id='ac-1',
                target_type='Node', target_id='n-1',
            ),
        ]
        result = build_deployment_map(
            systems, nodes, rels,
            DeploymentMappingContext(sys_domain={'efs': 'channels'}, sys_subdomain={'efs': 'retail'}),
        )
        assert len(result) == 1
        assert result[0] == ('channels.retail.efs', 'srv')

    def test_system_without_subdomain_unaffected_when_subdomain_dict_provided(self):
        """System without subdomain keeps domain.system path even when sys_subdomain passed."""
        systems = [
            System(c4_id='efs', name='EFS', archi_id='ac-1'),
        ]
        nodes = [
            DeploymentNode(c4_id='srv', name='Server', archi_id='n-1', tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='RealizationRelationship', name='',
                source_type='ApplicationComponent', source_id='ac-1',
                target_type='Node', target_id='n-1',
            ),
        ]
        result = build_deployment_map(
            systems, nodes, rels,
            DeploymentMappingContext(sys_domain={'efs': 'channels'}, sys_subdomain={}),
        )
        assert len(result) == 1
        assert result[0] == ('channels.efs', 'srv')

    def test_subsystem_inherits_subdomain_from_parent_path(self):
        """Subsystem gets domain.subdomain.system.subsystem path."""
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1')
        systems = [
            System(c4_id='efs', name='EFS', archi_id='ac-1', subsystems=[sub]),
        ]
        nodes = [
            DeploymentNode(c4_id='srv', name='Server', archi_id='n-1', tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='RealizationRelationship', name='',
                source_type='ApplicationComponent', source_id='sub-1',
                target_type='Node', target_id='n-1',
            ),
        ]
        result = build_deployment_map(
            systems, nodes, rels,
            DeploymentMappingContext(sys_domain={'efs': 'channels'}, sys_subdomain={'efs': 'retail'}),
        )
        assert len(result) == 1
        assert result[0] == ('channels.retail.efs.core', 'srv')


class TestAssignDomainsOverrides:
    """Tests for domain_overrides (Pass 0) in assign_domains."""

    def test_override_assigns_domain(self):
        domains = [DomainInfo(c4_id='products', name='Products', archi_ids=set())]
        sys = System(c4_id='crm', name='CRM', archi_id='s-1', metadata={})
        result = assign_domains(
            [sys], domains, promote_children={}, extra_domain_patterns=[],
            domain_overrides={'CRM': 'products'},
        )
        assert sys.domain == 'products'
        assert sys in result['products']

    def test_override_beats_view_membership(self):
        domains = [
            DomainInfo(c4_id='channels', name='Channels', archi_ids={'s-1'}),
            DomainInfo(c4_id='products', name='Products', archi_ids=set()),
        ]
        sys = System(c4_id='crm', name='CRM', archi_id='s-1', metadata={})
        assign_domains(
            [sys], domains, promote_children={}, extra_domain_patterns=[],
            domain_overrides={'CRM': 'products'},
        )
        assert sys.domain == 'products'  # override beats view

    def test_override_creates_new_domain_key(self):
        domains = []
        sys = System(c4_id='crm', name='CRM', archi_id='s-1', metadata={})
        result = assign_domains(
            [sys], domains, promote_children={}, extra_domain_patterns=[],
            domain_overrides={'CRM': 'new_domain'},
        )
        assert sys.domain == 'new_domain'
        assert 'new_domain' in result

    def test_no_overrides_is_noop(self):
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids={'s-1'})]
        sys = System(c4_id='crm', name='CRM', archi_id='s-1', metadata={})
        assign_domains(
            [sys], domains, promote_children={}, extra_domain_patterns=[],
            domain_overrides=None,
        )
        assert sys.domain == 'channels'


class TestReviewedSystemsInBuild:
    """Tests for reviewed_systems tag stripping in build_systems."""

    def test_reviewed_strips_to_review(self):
        comps = [AppComponent(archi_id='id-1', name='Legacy', source_folder='!РАЗБОР')]
        systems, _ = build_systems(comps, SystemBuildConfig(reviewed_systems=['Legacy']))
        assert 'to_review' not in systems[0].tags

    def test_non_reviewed_keeps_tag(self):
        comps = [AppComponent(archi_id='id-1', name='Legacy', source_folder='!РАЗБОР')]
        systems, _ = build_systems(comps, SystemBuildConfig(reviewed_systems=[]))
        assert 'to_review' in systems[0].tags

    def test_reviewed_noop_if_no_tag(self):
        comps = [AppComponent(archi_id='id-1', name='Normal', source_folder='')]
        systems, _ = build_systems(comps, SystemBuildConfig(reviewed_systems=['Normal']))
        assert systems[0].tags == []


# ── CommunicationNetwork/Path → infraZone ───────────────────────────────

class TestInfraZoneKind:
    def test_communication_network_becomes_infra_zone(self):
        """CommunicationNetwork tech_type should produce segment kind."""
        elems = [
            TechElement(archi_id='cn-1', name='LAN Segment', tech_type='CommunicationNetwork'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 1
        assert roots[0].kind == 'segment'

    def test_path_becomes_segment(self):
        """Path tech_type should produce segment kind."""
        elems = [
            TechElement(archi_id='p-1', name='WAN Link', tech_type='Path'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 1
        assert roots[0].kind == 'segment'

    def test_segment_with_child_node(self):
        """segment → vm aggregation creates proper hierarchy."""
        elems = [
            TechElement(archi_id='cn-1', name='VLAN_10', tech_type='CommunicationNetwork'),
            TechElement(archi_id='n-1', name='Server 1', tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AggregationRelationship', name='',
                source_type='CommunicationNetwork', source_id='cn-1',
                target_type='Node', target_id='n-1',
            ),
        ]
        roots = build_deployment_topology(elems, rels)
        assert len(roots) == 1
        assert roots[0].kind == 'segment'
        assert len(roots[0].children) == 1
        assert roots[0].children[0].kind == 'vm'  # Node inside segment → vm


# ── Location → infraLocation ────────────────────────────────────────────

class TestLocationKind:
    def test_location_becomes_site(self):
        """Location tech_type should produce site kind."""
        elems = [
            TechElement(archi_id='loc-1', name='HQ Datacenter', tech_type='Location'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 1
        assert roots[0].kind == 'site'

    def test_location_with_child_node(self):
        """Location → Node aggregation creates proper hierarchy."""
        elems = [
            TechElement(archi_id='loc-1', name='HQ', tech_type='Location'),
            TechElement(archi_id='n-1', name='Server 1', tech_type='Node'),
        ]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AggregationRelationship', name='',
                source_type='Location', source_id='loc-1',
                target_type='Node', target_id='n-1',
            ),
        ]
        roots = build_deployment_topology(elems, rels)
        assert len(roots) == 1
        assert roots[0].kind == 'site'
        assert len(roots[0].children) == 1
        assert roots[0].children[0].kind == 'server'  # Node inside site → server


# ── build_tech_archi_to_c4_map ──────────────────────────────────────────

class TestBuildTechArchiToC4Map:
    def test_basic_mapping(self):
        child = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                               tech_type='SystemSoftware', kind='infraSoftware')
        parent = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                                tech_type='Node', children=[child])
        result = build_tech_archi_to_c4_map([parent])
        assert result['n-1'] == 'srv'
        assert result['sw-1'] == 'srv.pg'

    def test_deployment_path_index_root_no_prefix(self):
        """Root node gets bare c4_id as path, no leading dot."""
        root = DeploymentNode(c4_id='dc_main', name='DC Main', archi_id='loc-1',
                              tech_type='Location', kind='infraLocation')
        result = build_tech_archi_to_c4_map([root])
        assert result['loc-1'] == 'dc_main'
        assert not result['loc-1'].startswith('.')

    def test_deployment_path_index_nested_qualified(self):
        """Deeply nested node gets fully qualified parent.child.grandchild path."""
        grandchild = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                                    tech_type='SystemSoftware', kind='infraSoftware')
        child = DeploymentNode(c4_id='worker', name='Worker', archi_id='n-1',
                               tech_type='Node', kind='infraNode', children=[grandchild])
        root = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                              tech_type='Location', kind='infraLocation', children=[child])
        result = build_tech_archi_to_c4_map([root])
        assert result['loc-1'] == 'dc'
        assert result['n-1'] == 'dc.worker'
        assert result['sw-1'] == 'dc.worker.pg'


# ── Kind assignment ────────────────────────────────────────────────────

class TestEnrichDeploymentFromVisualNesting:
    def test_empty_pairs_returns_zero(self):
        nodes = [DeploymentNode(c4_id='n1', name='N1', archi_id='a-1', tech_type='Node')]
        assert enrich_deployment_from_visual_nesting(nodes, []) == 0

    def test_reparents_root_to_parent(self):
        parent = DeploymentNode(c4_id='parent', name='Parent', archi_id='p-1', tech_type='Node')
        child = DeploymentNode(c4_id='child', name='Child', archi_id='c-1', tech_type='Node')
        nodes = [parent, child]
        count = enrich_deployment_from_visual_nesting(nodes, [('p-1', 'c-1')])
        assert count == 1
        assert child in parent.children
        # child should no longer be a root node
        assert child not in nodes

    def test_unknown_archi_ids_ignored(self):
        parent = DeploymentNode(c4_id='n1', name='N1', archi_id='a-1', tech_type='Node')
        nodes = [parent]
        count = enrich_deployment_from_visual_nesting(nodes, [('unknown', 'also-unknown')])
        assert count == 0
        assert len(nodes) == 1

    def test_already_nested_not_reparented_again(self):
        child = DeploymentNode(c4_id='child', name='Child', archi_id='c-1', tech_type='Node')
        parent = DeploymentNode(c4_id='parent', name='Parent', archi_id='p-1', tech_type='Node',
                                children=[child])
        nodes = [parent]
        # child is not in root_ids, so should be ignored
        count = enrich_deployment_from_visual_nesting(nodes, [('p-1', 'c-1')])
        assert count == 0

    def test_self_reference_ignored(self):
        node = DeploymentNode(c4_id='n1', name='N1', archi_id='a-1', tech_type='Node')
        nodes = [node]
        count = enrich_deployment_from_visual_nesting(nodes, [('a-1', 'a-1')])
        assert count == 0

    def test_no_cycle_created(self):
        """Parent should not be reparented as child of one of its descendants."""
        # A has child B → trying to make A child of B would create cycle
        child_b = DeploymentNode(c4_id='b', name='B', archi_id='b-1', tech_type='Node')
        parent_a = DeploymentNode(c4_id='a', name='A', archi_id='a-1', tech_type='Node',
                                  children=[child_b])
        nodes = [parent_a, child_b]
        # b-1 is not in root_ids, but a-1 is; trying ('b-1', 'a-1') → make A child of B
        # child_aid='a-1', parent_aid='b-1'
        # _is_descendant(A, 'b-1') → A.children=[B], B.archi_id=='b-1' → True → skip
        count = enrich_deployment_from_visual_nesting(nodes, [('b-1', 'a-1')])
        assert count == 0

    def test_deep_cycle_detection(self):
        """Detect cycle through multiple levels of nesting (hits recursive _is_descendant)."""
        # B (root) has grandchild C (not a root): B → X(hidden) → C
        # X is not in deployment_nodes (not a root), only B and A are roots
        # Setup: A(root), B(root), X is a child of A, C is a child of X
        # Trying to make A a child of C forces _is_descendant(A, c-archi)
        # A.children=[X], X.archi_id!='c-archi' → recurse: X.children=[C], C.archi_id=='c-archi' → True
        c_node = DeploymentNode(c4_id='c', name='C', archi_id='c-1', tech_type='Node')
        x_node = DeploymentNode(c4_id='x', name='X', archi_id='x-1', tech_type='Node',
                                children=[c_node])
        a_node = DeploymentNode(c4_id='a', name='A', archi_id='a-1', tech_type='Node',
                                children=[x_node])
        # B is a root, C is a root (both in deployment_nodes)
        nodes = [a_node, c_node]
        # Try making a-1 a child of c-1: ('c-1', 'a-1')
        # child_aid='a-1', parent_aid='c-1'
        # _is_descendant(a_node, 'c-1') → a.children=[x] → x.archi_id!='c-1' →
        #   _is_descendant(x, 'c-1') → x.children=[c] → c.archi_id=='c-1' → True → lines 167-168
        count = enrich_deployment_from_visual_nesting(nodes, [('c-1', 'a-1')])
        assert count == 0

    def test_multiple_children_reparented(self):
        parent = DeploymentNode(c4_id='parent', name='Parent', archi_id='p-1', tech_type='Node')
        child1 = DeploymentNode(c4_id='c1', name='Child1', archi_id='c-1', tech_type='Node')
        child2 = DeploymentNode(c4_id='c2', name='Child2', archi_id='c-2', tech_type='Node')
        nodes = [parent, child1, child2]
        count = enrich_deployment_from_visual_nesting(nodes, [('p-1', 'c-1'), ('p-1', 'c-2')])
        assert count == 2
        assert len(nodes) == 1  # only parent remains as root

    def test_first_diagram_wins_on_conflict(self):
        """When two visual nesting pairs propose different parents for the same child,
        the first pair wins (first diagram is most authoritative)."""
        parent_a = DeploymentNode(c4_id='pa', name='ParentA', archi_id='pa-1', tech_type='Node')
        parent_b = DeploymentNode(c4_id='pb', name='ParentB', archi_id='pb-1', tech_type='Node')
        child = DeploymentNode(c4_id='ch', name='Child', archi_id='ch-1', tech_type='Node')
        nodes = [parent_a, parent_b, child]
        # Two conflicting pairs: pa-1 wants child, pb-1 also wants child
        count = enrich_deployment_from_visual_nesting(
            nodes, [('pa-1', 'ch-1'), ('pb-1', 'ch-1')])
        assert count == 1
        assert child in parent_a.children
        assert child not in parent_b.children

    def test_already_nested_by_aggregation_skipped(self):
        """A node already nested via AggregationRelationship (not a root) is not
        re-parented by visual nesting, even if visual nesting suggests a different parent."""
        child = DeploymentNode(c4_id='ch', name='Child', archi_id='ch-1', tech_type='Node')
        agg_parent = DeploymentNode(c4_id='ap', name='AggParent', archi_id='ap-1',
                                    tech_type='Node', children=[child])
        visual_parent = DeploymentNode(c4_id='vp', name='VisParent', archi_id='vp-1',
                                       tech_type='Node')
        nodes = [agg_parent, visual_parent]  # child is NOT a root
        count = enrich_deployment_from_visual_nesting(nodes, [('vp-1', 'ch-1')])
        assert count == 0
        assert child in agg_parent.children
        assert child not in visual_parent.children

    def test_enrichment_counts_match(self):
        """Returned count must equal the actual number of nodes moved."""
        parent = DeploymentNode(c4_id='p', name='Parent', archi_id='p-1', tech_type='Node')
        c1 = DeploymentNode(c4_id='c1', name='C1', archi_id='c-1', tech_type='Node')
        c2 = DeploymentNode(c4_id='c2', name='C2', archi_id='c-2', tech_type='Node')
        c3 = DeploymentNode(c4_id='c3', name='C3', archi_id='c-3', tech_type='Node')
        nodes = [parent, c1, c2, c3]
        count = enrich_deployment_from_visual_nesting(
            nodes, [('p-1', 'c-1'), ('p-1', 'c-2'), ('p-1', 'c-3')])
        assert count == 3
        assert len(parent.children) == 3
        assert len(nodes) == 1  # only parent remains


# ── _extract_visual_nesting (parser) ─────────────────────────────────────


class TestExtractVisualNesting:
    def test_visual_nesting_through_group_container(self):
        """A group element without archimateElement (no archi_id) wrapping two Nodes
        should propagate the grandparent's archi_id to both children."""
        # Structure: grandparent(archi=gp-1) > group(no archi) > child1(archi=c-1) + child2(archi=c-2)
        xml_str = '''<root>
            <children>
                <archimateElement href="tech.xml#gp-1"/>
                <children>
                    <children>
                        <archimateElement href="tech.xml#c-1"/>
                    </children>
                    <children>
                        <archimateElement href="tech.xml#c-2"/>
                    </children>
                </children>
            </children>
        </root>'''
        root = ET.fromstring(xml_str)
        nesting: list[tuple[str, str]] = []
        _extract_visual_nesting(root, None, nesting)
        # Both children should be nested under grandparent (gp-1), not lost
        assert ('gp-1', 'c-1') in nesting
        assert ('gp-1', 'c-2') in nesting

    def test_direct_nesting_without_group(self):
        """Direct parent-child nesting without intermediate groups."""
        xml_str = '''<root>
            <children>
                <archimateElement href="tech.xml#p-1"/>
                <children>
                    <archimateElement href="tech.xml#c-1"/>
                </children>
            </children>
        </root>'''
        root = ET.fromstring(xml_str)
        nesting: list[tuple[str, str]] = []
        _extract_visual_nesting(root, None, nesting)
        assert nesting == [('p-1', 'c-1')]

    def test_root_element_without_parent_not_added(self):
        """Top-level element with no parent should not produce a nesting pair."""
        xml_str = '''<root>
            <children>
                <archimateElement href="tech.xml#r-1"/>
            </children>
        </root>'''
        root = ET.fromstring(xml_str)
        nesting: list[tuple[str, str]] = []
        _extract_visual_nesting(root, None, nesting)
        assert nesting == []


# ── build_integrations edge cases ────────────────────────────────────────

class TestValidateDeploymentTree:
    def test_valid_tree_no_violations(self):
        """Well-formed tree returns no violations."""
        sw = DeploymentNode(c4_id='pg', name='PG', archi_id='sw-1',
                            tech_type='SystemSoftware', kind='infraSoftware')
        node = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                              tech_type='Node', kind='infraNode', children=[sw])
        loc = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                             tech_type='Location', kind='infraLocation', children=[node])
        assert validate_deployment_tree([loc]) == []

    def test_leaf_with_children_violation(self):
        """infraSoftware with children triggers violation (a)."""
        child = DeploymentNode(c4_id='mod', name='Module', archi_id='sw-2',
                               tech_type='SystemSoftware', kind='infraSoftware')
        leaf = DeploymentNode(c4_id='pg', name='PG', archi_id='sw-1',
                              tech_type='infraSoftware', kind='infraSoftware',
                              children=[child])
        violations = validate_deployment_tree([leaf])
        assert any('Leaf' in v and 'PG' in v for v in violations)

    def test_datastore_leaf_with_children_violation(self):
        """dataStore with children also triggers violation (a)."""
        child = DeploymentNode(c4_id='tbl', name='Table', archi_id='sw-2',
                               tech_type='SystemSoftware', kind='infraSoftware')
        ds = DeploymentNode(c4_id='oracle', name='Oracle', archi_id='ds-1',
                            tech_type='SystemSoftware', kind='infraSoftware',
                            children=[child])
        violations = validate_deployment_tree([ds])
        assert any('Leaf' in v and 'Oracle' in v for v in violations)

    def test_duplicate_archi_id_violation(self):
        """Two nodes with same archi_id triggers violation (b)."""
        n1 = DeploymentNode(c4_id='a', name='NodeA', archi_id='dup-1',
                            tech_type='Node', kind='infraNode')
        n2 = DeploymentNode(c4_id='b', name='NodeB', archi_id='dup-1',
                            tech_type='Node', kind='infraNode')
        violations = validate_deployment_tree([n1, n2])
        assert any('Duplicate archi_id' in v for v in violations)

    def test_sibling_c4_id_uniqueness_violation(self):
        """Two siblings with same c4_id triggers violation (c)."""
        c1 = DeploymentNode(c4_id='srv', name='Server1', archi_id='n-1',
                            tech_type='Node', kind='infraNode')
        c2 = DeploymentNode(c4_id='srv', name='Server2', archi_id='n-2',
                            tech_type='Node', kind='infraNode')
        parent = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                                tech_type='Location', kind='infraLocation',
                                children=[c1, c2])
        violations = validate_deployment_tree([parent])
        assert any('Duplicate sibling c4_id' in v for v in violations)

    def test_double_dot_path_violation(self):
        """A node producing '..' in qualified path triggers violation (d)."""
        # A node with empty c4_id under a parent would produce 'parent.' path
        child = DeploymentNode(c4_id='', name='Empty', archi_id='e-1',
                               tech_type='Node', kind='infraNode')
        DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                       tech_type='Location', kind='infraLocation',
                       children=[child])
        # parent path = 'dc', child path = 'dc.' — check if '..' appears
        # Actually '..' requires two adjacent dots: e.g. parent c4_id='a', child c4_id=''
        # path would be 'a.' which has no '..' — need nested empty
        inner = DeploymentNode(c4_id='x', name='Inner', archi_id='i-1',
                               tech_type='Node', kind='infraNode')
        mid = DeploymentNode(c4_id='', name='Mid', archi_id='m-1',
                             tech_type='Node', kind='infraNode', children=[inner])
        root = DeploymentNode(c4_id='top', name='Top', archi_id='r-1',
                              tech_type='Location', kind='infraLocation',
                              children=[mid])
        violations = validate_deployment_tree([root])
        # 'top..x' contains '..' — must be caught
        assert any('..' in v for v in violations), f'Expected double-dot violation, got: {violations}'


# ── Builder encapsulation (Issue #1) ────────────────────────────────────

