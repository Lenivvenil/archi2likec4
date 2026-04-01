"""Tests for builders/integrations.py module."""

from archi2likec4.builders import (
    attach_interfaces,
    build_integrations,
    build_systems,
)
from archi2likec4.models import (
    AppComponent,
    AppInterface,
    RawRelationship,
    Subsystem,
    System,
)


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

class TestBuildIntegrationsEdgeCases:
    def test_access_relationship_skipped(self):
        comps = [
            AppComponent(archi_id='s-1', name='SysA'),
            AppComponent(archi_id='s-2', name='SysB'),
        ]
        systems, _ = build_systems(comps)
        rel = RawRelationship(
            rel_id='r-1', rel_type='AccessRelationship', name='',
            source_type='ApplicationComponent', source_id='s-1',
            target_type='ApplicationComponent', target_id='s-2',
        )
        integrations, skipped, total = build_integrations(systems, [rel], {})
        assert len(integrations) == 0
        assert total == 0  # AccessRelationship not counted

    def test_structural_relationship_skipped(self):
        comps = [
            AppComponent(archi_id='s-1', name='SysA'),
            AppComponent(archi_id='s-2', name='SysB'),
        ]
        systems, _ = build_systems(comps)
        for rel_type in ('CompositionRelationship', 'AggregationRelationship',
                         'RealizationRelationship', 'AssignmentRelationship'):
            rel = RawRelationship(
                rel_id='r-1', rel_type=rel_type, name='',
                source_type='ApplicationComponent', source_id='s-1',
                target_type='ApplicationComponent', target_id='s-2',
            )
            integrations, skipped, total = build_integrations(systems, [rel], {})
            assert len(integrations) == 0
            assert total == 0

    def test_application_function_relationship_skipped(self):
        comps = [AppComponent(archi_id='s-1', name='SysA')]
        systems, _ = build_systems(comps)
        rel = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='',
            source_type='ApplicationFunction', source_id='fn-1',
            target_type='ApplicationComponent', target_id='s-1',
        )
        integrations, skipped, total = build_integrations(systems, [rel], {})
        assert total == 0

    def test_subsystem_archi_id_in_path(self):
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1')
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1', subsystems=[sub])
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        rel = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='data',
            source_type='ApplicationComponent', source_id='sub-1',
            target_type='ApplicationComponent', target_id='s-2',
        )
        integrations, skipped, total = build_integrations([sys1, sys2], [rel], {})
        assert total == 1
        assert skipped == 0
        assert len(integrations) == 1
        assert 'sysa' in integrations[0].source_path

    def test_promoted_parents_fan_out_source(self):
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1')
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        # promoted_parents maps parent archi_id → list of child c4_ids
        promoted = {'parent-1': ['sysa', 'sysb']}
        rel = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='flow',
            source_type='ApplicationComponent', source_id='parent-1',
            target_type='ApplicationComponent', target_id='s-2',
        )
        integrations, skipped, total = build_integrations([sys1, sys2], [rel], {},
                                                          promoted_parents=promoted)
        assert total == 1
        assert skipped == 0

    def test_promoted_parents_fan_out_target(self):
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1')
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        promoted = {'parent-1': ['sysa', 'sysb']}
        rel = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='flow',
            source_type='ApplicationComponent', source_id='s-1',
            target_type='ApplicationComponent', target_id='parent-1',
        )
        integrations, skipped, total = build_integrations([sys1, sys2], [rel], {},
                                                          promoted_parents=promoted)
        assert total == 1
        assert skipped == 0

    def test_interface_as_target(self):
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1')
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        iface_c4_path = {'iface-1': 'sysb'}
        rel = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='call',
            source_type='ApplicationComponent', source_id='s-1',
            target_type='ApplicationInterface', target_id='iface-1',
        )
        integrations, skipped, total = build_integrations([sys1, sys2], [rel], iface_c4_path)
        assert total == 1
        assert skipped == 0

    def test_interface_as_source(self):
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1')
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        iface_c4_path = {'iface-src': 'sysa'}
        rel = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='call',
            source_type='ApplicationInterface', source_id='iface-src',
            target_type='ApplicationComponent', target_id='s-2',
        )
        integrations, skipped, total = build_integrations([sys1, sys2], [rel], iface_c4_path)
        assert total == 1
        assert skipped == 0

    def test_two_flows_dedup_label_joined(self):
        """2-3 flows between same pair get joined with '; '."""
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1')
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        rels = [
            RawRelationship(
                rel_id=f'r-{i}', rel_type='FlowRelationship', name=f'flow{i}',
                source_type='ApplicationComponent', source_id='s-1',
                target_type='ApplicationComponent', target_id='s-2',
            )
            for i in range(2)
        ]
        integrations, _, _ = build_integrations([sys1, sys2], rels, {})
        assert len(integrations) == 1
        assert '; ' in integrations[0].name

    def test_many_flows_dedup_label(self):
        """4+ flows between same pair produces truncated label."""
        sys1 = System(c4_id='sysa', name='SysA', archi_id='s-1')
        sys2 = System(c4_id='sysb', name='SysB', archi_id='s-2')
        rels = [
            RawRelationship(
                rel_id=f'r-{i}', rel_type='FlowRelationship', name=f'flow{i}',
                source_type='ApplicationComponent', source_id='s-1',
                target_type='ApplicationComponent', target_id='s-2',
            )
            for i in range(5)
        ]
        integrations, _, _ = build_integrations([sys1, sys2], rels, {})
        assert len(integrations) == 1
        assert '...' in integrations[0].name or '5 flows' in integrations[0].name


# ── validate_deployment_tree ─────────────────────────────────────────────


