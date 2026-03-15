"""Tests for archi2likec4.builders — system hierarchy, integrations, domains."""


from archi2likec4.builders import (
    apply_domain_prefix,
    assign_domains,
    assign_subdomains,
    attach_functions,
    attach_interfaces,
    build_archi_to_c4_map,
    build_data_access,
    build_data_entities,
    build_datastore_entity_links,
    build_deployment_map,
    build_deployment_topology,
    build_integrations,
    build_systems,
    build_tech_archi_to_c4_map,
)
from archi2likec4.models import (
    AppComponent,
    AppFunction,
    AppInterface,
    DataAccess,
    DataEntity,
    DataObject,
    DeploymentNode,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    RawRelationship,
    Subsystem,
    System,
    TechElement,
)

# ── build_systems ────────────────────────────────────────────────────────

class TestBuildSystems:
    def test_simple_system(self):
        comps = [AppComponent(archi_id='id-1', name='CRM')]
        systems, _ = build_systems(comps, promote_children={})
        assert len(systems) == 1
        assert systems[0].c4_id == 'crm'
        assert systems[0].name == 'CRM'
        assert systems[0].archi_id == 'id-1'

    def test_dot_creates_subsystem(self):
        comps = [
            AppComponent(archi_id='id-1', name='CRM'),
            AppComponent(archi_id='id-2', name='CRM.Core'),
        ]
        systems, _ = build_systems(comps, promote_children={})
        assert len(systems) == 1
        assert len(systems[0].subsystems) == 1
        assert systems[0].subsystems[0].name == 'CRM.Core'

    def test_dot_without_parent_becomes_system(self):
        """If parent part doesn't match a known system, treat as standalone system."""
        comps = [AppComponent(archi_id='id-1', name='Unknown.Module')]
        systems, _ = build_systems(comps, promote_children={})
        assert len(systems) == 1
        assert systems[0].name == 'Unknown.Module'

    def test_duplicate_names_keep_richer(self):
        """When two components have the same name, keep the one with more properties."""
        comps = [
            AppComponent(archi_id='id-1', name='CRM', properties={}),
            AppComponent(archi_id='id-2', name='CRM', properties={'CI': '123', 'Full name': 'CRM Full'}),
        ]
        systems, _ = build_systems(comps, promote_children={})
        assert len(systems) == 1
        assert systems[0].archi_id == 'id-2'  # richer one wins
        assert 'id-1' in systems[0].extra_archi_ids

    def test_trailing_dot_stripped(self):
        comps = [AppComponent(archi_id='id-1', name='CRM.')]
        systems, _ = build_systems(comps, promote_children={})
        assert len(systems) == 1
        assert systems[0].name == 'CRM'

    def test_tags_from_source_folder(self):
        comps = [
            AppComponent(archi_id='id-1', name='ExtSvc', source_folder='!External_services'),
            AppComponent(archi_id='id-2', name='Review', source_folder='!РАЗБОР'),
        ]
        systems, _ = build_systems(comps, promote_children={})
        sys_by_name = {s.name: s for s in systems}
        assert 'external' in sys_by_name['ExtSvc'].tags
        assert 'to_review' in sys_by_name['Review'].tags

    def test_sorted_by_name(self):
        comps = [
            AppComponent(archi_id='id-1', name='Zebra'),
            AppComponent(archi_id='id-2', name='Alpha'),
        ]
        systems, _ = build_systems(comps, promote_children={})
        assert systems[0].name == 'Alpha'
        assert systems[1].name == 'Zebra'

    def test_multiple_subsystems(self):
        comps = [
            AppComponent(archi_id='id-1', name='CRM'),
            AppComponent(archi_id='id-2', name='CRM.Core'),
            AppComponent(archi_id='id-3', name='CRM.API'),
        ]
        systems, _ = build_systems(comps, promote_children={})
        assert len(systems) == 1
        assert len(systems[0].subsystems) == 2


# ── attach_functions ─────────────────────────────────────────────────────

class TestAttachFunctions:
    def _make_system(self, archi_id='sys-1', name='TestSys', c4_id='test_sys'):
        return System(c4_id=c4_id, name=name, archi_id=archi_id)

    def test_attach_via_filesystem_parent(self):
        sys = self._make_system()
        fn = AppFunction(archi_id='fn-1', name='DoStuff', parent_archi_id='sys-1')
        orphans = attach_functions([sys], [fn])
        assert orphans == 0
        assert len(sys.functions) == 1
        assert sys.functions[0].c4_id == 'dostuff'

    def test_relationship_parent_takes_priority(self):
        sys1 = self._make_system(archi_id='sys-1', name='Sys1', c4_id='sys1')
        sys2 = self._make_system(archi_id='sys-2', name='Sys2', c4_id='sys2')
        fn = AppFunction(archi_id='fn-1', name='DoStuff', parent_archi_id='sys-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-2',
                target_type='ApplicationFunction', target_id='fn-1',
            ),
        ]
        orphans = attach_functions([sys1, sys2], [fn], rels)
        assert orphans == 0
        assert len(sys1.functions) == 0  # filesystem parent NOT used
        assert len(sys2.functions) == 1  # relationship parent used

    def test_orphan_counted(self):
        sys = self._make_system()
        fn = AppFunction(archi_id='fn-1', name='Orphan', parent_archi_id='')
        orphans = attach_functions([sys], [fn])
        assert orphans == 1

    def test_attach_to_subsystem(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1')
        sys = self._make_system()
        sys.subsystems.append(sub)
        fn = AppFunction(archi_id='fn-1', name='CoreFunc', parent_archi_id='sub-1')
        orphans = attach_functions([sys], [fn])
        assert orphans == 0
        assert len(sub.functions) == 1

    def test_unique_c4_ids_within_parent(self):
        sys = self._make_system()
        fn1 = AppFunction(archi_id='fn-1', name='Action', parent_archi_id='sys-1')
        fn2 = AppFunction(archi_id='fn-2', name='Action', parent_archi_id='sys-1')
        attach_functions([sys], [fn1, fn2])
        ids = [f.c4_id for f in sys.functions]
        assert len(ids) == 2
        assert len(set(ids)) == 2  # all unique

    def test_extra_archi_ids_used(self):
        """Functions should resolve to system via extra_archi_ids too."""
        sys = self._make_system(archi_id='sys-1')
        sys.extra_archi_ids = ['sys-dup']
        fn = AppFunction(archi_id='fn-1', name='DupFunc', parent_archi_id='sys-dup')
        orphans = attach_functions([sys], [fn])
        assert orphans == 0
        assert len(sys.functions) == 1


# ── build_data_entities ──────────────────────────────────────────────────

class TestBuildDataEntities:
    def test_basic(self):
        objs = [DataObject(archi_id='do-1', name='Account')]
        entities = build_data_entities(objs, set())
        assert len(entities) == 1
        assert entities[0].c4_id == 'de_account'

    def test_unique_ids(self):
        objs = [
            DataObject(archi_id='do-1', name='Account'),
            DataObject(archi_id='do-2', name='Account'),
        ]
        entities = build_data_entities(objs, set())
        ids = [e.c4_id for e in entities]
        assert len(set(ids)) == 2

    def test_avoids_used_ids(self):
        objs = [DataObject(archi_id='do-1', name='Account')]
        used = {'de_account'}
        entities = build_data_entities(objs, used)
        assert entities[0].c4_id == 'de_account_2'


# ── assign_domains ───────────────────────────────────────────────────────

class TestAssignDomains:
    def test_basic_assignment(self):
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids={'sys-1'})]
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1')
        result = assign_domains([sys], domains)
        assert len(result['channels']) == 1
        assert sys.domain == 'channels'

    def test_unassigned(self):
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids={'other-id'})]
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        result = assign_domains([sys], domains, promote_children={})
        assert len(result['unassigned']) == 1
        assert sys.domain == 'unassigned'

    def test_extra_domain_patterns(self):
        """Systems matching extra_domain_patterns should be assigned."""
        domains = []
        sys = System(c4_id='elk', name='ELK', archi_id='sys-1')
        patterns = [{'c4_id': 'platform', 'name': 'Platform', 'patterns': ['ELK', 'Grafana']}]
        assign_domains([sys], domains, extra_domain_patterns=patterns)
        # ELK matches 'platform' pattern
        assert sys.domain == 'platform'

    def test_most_hits_wins(self):
        d1 = DomainInfo(c4_id='d1', name='D1', archi_ids={'sys-1'})
        d2 = DomainInfo(c4_id='d2', name='D2', archi_ids={'sys-1', 'sub-1'})
        sub = Subsystem(c4_id='sub', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', subsystems=[sub])
        assign_domains([sys], [d1, d2])
        assert sys.domain == 'd2'  # 2 hits vs 1


# ── apply_domain_prefix ──────────────────────────────────────────────────

class TestApplyDomainPrefix:
    def test_integration_paths(self):
        intg = Integration(source_path='efs', target_path='crm', name='flow', rel_type='')
        sys_domain = {'efs': 'channels', 'crm': 'customer_service'}
        apply_domain_prefix([intg], [], sys_domain)
        assert intg.source_path == 'channels.efs'
        assert intg.target_path == 'customer_service.crm'

    def test_data_access_paths(self):
        da = DataAccess(system_path='efs', entity_id='de_account', name='')
        sys_domain = {'efs': 'channels'}
        apply_domain_prefix([], [da], sys_domain)
        assert da.system_path == 'channels.efs'

    def test_unknown_domain_fallback(self):
        intg = Integration(source_path='unknown', target_path='efs', name='', rel_type='')
        sys_domain = {'efs': 'channels'}
        apply_domain_prefix([intg], [], sys_domain)
        assert intg.source_path == 'unassigned.unknown'


# ── build_archi_to_c4_map ───────────────────────────────────────────────

class TestBuildArchiToC4Map:
    def test_system_mapping(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sys-1'] == 'channels.efs'

    def test_subsystem_mapping(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', subsystems=[sub])
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sub-1'] == 'channels.efs.core'

    def test_function_mapping(self):
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', functions=[fn])
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['fn-1'] == 'channels.efs.do_stuff'

    def test_extra_archi_ids(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     extra_archi_ids=['sys-dup'])
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sys-dup'] == 'channels.efs'


# ── promote_children ────────────────────────────────────────────────────

class TestPromoteChildren:
    """Tests for PROMOTE_CHILDREN feature — promoting subsystems to standalone systems."""

    def test_promoted_becomes_system(self):
        """2-segment promoted name becomes standalone system, parent disappears."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.ServiceA'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        names = [s.name for s in systems]
        assert 'Platform.ServiceA' in names
        assert 'Platform' not in names

    def test_promoted_parent_removed(self):
        """Promoted parent is not in the result even if it exists as AppComponent."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.A'),
            AppComponent(archi_id='id-2', name='Platform.B'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        assert all(s.name != 'Platform' for s in systems)
        assert len(systems) == 2

    def test_promoted_parent_archi_id_fans_out(self):
        """Parent archi_id fans out to ALL children (not remapped to one)."""
        comps = [
            AppComponent(archi_id='id-parent', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.ServiceA'),
            AppComponent(archi_id='id-2', name='Platform.ServiceB'),
        ]
        systems, promoted_parents = build_systems(comps, promote_children={'Platform': 'infra'})
        sys_by_name = {s.name: s for s in systems}
        # Neither child should have parent archi_id in extra_archi_ids
        assert 'id-parent' not in sys_by_name['Platform.ServiceA'].extra_archi_ids
        assert 'id-parent' not in sys_by_name['Platform.ServiceB'].extra_archi_ids
        # promoted_parents should map parent archi_id → all children c4_ids
        assert 'id-parent' in promoted_parents
        assert sorted(promoted_parents['id-parent']) == ['platform_servicea', 'platform_serviceb']

    def test_three_segment_becomes_subsystem(self):
        """3-segment name under promoted parent → subsystem of the 2-segment system."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Core'),
            AppComponent(archi_id='id-2', name='Platform.Core.Module'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        assert len(systems) == 1
        assert systems[0].name == 'Platform.Core'
        assert len(systems[0].subsystems) == 1
        assert systems[0].subsystems[0].name == 'Platform.Core.Module'
        assert systems[0].subsystems[0].c4_id == 'module'

    def test_three_segment_only_promoted_parents_populated(self):
        """Parent with only 3-segment children must still appear in promoted_parents."""
        comps = [
            AppComponent(archi_id='id-parent', name='Platform'),
            AppComponent(archi_id='id-2', name='Platform.Core.Module'),
        ]
        systems, promoted_parents = build_systems(comps, promote_children={'Platform': 'infra'})
        # Auto-created 2-seg system should exist
        assert len(systems) == 1
        assert systems[0].name == 'Platform.Core'
        # Parent archi_id must fan out to auto-created child
        assert 'id-parent' in promoted_parents
        assert len(promoted_parents['id-parent']) == 1

    def test_non_promoted_parent_unchanged(self):
        """Systems not in promote_children keep the old subsystem behavior."""
        comps = [
            AppComponent(archi_id='id-1', name='ABC'),
            AppComponent(archi_id='id-2', name='ABC.Sub'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        assert len(systems) == 1
        assert systems[0].name == 'ABC'
        assert len(systems[0].subsystems) == 1

    def test_promoted_c4_id(self):
        """Promoted system c4_id is derived from the full dotted name."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Card_Service'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        assert systems[0].c4_id == 'platform_card_service'

    def test_promoted_preserves_metadata(self):
        """Promoted system retains its properties, tags, etc."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Svc',
                         properties={'CI': 'CI-42'}, source_folder='!External_services'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        s = systems[0]
        assert s.metadata['ci'] == 'CI-42'
        assert 'external' in s.tags

    def test_multiple_promoted_children(self):
        """Multiple children of promoted parent become separate systems."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.A'),
            AppComponent(archi_id='id-2', name='Platform.B'),
            AppComponent(archi_id='id-3', name='Platform.C'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        names = sorted(s.name for s in systems)
        assert names == ['Platform.A', 'Platform.B', 'Platform.C']

    def test_warn_threshold(self, caplog):
        """Parent with ≥ threshold subsystems triggers a warning."""
        comps = [AppComponent(archi_id='id-p', name='BigSys')]
        comps += [
            AppComponent(archi_id=f'id-{i}', name=f'BigSys.Sub{i}')
            for i in range(12)
        ]
        with caplog.at_level('WARNING', logger='archi2likec4'):
            systems, _ = build_systems(comps, promote_children={})
        assert any('BigSys' in msg and 'PROMOTE_CHILDREN' in msg
                    for msg in caplog.messages)

    def test_no_warn_below_threshold(self, caplog):
        """Parent with < threshold subsystems does not trigger a warning."""
        comps = [
            AppComponent(archi_id='id-p', name='SmallSys'),
            AppComponent(archi_id='id-1', name='SmallSys.A'),
            AppComponent(archi_id='id-2', name='SmallSys.B'),
            AppComponent(archi_id='id-3', name='SmallSys.C'),
        ]
        with caplog.at_level('WARNING', logger='archi2likec4'):
            systems, _ = build_systems(comps, promote_children={})
        assert not any('SmallSys' in msg for msg in caplog.messages)

    def test_parent_kept_when_no_children(self):
        """Parent in promote_children is kept if no dot-children exist (P2 fix)."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Other'),
        ]
        systems, _ = build_systems(comps, promote_children={'Platform': 'infra'})
        names = [s.name for s in systems]
        assert 'Platform' in names  # not removed since no children found

    def test_parent_archi_id_function_becomes_orphan(self):
        """Functions referencing promoted parent become honest orphans (fan-out)."""
        comps = [
            AppComponent(archi_id='id-parent', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Alpha'),
            AppComponent(archi_id='id-2', name='Platform.Beta'),
        ]
        systems, promoted_parents = build_systems(comps, promote_children={'Platform': 'infra'})
        fn = AppFunction(archi_id='fn-1', name='ParentFunc', parent_archi_id='id-parent')
        orphans = attach_functions(systems, [fn], promoted_parents=promoted_parents)
        # Function becomes orphan — parent no longer exists as a single system
        assert orphans == 1
        sys_by_name = {s.name: s for s in systems}
        assert len(sys_by_name['Platform.Alpha'].functions) == 0
        assert len(sys_by_name['Platform.Beta'].functions) == 0


# ── attach_interfaces: reverse direction ────────────────────────────────

class TestAttachInterfacesReverse:
    """Tests for reverse structural direction (Interface → Component)."""

    def test_reverse_composition_resolves_interface(self):
        """Interface → Component composition should resolve interface ownership."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='EFS.API',
                             documentation='http://api.efs.com')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationInterface', source_id='iface-1',
                target_type='ApplicationComponent', target_id='sys-1',
            ),
        ]
        iface_c4_path = attach_interfaces([sys], [iface], rels)
        assert 'iface-1' in iface_c4_path
        assert iface_c4_path['iface-1'] == 'efs'

    def test_forward_direction_takes_priority(self):
        """If both directions exist, forward (Component → Interface) wins."""
        sys1 = System(c4_id='sys1', name='Sys1', archi_id='sys-1')
        sys2 = System(c4_id='sys2', name='Sys2', archi_id='sys-2')
        iface = AppInterface(archi_id='iface-1', name='SharedAPI')
        rels = [
            # Forward: Sys1 → Interface
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationInterface', target_id='iface-1',
            ),
            # Reverse: Interface → Sys2
            RawRelationship(
                rel_id='r-2', rel_type='CompositionRelationship', name='',
                source_type='ApplicationInterface', source_id='iface-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        iface_c4_path = attach_interfaces([sys1, sys2], [iface], rels)
        # Forward direction should win (processed first, setdefault for reverse)
        assert iface_c4_path['iface-1'] == 'sys1'


# ── assign_domains: fallback_domain ─────────────────────────────────────

class TestAssignDomainsFallback:
    """Tests for PROMOTE_CHILDREN fallback_domain in assign_domains."""

    def test_promoted_child_gets_fallback_domain(self):
        """Unassigned promoted child should get fallback domain from config."""
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids=set())]
        sys = System(c4_id='efs_card_service', name='EFS.Card_Service', archi_id='s-1')
        result = assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        assert sys.domain == 'channels'
        assert sys in result['channels']

    def test_non_promoted_stays_unassigned(self):
        """System not matching any promote prefix stays unassigned."""
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids=set())]
        sys = System(c4_id='crm', name='CRM', archi_id='s-1')
        assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        assert sys.domain != 'channels'

    def test_view_membership_overrides_fallback(self):
        """If system is assigned via view membership, fallback is not used."""
        domains = [
            DomainInfo(c4_id='products', name='Products', archi_ids={'s-1'}),
            DomainInfo(c4_id='channels', name='Channels', archi_ids=set()),
        ]
        sys = System(c4_id='efs_svc', name='EFS.Svc', archi_id='s-1')
        assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        # View membership (products) takes priority over fallback (channels)
        assert sys.domain == 'products'

    def test_custom_extra_domain_patterns(self):
        """Custom extra_domain_patterns override hardcoded EXTRA_DOMAIN_PATTERNS."""
        domains = [DomainInfo(c4_id='core', name='Core', archi_ids=set())]
        sys = System(c4_id='my_grafana', name='Grafana', archi_id='s-1')
        custom_patterns = [
            {'c4_id': 'monitoring', 'name': 'Monitoring', 'patterns': ['Grafana', 'ELK']},
        ]
        result = assign_domains(
            [sys], domains, promote_children={},
            extra_domain_patterns=custom_patterns)
        assert sys.domain == 'monitoring'
        assert sys in result['monitoring']

    def test_empty_extra_domain_patterns(self):
        """Empty extra_domain_patterns means no third-pass assignment."""
        domains = [DomainInfo(c4_id='core', name='Core', archi_ids=set())]
        sys = System(c4_id='my_grafana', name='Grafana', archi_id='s-1')
        result = assign_domains(
            [sys], domains, promote_children={},
            extra_domain_patterns=[])
        # With no patterns, system stays unassigned
        assert sys.domain == 'unassigned'
        assert sys in result['unassigned']


# ── integration fan-out ──────────────────────────────────────────────────

class TestIntegrationFanOut:
    """Tests for promoted parent fan-out in build_integrations."""

    def test_source_fans_out_to_all_children(self):
        """Integration from promoted parent → target fans out to all children."""
        sys_a = System(c4_id='child_a', name='P.A', archi_id='id-a')
        sys_b = System(c4_id='child_b', name='P.B', archi_id='id-b')
        sys_x = System(c4_id='target', name='Target', archi_id='id-x')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='data',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='ApplicationComponent', target_id='id-x',
            ),
        ]
        promoted = {'id-parent': ['child_a', 'child_b']}
        intgs, _, _ = build_integrations([sys_a, sys_b, sys_x], rels, {}, promoted)
        pairs = sorted((i.source_path, i.target_path) for i in intgs)
        assert ('child_a', 'target') in pairs
        assert ('child_b', 'target') in pairs

    def test_target_fans_out_to_all_children(self):
        """Integration from source → promoted parent fans out to all children."""
        sys_x = System(c4_id='source', name='Source', archi_id='id-x')
        sys_a = System(c4_id='child_a', name='P.A', archi_id='id-a')
        sys_b = System(c4_id='child_b', name='P.B', archi_id='id-b')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='call',
                source_type='ApplicationComponent', source_id='id-x',
                target_type='ApplicationComponent', target_id='id-parent',
            ),
        ]
        promoted = {'id-parent': ['child_a', 'child_b']}
        intgs, _, _ = build_integrations([sys_x, sys_a, sys_b], rels, {}, promoted)
        pairs = sorted((i.source_path, i.target_path) for i in intgs)
        assert ('source', 'child_a') in pairs
        assert ('source', 'child_b') in pairs

    def test_no_fanout_without_promoted(self):
        """Without promoted_parents, unresolvable endpoints are skipped."""
        sys_x = System(c4_id='target', name='Target', archi_id='id-x')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='ApplicationComponent', target_id='id-x',
            ),
        ]
        intgs, skipped, total = build_integrations([sys_x], rels, {})
        assert len(intgs) == 0  # skipped, no promoted_parents
        assert skipped == 1

    def test_fanout_skips_self_loops(self):
        """Fan-out doesn't create self-loops between siblings."""
        sys_a = System(c4_id='child_a', name='P.A', archi_id='id-a')
        sys_b = System(c4_id='child_b', name='P.B', archi_id='id-b')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='ApplicationComponent', target_id='id-a',
            ),
        ]
        promoted = {'id-parent': ['child_a', 'child_b']}
        intgs, _, _ = build_integrations([sys_a, sys_b], rels, {}, promoted)
        # child_a → child_a would be self-loop, only child_b → child_a
        pairs = [(i.source_path, i.target_path) for i in intgs]
        assert ('child_a', 'child_a') not in pairs
        assert ('child_b', 'child_a') in pairs


# ── data access fan-out ──────────────────────────────────────────────────

class TestDataAccessFanOut:
    """Tests for promoted parent fan-out in build_data_access."""

    def test_source_fans_out_to_all_children(self):
        """Data access from promoted parent → entity fans out to all children."""
        sys_a = System(c4_id='child_a', name='P.A', archi_id='id-a')
        sys_b = System(c4_id='child_b', name='P.B', archi_id='id-b')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='reads',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        promoted = {'id-parent': ['child_a', 'child_b']}
        accesses = build_data_access([sys_a, sys_b], [entity], rels, promoted)
        paths = sorted(da.system_path for da in accesses)
        assert 'child_a' in paths
        assert 'child_b' in paths

    def test_no_fanout_without_promoted(self):
        """Without promoted_parents, unresolvable endpoints are skipped."""
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='reads',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        accesses = build_data_access([], [entity], rels)
        assert len(accesses) == 0


# ── Deployment topology ─────────────────────────────────────────────────

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
        assert roots[0].kind == 'infraNode'
        assert len(roots[0].children) == 1
        assert roots[0].children[0].name == 'PostgreSQL'
        assert roots[0].children[0].kind == 'dataStore'

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
        assert by_name['Srv'].kind == 'infraNode'
        assert by_name['Power'].kind == 'infraNode'
        assert by_name['Nginx'].kind == 'infraSoftware'
        assert by_name['Eureka'].kind == 'infraSoftware'
        assert by_name['app.war'].kind == 'infraSoftware'
        assert by_name['LAN_Segment'].kind == 'infraZone'
        assert by_name['WAN_Link'].kind == 'infraZone'

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
        result = build_deployment_map(systems, nodes, rels, {'efs': 'channels'})
        assert len(result) == 1
        assert result[0] == ('channels.efs', 'server_1')

    def test_no_tech_elements(self):
        """Empty deployment_nodes → empty mapping."""
        systems = [System(c4_id='efs', name='EFS', archi_id='ac-1')]
        result = build_deployment_map(systems, [], [], {'efs': 'channels'})
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
        result = build_deployment_map(systems, nodes, rels, {'efs': 'channels'})
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
        result = build_deployment_map(systems, [parent], rels, {'efs': 'channels'})
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
            sys_domain={'efs': 'channels'},
            sys_subdomain={'efs': 'retail'},
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
            sys_domain={'efs': 'channels'},
            sys_subdomain={},
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
            sys_domain={'efs': 'channels'},
            sys_subdomain={'efs': 'retail'},
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
        systems, _ = build_systems(comps, promote_children={}, reviewed_systems=['Legacy'])
        assert 'to_review' not in systems[0].tags

    def test_non_reviewed_keeps_tag(self):
        comps = [AppComponent(archi_id='id-1', name='Legacy', source_folder='!РАЗБОР')]
        systems, _ = build_systems(comps, promote_children={}, reviewed_systems=[])
        assert 'to_review' in systems[0].tags

    def test_reviewed_noop_if_no_tag(self):
        comps = [AppComponent(archi_id='id-1', name='Normal', source_folder='')]
        systems, _ = build_systems(comps, promote_children={}, reviewed_systems=['Normal'])
        assert systems[0].tags == []


# ── CommunicationNetwork/Path → infraZone ───────────────────────────────

class TestInfraZoneKind:
    def test_communication_network_becomes_infra_zone(self):
        """CommunicationNetwork tech_type should produce infraZone kind."""
        elems = [
            TechElement(archi_id='cn-1', name='LAN Segment', tech_type='CommunicationNetwork'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 1
        assert roots[0].kind == 'infraZone'

    def test_path_becomes_infra_zone(self):
        """Path tech_type should produce infraZone kind."""
        elems = [
            TechElement(archi_id='p-1', name='WAN Link', tech_type='Path'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 1
        assert roots[0].kind == 'infraZone'

    def test_infra_zone_with_child_node(self):
        """infraZone → infraNode aggregation creates proper hierarchy."""
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
        assert roots[0].kind == 'infraZone'
        assert len(roots[0].children) == 1
        assert roots[0].children[0].kind == 'infraNode'


# ── Location → infraLocation ────────────────────────────────────────────

class TestLocationKind:
    def test_location_becomes_infra_location(self):
        """Location tech_type should produce infraLocation kind."""
        elems = [
            TechElement(archi_id='loc-1', name='HQ Datacenter', tech_type='Location'),
        ]
        roots = build_deployment_topology(elems, [])
        assert len(roots) == 1
        assert roots[0].kind == 'infraLocation'

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
        assert roots[0].kind == 'infraLocation'
        assert len(roots[0].children) == 1
        assert roots[0].children[0].kind == 'infraNode'


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


# ── dataStore detection ─────────────────────────────────────────────────

class TestDataStoreDetection:
    def test_postgresql_becomes_datastore(self):
        elems = [TechElement(archi_id='sw-1', name='PostgreSQL 15', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'dataStore'

    def test_oracle_becomes_datastore(self):
        elems = [TechElement(archi_id='sw-1', name='Oracle DB', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'dataStore'

    def test_redis_becomes_datastore(self):
        elems = [TechElement(archi_id='sw-1', name='Redis Cluster', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'dataStore'

    def test_mongo_becomes_datastore(self):
        elems = [TechElement(archi_id='sw-1', name='Mongo DB', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'dataStore'

    def test_nginx_stays_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Nginx', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_eureka_stays_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Eureka', tech_type='TechnologyService')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_node_never_datastore(self):
        """Even if Node name contains 'database', it stays infraNode."""
        elems = [TechElement(archi_id='n-1', name='Database Server', tech_type='Node')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraNode'

    def test_stage_db_becomes_datastore(self):
        elems = [TechElement(archi_id='sw-1', name='Stage DB', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'dataStore'


# ── build_datastore_entity_links ─────────────────────────────────────────


class TestBuildDatastoreEntityLinks:
    def test_access_relationship_creates_link(self):
        """AccessRelationship SystemSoftware→DataObject creates dataStore→entity link."""
        child = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                               tech_type='SystemSoftware', kind='dataStore')
        parent = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                                tech_type='Node', children=[child])
        entities = [DataEntity(c4_id='de_users', name='Users', archi_id='do-1')]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_datastore_entity_links([parent], entities, rels)
        assert len(result) == 1
        assert result[0] == ('srv.pg', 'de_users')

    def test_no_access_relationships(self):
        child = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                               tech_type='SystemSoftware', kind='dataStore')
        entities = [DataEntity(c4_id='de_users', name='Users', archi_id='do-1')]
        result = build_datastore_entity_links([child], entities, [])
        assert result == []

    def test_empty_inputs(self):
        assert build_datastore_entity_links([], [], []) == []

    def test_reverse_direction(self):
        """DataObject→SystemSoftware direction also works."""
        node = DeploymentNode(c4_id='redis', name='Redis', archi_id='sw-1',
                              tech_type='SystemSoftware', kind='dataStore')
        entities = [DataEntity(c4_id='de_cache', name='Cache', archi_id='do-1')]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='DataObject', source_id='do-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
        ]
        result = build_datastore_entity_links([node], entities, rels)
        assert len(result) == 1
        assert result[0] == ('redis', 'de_cache')


# ── assign_subdomains ────────────────────────────────────────────────────

class TestAssignSubdomains:
    def test_system_assigned_to_subdomain(self):
        """System whose archi_id is in ParsedSubdomain.component_ids gets assigned."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'banking'
        assert len(subdomains) == 1
        assert subdomains[0].c4_id == 'banking'
        assert subdomains[0].name == 'Banking'
        assert subdomains[0].domain_id == 'channels'
        assert 'efs' in subdomains[0].system_ids
        assert ('channels', 'banking') in subdomain_systems
        assert 'efs' in subdomain_systems[('channels', 'banking')]

    def test_system_without_subdomain_falls_back(self):
        """System not in any ParsedSubdomain keeps empty subdomain."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-2', domain='customer_service')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],  # sys-2 not included
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == ''
        assert len(subdomains) == 0

    def test_extra_archi_ids_matched(self):
        """System with matching extra_archi_id also gets assigned to subdomain."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     extra_archi_ids=['sys-dup'], domain='channels')
        psd = ParsedSubdomain(
            archi_id='payments',
            name='Payments',
            domain_folder='channels',
            component_ids=['sys-dup'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'payments'

    def test_cross_domain_subdomains_not_merged(self):
        """Same subdomain name in different domains creates separate Subdomain objects."""
        sys1 = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        sys2 = System(c4_id='crm', name='CRM', archi_id='sys-2', domain='products')
        psd1 = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        psd2 = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='products',
            component_ids=['sys-2'],
        )
        subdomains, _ = assign_subdomains([sys1, sys2], [psd1, psd2])
        assert len(subdomains) == 2
        assert {(s.domain_id, s.c4_id) for s in subdomains} == {
            ('channels', 'core'), ('products', 'core')
        }

    def test_empty_parsed_subdomains(self):
        """No parsed subdomains → no assignments."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        subdomains, subdomain_systems = assign_subdomains([sys], [])
        assert sys.subdomain == ''
        assert subdomains == []
        assert subdomain_systems == {}

    def test_multiple_systems_in_same_subdomain(self):
        """Multiple systems can belong to the same subdomain."""
        sys1 = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        sys2 = System(c4_id='cards', name='Cards', archi_id='sys-2', domain='channels')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1', 'sys-2'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys1, sys2], [psd])
        assert len(subdomains) == 1
        assert sorted(subdomains[0].system_ids) == ['cards', 'efs']
        assert sorted(subdomain_systems[('channels', 'banking')]) == ['cards', 'efs']

    def test_foreign_domain_subdomain_not_assigned(self):
        """System moved to a different domain must not keep the parsed subdomain."""
        # System appears in parsed subdomain for 'channels', but its final domain is 'products'
        # (e.g. moved by domain_overrides). Should not receive the foreign subdomain.
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='products')
        psd = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',  # different domain
            component_ids=['sys-1'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == ''
        assert subdomains == []
        assert subdomain_systems == {}

    def test_merged_system_extra_archi_id_finds_same_domain_subdomain(self):
        """Merged system whose primary archi_id hits a foreign subdomain must
        keep searching extra_archi_ids until a same-domain candidate is found.

        Regression: previously the loop broke on the first match regardless of
        domain, then the outer domain guard skipped the system entirely.
        """
        # Merged system: primary id came from 'products', extra id from 'channels'
        sys = System(
            c4_id='efs',
            name='EFS',
            archi_id='sys-foreign',   # component_id in products/retail
            extra_archi_ids=['sys-correct'],  # component_id in channels/banking
            domain='channels',
        )
        psd_foreign = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='products',   # foreign domain
            component_ids=['sys-foreign'],
        )
        psd_correct = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',   # correct domain
            component_ids=['sys-correct'],
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd_foreign, psd_correct]
        )
        assert sys.subdomain == 'banking', (
            'extra_archi_id hit in same domain must be used when primary id '
            'points to a foreign-domain subdomain'
        )
        assert any(sd.c4_id == 'banking' for sd in subdomains)
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])

    def test_manual_overrides_take_precedence(self):
        """manual_overrides override folder-based auto-detection."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        # Auto-detection would assign to 'retail'
        psd_retail = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        # Manual override targets 'banking'
        psd_banking = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=[],  # no auto components
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd_retail, psd_banking],
            manual_overrides={'EFS': 'banking'},
        )
        assert sys.subdomain == 'banking'
        assert any(sd.c4_id == 'banking' for sd in subdomains)
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])
        assert 'efs' not in subdomain_systems.get(('channels', 'retail'), [])

    def test_manual_overrides_unknown_system_skipped(self):
        """manual_overrides with an unknown system name is silently skipped."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',
            component_ids=[],
        )
        # 'NoSuchSystem' doesn't exist — should not raise
        subdomains, _ = assign_subdomains(
            [sys], [psd],
            manual_overrides={'NoSuchSystem': 'retail'},
        )
        assert sys.subdomain == ''

    def test_manual_overrides_invalid_subdomain_falls_back_to_auto(self):
        """manual_overrides with a non-existent subdomain must not clear auto-detection.

        A bad override like {'EFS': 'missing'} should be ignored so that the system
        still receives its folder-based subdomain assignment instead of getting none.
        """
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        # 'missing' subdomain does not exist — auto-detection should still run
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd],
            manual_overrides={'EFS': 'missing'},
        )
        assert sys.subdomain == 'banking', (
            'invalid override target must not clear auto-detected subdomain'
        )
        assert len(subdomains) == 1
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])

    def test_manual_overrides_cross_domain_collision(self):
        """manual_overrides use domain-scoped lookup to avoid cross-domain collisions.

        When two domains each have a subdomain with the same archi_id (e.g. 'core'),
        the override must assign the system to the subdomain in its own domain,
        not the one from the other domain.
        """
        sys_efs = System(c4_id='efs', name='EFS', archi_id='sys-efs', domain='channels')
        # channels/core — correct target for EFS override
        psd_channels_core = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='channels',
            component_ids=[],
        )
        # products/core — same archi_id in a different domain
        psd_products_core = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='products',
            component_ids=[],
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys_efs],
            [psd_channels_core, psd_products_core],
            manual_overrides={'EFS': 'core'},
        )
        assert sys_efs.subdomain == 'core', (
            'EFS should be assigned to channels/core, not left empty due to collision'
        )
        assert 'efs' in subdomain_systems.get(('channels', 'core'), [])
        # Only the channels-domain subdomain should appear (domain_id='channels')
        matching = [sd for sd in subdomains if sd.c4_id == 'core']
        assert len(matching) == 1
        assert matching[0].domain_id == 'channels'

    def test_unassigned_system_not_placed_in_subdomain(self):
        """System with no domain (domain='') must not be assigned to any subdomain."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == '', 'unassigned system must not receive a subdomain'
        assert subdomains == []
        assert subdomain_systems == {}

    def test_unassigned_system_not_placed_via_manual_override(self):
        """manual_overrides must not assign a subdomain to an unassigned (domain='') system."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=[],
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd],
            manual_overrides={'EFS': 'banking'},
        )
        assert sys.subdomain == '', 'unassigned system must not receive a subdomain via override'
        assert subdomains == []
        assert subdomain_systems == {}

    def test_collision_guard_system_same_name_as_subdomain(self):
        """System whose c4_id equals a subdomain c4_id gets auto-assigned to that subdomain."""
        # Mirrors real-world: system "AIM" and subdomain folder "AIM" → both make_id → 'aim'
        sys = System(c4_id='aim', name='AIM', archi_id='sys-aim', domain='channels')
        psd = ParsedSubdomain(
            archi_id='aim',
            name='AIM',
            domain_folder='channels',
            component_ids=[],  # system NOT in component_ids (no folder membership)
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'aim', 'collision guard must assign system to matching subdomain'
        assert len(subdomains) == 1
        assert subdomains[0].c4_id == 'aim'
        assert 'aim' in subdomains[0].system_ids
        assert ('channels', 'aim') in subdomain_systems
        assert 'aim' in subdomain_systems[('channels', 'aim')]

    def test_collision_guard_only_same_domain(self):
        """Collision guard must NOT fire across different domains."""
        sys = System(c4_id='loan', name='Loan', archi_id='sys-loan', domain='products')
        psd = ParsedSubdomain(
            archi_id='loan',
            name='Loan',
            domain_folder='channels',  # different domain!
            component_ids=[],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == '', 'cross-domain collision guard must not fire'
        assert subdomains == []

    def test_collision_guard_skipped_when_already_assigned(self):
        """Collision guard must not re-assign a system that already has a subdomain."""
        sys = System(c4_id='aim', name='AIM', archi_id='sys-aim', domain='channels')
        psd_banking = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-aim'],  # folder membership → assigned via normal path
        )
        psd_aim = ParsedSubdomain(
            archi_id='aim',
            name='AIM',
            domain_folder='channels',
            component_ids=[],
        )
        subdomains, _ = assign_subdomains([sys], [psd_banking, psd_aim])
        assert sys.subdomain == 'banking', 'normal assignment must not be overwritten by collision guard'


# ── apply_domain_prefix with subdomain ──────────────────────────────────

class TestApplyDomainPrefixSubdomain:
    def test_integration_path_includes_subdomain(self):
        """Integration source/target paths include subdomain when assigned."""
        intg = Integration(source_path='efs', target_path='crm', name='flow', rel_type='')
        sys_domain = {'efs': 'channels', 'crm': 'customer_service'}
        sys_subdomain = {'efs': 'banking'}
        apply_domain_prefix([intg], [], sys_domain, sys_subdomain)
        assert intg.source_path == 'channels.banking.efs'
        assert intg.target_path == 'customer_service.crm'  # no subdomain

    def test_data_access_path_includes_subdomain(self):
        da = DataAccess(system_path='efs', entity_id='de_account', name='')
        sys_domain = {'efs': 'channels'}
        sys_subdomain = {'efs': 'banking'}
        apply_domain_prefix([], [da], sys_domain, sys_subdomain)
        assert da.system_path == 'channels.banking.efs'

    def test_no_subdomain_unchanged(self):
        """Without sys_subdomain parameter, behavior is unchanged."""
        intg = Integration(source_path='efs', target_path='crm', name='', rel_type='')
        sys_domain = {'efs': 'channels', 'crm': 'products'}
        apply_domain_prefix([intg], [], sys_domain)
        assert intg.source_path == 'channels.efs'
        assert intg.target_path == 'products.crm'


# ── build_archi_to_c4_map with subdomain ────────────────────────────────

class TestBuildArchiToC4MapSubdomain:
    def test_system_path_includes_subdomain(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     domain='channels', subdomain='banking')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'},
                                       sys_subdomain={'efs': 'banking'})
        assert result['sys-1'] == 'channels.banking.efs'

    def test_subsystem_path_inherits_subdomain(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], domain='channels', subdomain='banking')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'},
                                       sys_subdomain={'efs': 'banking'})
        assert result['sub-1'] == 'channels.banking.efs.core'

    def test_function_path_inherits_subdomain(self):
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     functions=[fn], domain='channels', subdomain='banking')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'},
                                       sys_subdomain={'efs': 'banking'})
        assert result['fn-1'] == 'channels.banking.efs.do_stuff'

    def test_no_subdomain_unchanged(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sys-1'] == 'channels.efs'
