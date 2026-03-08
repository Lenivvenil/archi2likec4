"""Tests for archi2likec4.builders — system hierarchy, integrations, domains."""

import pytest

from archi2likec4.models import (
    AppComponent,
    AppFunction,
    AppInterface,
    DataAccess,
    DataEntity,
    DataObject,
    DomainInfo,
    Integration,
    RawRelationship,
    Subsystem,
    System,
)
from archi2likec4.builders import (
    apply_domain_prefix,
    assign_domains,
    attach_functions,
    attach_interfaces,
    build_archi_to_c4_map,
    build_data_access,
    build_data_entities,
    build_integrations,
    build_systems,
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
        """Systems matching EXTRA_DOMAIN_PATTERNS should be assigned."""
        domains = []
        sys = System(c4_id='elk', name='ELK', archi_id='sys-1')
        result = assign_domains([sys], domains)
        # ELK matches 'platform' pattern
        assert sys.domain == 'platform'

    def test_most_hits_wins(self):
        d1 = DomainInfo(c4_id='d1', name='D1', archi_ids={'sys-1'})
        d2 = DomainInfo(c4_id='d2', name='D2', archi_ids={'sys-1', 'sub-1'})
        sub = Subsystem(c4_id='sub', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', subsystems=[sub])
        result = assign_domains([sys], [d1, d2])
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

    def test_warn_threshold(self, capsys):
        """Parent with ≥ threshold subsystems triggers a warning."""
        comps = [AppComponent(archi_id='id-p', name='BigSys')]
        comps += [
            AppComponent(archi_id=f'id-{i}', name=f'BigSys.Sub{i}')
            for i in range(12)
        ]
        systems, _ = build_systems(comps, promote_children={})
        captured = capsys.readouterr()
        assert 'WARN' in captured.out
        assert 'BigSys' in captured.out
        assert 'PROMOTE_CHILDREN' in captured.out

    def test_no_warn_below_threshold(self, capsys):
        """Parent with < threshold subsystems does not trigger a warning."""
        comps = [
            AppComponent(archi_id='id-p', name='SmallSys'),
            AppComponent(archi_id='id-1', name='SmallSys.A'),
            AppComponent(archi_id='id-2', name='SmallSys.B'),
            AppComponent(archi_id='id-3', name='SmallSys.C'),
        ]
        systems, _ = build_systems(comps, promote_children={})
        captured = capsys.readouterr()
        assert 'SmallSys' not in captured.out

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
        result = assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        assert sys.domain != 'channels'

    def test_view_membership_overrides_fallback(self):
        """If system is assigned via view membership, fallback is not used."""
        domains = [
            DomainInfo(c4_id='products', name='Products', archi_ids={'s-1'}),
            DomainInfo(c4_id='channels', name='Channels', archi_ids=set()),
        ]
        sys = System(c4_id='efs_svc', name='EFS.Svc', archi_id='s-1')
        result = assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        # View membership (products) takes priority over fallback (channels)
        assert sys.domain == 'products'


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
        intgs = build_integrations([sys_a, sys_b, sys_x], rels, {}, promoted)
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
        intgs = build_integrations([sys_x, sys_a, sys_b], rels, {}, promoted)
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
        intgs = build_integrations([sys_x], rels, {})
        assert len(intgs) == 0  # skipped, no promoted_parents

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
        intgs = build_integrations([sys_a, sys_b], rels, {}, promoted)
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
