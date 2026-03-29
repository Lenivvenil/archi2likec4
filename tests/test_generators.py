"""Tests for archi2likec4.generators — .c4 file content generation."""

from archi2likec4.generators import (
    generate_audit_md,
    generate_datastore_mapping_c4,
    generate_deployment_c4,
    generate_deployment_overview_view,
    generate_domain_c4,
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_entities,
    generate_landscape_view,
    generate_persistence_map,
    generate_relationships,
    generate_solution_views,
    generate_spec,
    generate_system_detail_c4,
)
from archi2likec4.generators.views import _generate_deployment_view, _resolve_elements, _system_path_from_c4
from archi2likec4.models import (
    AppFunction,
    DataAccess,
    DataEntity,
    DeploymentNode,
    Integration,
    RawRelationship,
    SolutionView,
    Subdomain,
    Subsystem,
    System,
)
from tests.helpers import MockBuilt, MockConfig

# ── generate_spec ────────────────────────────────────────────────────────

class TestGenerateSpec:
    def test_contains_kinds(self):
        spec = generate_spec()
        assert 'element domain' in spec
        assert 'element system' in spec
        assert 'element subsystem' in spec
        assert 'element appFunction' in spec
        assert 'element dataEntity' in spec

    def test_specification_contains_subdomain_kind(self):
        spec = generate_spec()
        assert 'element subdomain' in spec
        # subdomain should appear between domain and system
        idx_domain = spec.index('element domain')
        idx_subdomain = spec.index('element subdomain')
        idx_system = spec.index('element system')
        assert idx_domain < idx_subdomain < idx_system

    def test_contains_tags(self):
        spec = generate_spec()
        assert 'tag to_review' in spec
        assert 'tag external' in spec

    def test_contains_colors(self):
        spec = generate_spec()
        assert 'color archi-app' in spec

    def test_custom_colors_from_config(self):
        cfg = MockConfig(spec_colors={
            'archi-app': '#FF0000',
            'archi-app-light': '#BDE0F0',
            'archi-data': '#F0D68A',
            'archi-store': '#B0B0B0',
            'archi-tech': '#93D275',
            'archi-tech-light': '#C5E6B8',
        })
        spec = generate_spec(cfg)
        assert 'color archi-app #FF0000' in spec
        assert '#7EB8DA' not in spec

    def test_custom_shapes_from_config(self):
        cfg = MockConfig(spec_shapes={
            'domain': 'hexagon',
            'subdomain': 'rectangle',
            'system': 'component',
            'subsystem': 'component',
            'appFunction': 'rectangle',
            'dataEntity': 'document',
            'dataStore': 'cylinder',
            'infraNode': 'rectangle',
            'infraSoftware': 'cylinder',
            'infraZone': 'rectangle',
            'infraLocation': 'rectangle',
        })
        spec = generate_spec(cfg)
        # domain should use hexagon now
        domain_idx = spec.index('element domain')
        domain_block = spec[domain_idx:spec.index('}', spec.index('}', domain_idx) + 1) + 1]
        assert 'shape hexagon' in domain_block

    def test_custom_tags_from_config(self):
        cfg = MockConfig(spec_tags=['custom_tag', 'another_tag'])
        spec = generate_spec(cfg)
        assert 'tag custom_tag' in spec
        assert 'tag another_tag' in spec
        assert 'tag to_review' not in spec

    def test_config_none_uses_defaults(self):
        spec_default = generate_spec()
        spec_none = generate_spec(None)
        assert spec_default == spec_none


# ── generate_domain_c4 ──────────────────────────────────────────────────

class TestGenerateDomainC4:
    def test_basic_structure(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     metadata={'ci': 'CI-1', 'full_name': 'EFS'})
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert "channels = domain 'Channels'" in result
        assert "efs = system 'EFS'" in result
        assert 'model {' in result

    def test_system_metadata(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     metadata={'ci': 'CI-42'})
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert "archi_id 'sys-1'" in result
        assert "ci 'CI-42'" in result

    def test_system_tags(self):
        sys = System(c4_id='ext', name='ExtSvc', archi_id='sys-1',
                     tags=['external'], metadata={})
        result = generate_domain_c4('platform', 'Platform', [sys])
        assert '#external' in result

    def test_systems_sorted_by_name(self):
        sys1 = System(c4_id='zebra', name='Zebra', archi_id='s1', metadata={})
        sys2 = System(c4_id='alpha', name='Alpha', archi_id='s2', metadata={})
        result = generate_domain_c4('d', 'D', [sys1, sys2])
        idx_alpha = result.index('Alpha')
        idx_zebra = result.index('Zebra')
        assert idx_alpha < idx_zebra

    def test_domain_file_contains_subdomain_block(self):
        sd = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                       system_ids=['efs'])
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     subdomain='payments')
        result = generate_domain_c4('channels', 'Channels', [sys], subdomains=[sd])
        assert "payments = subdomain 'Payments'" in result
        assert 'model {' in result

    def test_system_nested_in_subdomain(self):
        sd = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                       system_ids=['efs'])
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     subdomain='payments')
        result = generate_domain_c4('channels', 'Channels', [sys], subdomains=[sd])
        # system block should come after subdomain opening
        idx_sd = result.index("payments = subdomain")
        idx_sys = result.index("efs = system")
        assert idx_sd < idx_sys

    def test_system_without_subdomain_at_domain_root(self):
        sd = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                       system_ids=['efs'])
        sys_in_sd = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                           subdomain='payments')
        sys_no_sd = System(c4_id='crm', name='CRM', archi_id='s2', metadata={},
                           subdomain='')
        result = generate_domain_c4('channels', 'Channels', [sys_in_sd, sys_no_sd],
                                    subdomains=[sd])
        # CRM should be present and not inside subdomain block
        assert "crm = system 'CRM'" in result
        # EFS inside subdomain
        assert "payments = subdomain" in result
        idx_sd_close = result.index('    }')
        idx_crm = result.index("crm = system")
        # CRM rendered after subdomain block closes
        assert idx_crm > idx_sd_close

    def test_system_with_documentation(self):
        # Covers _render_system documentation branch (lines 23-26)
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     documentation='An enterprise file system')
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert "description 'An enterprise file system'" in result

    def test_system_long_documentation_truncated(self):
        # Covers _render_system documentation truncation (lines 24-25)
        long_doc = 'z' * 600
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     documentation=long_doc)
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert '...' in result

    def test_system_with_links(self):
        # Covers _render_system links (line 28)
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     links=[('https://docs.example.com', 'Docs')])
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert 'https://docs.example.com' in result

    def test_system_with_api_interfaces(self):
        # Covers _render_system api_interfaces (lines 34-35)
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     api_interfaces=['REST', 'gRPC'])
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert 'api_interfaces' in result
        assert 'REST' in result

    def test_subdomain_with_no_systems_skipped(self):
        # Covers line 80: subdomain skipped when it has no systems assigned
        sd_empty = Subdomain(c4_id='empty_sd', name='EmptySD', domain_id='channels',
                             system_ids=[])
        sd_full = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                            system_ids=['efs'])
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     subdomain='payments')
        result = generate_domain_c4('channels', 'Channels', [sys],
                                    subdomains=[sd_empty, sd_full])
        assert 'empty_sd' not in result
        assert 'payments' in result


# ── generate_system_detail_c4 ───────────────────────────────────────────

class TestGenerateSystemDetailC4:
    def test_extend_block(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert 'extend channels.efs {' in result
        assert "core = subsystem 'EFS.Core'" in result

    def test_detail_view(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[], functions=[], metadata={})
        # Need at least something to generate
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff')
        sys.functions.append(fn)
        result = generate_system_detail_c4('channels', sys)
        assert 'view efs_detail of channels.efs' in result
        assert "title 'EFS'" in result
        assert 'include *' in result

    def test_appfunctions_rendered(self):
        fn = AppFunction(archi_id='fn-1', name='CreateAccount', c4_id='create_account',
                         documentation='Creates a new account')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     functions=[fn], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert "create_account = appFunction 'CreateAccount'" in result
        assert "description 'Creates a new account'" in result

    def test_extend_path_includes_subdomain(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={}, subdomain='payments')
        result = generate_system_detail_c4('channels', sys)
        assert 'extend channels.payments.efs {' in result
        assert 'view efs_detail of channels.payments.efs' in result

    def test_extend_path_without_subdomain(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={}, subdomain='')
        result = generate_system_detail_c4('channels', sys)
        assert 'extend channels.efs {' in result
        assert 'view efs_detail of channels.efs' in result

    def test_appfunction_long_doc_truncated(self):
        # Covers _render_appfunction truncation branch (line 18)
        long_doc = 'x' * 400
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff',
                         documentation=long_doc)
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     functions=[fn], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert '...' in result

    def test_subsystem_with_tags_and_doc(self):
        # Covers _render_subsystem tag (line 38) and documentation (lines 40-43)
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        tags=['internal'], documentation='A core subsystem',
                        metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert '#internal' in result
        assert "description 'A core subsystem'" in result

    def test_subsystem_long_doc_truncated(self):
        # Covers _render_subsystem truncation branch (lines 41-42)
        long_doc = 'y' * 600
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        documentation=long_doc, metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert '...' in result

    def test_subsystem_with_links(self):
        # Covers _render_subsystem links (line 45)
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        links=[('https://wiki.example.com', 'Wiki')], metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert 'https://wiki.example.com' in result

    def test_subsystem_with_metadata_items(self):
        # Covers _render_subsystem metadata loop (line 49)
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        metadata={'ci': 'CI-10', 'team': 'platform'})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert "ci 'CI-10'" in result

    def test_subsystem_with_nested_appfunctions(self):
        # Covers _render_subsystem functions block (lines 53-55)
        fn = AppFunction(archi_id='fn-1', name='DoWork', c4_id='do_work')
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        functions=[fn], metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert "do_work = appFunction 'DoWork'" in result


# ── generate_relationships ───────────────────────────────────────────────

class TestGenerateRelationships:
    def test_empty(self):
        result = generate_relationships([])
        assert '// No integrations found' in result

    def test_with_integrations(self):
        intg = Integration(source_path='channels.efs', target_path='products.abs',
                           name='Payment flow', rel_type='')
        result = generate_relationships([intg])
        assert "channels.efs -> products.abs 'Payment flow'" in result

    def test_unnamed_integration(self):
        intg = Integration(source_path='channels.efs', target_path='products.abs',
                           name='', rel_type='')
        result = generate_relationships([intg])
        assert 'channels.efs -> products.abs' in result
        assert "'" not in result.split('products.abs')[1].split('\n')[0]


# ── generate_entities ────────────────────────────────────────────────────

class TestGenerateEntities:
    def test_empty(self):
        result = generate_entities([], [])
        assert '// No data entities found' in result

    def test_with_entity(self):
        entity = DataEntity(c4_id='de_account', name='Account',
                            archi_id='do-1', documentation='Customer account')
        result = generate_entities([entity], [])
        assert "de_account = dataEntity 'Account'" in result
        assert '#entity' in result
        assert "description 'Customer account'" in result

    def test_with_data_access(self):
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        da = DataAccess(system_path='channels.efs', entity_id='de_account', name='reads')
        result = generate_entities([entity], [da])
        assert "channels.efs -> de_account 'reads'" in result


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
        archi_to_c4 = {'a1': 'dom.sys1', 'e1': 'entities.ent1'}
        c4_paths, entity_paths, unresolved, total = _resolve_elements(
            ['a1', 'e1'], archi_to_c4, None, None, {'e1'}, 'functional',
        )
        assert c4_paths == ['dom.sys1']
        assert entity_paths == []
        assert unresolved == 0
        assert total == 1

    def test_integration_separates_entities(self):
        archi_to_c4 = {'a1': 'dom.sys1', 'e1': 'entities.ent1'}
        c4_paths, entity_paths, unresolved, total = _resolve_elements(
            ['a1', 'e1'], archi_to_c4, None, None, {'e1'}, 'integration',
        )
        assert c4_paths == ['dom.sys1']
        assert entity_paths == ['entities.ent1']
        assert unresolved == 0
        assert total == 1

    def test_deployment_prefers_tech_map(self):
        archi_to_c4 = {'a1': 'dom.sys1'}
        tech_map = {'a1': 'infra.node1'}
        c4_paths, entity_paths, unresolved, total = _resolve_elements(
            ['a1'], archi_to_c4, None, tech_map, set(), 'deployment',
        )
        assert c4_paths == ['infra.node1']
        assert total == 1

    def test_deployment_falls_back_to_archi(self):
        archi_to_c4 = {'a1': 'dom.sys1'}
        c4_paths, _, unresolved, _ = _resolve_elements(
            ['a1'], archi_to_c4, None, {}, set(), 'deployment',
        )
        assert c4_paths == ['dom.sys1']
        assert unresolved == 0

    def test_promoted_fanout(self):
        promoted = {'parent1': ['dom.child1', 'dom.child2']}
        c4_paths, _, unresolved, total = _resolve_elements(
            ['parent1'], {}, promoted, None, set(), 'functional',
        )
        assert c4_paths == ['dom.child1', 'dom.child2']
        assert unresolved == 0
        assert total == 1

    def test_unresolved_counted(self):
        c4_paths, _, unresolved, total = _resolve_elements(
            ['unknown1', 'unknown2'], {}, None, None, set(), 'functional',
        )
        assert c4_paths == []
        assert unresolved == 2
        assert total == 2

    def test_deployment_skips_entities(self):
        archi_to_c4 = {'e1': 'entities.ent1'}
        c4_paths, entity_paths, unresolved, total = _resolve_elements(
            ['e1'], archi_to_c4, None, None, {'e1'}, 'deployment',
        )
        assert c4_paths == []
        assert entity_paths == []
        assert total == 0

    def test_integration_unresolved_entity_not_counted(self):
        """Entities that can't be resolved are silently dropped, not counted as unresolved."""
        c4_paths, entity_paths, unresolved, total = _resolve_elements(
            ['e_unknown'], {}, None, None, {'e_unknown'}, 'integration',
        )
        assert entity_paths == []
        assert unresolved == 0
        assert total == 0


# ── _generate_deployment_view ────────────────────────────────────────────

class TestGenerateDeploymentView:
    def test_basic_infra_paths(self):
        """Infra paths are emitted with env prefix and .** suffix."""
        lines = _generate_deployment_view(
            view_id='deployment_myapp',
            title='Deployment Architecture: MyApp',
            c4_paths=['loc.cluster.node1'],
            deploy_targets={},
            tech_archi_to_c4={'infra-1': 'loc.cluster.node1'},
            deployment_env='prod',
        )
        content = '\n'.join(lines)
        assert 'deployment view deployment_myapp' in content
        assert 'prod.loc.cluster.node1.**' in content

    def test_empty_paths_returns_empty(self):
        """No c4_paths → no lines."""
        lines = _generate_deployment_view(
            view_id='deployment_empty',
            title='Empty',
            c4_paths=[],
            deploy_targets={},
            tech_archi_to_c4=None,
            deployment_env='prod',
        )
        assert lines == []

    def test_app_only_no_infra_returns_empty(self):
        """App paths without infra mapping → no lines (app paths excluded from deployment views)."""
        lines = _generate_deployment_view(
            view_id='deployment_apponly',
            title='App Only',
            c4_paths=['channels.efs'],
            deploy_targets={},
            tech_archi_to_c4={'infra-1': 'loc.cluster.node1'},
            deployment_env='prod',
        )
        assert lines == []

    def test_enrichment_from_deploy_targets(self):
        """Infra paths enriched from deploy_targets for app paths."""
        lines = _generate_deployment_view(
            view_id='deployment_enrich',
            title='Enriched',
            c4_paths=['channels.efs'],
            deploy_targets={'channels.efs': {'loc.server1'}},
            tech_archi_to_c4={},
            deployment_env='prod',
        )
        content = '\n'.join(lines)
        assert 'prod.loc.server1.**' in content

    def test_prefix_match_enrichment(self):
        """Subsystem deploy mappings picked up via prefix match on system path."""
        lines = _generate_deployment_view(
            view_id='deployment_prefix',
            title='Prefix',
            c4_paths=['channels.efs'],
            deploy_targets={'channels.efs.subsys': {'loc.node2'}},
            tech_archi_to_c4={},
            deployment_env='staging',
        )
        content = '\n'.join(lines)
        assert 'staging.loc.node2.**' in content

    def test_ancestor_dedup(self):
        """Ancestor dedup: 'loc' subsumes 'loc.cluster.node1'."""
        lines = _generate_deployment_view(
            view_id='deployment_dedup',
            title='Dedup',
            c4_paths=['loc', 'loc.cluster.node1'],
            deploy_targets={},
            tech_archi_to_c4={'i1': 'loc', 'i2': 'loc.cluster.node1'},
            deployment_env='prod',
        )
        content = '\n'.join(lines)
        assert 'prod.loc.**' in content
        assert 'prod.loc.cluster.node1.**' not in content

    def test_qa11_warning(self, caplog):
        """QA-11 warning emitted when element count exceeds threshold."""
        import logging
        many_infra = [f'loc.node{i}' for i in range(45)]
        tech_map = {f'i{i}': f'loc.node{i}' for i in range(45)}
        with caplog.at_level(logging.WARNING):
            lines = _generate_deployment_view(
                view_id='deployment_big',
                title='Big',
                c4_paths=many_infra,
                deploy_targets={},
                tech_archi_to_c4=tech_map,
                deployment_env='prod',
                max_deployment=40,
            )
        assert lines  # should produce output
        assert 'QA-11' in caplog.text

    def test_no_trailing_comma(self):
        """Last include line should not have trailing comma."""
        lines = _generate_deployment_view(
            view_id='deployment_comma',
            title='Comma',
            c4_paths=['loc.node1', 'loc.node2'],
            deploy_targets={},
            tech_archi_to_c4={'i1': 'loc.node1', 'i2': 'loc.node2'},
            deployment_env='prod',
        )
        include_lines = [ln for ln in lines if ln.strip().startswith('prod.')]
        assert not include_lines[-1].endswith(',')


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
        files, unresolved, total = generate_solution_views([sv], archi_to_c4, {'efs': 'channels'})
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels', 'abs': 'products'}, rels)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels', 'abs': 'products'}, rels)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels', 'abs': 'products'}, [])
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, {'efs_card': 'channels', 'efs_loan': 'channels', 'abs': 'products'},
            rels, promoted_archi_to_c4)
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
        files, unresolved, total = generate_solution_views([sv], {}, {})
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, {}, entity_archi_ids=entity_archi_ids)
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
        _, unresolved, total = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels'}, entity_archi_ids=entity_archi_ids)
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
        _, unresolved, total = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels'}, entity_archi_ids=entity_archi_ids)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels'},
            deployment_map=deploy_map)
        assert 'app_only' in files
        content = files['app_only']
        # App path is NOT included directly — it lives inside node via instanceOf
        assert 'channels.efs' not in content
        # Infra path appears with prod. prefix and .** suffix
        assert 'prod.server_1.**' in content
        assert 'deployment view' in content


# ── Deployment generators ───────────────────────────────────────────────

class TestGenerateSpec_InfraKinds:
    def test_spec_includes_infra_node(self):
        spec = generate_spec()
        assert 'deploymentNode infraNode' in spec
        assert 'deploymentNode infraZone' in spec
        assert 'deploymentNode infraSoftware' in spec
        assert 'deploymentNode infraLocation' in spec
        assert 'archi-tech' in spec

    def test_spec_infra_zone_style(self):
        spec = generate_spec()
        # infraZone should have dotted border
        zone_idx = spec.index('deploymentNode infraZone')
        zone_block = spec[zone_idx:spec.index('}', spec.index('}', zone_idx) + 1) + 1]
        assert 'border dotted' in zone_block

    def test_spec_no_deployed_on(self):
        spec = generate_spec()
        assert 'relationship deployedOn' not in spec

    def test_spec_includes_infra_tags(self):
        spec = generate_spec()
        assert 'tag infrastructure' in spec
        assert 'tag cluster' in spec


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


class TestGenerateDeploymentOverviewView:
    def test_view_content(self):
        content = generate_deployment_overview_view()
        assert 'deployment view deployment_architecture' in content
        assert 'prod.**' in content

    def test_custom_env(self):
        content = generate_deployment_overview_view(env='staging')
        assert 'staging.**' in content


class TestGenerateDatastoreMapping:
    def test_generates_persists_relationships(self):
        links = [('srv.pg', 'de_users'), ('srv.pg', 'de_orders')]
        content = generate_datastore_mapping_c4(links)
        assert 'persists' in content
        assert 'srv.pg -[persists]-> de_users' in content
        assert 'srv.pg -[persists]-> de_orders' in content

    def test_empty_links(self):
        content = generate_datastore_mapping_c4([])
        assert 'persists' not in content


# ── generate_audit_md ───────────────────────────────────────────────────


class TestGenerateAuditMd:
    def test_summary_present(self):
        built = MockBuilt(systems=[
            System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels'),
        ])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '## Сводка' in result
        assert '| Систем | 1 |' in result

    def test_unassigned_listed(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        s2 = System(c4_id='efs', name='EFS', archi_id='s2', metadata={}, domain='channels')
        built = MockBuilt(
            systems=[s1, s2],
            domain_systems={'unassigned': [s1], 'channels': [s2]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[Critical] Системы без домена (1)' in result
        assert '| 1 | AD |' in result

    def test_metadata_completeness(self):
        meta_full = {k: 'filled' for k in [
            'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        meta_empty = {k: 'TBD' for k in meta_full}
        s_good = System(c4_id='a', name='A', archi_id='s1', metadata=dict(meta_full), domain='d')
        s_bad = System(c4_id='b', name='B', archi_id='s2', metadata=dict(meta_empty), domain='d')
        built = MockBuilt(systems=[s_good, s_bad])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[High] Незаполненные карточки' in result
        assert '| 1 | B |' in result

    def test_to_review_listed(self):
        s = System(c4_id='x', name='ReviewMe', archi_id='s1', metadata={},
                   tags=['to_review'], domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[High] Системы на разборе (1)' in result
        assert 'ReviewMe' in result

    def test_promote_candidates(self):
        subs = [Subsystem(c4_id=f'sub{i}', name=f'S{i}', archi_id=f'sub-{i}', metadata={})
                for i in range(12)]
        s = System(c4_id='big', name='BigParent', archi_id='s1',
                   metadata={}, subsystems=subs, domain='d')
        built = MockBuilt(systems=[s])
        result = generate_audit_md(built, 0, 0, MockConfig(promote_warn_threshold=10))
        assert '[Medium] Кандидаты на декомпозицию (1)' in result
        assert 'BigParent' in result
        assert '| 1 | BigParent | 12 |' in result

    def test_section_omitted_when_zero(self):
        meta = {k: 'filled' for k in [
            'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        s = System(c4_id='a', name='A', archi_id='s1', metadata=dict(meta),
                   domain='d', documentation='Has docs')
        built = MockBuilt(systems=[s], domain_systems={'d': [s]})
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Системы без домена' not in result
        assert 'Системы на разборе' not in result
        assert 'Осиротевшие функции' not in result

    def test_no_infra_mapping(self):
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = MockBuilt(systems=[s], deployment_map=[])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[Medium] Системы без инфраструктурной привязки' in result
        assert 'EFS' in result

    def test_orphan_fns_shown(self):
        from archi2likec4.builders._result import BuildDiagnostics
        built = MockBuilt(diagnostics=BuildDiagnostics(orphan_fns=3, intg_skipped=0, intg_total_eligible=0))
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[Low] Осиротевшие функции (3)' in result

    def test_solution_view_coverage(self):
        built = MockBuilt()
        result = generate_audit_md(built, 100, 500, MockConfig())
        assert 'Покрытие solution views' in result
        assert '100' in result

    def test_suppress_excludes_from_unassigned(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        s2 = System(c4_id='legacy', name='Legacy', archi_id='s2', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s1, s2],
            domain_systems={'unassigned': [s1, s2]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig(audit_suppress=['Legacy']))
        assert '[Critical] Системы без домена (1)' in result
        assert 'AD' in result
        assert 'Legacy' not in result.split('Сводка')[1]  # not in incident tables

    def test_suppress_hides_section_when_all_suppressed(self):
        s = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig(audit_suppress=['AD']))
        assert 'Системы без домена' not in result

    def test_suppress_footer_count(self):
        s = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig(audit_suppress=['AD']))
        assert 'audit_suppress' in result
        assert '1' in result

    def test_qa10_floating_software(self):
        sw = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                            tech_type='SystemSoftware', kind='infraSoftware')
        built = MockBuilt(deployment_nodes=[sw])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Проблемы иерархии развёртывания' in result
        assert 'PostgreSQL' in result
        assert 'root' in result.lower()

    def test_qa10_clean_hierarchy(self):
        """No QA-10 when all nodes are properly nested."""
        child = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                               tech_type='Node', kind='infraNode')
        parent = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                                tech_type='Location', kind='infraLocation',
                                children=[child])
        built = MockBuilt(deployment_nodes=[parent])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Проблемы иерархии развёртывания' not in result

    def test_qa10_infra_zone_root_without_location(self):
        """QA-10 should flag root infraZone not under infraLocation."""
        loc = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                             tech_type='Location', kind='infraLocation',
                             children=[])
        zone = DeploymentNode(c4_id='lan', name='LAN', archi_id='cn-1',
                              tech_type='CommunicationNetwork', kind='infraZone')
        built = MockBuilt(deployment_nodes=[loc, zone])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Проблемы иерархии развёртывания' in result
        assert 'LAN' in result

    def test_qa10_infra_zone_under_location_ok(self):
        """QA-10 should NOT flag infraZone nested under infraLocation."""
        zone = DeploymentNode(c4_id='lan', name='LAN', archi_id='cn-1',
                              tech_type='CommunicationNetwork', kind='infraZone')
        loc = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                             tech_type='Location', kind='infraLocation',
                             children=[zone])
        built = MockBuilt(deployment_nodes=[loc])
        result = generate_audit_md(built, 0, 0, MockConfig())
        # LAN is nested under DC, should not be flagged — no QA-10 section at all
        assert 'Проблемы иерархии развёртывания' not in result


    def test_stable_qa_ids(self):
        """QA IDs in AUDIT.md use inc.qa_id, not sequential numbering."""
        s = System(c4_id='x', name='ReviewMe', archi_id='s1', metadata={},
                   tags=['to_review'], domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        # QA-1 (unassigned) and QA-3 (to_review) should use actual QA IDs
        assert '## QA-1.' in result
        assert '## QA-3.' in result
        # Should NOT have QA-2 as second section (sequential numbering would)
        assert '## QA-2. [High] Системы на разборе' not in result

    def test_suppress_incident_qa_note(self):
        """When QA category suppressed, AUDIT.md footer mentions suppressed QA-IDs."""
        s = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0,
                                   MockConfig(audit_suppress_incidents=['QA-1']))
        assert 'Системы без домена' not in result
        assert 'QA-1' in result  # mentioned in suppressed note

    def test_qa9_subsystem_mapping_not_false_positive(self):
        """QA-9 should not flag system when subsystem has deployment mapping."""
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels',
                   subsystems=[Subsystem(c4_id='core', name='EFS.Core', archi_id='sub1', metadata={})])
        # Mapping is on subsystem level: channels.efs.core → server
        built = MockBuilt(
            systems=[s],
            deployment_map=[('channels.efs.core', 'server1')],
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Системы без инфраструктурной привязки' not in result


class TestSolutionViewDeployment:
    def test_deployment_view_with_tech_map(self):
        sv = SolutionView(
            name='deployment_architecture.PaymentSvc',
            view_type='deployment',
            solution='payment_svc',
            element_archi_ids=['n-1', 'sw-1'],
        )
        tech_archi_to_c4 = {'n-1': 'server_1', 'sw-1': 'server_1.pg'}
        files, unresolved, total = generate_solution_views(
            [sv], {}, {}, tech_archi_to_c4=tech_archi_to_c4)
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
        files, unresolved, total = generate_solution_views(
            [sv], archi_to_c4, {'efs': 'channels', 'abs': 'products'},
            deployment_map=deploy_map)
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
        files, _, _ = generate_solution_views(
            [sv], {}, {}, tech_archi_to_c4=tech_archi_to_c4)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, rels,
            sys_subdomain=sys_subdomain)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, rels,
            sys_subdomain=sys_subdomain)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
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
        files, _, _ = generate_solution_views(
            [sv], archi_to_c4, sys_domain, sys_subdomain=sys_subdomain)
        content = files['channels']
        # sys_subdomain is authoritative: core is in subdomain efs, so path is channels.efs.core
        assert 'of channels.efs.core' in content


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
