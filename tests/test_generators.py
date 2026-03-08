"""Tests for archi2likec4.generators — .c4 file content generation."""

import pytest

from archi2likec4.models import (
    AppFunction,
    DataAccess,
    DataEntity,
    DeploymentNode,
    Integration,
    RawRelationship,
    SolutionView,
    Subsystem,
    System,
)
from archi2likec4.generators import (
    generate_deployment_c4,
    generate_deployment_mapping_c4,
    generate_deployment_view,
    generate_domain_c4,
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_entities,
    generate_landscape_view,
    generate_persistence_map,
    generate_relationships,
    generate_spec,
    generate_system_detail_c4,
    generate_solution_views,
)


# ── generate_spec ────────────────────────────────────────────────────────

class TestGenerateSpec:
    def test_contains_kinds(self):
        spec = generate_spec()
        assert 'element domain' in spec
        assert 'element system' in spec
        assert 'element subsystem' in spec
        assert 'element appFunction' in spec
        assert 'element dataEntity' in spec

    def test_contains_tags(self):
        spec = generate_spec()
        assert 'tag to_review' in spec
        assert 'tag external' in spec

    def test_contains_colors(self):
        spec = generate_spec()
        assert 'color archi-app' in spec


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


# ── Deployment generators ───────────────────────────────────────────────

class TestGenerateSpec_InfraKinds:
    def test_spec_includes_infra_node(self):
        spec = generate_spec()
        assert 'element infraNode' in spec
        assert 'element infraSoftware' in spec
        assert 'archi-tech' in spec

    def test_spec_includes_deployed_on(self):
        spec = generate_spec()
        assert 'relationship deployedOn' in spec

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
        assert 'model {' in content

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
        parent_line = next(l for l in lines if 'srv_1 = infraNode' in l)
        child_line = next(l for l in lines if 'pg = infraSoftware' in l)
        assert len(child_line) - len(child_line.lstrip()) > len(parent_line) - len(parent_line.lstrip())


class TestGenerateDeploymentMapping:
    def test_mapping(self):
        mapping = [('channels.efs', 'server_1'), ('products.mls', 'db_cluster')]
        content = generate_deployment_mapping_c4(mapping)
        assert 'channels.efs -[deployedOn]-> server_1' in content
        assert 'products.mls -[deployedOn]-> db_cluster' in content
        assert 'model {' in content


class TestGenerateDeploymentView:
    def test_view_content(self):
        content = generate_deployment_view()
        assert 'view deployment_architecture' in content
        assert 'infraNode' in content
        assert 'infraSoftware' in content
