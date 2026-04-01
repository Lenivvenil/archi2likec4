"""Tests for view generation in archi2likec4.generators."""

from archi2likec4.generators import (
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_landscape_view,
    generate_persistence_map,
    generate_solution_views,
)
from archi2likec4.generators.views import (
    ViewContext,
    _generate_deployment_view,
    _generate_functional_view,
    _generate_integration_view,
    _group_by_solution,
    _resolve_elements,
    _system_path_from_c4,
    _ViewData,
    build_view_context,
)
from archi2likec4.models import (
    RawRelationship,
    SolutionView,
)

# ── generate_landscape_view ──────────────────────────────────────────────

class TestGenerateLandscapeView:
    def test_structure(self):
        result = generate_landscape_view()
        assert 'view index' in result
        assert "title 'Application Landscape'" in result
        assert 'include *' in result
        assert 'exclude * where kind is dataEntity' in result


# ── generate_domain_functional_view ──────────────────────────────────────

class TestGenerateDomainFunctionalView:
    def test_structure(self):
        result = generate_domain_functional_view('channels', 'Channels')
        assert 'view channels_functional of channels' in result
        assert "title 'Channels - Functional Architecture'" in result
        assert 'include *' in result
        assert 'exclude * where kind is subsystem' in result
        assert 'exclude * where kind is appFunction' in result
        assert 'exclude * where kind is dataEntity' in result

    def test_escaping(self):
        result = generate_domain_functional_view('customer_service', "Customer's Service")
        assert "Customer\\'s Service" in result


# ── generate_domain_integration_view ─────────────────────────────────────

class TestGenerateDomainIntegrationView:
    def test_structure(self):
        result = generate_domain_integration_view('channels', 'Channels')
        assert 'view channels_integration of channels' in result
        assert '-> channels ->' in result


# ── generate_persistence_map ─────────────────────────────────────────────

class TestGeneratePersistenceMap:
    def test_structure(self):
        result = generate_persistence_map()
        assert 'view persistence_map' in result
        assert 'element.kind = dataEntity' in result


# ── _resolve_elements ───────────────────────────────────────────────────

class TestResolveElements:
    def test_functional_skips_entities(self):
        ctx = ViewContext(archi_to_c4={'a1': 'dom.sys1', 'e1': 'entities.ent1'}, sys_domain={}, entity_archi_ids={'e1'})
        c4_paths, entity_paths, unresolved, total = _resolve_elements(['a1', 'e1'], ctx, 'functional')
        assert c4_paths == ['dom.sys1']
        assert entity_paths == []
        assert unresolved == 0
        assert total == 1

    def test_integration_separates_entities(self):
        ctx = ViewContext(archi_to_c4={'a1': 'dom.sys1', 'e1': 'entities.ent1'}, sys_domain={}, entity_archi_ids={'e1'})
        c4_paths, entity_paths, unresolved, total = _resolve_elements(['a1', 'e1'], ctx, 'integration')
        assert c4_paths == ['dom.sys1']
        assert entity_paths == ['entities.ent1']
        assert unresolved == 0
        assert total == 1

    def test_deployment_prefers_tech_map(self):
        ctx = ViewContext(archi_to_c4={'a1': 'dom.sys1'}, sys_domain={}, tech_archi_to_c4={'a1': 'infra.node1'})
        c4_paths, entity_paths, unresolved, total = _resolve_elements(['a1'], ctx, 'deployment')
        assert c4_paths == ['infra.node1']
        assert total == 1

    def test_deployment_falls_back_to_archi(self):
        ctx = ViewContext(archi_to_c4={'a1': 'dom.sys1'}, sys_domain={}, tech_archi_to_c4={})
        c4_paths, _, unresolved, _ = _resolve_elements(['a1'], ctx, 'deployment')
        assert c4_paths == ['dom.sys1']
        assert unresolved == 0

    def test_promoted_fanout(self):
        ctx = ViewContext(
            archi_to_c4={}, sys_domain={},
            promoted_archi_to_c4={'parent1': ['dom.child1', 'dom.child2']},
        )
        c4_paths, _, unresolved, total = _resolve_elements(['parent1'], ctx, 'functional')
        assert c4_paths == ['dom.child1', 'dom.child2']
        assert unresolved == 0
        assert total == 1

    def test_unresolved_counted(self):
        ctx = ViewContext(archi_to_c4={}, sys_domain={})
        c4_paths, _, unresolved, total = _resolve_elements(['unknown1', 'unknown2'], ctx, 'functional')
        assert c4_paths == []
        assert unresolved == 2
        assert total == 2

    def test_deployment_skips_entities(self):
        ctx = ViewContext(archi_to_c4={'e1': 'entities.ent1'}, sys_domain={}, entity_archi_ids={'e1'})
        c4_paths, entity_paths, unresolved, total = _resolve_elements(['e1'], ctx, 'deployment')
        assert c4_paths == []
        assert entity_paths == []
        assert total == 0

    def test_integration_unresolved_entity_not_counted(self):
        """Entities that can't be resolved are silently dropped, not counted as unresolved."""
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, entity_archi_ids={'e_unknown'})
        c4_paths, entity_paths, unresolved, total = _resolve_elements(['e_unknown'], ctx, 'integration')
        assert entity_paths == []
        assert unresolved == 0
        assert total == 0


# ── _generate_deployment_view ────────────────────────────────────────────

class TestGenerateDeploymentView:
    @staticmethod
    def _vd(view_id: str, title: str, c4_paths: list[str]) -> _ViewData:
        return _ViewData(view_id=view_id, title=title, c4_paths=c4_paths,
                         unique_paths=list(dict.fromkeys(c4_paths)), entity_paths=[], relationship_archi_ids=[])

    def test_basic_infra_paths(self):
        """Infra paths are emitted with env prefix and .** suffix."""
        vd = self._vd('deployment_myapp', 'Deployment Architecture: MyApp', ['loc.cluster.node1'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4={'infra-1': 'loc.cluster.node1'})
        lines = _generate_deployment_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'deployment view deployment_myapp' in content
        assert 'prod.loc.cluster.node1.**' in content

    def test_empty_paths_returns_empty(self):
        """No c4_paths → no lines."""
        vd = self._vd('deployment_empty', 'Empty', [])
        ctx = ViewContext(archi_to_c4={}, sys_domain={})
        assert _generate_deployment_view(vd, ctx) == []

    def test_app_only_no_infra_returns_empty(self):
        """App paths without infra mapping → no lines (app paths excluded from deployment views)."""
        vd = self._vd('deployment_apponly', 'App Only', ['channels.efs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4={'infra-1': 'loc.cluster.node1'})
        assert _generate_deployment_view(vd, ctx) == []

    def test_enrichment_from_deploy_targets(self):
        """Infra paths enriched from deploy_targets for app paths."""
        vd = self._vd('deployment_enrich', 'Enriched', ['channels.efs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4={},
                          deploy_targets={'channels.efs': {'loc.server1'}})
        lines = _generate_deployment_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'prod.loc.server1.**' in content

    def test_prefix_match_enrichment(self):
        """Subsystem deploy mappings picked up via prefix match on system path."""
        vd = self._vd('deployment_prefix', 'Prefix', ['channels.efs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4={},
                          deploy_targets={'channels.efs.subsys': {'loc.node2'}}, deployment_env='staging')
        lines = _generate_deployment_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'staging.loc.node2.**' in content

    def test_ancestor_dedup(self):
        """Ancestor dedup: 'loc' subsumes 'loc.cluster.node1'."""
        vd = self._vd('deployment_dedup', 'Dedup', ['loc', 'loc.cluster.node1'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4={'i1': 'loc', 'i2': 'loc.cluster.node1'})
        lines = _generate_deployment_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'prod.loc.**' in content
        assert 'prod.loc.cluster.node1.**' not in content

    def test_qa11_warning(self, caplog):
        """QA-11 warning emitted when element count exceeds threshold."""
        import logging
        many_infra = [f'loc.node{i}' for i in range(45)]
        tech_map = {f'i{i}': f'loc.node{i}' for i in range(45)}
        vd = self._vd('deployment_big', 'Big', many_infra)
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4=tech_map)
        with caplog.at_level(logging.WARNING):
            lines = _generate_deployment_view(vd, ctx)
        assert lines  # should produce output
        assert 'QA-11' in caplog.text

    def test_no_trailing_comma(self):
        """Last include line should not have trailing comma."""
        vd = self._vd('deployment_comma', 'Comma', ['loc.node1', 'loc.node2'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={}, tech_archi_to_c4={'i1': 'loc.node1', 'i2': 'loc.node2'})
        lines = _generate_deployment_view(vd, ctx)
        include_lines = [ln for ln in lines if ln.strip().startswith('prod.')]
        assert not include_lines[-1].endswith(',')


# ── _generate_functional_view ────────────────────────────────────────────


class TestGenerateFunctionalView:
    @staticmethod
    def _vd(view_id: str, title: str, unique_paths: list[str]) -> _ViewData:
        return _ViewData(view_id=view_id, title=title, c4_paths=unique_paths,
                         unique_paths=unique_paths, entity_paths=[], relationship_archi_ids=[])

    def test_single_system_scoped_view(self):
        """Single system produces a scoped 'of' view with include *."""
        vd = self._vd('functional_myapp', 'Functional Architecture: MyApp', ['channels.efs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels'}, sys_ids={'efs'})
        lines = _generate_functional_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'view functional_myapp of channels.efs' in content
        assert 'include *' in content
        assert 'exclude * where kind is dataEntity' in content
        assert 'exclude * where kind is dataStore' in content

    def test_multi_system_primary_gets_wildcard(self):
        """Multi-system: primary system (most elements) gets .* include."""
        vd = self._vd('functional_multi', 'Functional Architecture: Multi', [
            'channels.efs', 'channels.efs', 'channels.efs',  # 3 elements
            'products.abs',  # 1 element
        ])
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels', 'abs': 'products'},
                          sys_ids={'efs', 'abs'})
        lines = _generate_functional_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'view functional_multi {' in content
        assert 'channels.efs.*' in content
        assert 'products.abs' in content
        # Non-primary should NOT have .*
        assert 'products.abs.*' not in content

    def test_empty_paths_returns_empty(self):
        """No paths → empty lines."""
        vd = self._vd('functional_empty', 'Empty', [])
        ctx = ViewContext(archi_to_c4={}, sys_domain={})
        assert _generate_functional_view(vd, ctx) == []

    def test_qa11_warning(self, caplog):
        """QA-11 warning emitted when element count exceeds threshold."""
        import logging
        paths = [f'channels.sys{i}' for i in range(30)]
        vd = self._vd('functional_big', 'Big', paths)
        ctx = ViewContext(archi_to_c4={}, sys_domain={f'sys{i}': 'channels' for i in range(30)},
                          sys_ids={f'sys{i}' for i in range(30)})
        with caplog.at_level(logging.WARNING):
            _generate_functional_view(vd, ctx)
        assert 'QA-11' in caplog.text

    def test_subdomain_path(self):
        """System in subdomain correctly resolved to 3-part path."""
        vd = self._vd('functional_sub', 'Subdomain', ['channels.cards.efs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels'},
                          sys_subdomain={'efs': 'cards'}, sys_ids={'efs'})
        lines = _generate_functional_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'view functional_sub of channels.cards.efs' in content

    def test_no_trailing_comma(self):
        """Last include line should not have trailing comma."""
        vd = self._vd('functional_comma', 'Comma', ['channels.efs', 'products.abs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels', 'abs': 'products'},
                          sys_ids={'efs', 'abs'})
        lines = _generate_functional_view(vd, ctx)
        include_section = [ln for ln in lines if ln.strip().startswith(('channels.', 'products.'))]
        assert not include_section[-1].endswith(',')


# ── _generate_integration_view ──────────────────────────────────────────


class TestGenerateIntegrationView:
    @staticmethod
    def _vd(view_id: str, title: str, unique_paths: list[str],
            entity_paths: list[str] | None = None,
            relationship_archi_ids: list[str] | None = None) -> _ViewData:
        return _ViewData(view_id=view_id, title=title, c4_paths=unique_paths,
                         unique_paths=unique_paths, entity_paths=entity_paths or [],
                         relationship_archi_ids=relationship_archi_ids or [])

    def test_basic_with_relationships(self):
        """Integration view with relationships includes system paths and edges."""
        vd = self._vd('integration_myapp', 'Integration Architecture: MyApp',
                       ['channels.efs', 'products.abs'], relationship_archi_ids=['rel-1'])
        ctx = ViewContext(
            archi_to_c4={'sys-1': 'channels.efs', 'sys-2': 'products.abs'},
            sys_domain={'efs': 'channels', 'abs': 'products'},
            rel_lookup={'rel-1': ('sys-1', 'sys-2', 'FlowRelationship')},
            sys_ids={'efs', 'abs'},
        )
        lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'view integration_myapp' in content
        assert 'channels.efs -> products.abs' in content

    def test_structural_rels_skipped(self):
        """Structural relationships are excluded from integration views."""
        vd = self._vd('integration_struct', 'Structural', ['channels.efs', 'products.abs'],
                       relationship_archi_ids=['rel-1'])
        ctx = ViewContext(
            archi_to_c4={'sys-1': 'channels.efs', 'sys-2': 'products.abs'},
            sys_domain={'efs': 'channels', 'abs': 'products'},
            rel_lookup={'rel-1': ('sys-1', 'sys-2', 'CompositionRelationship')},
            sys_ids={'efs', 'abs'},
        )
        lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'channels.efs -> products.abs' not in content

    def test_orphan_removal(self):
        """Systems not in any relationship pair are removed."""
        vd = self._vd('integration_orphan', 'Orphan', ['channels.efs', 'products.abs', 'infra.monitor'],
                       relationship_archi_ids=['rel-1'])
        ctx = ViewContext(
            archi_to_c4={'sys-1': 'channels.efs', 'sys-2': 'products.abs', 'sys-3': 'infra.monitor'},
            sys_domain={'efs': 'channels', 'abs': 'products', 'monitor': 'infra'},
            rel_lookup={'rel-1': ('sys-1', 'sys-2', 'FlowRelationship')},
            sys_ids={'efs', 'abs', 'monitor'},
        )
        lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'infra.monitor' not in content
        assert 'channels.efs' in content

    def test_entity_cap_excludes_excess(self, caplog):
        """Entities exceeding cap are excluded with comment."""
        import logging
        entities = [f'de_entity{i}' for i in range(15)]
        vd = self._vd('integration_cap', 'Cap', ['channels.efs'], entity_paths=entities)
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels'}, sys_ids={'efs'})
        with caplog.at_level(logging.INFO):
            lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert '15 data entities excluded' in content
        assert 'de_entity0' not in content

    def test_entity_only_overcap_returns_empty(self):
        """View with only entities exceeding cap and no systems/rels returns []."""
        vd = self._vd('integration_entity_only_overcap', 'EntityOnlyOvercap', [],
                       entity_paths=[f'de_entity{i}' for i in range(15)])
        ctx = ViewContext(archi_to_c4={}, sys_domain={})
        assert _generate_integration_view(vd, ctx) == []

    def test_entity_cap_includes_within_limit(self):
        """Entities within cap are included."""
        vd = self._vd('integration_ent', 'Entities', ['channels.efs'],
                       entity_paths=['de_account', 'de_card'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels'}, sys_ids={'efs'})
        lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'de_account' in content
        assert 'de_card' in content

    def test_promoted_parent_fanout(self):
        """Promoted parent fans out to children in relationship endpoints."""
        vd = self._vd('integration_fanout', 'Fanout',
                       ['channels.efs_card', 'channels.efs_loan', 'products.abs'],
                       relationship_archi_ids=['rel-1'])
        ctx = ViewContext(
            archi_to_c4={'sys-2': 'products.abs'},
            sys_domain={'efs_card': 'channels', 'efs_loan': 'channels', 'abs': 'products'},
            promoted_archi_to_c4={'parent-1': ['channels.efs_card', 'channels.efs_loan']},
            rel_lookup={'rel-1': ('parent-1', 'sys-2', 'FlowRelationship')},
            sys_ids={'efs_card', 'efs_loan', 'abs'},
        )
        lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'channels.efs_card -> products.abs' in content
        assert 'channels.efs_loan -> products.abs' in content

    def test_qa11_warning(self, caplog):
        """QA-11 warning emitted when element count exceeds threshold."""
        import logging
        paths = [f'dom.sys{i}' for i in range(30)]
        rels = [(f'sys-{i}', f'sys-{i+1}', 'FlowRelationship') for i in range(25)]
        rel_lookup = {f'rel-{i}': r for i, r in enumerate(rels)}
        archi_to_c4 = {f'sys-{i}': f'dom.sys{i}' for i in range(30)}
        # Use enough data to exceed default _MAX_INTEGRATION (50)
        vd = self._vd('integration_big', 'Big', paths, relationship_archi_ids=list(rel_lookup.keys()))
        ctx = ViewContext(archi_to_c4=archi_to_c4, sys_domain={f'sys{i}': 'dom' for i in range(30)},
                          rel_lookup=rel_lookup, sys_ids={f'sys{i}' for i in range(30)})
        with caplog.at_level(logging.WARNING):
            _generate_integration_view(vd, ctx)
        assert 'QA-11' in caplog.text

    def test_no_trailing_comma(self):
        """Last include line should not have trailing comma."""
        vd = self._vd('integration_comma', 'Comma', ['channels.efs', 'products.abs'],
                       relationship_archi_ids=['rel-1'])
        ctx = ViewContext(
            archi_to_c4={'sys-1': 'channels.efs', 'sys-2': 'products.abs'},
            sys_domain={'efs': 'channels', 'abs': 'products'},
            rel_lookup={'rel-1': ('sys-1', 'sys-2', 'FlowRelationship')},
            sys_ids={'efs', 'abs'},
        )
        lines = _generate_integration_view(vd, ctx)
        include_lines = [ln for ln in lines if '->' in ln or ln.strip().startswith(('channels.', 'products.'))]
        assert not include_lines[-1].endswith(',')

    def test_exclude_datastore(self):
        """Integration view always has exclude dataStore."""
        vd = self._vd('integration_ds', 'DataStore', ['channels.efs'])
        ctx = ViewContext(archi_to_c4={}, sys_domain={'efs': 'channels'}, sys_ids={'efs'})
        lines = _generate_integration_view(vd, ctx)
        content = '\n'.join(lines)
        assert 'exclude * where kind is dataStore' in content


# ── build_view_context / _group_by_solution ──────────────────────────

class TestGroupBySolution:
    def test_groups_by_solution_slug(self):
        sv1 = SolutionView(name='f.A', view_type='functional', solution='sol_a', element_archi_ids=['e1'])
        sv2 = SolutionView(name='f.B', view_type='functional', solution='sol_b', element_archi_ids=['e2'])
        sv3 = SolutionView(name='i.A', view_type='integration', solution='sol_a', element_archi_ids=['e3'])
        result = _group_by_solution([sv1, sv2, sv3])
        assert set(result.keys()) == {'sol_a', 'sol_b'}
        assert len(result['sol_a']) == 2
        assert len(result['sol_b']) == 1

    def test_empty_list(self):
        assert _group_by_solution([]) == {}


class TestBuildViewContext:
    def test_builds_lookups(self):
        rel = RawRelationship(
            rel_id='r1', rel_type='FlowRelationship', name='',
            source_type='ApplicationComponent', source_id='s1',
            target_type='ApplicationComponent', target_id='t1',
        )
        ctx = build_view_context(
            archi_to_c4={},
            sys_domain={'sys1': 'dom1'},
            relationships=[rel],
            entity_archi_ids=None,
            deployment_map=[('dom1.sys1', 'loc.node1')],
        )
        assert ctx.entity_archi_ids == set()
        assert ctx.sys_ids == {'sys1'}
        assert 'r1' in ctx.rel_lookup
        assert 'dom1.sys1' in ctx.deploy_targets

    def test_preserves_entity_archi_ids(self):
        ctx = build_view_context(
            archi_to_c4={},
            sys_domain={},
            entity_archi_ids={'ent1', 'ent2'},
        )
        assert ctx.entity_archi_ids == {'ent1', 'ent2'}


# ── generate_solution_views ──────────────────────────────────────────────

class TestGenerateSolutionViews:
    def test_functional_single_system(self):
        sv = SolutionView(
            name='functional_architecture.AutoRepay',
            view_type='functional',
            solution='auto_repay',
            element_archi_ids=['sys-1'],
        )
        archi_to_c4 = {'sys-1': 'channels.efs'}
        ctx = build_view_context(archi_to_c4, {'efs': 'channels'})
        files, unresolved, total = generate_solution_views([sv], ctx)
        assert 'auto_repay' in files
        content = files['auto_repay']
        assert 'view functional_auto_repay of channels.efs' in content
        assert unresolved == 0
        assert total == 1

    def test_integration_with_relationships(self):
        sv = SolutionView(
            name='integration_architecture.AutoRepay',
            view_type='integration',
            solution='auto_repay',
            element_archi_ids=['sys-1', 'sys-2'],
            relationship_archi_ids=['rel-1'],
        )
        archi_to_c4 = {
            'sys-1': 'channels.efs',
            'sys-2': 'products.abs',
        }
        rels = [
            RawRelationship(
                rel_id='rel-1', rel_type='FlowRelationship', name='pay',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        ctx = build_view_context(archi_to_c4, {'efs': 'channels', 'abs': 'products'}, rels)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['auto_repay']
        assert 'channels.efs -> products.abs' in content

    def test_structural_rels_skipped_in_integration(self):
        sv = SolutionView(
            name='integration_architecture.Test',
            view_type='integration',
            solution='test',
            element_archi_ids=['sys-1', 'sys-2'],
            relationship_archi_ids=['rel-1'],
        )
        archi_to_c4 = {
            'sys-1': 'channels.efs',
            'sys-2': 'products.abs',
        }
        rels = [
            RawRelationship(
                rel_id='rel-1', rel_type='CompositionRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        ctx = build_view_context(archi_to_c4, {'efs': 'channels', 'abs': 'products'}, rels)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['test']
        # Should NOT contain direct relationship (structural filtered)
        assert 'channels.efs -> products.abs' not in content

    def test_integration_no_wildcard_fallback(self):
        """Integration view with no resolved rels should NOT emit wildcard edges."""
        sv = SolutionView(
            name='integration_architecture.NoRels',
            view_type='integration',
            solution='no_rels',
            element_archi_ids=['sys-1', 'sys-2'],
            relationship_archi_ids=[],
        )
        archi_to_c4 = {
            'sys-1': 'channels.efs',
            'sys-2': 'products.abs',
        }
        ctx = build_view_context(archi_to_c4, {'efs': 'channels', 'abs': 'products'}, [])
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['no_rels']
        assert '-> *' not in content
        assert '* ->' not in content
        # Systems should still be included
        assert 'channels.efs' in content

    def test_integration_promoted_parent_fanout(self):
        """P1-5: promoted parent archi_id should fan out in relationship endpoints."""
        sv = SolutionView(
            name='integration_architecture.Test',
            view_type='integration',
            solution='test',
            element_archi_ids=['parent-1', 'sys-2'],
            relationship_archi_ids=['rel-1'],
        )
        # parent-1 is a promoted parent — NOT in archi_to_c4, only in promoted map
        archi_to_c4 = {
            'child-a': 'channels.efs_card',
            'child-b': 'channels.efs_loan',
            'sys-2': 'products.abs',
        }
        promoted_archi_to_c4 = {
            'parent-1': ['channels.efs_card', 'channels.efs_loan'],
        }
        rels = [
            RawRelationship(
                rel_id='rel-1', rel_type='FlowRelationship', name='pay',
                source_type='ApplicationComponent', source_id='parent-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        ctx = build_view_context(
            archi_to_c4, {'efs_card': 'channels', 'efs_loan': 'channels', 'abs': 'products'},
            rels, promoted_archi_to_c4=promoted_archi_to_c4)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['test']
        # Fan-out: promoted parent → both children create relationships
        assert 'channels.efs_card -> products.abs' in content
        assert 'channels.efs_loan -> products.abs' in content

    def test_empty_when_no_resolved_paths(self):
        sv = SolutionView(
            name='functional_architecture.Ghost',
            view_type='functional',
            solution='ghost',
            element_archi_ids=['unknown-1'],
        )
        ctx = build_view_context({}, {})
        files, unresolved, total = generate_solution_views([sv], ctx)
        assert 'ghost' not in files
        assert unresolved == 1
        assert total == 1

    def test_entity_only_integration_view_not_dropped(self):
        """Integration view with only data entities should still render."""
        sv = SolutionView(
            name='integration_architecture.DataOnly',
            view_type='integration',
            solution='data_only',
            element_archi_ids=['do-1', 'do-2'],
            relationship_archi_ids=[],
        )
        archi_to_c4 = {'do-1': 'de_account', 'do-2': 'de_card'}
        entity_archi_ids = {'do-1', 'do-2'}
        ctx = build_view_context(archi_to_c4, {}, entity_archi_ids=entity_archi_ids)
        files, _, _ = generate_solution_views([sv], ctx)
        assert 'data_only' in files
        content = files['data_only']
        assert 'de_account' in content
        assert 'de_card' in content

    def test_coverage_not_inflated_by_filtered_entities(self):
        """Filtered entity IDs should not inflate total_elements."""
        sv = SolutionView(
            name='functional_architecture.Mixed',
            view_type='functional',
            solution='mixed',
            element_archi_ids=['sys-1', 'do-1', 'unknown-1'],
        )
        archi_to_c4 = {'sys-1': 'channels.efs', 'do-1': 'de_account'}
        entity_archi_ids = {'do-1'}
        ctx = build_view_context(archi_to_c4, {'efs': 'channels'}, entity_archi_ids=entity_archi_ids)
        _, unresolved, total = generate_solution_views([sv], ctx)
        # total should be 2 (sys-1 + unknown-1), not 3 (do-1 is filtered)
        assert total == 2
        assert unresolved == 1

    def test_integration_coverage_not_inflated_by_filtered_entities(self):
        """Integration view: filtered entity IDs should not inflate total_elements."""
        sv = SolutionView(
            name='integration_architecture.Mixed',
            view_type='integration',
            solution='mixed_int',
            element_archi_ids=['sys-1', 'do-1', 'unknown-1'],
        )
        archi_to_c4 = {'sys-1': 'channels.efs', 'do-1': 'de_account'}
        entity_archi_ids = {'do-1'}
        ctx = build_view_context(archi_to_c4, {'efs': 'channels'}, entity_archi_ids=entity_archi_ids)
        _, unresolved, total = generate_solution_views([sv], ctx)
        # total should be 2 (sys-1 + unknown-1), not 3 (do-1 is entity)
        assert total == 2
        assert unresolved == 1

    def test_deployment_view_enriched_from_deploy_map(self):
        """Deployment view uses deployment_map for infra paths; app paths excluded."""
        sv = SolutionView(
            name='deployment_architecture.AppOnly',
            view_type='deployment',
            solution='app_only',
            element_archi_ids=['ac-1'],
        )
        archi_to_c4 = {'ac-1': 'channels.efs'}
        deploy_map = [('channels.efs', 'server_1')]
        ctx = build_view_context(archi_to_c4, {'efs': 'channels'}, deployment_map=deploy_map)
        files, _, _ = generate_solution_views([sv], ctx)
        assert 'app_only' in files
        content = files['app_only']
        # App path is NOT included directly — it lives inside node via instanceOf
        assert 'channels.efs' not in content
        # Infra path appears with prod. prefix and .** suffix
        assert 'prod.server_1.**' in content
        assert 'deployment view' in content

    def test_dispatcher_all_three_view_types_in_one_solution(self):
        """Dispatcher produces all three view types in a single solution file."""
        archi_to_c4 = {
            'sys-1': 'channels.efs',
            'sys-2': 'products.abs',
        }
        sys_domain = {'efs': 'channels', 'abs': 'products'}
        rels = [
            RawRelationship(
                rel_id='rel-1', rel_type='FlowRelationship', name='pay',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        deploy_map = [('channels.efs', 'server_1')]
        tech_archi_to_c4 = {'tech-1': 'server_1'}
        views = [
            SolutionView(name='sol.Pay', view_type='functional', solution='pay',
                         element_archi_ids=['sys-1', 'sys-2']),
            SolutionView(name='sol.Pay', view_type='integration', solution='pay',
                         element_archi_ids=['sys-1', 'sys-2'], relationship_archi_ids=['rel-1']),
            SolutionView(name='sol.Pay', view_type='deployment', solution='pay',
                         element_archi_ids=['sys-1', 'tech-1']),
        ]
        ctx = build_view_context(archi_to_c4, sys_domain, rels,
            tech_archi_to_c4=tech_archi_to_c4, deployment_map=deploy_map)
        files, unresolved, total = generate_solution_views(views, ctx)
        assert 'pay' in files
        content = files['pay']
        # All three view types present
        assert 'view functional_pay' in content
        assert 'view integration_pay' in content
        assert 'deployment view deployment_pay' in content
        # Functional view title
        assert "Functional Architecture: Pay" in content
        # Integration view has relationship
        assert 'channels.efs -> products.abs' in content
        # Deployment view has infra
        assert 'prod.server_1.**' in content
        assert unresolved == 0
        assert total > 0

    def test_dispatcher_unknown_view_type_produces_no_lines(self):
        """Unknown view type is silently skipped (no crash, no file)."""
        sv = SolutionView(
            name='sol.X', view_type='unknown', solution='x',
            element_archi_ids=['sys-1'],
        )
        ctx = build_view_context({'sys-1': 'dom.sys'}, {'sys': 'dom'})
        files, _, _ = generate_solution_views([sv], ctx)
        # No file emitted since unknown type produces no view lines
        assert 'x' not in files


# ── SolutionViewDeployment ───────────────────────────────────────────────

class TestSolutionViewDeployment:
    def test_deployment_view_with_tech_map(self):
        sv = SolutionView(
            name='deployment_architecture.PaymentSvc',
            view_type='deployment',
            solution='payment_svc',
            element_archi_ids=['n-1', 'sw-1'],
        )
        tech_archi_to_c4 = {'n-1': 'server_1', 'sw-1': 'server_1.pg'}
        ctx = build_view_context({}, {}, tech_archi_to_c4=tech_archi_to_c4)
        files, unresolved, total = generate_solution_views([sv], ctx)
        assert 'payment_svc' in files
        content = files['payment_svc']
        assert 'Deployment' in content
        assert 'server_1' in content
        assert unresolved == 0  # resolved via tech_archi_to_c4
        assert total == 2

    def test_deployment_solution_view_includes_infra_from_map(self):
        """Deployment solution view pulls infra paths from deployment_map when diagram has only app elements."""
        sv = SolutionView(
            name='deployment_architecture.PaymentDeploy',
            view_type='deployment',
            solution='payment_deploy',
            element_archi_ids=['ac-1', 'ac-2'],
        )
        archi_to_c4 = {'ac-1': 'channels.efs', 'ac-2': 'products.abs'}
        deploy_map = [
            ('channels.efs', 'dc.server_1'),
            ('products.abs', 'dc.server_2'),
        ]
        ctx = build_view_context(archi_to_c4, {'efs': 'channels', 'abs': 'products'},
            deployment_map=deploy_map)
        files, unresolved, total = generate_solution_views([sv], ctx)
        assert 'payment_deploy' in files
        content = files['payment_deploy']
        # App paths are NOT included in deployment views (they live inside nodes via instanceOf)
        assert 'channels.efs' not in content
        assert 'products.abs' not in content
        # Infra paths pulled from deployment_map, with prod. prefix and .** wildcard
        assert 'prod.dc.server_1.**' in content
        assert 'prod.dc.server_2.**' in content
        assert 'deployment view' in content

    def test_deployment_view_uses_wildcard_expansion(self):
        """Deployment view uses .** wildcard to include nested deployment nodes."""
        sv = SolutionView(
            name='deployment_architecture.InfraOnly',
            view_type='deployment',
            solution='infra_only',
            element_archi_ids=['n-1', 'sw-1'],
        )
        tech_archi_to_c4 = {'n-1': 'dc.server_1', 'sw-1': 'dc.server_1.pg'}
        ctx = build_view_context({}, {}, tech_archi_to_c4=tech_archi_to_c4)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['infra_only']
        # Ancestor dedup: dc.server_1 is ancestor of dc.server_1.pg → only dc.server_1.** emitted
        assert 'prod.dc.server_1.**' in content
        assert 'prod.dc.server_1.pg.**' not in content
        assert 'deployment view' in content


# ── generate_solution_views: subdomain-aware paths ───────────────────────

class TestSolutionViewsSubdomainPaths:
    def test_functional_subdomain_single_system_scoped_view(self):
        """Functional view for a subdomain path should scope to the full 3-part path."""
        sv = SolutionView(
            name='functional_architecture.AutoRepay',
            view_type='functional',
            solution='auto_repay',
            element_archi_ids=['sys-1'],
        )
        # channels.retail.efs — subdomain path
        archi_to_c4 = {'sys-1': 'channels.retail.efs'}
        sys_domain = {'efs': 'channels'}
        sys_subdomain = {'efs': 'retail'}
        ctx = build_view_context(archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['auto_repay']
        # Must scope to the system, not just the subdomain
        assert 'view functional_auto_repay of channels.retail.efs' in content
        assert 'view functional_auto_repay of channels.retail {' not in content

    def test_integration_subdomain_same_subdomain_no_self_edge(self):
        """Two systems in the same subdomain must not collapse to a self-edge."""
        sv = SolutionView(
            name='integration_architecture.Retail',
            view_type='integration',
            solution='retail',
            element_archi_ids=['sys-1', 'sys-2'],
            relationship_archi_ids=['rel-1'],
        )
        archi_to_c4 = {
            'sys-1': 'channels.retail.efs',
            'sys-2': 'channels.retail.cards',
        }
        rels = [
            RawRelationship(
                rel_id='rel-1', rel_type='FlowRelationship', name='pay',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        sys_domain = {'efs': 'channels', 'cards': 'channels'}
        sys_subdomain = {'efs': 'retail', 'cards': 'retail'}
        ctx = build_view_context(archi_to_c4, sys_domain, rels, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['retail']
        # The two systems are distinct — relationship must appear
        assert 'channels.retail.efs -> channels.retail.cards' in content

    def test_integration_cross_domain_relationship(self):
        """Integration view: cross-domain subdomain paths produce correct endpoints."""
        sv = SolutionView(
            name='integration_architecture.CrossDomain',
            view_type='integration',
            solution='cross',
            element_archi_ids=['sys-1', 'sys-2'],
            relationship_archi_ids=['rel-1'],
        )
        archi_to_c4 = {
            'sys-1': 'channels.retail.efs',
            'sys-2': 'products.abs',
        }
        rels = [
            RawRelationship(
                rel_id='rel-1', rel_type='FlowRelationship', name='pay',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='ApplicationComponent', target_id='sys-2',
            ),
        ]
        sys_domain = {'efs': 'channels', 'abs': 'products'}
        sys_subdomain = {'efs': 'retail'}
        ctx = build_view_context(archi_to_c4, sys_domain, rels, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['cross']
        assert 'channels.retail.efs -> products.abs' in content

    def test_functional_subsystem_path_collapses_to_system(self):
        """Functional view: deeper paths (system.subsystem) collapse to system path."""
        sv = SolutionView(
            name='functional_architecture.AutoRepay',
            view_type='functional',
            solution='auto_repay',
            element_archi_ids=['fn-1'],
        )
        # channels.retail.efs.do_loan — function inside subdomain system
        archi_to_c4 = {'fn-1': 'channels.retail.efs.do_loan'}
        sys_domain = {'efs': 'channels'}
        sys_subdomain = {'efs': 'retail'}
        ctx = build_view_context(archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['auto_repay']
        # Should scope to channels.retail.efs, not channels.retail
        assert 'of channels.retail.efs' in content

    def test_functional_subsystem_not_confused_with_subdomain_system(self):
        """Subsystem path must not be treated as a subdomain.system path.

        Scenario: system 'efs' has subsystem 'core' (path channels.efs.core).
        Separately, system 'core' is in subdomain 'efs' (sys_subdomain['core']='efs').
        Without sys_ids context the check sys_subdomain.get('core')=='efs' fires and
        would return channels.efs.core as the system path for the subsystem.
        With sys_ids, parts[2]='core' is verified to be a known system first —
        but 'efs' (parts[1]) is NOT a known system in sys_domain for this element,
        so the subsystem path should collapse to the system path channels.efs.
        """
        sv = SolutionView(
            name='functional_architecture.Channels',
            view_type='functional',
            solution='channels',
            element_archi_ids=['sub-1'],
        )
        # channels.efs.core — subsystem 'core' under system 'efs'
        # sys_domain contains 'efs' (real system) but NOT 'core' as a system in this scenario
        archi_to_c4 = {'sub-1': 'channels.efs.core'}
        # 'efs' is a real system (no subdomain); 'core' is a system in subdomain 'efs' elsewhere
        # but here we only have 'efs' in sys_domain
        sys_domain = {'efs': 'channels'}
        # sys_subdomain says 'core' maps to subdomain 'efs'
        sys_subdomain = {'core': 'efs'}
        ctx = build_view_context(archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['channels']
        # Should scope to channels.efs (the actual system), not channels.efs.core
        # because 'core' is not in sys_domain (not a known system in this context)
        assert 'of channels.efs' in content
        assert 'of channels.efs.core' not in content

    def test_functional_subsystem_not_confused_with_cross_domain_system(self):
        """Subsystem path must not be treated as a subdomain.system path when the
        colliding system exists in sys_domain but belongs to a different domain.

        Scenario: system 'efs' is in domain 'channels' (no subdomain).
        System 'core' is a real system in domain 'products' (sys_domain has it).
        sys_subdomain says 'core' maps to subdomain 'efs'.
        Path channels.efs.core is a subsystem of 'efs', NOT system 'core'.
        The sys_ids guard alone is insufficient: 'core' IS in sys_ids, so the
        ambiguity is only resolved by also checking sys_domain['core']=='channels'.
        """
        sv = SolutionView(
            name='functional_architecture.Channels',
            view_type='functional',
            solution='channels',
            element_archi_ids=['sub-1'],
        )
        archi_to_c4 = {'sub-1': 'channels.efs.core'}
        # 'core' is a known system in sys_domain, but in domain 'products', not 'channels'
        sys_domain = {'efs': 'channels', 'core': 'products'}
        sys_subdomain = {'core': 'efs'}
        ctx = build_view_context(archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['channels']
        # Should collapse to channels.efs (system), not channels.efs.core
        assert 'of channels.efs' in content
        assert 'of channels.efs.core' not in content

    def test_functional_system_in_subdomain_with_same_name_as_sibling_system(self):
        """Path resolves to the subdomain.system form when sys_subdomain is authoritative.

        Scenario: system 'efs' is in domain 'channels' (no subdomain).
        System 'core' is ALSO in domain 'channels', assigned to subdomain 'efs'.
        sys_subdomain = {'core': 'efs'} and sys_domain = {'efs': 'channels', 'core': 'channels'}.
        Path 'channels.efs.core.fn' belongs to system 'core' (in subdomain 'efs'), NOT to
        a subsystem of 'efs'.  A subsystem would not appear in sys_domain; since 'core' IS in
        sys_domain, sys_subdomain.get('core')=='efs' is authoritative and the 3-part system
        path channels.efs.core is correct.
        """
        sv = SolutionView(
            name='functional_architecture.Channels',
            view_type='functional',
            solution='channels',
            element_archi_ids=['sub-1'],
        )
        # 4-part path: domain.subdomain.system.fn (core is the system in subdomain efs)
        archi_to_c4 = {'sub-1': 'channels.efs.core.fn'}
        # Both 'efs' and 'core' are known systems in 'channels'; 'core' is in subdomain 'efs'
        sys_domain = {'efs': 'channels', 'core': 'channels'}
        sys_subdomain = {'core': 'efs'}
        ctx = build_view_context(archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
        files, _, _ = generate_solution_views([sv], ctx)
        content = files['channels']
        # sys_subdomain is authoritative: core is in subdomain efs, so path is channels.efs.core
        assert 'of channels.efs.core' in content


# ── _system_path_from_c4 ──────────────────────────────────────────────────

class TestSystemPathFromC4:
    """Unit tests for _system_path_from_c4 path disambiguation helper."""

    def test_two_part_path_no_subdomain(self):
        """Simple domain.system path returned as-is."""
        assert _system_path_from_c4('products.billing', None) == 'products.billing'

    def test_two_part_path_with_subdomain_dict(self):
        """Two-part path has no subdomain segment — returns domain.system unchanged."""
        assert _system_path_from_c4('products.billing', {'billing': 'core'}) == 'products.billing'

    def test_three_part_path_subsystem_no_subdomain_dict(self):
        """Three-part path without sys_subdomain falls back to domain.segment1."""
        assert _system_path_from_c4('products.billing.invoices', None) == 'products.billing'

    def test_three_part_path_system_in_subdomain(self):
        """Three-part path domain.subdomain.system identified via sys_subdomain lookup."""
        sys_subdomain = {'payments': 'core'}
        result = _system_path_from_c4('products.core.payments', sys_subdomain)
        assert result == 'products.core.payments'

    def test_three_part_path_segment2_not_in_subdomain(self):
        """Three-part path where parts[2] has no subdomain mapping → domain.parts[1]."""
        sys_subdomain = {'other': 'core'}
        result = _system_path_from_c4('products.billing.invoices', sys_subdomain)
        assert result == 'products.billing'

    def test_four_part_path_system_in_subdomain(self):
        """Four-part path domain.subdomain.system.fn extracts domain.subdomain.system."""
        sys_subdomain = {'payments': 'core'}
        result = _system_path_from_c4('products.core.payments.fn1', sys_subdomain)
        assert result == 'products.core.payments'

    def test_sys_ids_filter_prevents_false_match(self):
        """sys_ids guard: parts[2] must be a known system; subsystem archi_id skipped."""
        sys_subdomain = {'invoices': 'billing'}
        # 'invoices' looks like a system in subdomain 'billing', but is not in sys_ids
        sys_ids = {'billing', 'other'}
        result = _system_path_from_c4('products.billing.invoices', sys_subdomain, sys_ids=sys_ids)
        assert result == 'products.billing'

    def test_sys_domain_filter_prevents_cross_domain_match(self):
        """sys_domain guard: parts[2] must belong to parts[0] domain."""
        sys_subdomain = {'payments': 'core'}
        sys_ids = {'payments'}
        # payments belongs to 'finance', not 'products'
        sys_domain = {'payments': 'finance'}
        result = _system_path_from_c4('products.core.payments', sys_subdomain, sys_ids=sys_ids, sys_domain=sys_domain)
        assert result == 'products.core'

    def test_single_part_path_returned_unchanged(self):
        """Single-segment path returned as-is (no dots)."""
        assert _system_path_from_c4('billing', None) == 'billing'
