"""Tests for builders/systems.py module."""


from archi2likec4.builders import (
    SystemBuildConfig,
    assign_domains,
    attach_functions,
    attach_interfaces,
    build_data_access,
    build_data_entities,
    build_datastore_entity_links,
    build_integrations,
    build_systems,
)
from archi2likec4.builders.systems import (
    _collect_systems,
    _promote_subsystems,
    _resolve_dot_names,
)
from archi2likec4.models import (
    AppComponent,
    AppFunction,
    AppInterface,
    DataEntity,
    DataObject,
    DeploymentNode,
    DomainInfo,
    RawRelationship,
    Subsystem,
    System,
)


class TestBuildSystems:
    def test_simple_system(self):
        comps = [AppComponent(archi_id='id-1', name='CRM')]
        systems, _ = build_systems(comps)
        assert len(systems) == 1
        assert systems[0].c4_id == 'crm'
        assert systems[0].name == 'CRM'
        assert systems[0].archi_id == 'id-1'

    def test_dot_creates_subsystem(self):
        comps = [
            AppComponent(archi_id='id-1', name='CRM'),
            AppComponent(archi_id='id-2', name='CRM.Core'),
        ]
        systems, _ = build_systems(comps)
        assert len(systems) == 1
        assert len(systems[0].subsystems) == 1
        assert systems[0].subsystems[0].name == 'CRM.Core'

    def test_dot_without_parent_becomes_system(self):
        """If parent part doesn't match a known system, treat as standalone system."""
        comps = [AppComponent(archi_id='id-1', name='Unknown.Module')]
        systems, _ = build_systems(comps)
        assert len(systems) == 1
        assert systems[0].name == 'Unknown.Module'

    def test_duplicate_names_keep_richer(self):
        """When two components have the same name, keep the one with more properties."""
        comps = [
            AppComponent(archi_id='id-1', name='CRM', properties={}),
            AppComponent(archi_id='id-2', name='CRM', properties={'CI': '123', 'Full name': 'CRM Full'}),
        ]
        systems, _ = build_systems(comps)
        assert len(systems) == 1
        assert systems[0].archi_id == 'id-2'  # richer one wins
        assert 'id-1' in systems[0].extra_archi_ids

    def test_trailing_dot_stripped(self):
        comps = [AppComponent(archi_id='id-1', name='CRM.')]
        systems, _ = build_systems(comps)
        assert len(systems) == 1
        assert systems[0].name == 'CRM'

    def test_tags_from_source_folder(self):
        comps = [
            AppComponent(archi_id='id-1', name='ExtSvc', source_folder='!External_services'),
            AppComponent(archi_id='id-2', name='Review', source_folder='!РАЗБОР'),
        ]
        systems, _ = build_systems(comps)
        sys_by_name = {s.name: s for s in systems}
        assert 'external' in sys_by_name['ExtSvc'].tags
        assert 'to_review' in sys_by_name['Review'].tags

    def test_sorted_by_name(self):
        comps = [
            AppComponent(archi_id='id-1', name='Zebra'),
            AppComponent(archi_id='id-2', name='Alpha'),
        ]
        systems, _ = build_systems(comps)
        assert systems[0].name == 'Alpha'
        assert systems[1].name == 'Zebra'

    def test_multiple_subsystems(self):
        comps = [
            AppComponent(archi_id='id-1', name='CRM'),
            AppComponent(archi_id='id-2', name='CRM.Core'),
            AppComponent(archi_id='id-3', name='CRM.API'),
        ]
        systems, _ = build_systems(comps)
        assert len(systems) == 1
        assert len(systems[0].subsystems) == 2


# ── _collect_systems ─────────────────────────────────────────────────────

class TestCollectSystems:
    def test_separates_dot_free_and_dotted(self):
        comps = [
            AppComponent(archi_id='id-1', name='CRM'),
            AppComponent(archi_id='id-2', name='CRM.Core'),
        ]
        system_acs, extra_ids, dot_acs = _collect_systems(comps)
        assert 'CRM' in system_acs
        assert len(dot_acs) == 1
        assert dot_acs[0].name == 'CRM.Core'

    def test_deduplicates_keeping_richer(self):
        comps = [
            AppComponent(archi_id='id-1', name='CRM', properties={}),
            AppComponent(archi_id='id-2', name='CRM', properties={'CI': '123'}),
        ]
        system_acs, extra_ids, _ = _collect_systems(comps)
        assert system_acs['CRM'].archi_id == 'id-2'
        assert 'id-1' in extra_ids['CRM']

    def test_trailing_dot_treated_as_dot_free(self):
        comps = [AppComponent(archi_id='id-1', name='CRM.')]
        system_acs, _, dot_acs = _collect_systems(comps)
        assert 'CRM' in system_acs
        assert len(dot_acs) == 0


# ── _promote_subsystems ─────────────────────────────────────────────────

class TestPromoteSubsystems:
    def test_two_segment_becomes_system(self):
        system_acs: dict[str, AppComponent] = {
            'EFS': AppComponent(archi_id='efs-1', name='EFS'),
        }
        extra_ids: dict[str, list[str]] = {}
        dot_acs = [AppComponent(archi_id='id-2', name='EFS.Card')]
        promoted_sub, regular, parent_remap = _promote_subsystems(
            dot_acs, system_acs, extra_ids, {'EFS': 'EFS'},
        )
        assert 'EFS.Card' in system_acs
        assert 'EFS' not in system_acs  # parent removed
        assert len(regular) == 0
        assert len(promoted_sub) == 0

    def test_three_segment_becomes_promoted_subsystem(self):
        system_acs: dict[str, AppComponent] = {
            'EFS': AppComponent(archi_id='efs-1', name='EFS'),
        }
        extra_ids: dict[str, list[str]] = {}
        dot_acs = [
            AppComponent(archi_id='id-2', name='EFS.Card'),
            AppComponent(archi_id='id-3', name='EFS.Card.ODS'),
        ]
        promoted_sub, regular, parent_remap = _promote_subsystems(
            dot_acs, system_acs, extra_ids, {'EFS': 'EFS'},
        )
        assert len(promoted_sub) == 1
        assert promoted_sub[0].name == 'EFS.Card.ODS'

    def test_non_promoted_goes_to_regular(self):
        system_acs: dict[str, AppComponent] = {}
        extra_ids: dict[str, list[str]] = {}
        dot_acs = [AppComponent(archi_id='id-1', name='CRM.Core')]
        promoted_sub, regular, _ = _promote_subsystems(
            dot_acs, system_acs, extra_ids, {},
        )
        assert len(regular) == 1
        assert len(promoted_sub) == 0

    def test_parent_remap_captures_archi_id(self):
        system_acs: dict[str, AppComponent] = {
            'EFS': AppComponent(archi_id='efs-1', name='EFS'),
        }
        extra_ids: dict[str, list[str]] = {}
        dot_acs = [AppComponent(archi_id='id-2', name='EFS.Card')]
        _, _, parent_remap = _promote_subsystems(
            dot_acs, system_acs, extra_ids, {'EFS': 'EFS'},
        )
        assert parent_remap == {'EFS': 'efs-1'}


# ── _resolve_dot_names ──────────────────────────────────────────────────

class TestResolveDotNames:
    def test_dot_with_parent_becomes_subsystem(self):
        system_acs: dict[str, AppComponent] = {
            'CRM': AppComponent(archi_id='id-1', name='CRM'),
        }
        extra_ids: dict[str, list[str]] = {}
        regular_dot_acs = [AppComponent(archi_id='id-2', name='CRM.Core')]
        subsystem_acs = _resolve_dot_names(regular_dot_acs, system_acs, extra_ids)
        assert len(subsystem_acs) == 1
        assert subsystem_acs[0].name == 'CRM.Core'

    def test_dot_without_parent_becomes_standalone(self):
        system_acs: dict[str, AppComponent] = {}
        extra_ids: dict[str, list[str]] = {}
        regular_dot_acs = [AppComponent(archi_id='id-1', name='Unknown.Module')]
        subsystem_acs = _resolve_dot_names(regular_dot_acs, system_acs, extra_ids)
        assert len(subsystem_acs) == 0
        assert 'Unknown.Module' in system_acs

    def test_standalone_deduplication(self):
        system_acs: dict[str, AppComponent] = {}
        extra_ids: dict[str, list[str]] = {}
        regular_dot_acs = [
            AppComponent(archi_id='id-1', name='X.Y', properties={}),
            AppComponent(archi_id='id-2', name='X.Y', properties={'key': 'val'}),
        ]
        _resolve_dot_names(regular_dot_acs, system_acs, extra_ids)
        assert system_acs['X.Y'].archi_id == 'id-2'
        assert 'id-1' in extra_ids['X.Y']


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

class TestPromoteChildren:
    """Tests for PROMOTE_CHILDREN feature — promoting subsystems to standalone systems."""

    def test_promoted_becomes_system(self):
        """2-segment promoted name becomes standalone system, parent disappears."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.ServiceA'),
        ]
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
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
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
        assert all(s.name != 'Platform' for s in systems)
        assert len(systems) == 2

    def test_promoted_parent_archi_id_fans_out(self):
        """Parent archi_id fans out to ALL children (not remapped to one)."""
        comps = [
            AppComponent(archi_id='id-parent', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.ServiceA'),
            AppComponent(archi_id='id-2', name='Platform.ServiceB'),
        ]
        systems, promoted_parents = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
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
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
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
        systems, promoted_parents = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
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
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
        assert len(systems) == 1
        assert systems[0].name == 'ABC'
        assert len(systems[0].subsystems) == 1

    def test_promoted_c4_id(self):
        """Promoted system c4_id is derived from the full dotted name."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Card_Service'),
        ]
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
        assert systems[0].c4_id == 'platform_card_service'

    def test_promoted_preserves_metadata(self):
        """Promoted system retains its properties, tags, etc."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Svc',
                         properties={'CI': 'CI-42'}, source_folder='!External_services'),
        ]
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
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
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
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
            systems, _ = build_systems(comps)
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
            systems, _ = build_systems(comps)
        assert not any('SmallSys' in msg for msg in caplog.messages)

    def test_parent_kept_when_no_children(self):
        """Parent in promote_children is kept if no dot-children exist (P2 fix)."""
        comps = [
            AppComponent(archi_id='id-p', name='Platform'),
            AppComponent(archi_id='id-1', name='Other'),
        ]
        systems, _ = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
        names = [s.name for s in systems]
        assert 'Platform' in names  # not removed since no children found

    def test_parent_archi_id_function_becomes_orphan(self):
        """Functions referencing promoted parent become honest orphans (fan-out)."""
        comps = [
            AppComponent(archi_id='id-parent', name='Platform'),
            AppComponent(archi_id='id-1', name='Platform.Alpha'),
            AppComponent(archi_id='id-2', name='Platform.Beta'),
        ]
        systems, promoted_parents = build_systems(comps, SystemBuildConfig(promote_children={'Platform': 'infra'}))
        fn = AppFunction(archi_id='fn-1', name='ParentFunc', parent_archi_id='id-parent')
        orphans = attach_functions(systems, [fn], promoted_parents=promoted_parents)
        # Function becomes orphan — parent no longer exists as a single system
        assert orphans == 1
        sys_by_name = {s.name: s for s in systems}
        assert len(sys_by_name['Platform.Alpha'].functions) == 0
        assert len(sys_by_name['Platform.Beta'].functions) == 0


# ── attach_interfaces: reverse direction ────────────────────────────────

class TestBuilderEncapsulation:
    """Issue #1: builder submodules must not import private _ functions from each other."""

    def test_no_private_cross_imports_between_builder_submodules(self):
        """No submodule in builders/ should import a _ function from a sibling submodule.

        Dynamically discovers all builder submodules and checks both relative
        and absolute imports.
        """
        import ast
        import importlib
        import inspect
        from pathlib import Path

        builders_dir = Path(importlib.import_module('archi2likec4.builders').__file__).parent
        submod_names = [
            p.stem for p in sorted(builders_dir.glob('*.py'))
            if p.stem != '__init__'
        ]
        assert len(submod_names) >= 5, f'Expected at least 5 builder submodules, found {submod_names}'

        for name in submod_names:
            mod = importlib.import_module(f'archi2likec4.builders.{name}')
            source = inspect.getsource(mod)
            tree = ast.parse(source)
            siblings = [s for s in submod_names if s != name]
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                # Check relative imports: from .sibling import _foo
                if node.level > 0 and node.module in siblings:
                    for alias in node.names:
                        assert not alias.name.startswith('_'), (
                            f'archi2likec4/builders/{name}.py imports private '
                            f'{alias.name!r} from .{node.module}'
                        )
                # Check absolute imports: from archi2likec4.builders.sibling import _foo
                if node.level == 0 and node.module:
                    for sibling in siblings:
                        if node.module == f'archi2likec4.builders.{sibling}':
                            for alias in node.names:
                                assert not alias.name.startswith('_'), (
                                    f'archi2likec4/builders/{name}.py imports private '
                                    f'{alias.name!r} from {node.module}'
                                )


# ── Determinism tests ───────────────────────────────────────────────────

class TestBuilderDeterminism:
    """Verify that builder functions produce identical output for identical input."""

    def _make_components(self):
        return [
            AppComponent(archi_id='id-a', name='Alpha', properties={'CI': 'A1'}),
            AppComponent(archi_id='id-b', name='Beta', properties={'CI': 'B1'}),
            AppComponent(archi_id='id-c', name='Alpha.Sub1'),
            AppComponent(archi_id='id-d', name='Alpha.Sub2'),
            AppComponent(archi_id='id-e', name='Gamma', properties={'CI': 'G1'}),
        ]

    def test_build_systems_deterministic(self):
        """build_systems returns identical output on repeated calls with same input."""
        for _ in range(3):
            systems, promoted = build_systems(self._make_components())
        systems_a, _ = build_systems(self._make_components())
        systems_b, _ = build_systems(self._make_components())
        assert [s.c4_id for s in systems_a] == [s.c4_id for s in systems_b]
        assert [s.name for s in systems_a] == [s.name for s in systems_b]
        for sa, sb in zip(systems_a, systems_b, strict=True):
            assert [sub.c4_id for sub in sa.subsystems] == [sub.c4_id for sub in sb.subsystems]

    def test_assign_domains_deterministic(self):
        """assign_domains returns identical assignments on repeated calls."""
        components = self._make_components()
        systems, _ = build_systems(components)
        domains = [
            DomainInfo(c4_id='core', name='Core', archi_ids={'id-a', 'id-c', 'id-d'}),
            DomainInfo(c4_id='infra', name='Infra', archi_ids={'id-b'}),
        ]
        import copy
        result_a = assign_domains(copy.deepcopy(systems), domains)
        result_b = assign_domains(copy.deepcopy(systems), domains)
        for domain_id in result_a:
            names_a = sorted(s.name for s in result_a.get(domain_id, []))
            names_b = sorted(s.name for s in result_b.get(domain_id, []))
            assert names_a == names_b, f'Domain {domain_id} differs'

    def test_build_integrations_deterministic(self):
        """build_integrations returns identical output on repeated calls."""
        systems = [
            System(c4_id='alpha', name='Alpha', archi_id='id-a'),
            System(c4_id='beta', name='Beta', archi_id='id-b'),
        ]
        rels = [
            RawRelationship(rel_id='r1', rel_type='FlowRelationship', name='flow1',
                            source_type='ApplicationComponent', source_id='id-a',
                            target_type='ApplicationComponent', target_id='id-b'),
            RawRelationship(rel_id='r2', rel_type='FlowRelationship', name='flow2',
                            source_type='ApplicationComponent', source_id='id-b',
                            target_type='ApplicationComponent', target_id='id-a'),
        ]
        intg_a, _, _ = build_integrations(systems, rels, {})
        intg_b, _, _ = build_integrations(systems, rels, {})
        assert [(i.source_path, i.target_path, i.name) for i in intg_a] == \
               [(i.source_path, i.target_path, i.name) for i in intg_b]

    def test_build_data_entities_deterministic(self):
        """build_data_entities returns same IDs and order for same input."""
        data_objects = [
            DataObject(archi_id='do-1', name='Orders'),
            DataObject(archi_id='do-2', name='Customers'),
            DataObject(archi_id='do-3', name='Products'),
        ]
        entities_a = build_data_entities(data_objects, set())
        entities_b = build_data_entities(data_objects, set())
        assert [(e.c4_id, e.name) for e in entities_a] == [(e.c4_id, e.name) for e in entities_b]


# ── systems.py edge cases (coverage uplift) ─────────────────────────────

class TestExtractUrl:
    """Tests for _extract_url helper."""

    def test_returns_none_for_empty_string(self):
        from archi2likec4.builders.systems import _extract_url
        assert _extract_url('') is None

    def test_returns_none_for_no_url(self):
        from archi2likec4.builders.systems import _extract_url
        assert _extract_url('No links here, just documentation.') is None

    def test_extracts_https_url(self):
        from archi2likec4.builders.systems import _extract_url
        result = _extract_url('See docs at https://example.com/api for details')
        assert result == 'https://example.com/api'

    def test_strips_trailing_punctuation(self):
        from archi2likec4.builders.systems import _extract_url
        result = _extract_url('Visit https://example.com/api.')
        assert result == 'https://example.com/api'


class TestAttachSubsystemsMissingParent:
    """Tests for _attach_subsystems when parent system is missing."""

    def test_missing_parent_logs_warning(self):
        from archi2likec4.builders.systems import _attach_subsystems
        systems: dict[str, System] = {
            'CRM': System(c4_id='crm', name='CRM', archi_id='sys-1'),
        }
        orphan = AppComponent(archi_id='id-2', name='Unknown.Module', source_folder='')
        _attach_subsystems(
            systems, [orphan],
            parent_name_fn=lambda ac: ac.name.split('.', 1)[0],
            sub_name_fn=lambda ac: ac.name.split('.', 1)[1],
        )
        # Unknown not in systems → skipped, CRM unchanged
        assert len(systems['CRM'].subsystems) == 0


class TestBuildCompIndex:
    """Tests for _build_comp_index with extra_archi_ids and subsystems."""

    def test_indexes_extra_archi_ids(self):
        from archi2likec4.builders.systems import _build_comp_index
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', extra_archi_ids=['sys-dup'])
        index = _build_comp_index([sys])
        assert 'sys-1' in index
        assert 'sys-dup' in index
        assert index['sys-dup'] == (sys, None)

    def test_indexes_subsystems(self):
        from archi2likec4.builders.systems import _build_comp_index
        sub = Subsystem(c4_id='core', name='CRM.Core', archi_id='sub-1')
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', subsystems=[sub])
        index = _build_comp_index([sys])
        assert 'sub-1' in index
        assert index['sub-1'] == (sys, sub)


class TestCollectSystemsDuplicateDisplacement:
    """Tests for _collect_systems duplicate AC displacement — lines 123-124."""

    def test_duplicate_with_fewer_props_tracked_in_extra_ids(self):
        """When a duplicate AC has fewer properties, its archi_id goes to extra_ids."""
        comps = [
            AppComponent(archi_id='id-rich', name='CRM', properties={'CI': '123', 'URL': 'x'}),
            AppComponent(archi_id='id-poor', name='CRM', properties={}),
        ]
        system_acs, extra_ids, _ = _collect_systems(comps)
        assert system_acs['CRM'].archi_id == 'id-rich'
        assert 'id-poor' in extra_ids['CRM']


class TestUpsertSystemAcDisplacement:
    """Tests for _upsert_system_ac — existing has more props, new AC's archi_id tracked."""

    def test_existing_richer_keeps_position(self):
        from archi2likec4.builders.systems import _upsert_system_ac
        system_acs: dict[str, AppComponent] = {
            'CRM': AppComponent(archi_id='id-rich', name='CRM', properties={'CI': '123', 'URL': 'x'}),
        }
        extra_ids: dict[str, list[str]] = {}
        new_ac = AppComponent(archi_id='id-poor', name='CRM', properties={})
        _upsert_system_ac(system_acs, extra_ids, 'CRM', new_ac)
        assert system_acs['CRM'].archi_id == 'id-rich'
        assert 'id-poor' in extra_ids['CRM']


class TestAttachFunctionsEdgeCases:
    """Tests for attach_functions edge cases — reverse rels, suffix collision, unknown orphans."""

    def test_reverse_relationship_direction(self):
        """source=AppFunction, target=AppComponent should also resolve parent."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1')
        fn = AppFunction(archi_id='fn-1', name='Process', parent_archi_id='')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationFunction', source_id='fn-1',
                target_type='ApplicationComponent', target_id='sys-1',
            ),
        ]
        orphans = attach_functions([sys], [fn], rels)
        assert orphans == 0
        assert len(sys.functions) == 1

    def test_triple_name_collision_suffix(self):
        """Three functions with same name should produce c4_ids with _2 and _3 suffixes."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1')
        fns = [
            AppFunction(archi_id=f'fn-{i}', name='Action', parent_archi_id='sys-1')
            for i in range(3)
        ]
        attach_functions([sys], fns)
        ids = sorted(f.c4_id for f in sys.functions)
        assert ids == ['action', 'action_2', 'action_3']

    def test_unknown_parent_orphan(self):
        """Function with parent_archi_id pointing to unknown system counts as orphan."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1')
        fn = AppFunction(archi_id='fn-1', name='Lost', parent_archi_id='nonexistent-id')
        orphans = attach_functions([sys], [fn])
        assert orphans == 1

    def test_promoted_parent_orphan(self):
        """Function referencing promoted parent counts as orphan."""
        sys = System(c4_id='child_a', name='P.A', archi_id='id-a')
        fn = AppFunction(archi_id='fn-1', name='Task', parent_archi_id='id-parent')
        promoted = {'id-parent': ['child_a']}
        orphans = attach_functions([sys], [fn], promoted_parents=promoted)
        assert orphans == 1


class TestResolveIfaceOwnerByName:
    """Tests for _resolve_iface_owner_by_name — various name resolution branches."""

    def test_two_part_name_matches_subsystem(self):
        from archi2likec4.builders.systems import _resolve_iface_owner_by_name
        sub = Subsystem(c4_id='core', name='CRM.Core', archi_id='sub-1')
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', subsystems=[sub])
        name_to_sys = {'CRM': sys}
        name_to_sub = {'CRM.Core': (sys, sub)}
        result = _resolve_iface_owner_by_name('CRM.Core.API', name_to_sys, name_to_sub)
        assert result == (sys, sub)

    def test_two_part_name_matches_system(self):
        from archi2likec4.builders.systems import _resolve_iface_owner_by_name
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        name_to_sys = {'CRM': sys}
        result = _resolve_iface_owner_by_name('CRM.SomeAPI', name_to_sys, {})
        assert result == (sys, None)

    def test_two_part_name_matches_promoted_system(self):
        from archi2likec4.builders.systems import _resolve_iface_owner_by_name
        sys = System(c4_id='efs_card', name='EFS.Card', archi_id='sys-1')
        name_to_sys = {'EFS.Card': sys}
        result = _resolve_iface_owner_by_name('EFS.Card.API', name_to_sys, {})
        assert result == (sys, None)

    def test_single_part_name_matches_system(self):
        from archi2likec4.builders.systems import _resolve_iface_owner_by_name
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        name_to_sys = {'CRM': sys}
        result = _resolve_iface_owner_by_name('CRM', name_to_sys, {})
        assert result == (sys, None)

    def test_unresolvable_returns_none(self):
        from archi2likec4.builders.systems import _resolve_iface_owner_by_name
        result = _resolve_iface_owner_by_name('Unknown.Thing', {}, {})
        assert result is None


class TestAttachInterfacesEdgeCases:
    """Tests for attach_interfaces edge cases — name-based fallback, subsystem ownership."""

    def test_name_based_fallback_resolution(self):
        """Interface resolved by name when no relationship exists."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='CRM.API', documentation='')
        result = attach_interfaces([sys], [iface], [])
        assert 'iface-1' in result
        assert result['iface-1'] == 'crm'

    def test_unresolved_interface_warning(self):
        """Interface that cannot be resolved is counted as unresolved."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='Unknown.API', documentation='')
        result = attach_interfaces([sys], [iface], [])
        assert 'iface-1' not in result

    def test_interface_owned_by_subsystem(self):
        """Interface ownership resolved to subsystem returns sys.sub path."""
        sub = Subsystem(c4_id='core', name='CRM.Core', archi_id='sub-1')
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', subsystems=[sub])
        iface = AppInterface(archi_id='iface-1', name='API', documentation='')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationComponent', source_id='sub-1',
                target_type='ApplicationInterface', target_id='iface-1',
            ),
        ]
        result = attach_interfaces([sys], [iface], rels)
        assert result['iface-1'] == 'crm.core'

    def test_name_to_sub_lookup_for_fallback(self):
        """Interface name matching subsystem name falls back to subsystem owner."""
        sub = Subsystem(c4_id='core', name='CRM.Core', archi_id='sub-1')
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', subsystems=[sub])
        iface = AppInterface(archi_id='iface-1', name='CRM.Core.Endpoint', documentation='')
        result = attach_interfaces([sys], [iface], [])
        assert result['iface-1'] == 'crm.core'

    def test_non_ownership_rel_skipped(self):
        """Non-ownership relationship types are skipped during interface resolution."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='CRM.API', documentation='')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationInterface', target_id='iface-1',
            ),
        ]
        # FlowRelationship is not an ownership rel, so interface resolved by name fallback
        result = attach_interfaces([sys], [iface], rels)
        assert 'iface-1' in result

    def test_ownership_rel_resolves_interface_to_system(self):
        """CompositionRelationship correctly resolves interface ownership to a system."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='CRM.API', documentation='')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationInterface', target_id='iface-1',
            ),
        ]
        result = attach_interfaces([sys], [iface], rels)
        assert result['iface-1'] == 'crm'

    def test_promoted_system_name_fallback(self):
        """Interface with dot-name matching a promoted system (dot name in name_to_sys)."""
        sys = System(c4_id='efs_card', name='EFS.Card_Service', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='EFS.Card_Service.Endpoint', documentation='')
        result = attach_interfaces([sys], [iface], [])
        assert result['iface-1'] == 'efs_card'

    def test_single_part_name_resolved_to_system(self):
        """Interface with a single-part name matching a system resolves correctly."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        iface = AppInterface(archi_id='iface-1', name='CRM', documentation='')
        result = attach_interfaces([sys], [iface], [])
        assert result['iface-1'] == 'crm'


# ── systems.py additional edge cases ─────────────────────────────────────

class TestAttachSubsystemsEdgeCases:
    """Tests for _attach_subsystems — missing parent, build_cfg propagation."""

    def test_subsystem_with_missing_parent_skipped(self):
        """Subsystem whose parent is not found is skipped with warning."""
        parent_systems: dict[str, System] = {}  # no parents at all
        orphan_ac = AppComponent(archi_id='sub-1', name='Missing.Core')
        from archi2likec4.builders.systems import _attach_subsystems
        _attach_subsystems(
            parent_systems, [orphan_ac],
            parent_name_fn=lambda ac: ac.name.split('.', 1)[0],
            sub_name_fn=lambda ac: ac.name.split('.', 1)[1],
        )
        # No crash, parent_systems still empty
        assert len(parent_systems) == 0

    def test_subsystem_with_build_cfg_metadata(self):
        """build_cfg.prop_map and standard_keys are passed through to subsystem metadata."""
        parent = System(c4_id='crm', name='CRM', archi_id='sys-1')
        parent_systems = {'CRM': parent}
        ac = AppComponent(archi_id='sub-1', name='CRM.Core', properties={'CI': '42'})
        cfg = SystemBuildConfig(prop_map={'CI': 'ci_number'}, standard_keys=['ci_number'])
        from archi2likec4.builders.systems import _attach_subsystems
        _attach_subsystems(
            parent_systems, [ac],
            parent_name_fn=lambda ac: ac.name.split('.', 1)[0],
            sub_name_fn=lambda ac: ac.name.split('.', 1)[1],
            build_cfg=cfg,
        )
        assert len(parent.subsystems) == 1
        assert parent.subsystems[0].metadata.get('ci_number') == '42'


class TestAttachFunctionsExtraEdgeCases:
    """Extra edge cases for attach_functions — subsystem attachment, no parent."""

    def test_function_no_parent_id_is_orphan(self):
        """Function with no parent_archi_id and no relationship is orphaned."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        fn = AppFunction(archi_id='fn-1', name='Calc', parent_archi_id='')
        orphans = attach_functions([sys], [fn])
        assert orphans == 1
        assert len(sys.functions) == 0

    def test_function_attached_to_subsystem_via_composition(self):
        """Function resolved to subsystem via CompositionRelationship."""
        sub = Subsystem(c4_id='core', name='CRM.Core', archi_id='sub-1')
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', subsystems=[sub])
        fn = AppFunction(archi_id='fn-1', name='Calc', parent_archi_id='')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationComponent', source_id='sub-1',
                target_type='ApplicationFunction', target_id='fn-1',
            ),
        ]
        orphans = attach_functions([sys], [fn], relationships=rels)
        assert orphans == 0
        assert len(sub.functions) == 1
        assert sub.functions[0].name == 'Calc'

    def test_function_attached_via_extra_archi_ids(self):
        """Function resolves to system via extra_archi_ids."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1', extra_archi_ids=['sys-dup'])
        fn = AppFunction(archi_id='fn-1', name='Calc', parent_archi_id='sys-dup')
        orphans = attach_functions([sys], [fn])
        assert orphans == 0
        assert len(sys.functions) == 1


class TestExtractUrlAndAssignTags:
    """Tests for _extract_url and _assign_tags helpers."""

    def test_extract_url_empty_string(self):
        from archi2likec4.builders.systems import _extract_url
        assert _extract_url('') is None

    def test_extract_url_no_url(self):
        from archi2likec4.builders.systems import _extract_url
        assert _extract_url('just some text') is None

    def test_extract_url_with_url(self):
        from archi2likec4.builders.systems import _extract_url
        assert _extract_url('see https://example.com/api for docs') == 'https://example.com/api'

    def test_extract_url_strips_trailing_punctuation(self):
        from archi2likec4.builders.systems import _extract_url
        assert _extract_url('URL: https://example.com/api.') == 'https://example.com/api'

    def test_assign_tags_review(self):
        from archi2likec4.builders.systems import _assign_tags
        assert _assign_tags('!РАЗБОР') == ['to_review']

    def test_assign_tags_external(self):
        from archi2likec4.builders.systems import _assign_tags
        assert _assign_tags('!External_services') == ['external']

    def test_assign_tags_normal_folder(self):
        from archi2likec4.builders.systems import _assign_tags
        assert _assign_tags('some_folder') == []


class TestBuildDataAccessMissingEntity:
    """Tests for data.py edge cases — missing entity, empty relationships."""

    def test_access_with_unknown_entity_skipped(self):
        """AccessRelationship referencing unknown DataObject is skipped."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='read',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='unknown-do',
            ),
        ]
        result = build_data_access([sys], [], rels)
        assert result == []

    def test_access_with_no_comp_path_skipped(self):
        """AccessRelationship with component not in any system is skipped."""
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='write',
                source_type='ApplicationComponent', source_id='unknown-comp',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_data_access([], [entity], rels)
        assert result == []

    def test_datastore_link_missing_tech_path(self):
        """SystemSoftware not in deployment is silently skipped."""
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        node = DeploymentNode(c4_id='server', archi_id='node-1', name='Server', tech_type='Node')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='unknown-sw',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_datastore_entity_links([node], [entity], rels)
        assert result == []

    def test_datastore_link_missing_entity(self):
        """DataObject not in entities list is silently skipped."""
        # sw-1 is the node itself (archi_id matches), so tech_path resolves
        node = DeploymentNode(c4_id='pg', archi_id='sw-1', name='PostgreSQL', tech_type='SystemSoftware')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='unknown-do',
            ),
        ]
        result = build_datastore_entity_links([node], [], rels)
        assert result == []

    def test_datastore_empty_nodes_returns_empty(self):
        """Empty deployment nodes returns empty list immediately."""
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        result = build_datastore_entity_links([], [entity], [])
        assert result == []

    def test_datastore_empty_entities_returns_empty(self):
        """Empty entities list returns empty list immediately."""
        node = DeploymentNode(c4_id='server', archi_id='node-1', name='Server', tech_type='Node')
        result = build_datastore_entity_links([node], [], [])
        assert result == []


# ── data.py edge cases (coverage uplift) ─────────────────────────────────

