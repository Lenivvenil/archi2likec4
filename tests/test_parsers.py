"""Tests for archi2likec4.parsers — XML parsing from coArchi model.

Uses temporary directories with minimal XML files to test parser logic
without depending on the real architectural_repository.
"""

from pathlib import Path

import pytest

from archi2likec4.parsers import (
    _detect_special_folder,
    _extract_ref_id,
    _find_parent_component,
    _is_in_trash,
    parse_application_components,
    parse_application_functions,
    parse_application_interfaces,
    parse_data_objects,
    parse_domain_mapping,
    parse_location_elements,
    parse_relationships,
    parse_solution_views,
    parse_subdomains,
    parse_technology_elements,
)

# Namespace used in coArchi XML (must be declared for valid XML)
_NS_DECL = 'xmlns:archimate="http://www.archimatetool.com/archimate"'
_XSI_DECL = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'


# ── Helpers ──────────────────────────────────────────────────────────────

def _write_component(path: Path, archi_id: str, name: str, **extra_attrs):
    """Write an ApplicationComponent XML file."""
    attrs = f'id="{archi_id}" name="{name}"'
    for k, v in extra_attrs.items():
        attrs += f' {k}="{v}"'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<element {attrs}/>', encoding='utf-8')


def _write_folder_xml(folder: Path, name: str):
    """Write a folder.xml with given name."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'folder.xml').write_text(
        f'<folder name="{name}"/>', encoding='utf-8'
    )


# ── _extract_ref_id ─────────────────────────────────────────────────────

class TestExtractRefId:
    def test_with_hash(self):
        assert _extract_ref_id('file.xml#id-abc-123') == 'id-abc-123'

    def test_without_hash(self):
        assert _extract_ref_id('no-hash-here') == ''

    def test_empty(self):
        assert _extract_ref_id('') == ''


# ── _is_in_trash ─────────────────────────────────────────────────────────

class TestIsInTrash:
    def test_not_in_trash(self, tmp_path):
        base = tmp_path / 'application'
        base.mkdir()
        xml = base / 'SomeFile.xml'
        xml.touch()
        assert _is_in_trash(xml, base) is False

    def test_in_trash_folder(self, tmp_path):
        base = tmp_path / 'application'
        trash = base / 'subfolder'
        _write_folder_xml(trash, 'Trash')
        xml = trash / 'SomeFile.xml'
        xml.touch()
        assert _is_in_trash(xml, base) is True

    def test_in_nested_trash(self, tmp_path):
        base = tmp_path / 'application'
        trash = base / 'sub1'
        _write_folder_xml(trash, 'Trash')
        deep = trash / 'sub2'
        deep.mkdir()
        xml = deep / 'SomeFile.xml'
        xml.touch()
        assert _is_in_trash(xml, base) is True


# ── parse_application_components ─────────────────────────────────────────

class TestParseApplicationComponents:
    def test_basic(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'ApplicationComponent_abc.xml',
            archi_id='id-abc', name='TestSystem',
        )
        result = parse_application_components(tmp_path)
        assert len(result) == 1
        assert result[0].archi_id == 'id-abc'
        assert result[0].name == 'TestSystem'

    def test_skips_unnamed(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'ApplicationComponent_abc.xml',
            archi_id='id-abc', name='',
        )
        result = parse_application_components(tmp_path)
        assert len(result) == 0

    def test_skips_trash(self, tmp_path):
        app_dir = tmp_path / 'application'
        trash = app_dir / 'old_stuff'
        _write_folder_xml(trash, 'Trash')
        _write_component(
            trash / 'ApplicationComponent_abc.xml',
            archi_id='id-abc', name='DeletedSystem',
        )
        result = parse_application_components(tmp_path)
        assert len(result) == 0

    def test_properties_parsed(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        xml_path = app_dir / 'ApplicationComponent_abc.xml'
        xml_path.write_text(
            '<element id="id-abc" name="TestSys">'
            '<properties key="CI" value="CI-42"/>'
            '<properties key="Full name" value="Test System"/>'
            '</element>',
            encoding='utf-8',
        )
        result = parse_application_components(tmp_path)
        assert result[0].properties['CI'] == 'CI-42'
        assert result[0].properties['Full name'] == 'Test System'

    def test_no_application_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_application_components(tmp_path)


# ── parse_application_interfaces ─────────────────────────────────────────

class TestParseApplicationInterfaces:
    def test_basic(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'ApplicationInterface_xyz.xml',
            archi_id='iface-1', name='EFS.API',
            documentation='http://api.efs.com',
        )
        result = parse_application_interfaces(tmp_path)
        assert len(result) == 1
        assert result[0].name == 'EFS.API'
        assert result[0].documentation == 'http://api.efs.com'


# ── parse_data_objects ───────────────────────────────────────────────────

class TestParseDataObjects:
    def test_basic(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'DataObject_do1.xml',
            archi_id='do-1', name='CustomerRecord',
        )
        result = parse_data_objects(tmp_path)
        assert len(result) == 1
        assert result[0].name == 'CustomerRecord'


# ── parse_application_functions ──────────────────────────────────────────

class TestParseApplicationFunctions:
    def test_basic(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'ApplicationFunction_fn1.xml',
            archi_id='fn-1', name='CreateAccount',
        )
        result = parse_application_functions(tmp_path)
        assert len(result) == 1
        assert result[0].name == 'CreateAccount'
        assert result[0].archi_id == 'fn-1'

    def test_parent_resolution(self, tmp_path):
        """Function nested under an ApplicationComponent folder gets parent."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'systems'
        sys_dir.mkdir(parents=True)
        _write_component(
            sys_dir / 'ApplicationComponent_sys1.xml',
            archi_id='sys-1', name='EFS',
        )
        _write_component(
            sys_dir / 'ApplicationFunction_fn1.xml',
            archi_id='fn-1', name='DoStuff',
        )
        result = parse_application_functions(tmp_path)
        assert len(result) == 1
        assert result[0].parent_archi_id == 'sys-1'


# ── parse_relationships ──────────────────────────────────────────────────

def _write_relationship(path: Path, rel_type: str, rel_id: str, name: str,
                         source_id: str, source_type: str,
                         target_id: str, target_type: str):
    """Write a relationship XML file matching coArchi format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<element {_XSI_DECL} id="{rel_id}" name="{name}">'
        f'<source href="s.xml#{source_id}" xsi:type="{source_type}"/>'
        f'<target href="t.xml#{target_id}" xsi:type="{target_type}"/>'
        f'</element>',
        encoding='utf-8',
    )


class TestParseRelationships:
    def test_flow_relationship(self, tmp_path):
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'FlowRelationship_r1.xml',
            rel_type='FlowRelationship', rel_id='r-1', name='data flow',
            source_id='src-1', source_type='archimate:ApplicationComponent',
            target_id='tgt-1', target_type='archimate:ApplicationComponent',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].rel_type == 'FlowRelationship'
        assert result[0].source_id == 'src-1'
        assert result[0].target_id == 'tgt-1'

    def test_irrelevant_type_skipped(self, tmp_path):
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'SpecializationRelationship_r1.xml',
            rel_type='SpecializationRelationship', rel_id='r-1', name='',
            source_id='src-1', source_type='archimate:ApplicationComponent',
            target_id='tgt-1', target_type='archimate:ApplicationComponent',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 0

    def test_no_relations_dir(self, tmp_path):
        result = parse_relationships(tmp_path)
        assert result == []

    def test_triggering_relationship_included(self, tmp_path):
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'TriggeringRelationship_r1.xml',
            rel_type='TriggeringRelationship', rel_id='r-1', name='trigger',
            source_id='src-1', source_type='archimate:ApplicationComponent',
            target_id='tgt-1', target_type='archimate:ApplicationComponent',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].rel_type == 'TriggeringRelationship'


# ── parse_technology_elements ────────────────────────────────────────────

def _write_tech_element(path: Path, tag: str, archi_id: str, name: str,
                        documentation: str = ''):
    """Write a Technology layer XML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc_attr = f' documentation="{documentation}"' if documentation else ''
    path.write_text(
        f'<archimate:{tag} xmlns:archimate="http://www.archimatetool.com/archimate"'
        f' name="{name}" id="{archi_id}"{doc_attr}/>',
        encoding='utf-8',
    )


class TestParseTechnologyElements:
    def test_parse_node(self, tmp_path):
        tech_dir = tmp_path / 'technology' / 'sub'
        _write_tech_element(
            tech_dir / 'Node_n1.xml',
            tag='Node', archi_id='n-1', name='Server 1',
            documentation='vCPU: 8',
        )
        result = parse_technology_elements(tmp_path)
        assert len(result) == 1
        assert result[0].archi_id == 'n-1'
        assert result[0].name == 'Server 1'
        assert result[0].tech_type == 'Node'
        assert result[0].documentation == 'vCPU: 8'

    def test_parse_system_software(self, tmp_path):
        tech_dir = tmp_path / 'technology' / 'sub'
        _write_tech_element(
            tech_dir / 'SystemSoftware_sw1.xml',
            tag='SystemSoftware', archi_id='sw-1', name='PostgreSQL',
        )
        result = parse_technology_elements(tmp_path)
        assert len(result) == 1
        assert result[0].tech_type == 'SystemSoftware'

    def test_empty_tech_dir(self, tmp_path):
        """Missing technology/ dir → empty list, no error."""
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_folder_xml_skipped(self, tmp_path):
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'folder.xml').write_text('<folder name="tech"/>')
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_multiple_types(self, tmp_path):
        tech_dir = tmp_path / 'technology' / 'sub'
        _write_tech_element(tech_dir / 'Node_n1.xml', 'Node', 'n-1', 'Srv1')
        _write_tech_element(tech_dir / 'Device_d1.xml', 'Device', 'd-1', 'IBM Power')
        _write_tech_element(tech_dir / 'Artifact_a1.xml', 'Artifact', 'a-1', 'app.war')
        result = parse_technology_elements(tmp_path)
        assert len(result) == 3
        types = {r.tech_type for r in result}
        assert types == {'Node', 'Device', 'Artifact'}


class TestRelationshipsExpanded:
    def test_aggregation_relationship_captured(self, tmp_path):
        """AggregationRelationship is now in relevant_types."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'AggregationRelationship_r1.xml',
            rel_type='AggregationRelationship', rel_id='r-1', name='contains',
            source_id='n-1', source_type='archimate:Node',
            target_id='sw-1', target_type='archimate:SystemSoftware',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].rel_type == 'AggregationRelationship'
        assert result[0].source_type == 'Node'
        assert result[0].target_type == 'SystemSoftware'

    def test_cross_layer_realization_captured(self, tmp_path):
        """RealizationRelationship Node→ApplicationComponent is now captured."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'RealizationRelationship_r1.xml',
            rel_type='RealizationRelationship', rel_id='r-1', name='',
            source_id='n-1', source_type='archimate:Node',
            target_id='ac-1', target_type='archimate:ApplicationComponent',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].source_type == 'Node'
        assert result[0].target_type == 'ApplicationComponent'

    def test_irrelevant_element_type_still_skipped(self, tmp_path):
        """BusinessService endpoints are still filtered out."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'FlowRelationship_r1.xml',
            rel_type='FlowRelationship', rel_id='r-1', name='',
            source_id='bs-1', source_type='archimate:BusinessService',
            target_id='ac-1', target_type='archimate:ApplicationComponent',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 0

    def test_application_service_realization_captured(self, tmp_path):
        """RealizationRelationship ApplicationService→Node should be parsed."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'RealizationRelationship_r1.xml',
            rel_type='RealizationRelationship', rel_id='r-1', name='',
            source_id='as-1', source_type='archimate:ApplicationService',
            target_id='n-1', target_type='archimate:Node',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].source_type == 'ApplicationService'
        assert result[0].target_type == 'Node'

    def test_location_aggregation_captured(self, tmp_path):
        """AggregationRelationship Location→Node should be parsed."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        _write_relationship(
            rel_dir / 'AggregationRelationship_r1.xml',
            rel_type='AggregationRelationship', rel_id='r-1', name='',
            source_id='loc-1', source_type='archimate:Location',
            target_id='n-1', target_type='archimate:Node',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].source_type == 'Location'


# ── parse_location_elements ─────────────────────────────────────────────

class TestParseLocationElements:
    def test_parse_location(self, tmp_path):
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        xml_path = other_dir / 'Location_loc1.xml'
        xml_path.write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Основной ЦОД" id="loc-1" documentation="HQ datacenter"/>',
            encoding='utf-8',
        )
        result = parse_location_elements(tmp_path)
        assert len(result) == 1
        assert result[0].name == 'Основной ЦОД'
        assert result[0].tech_type == 'Location'
        assert result[0].archi_id == 'loc-1'

    def test_no_other_dir(self, tmp_path):
        result = parse_location_elements(tmp_path)
        assert result == []


# ── parse_solution_views: deployment patterns ────────────────────────────

def _write_diagram(path, diagram_name, elements=None):
    """Write an ArchimateDiagramModel XML with given name and optional element refs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    el_xml = ''
    for eid in (elements or []):
        el_xml += (f'<child><archimateElement '
                   f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                   f'xsi:type="archimate:Node" href="x.xml#{eid}"/></child>')
    path.write_text(
        f'<archimate:ArchimateDiagramModel '
        f'xmlns:archimate="http://www.archimatetool.com/archimate" '
        f'name="{diagram_name}" id="v-1">{el_xml}'
        f'</archimate:ArchimateDiagramModel>',
        encoding='utf-8',
    )


class TestParseSolutionViewsDeployment:
    def test_english_deployment_pattern(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_d1.xml',
            'deployment_architecture.Payment_Service',
            elements=['n-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert result[0].view_type == 'deployment'
        assert result[0].solution == 'payment_service'

    def test_russian_deployment_pattern(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_d2.xml',
            'Схема развёртывания.Платёжный сервис',
            elements=['n-1'],
        )
        ru_patterns = [
            {'pattern': r'^Схема разв[её]ртывания[.\s]+(.+)$', 'view_type': 'deployment'},
        ]
        result = parse_solution_views(tmp_path, extra_view_patterns=ru_patterns)
        assert len(result) == 1
        assert result[0].view_type == 'deployment'


# ── _detect_special_folder ──────────────────────────────────────────────

class TestDetectSpecialFolder:
    def test_no_special_folder(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        xml = app_dir / 'ApplicationComponent_x.xml'
        xml.touch()
        assert _detect_special_folder(xml) == ''

    def test_special_folder_detected(self, tmp_path):
        app_dir = tmp_path / 'application'
        special = app_dir / 'review'
        _write_folder_xml(special, '!РАЗБОР')
        xml = special / 'ApplicationComponent_x.xml'
        xml.touch()
        assert _detect_special_folder(xml) == '!РАЗБОР'

    def test_nested_special_folder(self, tmp_path):
        app_dir = tmp_path / 'application'
        special = app_dir / 'ext'
        _write_folder_xml(special, '!External_services')
        nested = special / 'sub'
        nested.mkdir()
        xml = nested / 'ApplicationComponent_x.xml'
        xml.touch()
        assert _detect_special_folder(xml) == '!External_services'


# ── _find_parent_component ──────────────────────────────────────────────

class TestFindParentComponent:
    def test_finds_single_parent(self, tmp_path):
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'systems'
        sys_dir.mkdir(parents=True)
        _write_component(
            sys_dir / 'ApplicationComponent_sys1.xml',
            archi_id='sys-1', name='CRM',
        )
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == 'sys-1'

    def test_no_parent(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        fn_xml = app_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == ''

    def test_ambiguous_multiple_parents(self, tmp_path):
        """Multiple components in same dir without matching folder name → skip."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'systems'
        sys_dir.mkdir(parents=True)
        _write_component(sys_dir / 'ApplicationComponent_a.xml', 'id-a', 'A')
        _write_component(sys_dir / 'ApplicationComponent_b.xml', 'id-b', 'B')
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        # Ambiguous: 2 components, no folder name match → walks up, no parent
        assert _find_parent_component(fn_xml, app_dir) == ''


# ── parse_domain_mapping ────────────────────────────────────────────────

class TestParseDomainMapping:
    def test_basic_domain(self, tmp_path):
        """Domain mapping from functional_areas diagram."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa_folder'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        diagram_path = domain_dir / 'ArchimateDiagramModel_v1.xml'
        diagram_path.parent.mkdir(parents=True, exist_ok=True)
        diagram_path.write_text(
            f'<archimate:ArchimateDiagramModel {_NS_DECL} name="Channels view" id="v-1">'
            f'<child><archimateElement xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="archimate:ApplicationComponent" href="x.xml#sys-1"/></child>'
            f'</archimate:ArchimateDiagramModel>',
            encoding='utf-8',
        )
        result = parse_domain_mapping(tmp_path, domain_renames={})
        assert len(result) == 1
        assert result[0].name == 'Channels'
        assert 'sys-1' in result[0].archi_ids

    def test_no_diagrams_dir(self, tmp_path):
        result = parse_domain_mapping(tmp_path)
        assert result == []

    def test_no_functional_areas(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        other = diagrams / 'other'
        _write_folder_xml(other, 'other_views')
        result = parse_domain_mapping(tmp_path)
        assert result == []


# ── parse_solution_views: functional/integration ────────────────────────

class TestParseSolutionViewsFuncInteg:
    def test_functional_view(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.AutoRepay',
            elements=['sys-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert result[0].view_type == 'functional'
        assert result[0].solution == 'autorepay'

    def test_integration_view(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_i1.xml',
            'integration_architecture.PaymentFlow',
            elements=['sys-1', 'sys-2'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert result[0].view_type == 'integration'

    def test_typo_functional_pattern(self, tmp_path):
        """fucntional_architecture (common typo) should be matched."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'fucntional_architecture.SomeService',
            elements=['sys-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert result[0].view_type == 'functional'

    def test_trash_diagram_skipped(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams'
        trash = diagrams_dir / 'old'
        _write_folder_xml(trash, 'Trash')
        _write_diagram(
            trash / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.Deleted',
            elements=['sys-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 0

    def test_unrecognized_name_skipped(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'random_diagram_name',
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 0

    def test_func_integ_same_solution_share_slug(self, tmp_path):
        """functional_architecture.X and integration_architecture.X must get the same slug."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.Pay',
            elements=['sys-1'],
        )
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_i1.xml',
            'integration_architecture.Pay',
            elements=['sys-2'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 2
        slugs = {sv.solution for sv in result}
        assert slugs == {'pay'}, f'Expected both views to share slug "pay", got {slugs}'

    def test_genuine_slug_collision_disambiguated(self, tmp_path):
        """Different solution names that produce the same slug get disambiguated."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.A B',
            elements=['sys-1'],
        )
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f2.xml',
            'functional_architecture.A_B',
            elements=['sys-2'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 2
        slugs = {sv.solution for sv in result}
        assert len(slugs) == 2, f'Expected distinct slugs for different names, got {slugs}'


class TestParseSolutionViewsExtraPatterns:
    """extra_view_patterns parameter allows custom locale patterns."""

    def test_custom_pattern_matched(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_c1.xml',
            'Architecture fonctionnelle.Paiement',
            elements=['sys-1'],
        )
        custom = [{'pattern': r'^Architecture fonctionnelle\.(.+)$', 'view_type': 'functional'}]
        result = parse_solution_views(tmp_path, extra_view_patterns=custom)
        assert len(result) == 1
        assert result[0].view_type == 'functional'
        assert result[0].solution == 'paiement'

    def test_no_extra_patterns_skips_russian(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_r1.xml',
            'Функциональная архитектура.Платежи',
            elements=['sys-1'],
        )
        result = parse_solution_views(tmp_path, extra_view_patterns=[])
        assert len(result) == 0

    def test_none_extra_patterns_uses_defaults(self, tmp_path):
        """None means 'use built-in defaults' — Russian patterns are included."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_r1.xml',
            'Функциональная архитектура.Платежи',
            elements=['sys-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert result[0].view_type == 'functional'


# ── parse_subdomains ─────────────────────────────────────────────────────

def _write_diagram_with_components(path: Path, diagram_name: str, component_ids: list[str]):
    """Write an ArchimateDiagramModel XML with ApplicationComponent refs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    el_xml = ''
    for cid in component_ids:
        el_xml += (
            f'<child>'
            f'<archimateElement '
            f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="archimate:ApplicationComponent" href="x.xml#{cid}"/>'
            f'</child>'
        )
    path.write_text(
        f'<archimate:ArchimateDiagramModel '
        f'xmlns:archimate="http://www.archimatetool.com/archimate" '
        f'name="{diagram_name}" id="v-1">{el_xml}'
        f'</archimate:ArchimateDiagramModel>',
        encoding='utf-8',
    )


class TestParseSubdomains:
    def test_subdomain_folder_extraction(self, tmp_path):
        """Two subdomain folders under a domain each produce a ParsedSubdomain."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')

        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')

        # Subdomain 1: Retail
        retail_dir = domain_dir / 'retail_sub'
        _write_folder_xml(retail_dir, 'Retail')
        _write_diagram_with_components(
            retail_dir / 'ArchimateDiagramModel_r1.xml',
            'Retail view',
            component_ids=['sys-retail-1', 'sys-retail-2'],
        )

        # Subdomain 2: Corporate
        corp_dir = domain_dir / 'corp_sub'
        _write_folder_xml(corp_dir, 'Corporate')
        _write_diagram_with_components(
            corp_dir / 'ArchimateDiagramModel_c1.xml',
            'Corporate view',
            component_ids=['sys-corp-1'],
        )

        result = parse_subdomains(tmp_path, domain_renames={})

        assert len(result) == 2
        names = {sd.name for sd in result}
        assert names == {'Retail', 'Corporate'}

        retail = next(sd for sd in result if sd.name == 'Retail')
        assert retail.domain_folder == 'channels'
        assert retail.archi_id == 'retail'
        assert set(retail.component_ids) == {'sys-retail-1', 'sys-retail-2'}

        corp = next(sd for sd in result if sd.name == 'Corporate')
        assert corp.domain_folder == 'channels'
        assert set(corp.component_ids) == {'sys-corp-1'}

    def test_no_subdomain_folders_returns_empty(self, tmp_path):
        """Domain without subdomain subdirectories produces no ParsedSubdomain."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        # No subdomain subdirs, only a diagram directly in domain
        _write_diagram_with_components(
            domain_dir / 'ArchimateDiagramModel_v1.xml',
            'Channels view',
            component_ids=['sys-1'],
        )
        result = parse_subdomains(tmp_path, domain_renames={})
        assert result == []

    def test_no_diagrams_dir_returns_empty(self, tmp_path):
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_no_functional_areas_returns_empty(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        other = diagrams / 'other'
        _write_folder_xml(other, 'other_views')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_domain_rename_applied_to_domain_folder(self, tmp_path):
        """domain_renames are applied to domain_folder in ParsedSubdomain."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'old_dir'
        _write_folder_xml(domain_dir, 'Channels')  # c4_id = 'channels'
        sub_dir = domain_dir / 'retail_sub'
        _write_folder_xml(sub_dir, 'Retail')
        _write_diagram_with_components(
            sub_dir / 'ArchimateDiagramModel_r1.xml',
            'Retail view',
            component_ids=['sys-1'],
        )
        result = parse_subdomains(
            tmp_path, domain_renames={'channels': ('digital_channels', 'Digital Channels')})
        assert len(result) == 1
        assert result[0].domain_folder == 'digital_channels'


# ── TestParserErrorPaths: malformed XML coverage ─────────────────────────

class TestParserErrorPaths:
    """Cover ET.ParseError branches and raise ParseError when all files fail."""

    def test_application_components_malformed_raises(self, tmp_path):
        """All ApplicationComponent XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationComponent_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='ApplicationComponent'):
            parse_application_components(tmp_path)

    def test_application_components_partial_malformed_ok(self, tmp_path):
        """Some malformed + some valid → returns valid, no exception."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationComponent_bad.xml').write_text('<broken', encoding='utf-8')
        _write_component(app_dir / 'ApplicationComponent_ok.xml', archi_id='ok-1', name='GoodSys')
        result = parse_application_components(tmp_path)
        assert len(result) == 1
        assert result[0].archi_id == 'ok-1'

    def test_application_interfaces_malformed_raises(self, tmp_path):
        """All ApplicationInterface XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationInterface_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='ApplicationInterface'):
            parse_application_interfaces(tmp_path)

    def test_data_objects_malformed_raises(self, tmp_path):
        """All DataObject XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'DataObject_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='DataObject'):
            parse_data_objects(tmp_path)

    def test_data_objects_partial_malformed_ok(self, tmp_path):
        """Some malformed DataObject + some valid → returns valid."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'DataObject_bad.xml').write_text('<broken', encoding='utf-8')
        _write_component(app_dir / 'DataObject_ok.xml', archi_id='do-1', name='GoodData')
        result = parse_data_objects(tmp_path)
        assert len(result) == 1
        assert result[0].archi_id == 'do-1'

    def test_application_functions_malformed_raises(self, tmp_path):
        """All ApplicationFunction XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationFunction_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='ApplicationFunction'):
            parse_application_functions(tmp_path)

    def test_technology_elements_malformed_raises(self, tmp_path):
        """All technology XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'Node_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='technology'):
            parse_technology_elements(tmp_path)

    def test_technology_elements_partial_malformed_ok(self, tmp_path):
        """Some malformed + some valid tech elements → returns valid."""
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'Node_bad.xml').write_text('<broken', encoding='utf-8')
        _write_tech_element(tech_dir / 'Node_ok.xml', 'Node', 'n-1', 'GoodNode')
        result = parse_technology_elements(tmp_path)
        assert len(result) == 1
        assert result[0].archi_id == 'n-1'

    def test_relationships_malformed_raises(self, tmp_path):
        """All relationship XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'FlowRelationship_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='relationship'):
            parse_relationships(tmp_path)

    def test_relationships_partial_malformed_ok(self, tmp_path):
        """Some malformed + some valid relationships → returns valid."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'FlowRelationship_bad.xml').write_text('<broken', encoding='utf-8')
        _write_relationship(
            rel_dir / 'FlowRelationship_ok.xml',
            rel_type='FlowRelationship', rel_id='r-1', name='flow',
            source_id='src-1', source_type='archimate:ApplicationComponent',
            target_id='tgt-1', target_type='archimate:ApplicationComponent',
        )
        result = parse_relationships(tmp_path)
        assert len(result) == 1
        assert result[0].rel_id == 'r-1'

    def test_is_in_trash_malformed_folder_xml(self, tmp_path):
        """Malformed folder.xml is ignored (no exception) — file not in trash."""
        base = tmp_path / 'application'
        sub = base / 'subfolder'
        sub.mkdir(parents=True)
        (sub / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        xml = sub / 'SomeFile.xml'
        xml.touch()
        assert _is_in_trash(xml, base) is False

    def test_detect_special_folder_malformed_folder_xml(self, tmp_path):
        """Malformed folder.xml in _detect_special_folder is skipped gracefully."""
        app_dir = tmp_path / 'application'
        sub = app_dir / 'review'
        sub.mkdir(parents=True)
        (sub / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        xml = sub / 'ApplicationComponent_x.xml'
        xml.touch()
        assert _detect_special_folder(xml) == ''


# ── XML security (Issue #7) ───────────────────────────────────────────────

class TestXmlSecurity:
    """Issue #7: parsers must use defusedxml to prevent XXE attacks."""

    def test_parsers_uses_defusedxml_not_stdlib(self):
        """ET alias in parsers must be defusedxml.ElementTree, not xml.etree.ElementTree."""
        import defusedxml.ElementTree as defused_et

        import archi2likec4.parsers as parsers_module
        assert parsers_module.ET is defused_et, (
            "parsers.py must use defusedxml.ElementTree, not xml.etree.ElementTree"
        )


# ── Issue #18: empty archi_id validation ─────────────────────────────────

class TestEmptyArchiId:
    """Issue #18: parsers must skip elements with empty id and log a warning."""

    def test_tech_element_empty_id_skipped(self, tmp_path):
        """parse_technology_elements: element with empty id must be skipped."""
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'Node_n1.xml').write_text(
            '<archimate:Node xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Server" id=""/>',
            encoding='utf-8',
        )
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_tech_element_empty_id_warns(self, tmp_path, caplog):
        """parse_technology_elements: empty id must produce a warning."""
        import logging
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'Node_n1.xml').write_text(
            '<archimate:Node xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Server" id=""/>',
            encoding='utf-8',
        )
        with caplog.at_level(logging.WARNING):
            parse_technology_elements(tmp_path)
        assert any('empty id' in r.message for r in caplog.records)

    def test_location_element_empty_id_skipped(self, tmp_path):
        """parse_location_elements: element with empty id must be skipped."""
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_loc1.xml').write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Datacenter" id=""/>',
            encoding='utf-8',
        )
        result = parse_location_elements(tmp_path)
        assert result == []

    def test_location_element_empty_id_warns(self, tmp_path, caplog):
        """parse_location_elements: empty id must produce a warning."""
        import logging
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_loc1.xml').write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Datacenter" id=""/>',
            encoding='utf-8',
        )
        with caplog.at_level(logging.WARNING):
            parse_location_elements(tmp_path)
        assert any('empty id' in r.message for r in caplog.records)

    def test_tech_element_whitespace_id_skipped(self, tmp_path):
        """parse_technology_elements: element with whitespace-only id must be skipped."""
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'Node_n1.xml').write_text(
            '<archimate:Node xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Server" id="   "/>',
            encoding='utf-8',
        )
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_location_element_whitespace_id_skipped(self, tmp_path):
        """parse_location_elements: element with whitespace-only id must be skipped."""
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_loc1.xml').write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="Datacenter" id="\t"/>',
            encoding='utf-8',
        )
        result = parse_location_elements(tmp_path)
        assert result == []


# ── Issue #16: consistent ET.ParseError handling ─────────────────────────

class TestParserErrorConsistency:
    """Issue #16: all parsers must use logger.warning for ET.ParseError, not propagate raw."""

    def test_location_malformed_warns_not_raises(self, tmp_path, caplog):
        """parse_location_elements: malformed XML is logged at WARNING level, no exception."""
        import logging
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_location_elements(tmp_path)
        assert result == []
        assert any('Cannot parse' in r.message for r in caplog.records)

    def test_location_partial_malformed_returns_valid(self, tmp_path):
        """parse_location_elements: one malformed + one valid → returns only valid."""
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_bad.xml').write_text('<broken', encoding='utf-8')
        (other_dir / 'Location_ok.xml').write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' id="loc-1" name="DC1"/>',
            encoding='utf-8',
        )
        result = parse_location_elements(tmp_path)
        assert len(result) == 1
        assert result[0].archi_id == 'loc-1'


# ── Issue #17: _detect_special_folder uses `is None` ─────────────────────

class TestDetectSpecialFolderNoneCheck:
    """Issue #17: _detect_special_folder must use `is None`, not `== None`."""

    def test_no_application_dir_returns_empty(self, tmp_path):
        """When application/ dir does not exist, model_root stays None → return ''."""
        xml = tmp_path / 'SomePath' / 'ApplicationComponent_x.xml'
        xml.parent.mkdir(parents=True)
        xml.touch()
        # No application/ directory: model_root will remain None → return ''
        assert _detect_special_folder(xml) == ''

    def test_application_dir_no_special_folder_returns_empty(self, tmp_path):
        """application/ exists but no !-prefixed folder → return ''."""
        app_dir = tmp_path / 'application'
        sub = app_dir / 'normal_folder'
        sub.mkdir(parents=True)
        (sub / 'folder.xml').write_text('<folder name="Normal"/>', encoding='utf-8')
        xml = sub / 'ApplicationComponent_x.xml'
        xml.touch()
        assert _detect_special_folder(xml) == ''


# ── Issue #22: ParseError propagates from _parse ─────────────────────────

class TestPipelineParseErrorPropagation:
    """Issue #22: ParseError from parsers must propagate through convert() to caller."""

    def test_convert_propagates_parse_error(self, tmp_path):
        """When _parse raises ParseError, convert() re-raises it unchanged."""
        from unittest.mock import patch

        from archi2likec4.exceptions import ParseError as PE
        from archi2likec4.pipeline import convert
        from tests.helpers import MockConfig

        cfg = MockConfig()
        with patch('archi2likec4.pipeline._parse', side_effect=PE('all XMLs bad')), \
                pytest.raises(PE, match='all XMLs bad'):
            convert(tmp_path, tmp_path / 'out', config=cfg)


# ── Parser edge cases: unicode, empty attrs, whitespace-only ───────────

class TestParserEdgeCases:
    """Validate parser robustness for edge case XML inputs."""

    def test_unicode_name_parsed(self, tmp_path):
        """ApplicationComponent with Cyrillic name is parsed correctly."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        xml = app_dir / 'ApplicationComponent_uni.xml'
        xml.write_text(
            '<element id="id-uni" name="Платёжный шлюз"/>',
            encoding='utf-8',
        )
        results = parse_application_components(tmp_path)
        assert len(results) == 1
        assert results[0].name == 'Платёжный шлюз'
        assert results[0].archi_id == 'id-uni'

    def test_whitespace_only_name_skipped(self, tmp_path):
        """Component with whitespace-only name is skipped."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        xml = app_dir / 'ApplicationComponent_ws.xml'
        xml.write_text('<element id="id-ws" name="   "/>', encoding='utf-8')
        results = parse_application_components(tmp_path)
        assert len(results) == 0

    def test_missing_id_skipped(self, tmp_path):
        """Component with no id attribute is skipped."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        xml = app_dir / 'ApplicationComponent_noid.xml'
        xml.write_text('<element name="NoId"/>', encoding='utf-8')
        results = parse_application_components(tmp_path)
        assert len(results) == 0

    def test_special_chars_in_name(self, tmp_path):
        """Component with special characters in name is parsed."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        xml = app_dir / 'ApplicationComponent_sp.xml'
        xml.write_text(
            '<element id="id-sp" name="System (v2.0) &amp; API"/>',
            encoding='utf-8',
        )
        results = parse_application_components(tmp_path)
        assert len(results) == 1
        assert results[0].name == 'System (v2.0) & API'


# ── Coverage uplift: uncovered lines in parsers.py ────────────────────

class TestDetectSpecialFolderViaFolderXml:
    """Cover lines 34-35: _detect_special_folder finds application dir via folder.xml."""

    def test_finds_app_dir_via_folder_xml(self, tmp_path):
        """When application/folder.xml exists, model_root is set via that path."""
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'folder.xml').write_text('<folder name="application"/>', encoding='utf-8')
        sub = app_dir / 'review'
        _write_folder_xml(sub, '!REVIEW')
        xml = sub / 'ApplicationComponent_x.xml'
        xml.touch()
        assert _detect_special_folder(xml) == '!REVIEW'


class TestFindParentComponentEdgeCases:
    """Cover lines 92-93, 99-114: malformed XML and multi-component folder name match."""

    def test_malformed_single_component_skipped(self, tmp_path):
        """Single ApplicationComponent XML that's malformed → skip, return ''."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'systems'
        sys_dir.mkdir(parents=True)
        (sys_dir / 'ApplicationComponent_bad.xml').write_text('<broken<xml', encoding='utf-8')
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == ''

    def test_multiple_components_folder_name_match(self, tmp_path):
        """Multiple components + folder.xml name matches one → returns that one."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'crm_dir'
        sys_dir.mkdir(parents=True)
        _write_folder_xml(sys_dir, 'CRM')
        _write_component(sys_dir / 'ApplicationComponent_a.xml', 'id-crm', 'CRM')
        _write_component(sys_dir / 'ApplicationComponent_b.xml', 'id-other', 'Other')
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == 'id-crm'

    def test_multiple_components_malformed_folder_xml(self, tmp_path):
        """Multiple components + malformed folder.xml → skip, return ''."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'systems'
        sys_dir.mkdir(parents=True)
        (sys_dir / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        _write_component(sys_dir / 'ApplicationComponent_a.xml', 'id-a', 'A')
        _write_component(sys_dir / 'ApplicationComponent_b.xml', 'id-b', 'B')
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == ''

    def test_multiple_components_malformed_component_in_match_loop(self, tmp_path):
        """Multiple components, folder name set, but one component XML malformed."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'crm_dir'
        sys_dir.mkdir(parents=True)
        _write_folder_xml(sys_dir, 'CRM')
        (sys_dir / 'ApplicationComponent_bad.xml').write_text('<broken<xml', encoding='utf-8')
        _write_component(sys_dir / 'ApplicationComponent_ok.xml', 'id-crm', 'CRM')
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == 'id-crm'

    def test_multiple_components_no_folder_name_match(self, tmp_path):
        """Multiple components, folder name doesn't match any → skip and walk up."""
        app_dir = tmp_path / 'application'
        sys_dir = app_dir / 'mixed_dir'
        sys_dir.mkdir(parents=True)
        _write_folder_xml(sys_dir, 'Unrelated')
        _write_component(sys_dir / 'ApplicationComponent_a.xml', 'id-a', 'A')
        _write_component(sys_dir / 'ApplicationComponent_b.xml', 'id-b', 'B')
        fn_xml = sys_dir / 'ApplicationFunction_fn1.xml'
        fn_xml.touch()
        assert _find_parent_component(fn_xml, app_dir) == ''


class TestExtractAllElementRefsAndVisualNesting:
    """Cover lines 151-154, 160-165, 184-187: relationship refs and visual nesting."""

    def test_relationship_refs_extracted(self, tmp_path):
        """_extract_all_element_refs collects archimateRelationship hrefs."""
        import defusedxml.ElementTree as ET

        from archi2likec4.parsers import _extract_all_element_refs
        xml_text = (
            '<root>'
            '<child><archimateElement href="x.xml#elem-1"/></child>'
            '<child><archimateRelationship href="r.xml#rel-1"/></child>'
            '</root>'
        )
        root = ET.fromstring(xml_text)
        elem_ids: list[str] = []
        rel_ids: list[str] = []
        _extract_all_element_refs(root, elem_ids, rel_ids)
        assert 'elem-1' in elem_ids
        assert 'rel-1' in rel_ids

    def test_visual_nesting_extracted(self, tmp_path):
        """_extract_visual_nesting collects parent→child pairs from diagram."""
        import defusedxml.ElementTree as ET

        from archi2likec4.parsers import _extract_visual_nesting
        xml_text = (
            '<root>'
            '<children>'
            '<archimateElement href="x.xml#parent-1"/>'
            '<children>'
            '<archimateElement href="x.xml#child-1"/>'
            '</children>'
            '</children>'
            '</root>'
        )
        root = ET.fromstring(xml_text)
        nesting: list[tuple[str, str]] = []
        _extract_visual_nesting(root, None, nesting)
        assert ('parent-1', 'child-1') in nesting

    def test_get_element_id_returns_none_when_no_ref(self):
        """_get_element_id returns None when no archimateElement child."""
        import defusedxml.ElementTree as ET

        from archi2likec4.parsers import _get_element_id
        node = ET.fromstring('<children><someOtherTag href="x.xml#id"/></children>')
        assert _get_element_id(node) is None

    def test_visual_nesting_without_child_id(self):
        """When nested children have no archimateElement, parent_id propagates."""
        import defusedxml.ElementTree as ET

        from archi2likec4.parsers import _extract_visual_nesting
        xml_text = (
            '<root>'
            '<children>'
            '<archimateElement href="x.xml#top-1"/>'
            '<children>'
            '<someOtherTag/>'
            '<children>'
            '<archimateElement href="x.xml#deep-1"/>'
            '</children>'
            '</children>'
            '</children>'
            '</root>'
        )
        root = ET.fromstring(xml_text)
        nesting: list[tuple[str, str]] = []
        _extract_visual_nesting(root, None, nesting)
        # deep-1's parent should be top-1 (propagated through the middle node)
        assert ('top-1', 'deep-1') in nesting


class TestParseInterfacesEdgeCases:
    """Cover lines 237, 242, 254, 256-257: empty id, empty name, parse warnings."""

    def test_no_app_dir_returns_empty(self, tmp_path):
        result = parse_application_interfaces(tmp_path)
        assert result == []

    def test_trash_interface_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        trash = app_dir / 'old'
        _write_folder_xml(trash, 'Trash')
        _write_component(trash / 'ApplicationInterface_x.xml', archi_id='iface-1', name='OldAPI')
        result = parse_application_interfaces(tmp_path)
        assert result == []

    def test_empty_name_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(app_dir / 'ApplicationInterface_x.xml', archi_id='iface-1', name='')
        result = parse_application_interfaces(tmp_path)
        assert result == []

    def test_empty_id_skipped(self, tmp_path, caplog):
        import logging
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationInterface_x.xml').write_text(
            '<element name="API"/>', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_application_interfaces(tmp_path)
        assert result == []

    def test_partial_malformed_warns(self, tmp_path, caplog):
        """Some malformed + some valid interfaces → logs parse_errors warning."""
        import logging
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationInterface_bad.xml').write_text('<broken', encoding='utf-8')
        _write_component(app_dir / 'ApplicationInterface_ok.xml', archi_id='ok-1', name='GoodAPI')
        with caplog.at_level(logging.WARNING):
            result = parse_application_interfaces(tmp_path)
        assert len(result) == 1
        assert any('could not be parsed' in r.message for r in caplog.records)


class TestParseDataObjectsEdgeCases:
    """Cover lines 271, 276, 288, 290-291: empty name/id skips."""

    def test_trash_data_object_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        trash = app_dir / 'old'
        _write_folder_xml(trash, 'Trash')
        _write_component(trash / 'DataObject_x.xml', archi_id='do-1', name='OldData')
        result = parse_data_objects(tmp_path)
        assert result == []

    def test_empty_name_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(app_dir / 'DataObject_x.xml', archi_id='do-1', name='')
        result = parse_data_objects(tmp_path)
        assert result == []

    def test_empty_id_skipped(self, tmp_path, caplog):
        import logging
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'DataObject_x.xml').write_text(
            '<element name="SomeData"/>', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_data_objects(tmp_path)
        assert result == []
        assert any('empty id' in r.message.lower() or 'Skipping DataObject' in r.message
                    for r in caplog.records)

    def test_no_app_dir_returns_empty(self, tmp_path):
        result = parse_data_objects(tmp_path)
        assert result == []


class TestParseFunctionsEdgeCases:
    """Cover lines 305, 311, 323, 325-326: no app_dir, empty name/id."""

    def test_no_app_dir_returns_empty(self, tmp_path):
        result = parse_application_functions(tmp_path)
        assert result == []

    def test_trash_function_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        trash = app_dir / 'old'
        _write_folder_xml(trash, 'Trash')
        _write_component(trash / 'ApplicationFunction_x.xml', archi_id='fn-1', name='OldFn')
        result = parse_application_functions(tmp_path)
        assert result == []

    def test_empty_name_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(app_dir / 'ApplicationFunction_x.xml', archi_id='fn-1', name='')
        result = parse_application_functions(tmp_path)
        assert result == []

    def test_empty_id_skipped(self, tmp_path, caplog):
        import logging
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationFunction_x.xml').write_text(
            '<element name="DoStuff"/>', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_application_functions(tmp_path)
        assert result == []

    def test_partial_malformed_warns(self, tmp_path, caplog):
        """Some malformed + valid function XMLs → logs warning."""
        import logging
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        (app_dir / 'ApplicationFunction_bad.xml').write_text('<broken', encoding='utf-8')
        _write_component(app_dir / 'ApplicationFunction_ok.xml', archi_id='fn-1', name='GoodFn')
        with caplog.at_level(logging.WARNING):
            result = parse_application_functions(tmp_path)
        assert len(result) == 1
        assert any('could not be parsed' in r.message for r in caplog.records)


class TestParseTechElementsEdgeCases:
    """Cover lines 366, 368, 380, 391, 394: non-prefix skip, empty name, fallback tech_type."""

    def test_non_prefix_file_skipped(self, tmp_path):
        """Files that don't start with known tech prefix are skipped."""
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'SomeOtherFile_x.xml').write_text(
            '<element name="thing" id="x-1"/>', encoding='utf-8')
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_trash_element_skipped(self, tmp_path):
        """Tech elements inside trash folder are skipped."""
        tech_dir = tmp_path / 'technology'
        trash = tech_dir / 'old'
        _write_folder_xml(trash, 'Trash')
        _write_tech_element(trash / 'Node_n1.xml', 'Node', 'n-1', 'OldServer')
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_empty_name_skipped(self, tmp_path):
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'Node_n1.xml').write_text(
            '<archimate:Node xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="" id="n-1"/>', encoding='utf-8')
        result = parse_technology_elements(tmp_path)
        assert result == []

    def test_tech_type_fallback_from_filename(self, tmp_path):
        """When XML tag doesn't contain archimate: prefix, tech_type falls back to filename."""
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        # Write XML where the root tag is just the raw tag (no namespace/archimate: prefix)
        # so tech_type extraction yields empty or same as root.tag
        (tech_dir / 'Node_n1.xml').write_text(
            '<Node name="Srv1" id="n-1"/>', encoding='utf-8')
        result = parse_technology_elements(tmp_path)
        assert len(result) == 1
        assert result[0].tech_type == 'Node'

    def test_unrecognized_tech_type_logged(self, tmp_path, caplog):
        """Unrecognized tech_type logs a debug message but still parses."""
        import logging
        tech_dir = tmp_path / 'technology'
        tech_dir.mkdir()
        (tech_dir / 'TechnologyFunction_tf1.xml').write_text(
            '<archimate:TechnologyFunction xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="TechFunc" id="tf-1"/>', encoding='utf-8')
        with caplog.at_level(logging.DEBUG):
            result = parse_technology_elements(tmp_path)
        assert len(result) == 1
        assert result[0].tech_type == 'TechnologyFunction'


class TestParseRelationshipsEdgeCases:
    """Cover lines 441, 458, 466: folder.xml skip, missing source/target."""

    def test_folder_xml_in_relations_skipped(self, tmp_path):
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'folder.xml').write_text('<folder name="relations"/>', encoding='utf-8')
        result = parse_relationships(tmp_path)
        assert result == []

    def test_missing_source_element_skipped(self, tmp_path):
        """Relationship without <source> element is skipped."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'FlowRelationship_r1.xml').write_text(
            f'<element {_XSI_DECL} id="r-1" name="flow">'
            f'<target href="t.xml#tgt-1" xsi:type="archimate:ApplicationComponent"/>'
            f'</element>', encoding='utf-8')
        result = parse_relationships(tmp_path)
        assert result == []

    def test_missing_target_element_skipped(self, tmp_path):
        """Relationship without <target> element is skipped."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'FlowRelationship_r1.xml').write_text(
            f'<element {_XSI_DECL} id="r-1" name="flow">'
            f'<source href="s.xml#src-1" xsi:type="archimate:ApplicationComponent"/>'
            f'</element>', encoding='utf-8')
        result = parse_relationships(tmp_path)
        assert result == []

    def test_empty_source_href_skipped(self, tmp_path):
        """Relationship with empty href in source is skipped (no #)."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'FlowRelationship_r1.xml').write_text(
            f'<element {_XSI_DECL} id="r-1" name="flow">'
            f'<source href="" xsi:type="archimate:ApplicationComponent"/>'
            f'<target href="t.xml#tgt-1" xsi:type="archimate:ApplicationComponent"/>'
            f'</element>', encoding='utf-8')
        result = parse_relationships(tmp_path)
        assert result == []

    def test_non_relationship_filename_skipped(self, tmp_path):
        """Files without underscore in stem are skipped."""
        rel_dir = tmp_path / 'relations'
        rel_dir.mkdir()
        (rel_dir / 'SomeFile.xml').write_text('<element/>', encoding='utf-8')
        result = parse_relationships(tmp_path)
        assert result == []


class TestParseDomainMappingEdgeCases:
    """Cover lines 525-555: trash domains, empty names, malformed diagrams, renames."""

    def test_trash_domain_skipped(self, tmp_path):
        """Domain folders named 'Trash' are skipped."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        trash_dir = fa_dir / 'trash_dir'
        _write_folder_xml(trash_dir, 'Trash')
        _write_diagram(
            trash_dir / 'ArchimateDiagramModel_v1.xml',
            'functional_architecture.Deleted',
            elements=['sys-1'],
        )
        result = parse_domain_mapping(tmp_path)
        assert result == []

    def test_empty_domain_name_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        empty_dir = fa_dir / 'empty_dir'
        _write_folder_xml(empty_dir, '')
        result = parse_domain_mapping(tmp_path)
        assert result == []

    def test_malformed_domain_folder_xml_skipped(self, tmp_path, caplog):
        import logging
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        bad_dir = fa_dir / 'bad_dir'
        bad_dir.mkdir(parents=True)
        (bad_dir / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_domain_mapping(tmp_path)
        assert result == []

    def test_malformed_diagram_xml_skipped(self, tmp_path, caplog):
        import logging
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        (domain_dir / 'ArchimateDiagramModel_v1.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_domain_mapping(tmp_path)
        assert len(result) == 1
        assert result[0].archi_ids == set()

    def test_domain_renames_applied(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'ch_dir'
        _write_folder_xml(domain_dir, 'Channels')
        diagram_path = domain_dir / 'ArchimateDiagramModel_v1.xml'
        diagram_path.parent.mkdir(parents=True, exist_ok=True)
        diagram_path.write_text(
            f'<archimate:ArchimateDiagramModel {_NS_DECL} name="view" id="v-1">'
            f'<child><archimateElement xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            f'xsi:type="archimate:ApplicationComponent" href="x.xml#sys-1"/></child>'
            f'</archimate:ArchimateDiagramModel>', encoding='utf-8')
        renames = {'channels': ('digital_channels', 'Digital Channels')}
        result = parse_domain_mapping(tmp_path, domain_renames=renames)
        assert len(result) == 1
        assert result[0].c4_id == 'digital_channels'
        assert result[0].name == 'Digital Channels'

    def test_non_dir_entries_in_fa_skipped(self, tmp_path):
        """Files (not dirs) in functional_areas are skipped."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        (fa_dir / 'some_file.txt').write_text('not a dir', encoding='utf-8')
        result = parse_domain_mapping(tmp_path)
        assert result == []

    def test_domain_dir_without_folder_xml_skipped(self, tmp_path):
        """Domain dir without folder.xml is skipped."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'no_folder_xml'
        domain_dir.mkdir(parents=True)
        result = parse_domain_mapping(tmp_path)
        assert result == []


class TestParseSubdomainsEdgeCases:
    """Cover lines 592-636: trash subdomains, malformed XMLs, empty names."""

    def test_trash_subdomain_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        trash_sub = domain_dir / 'trash_sub'
        _write_folder_xml(trash_sub, 'Trash')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_empty_subdomain_name_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        empty_sub = domain_dir / 'empty_sub'
        _write_folder_xml(empty_sub, '')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_malformed_subdomain_folder_xml_skipped(self, tmp_path, caplog):
        import logging
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        bad_sub = domain_dir / 'bad_sub'
        bad_sub.mkdir(parents=True)
        (bad_sub / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_subdomains(tmp_path)
        assert result == []

    def test_malformed_diagram_in_subdomain_skipped(self, tmp_path, caplog):
        import logging
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        sub = domain_dir / 'retail_sub'
        _write_folder_xml(sub, 'Retail')
        (sub / 'ArchimateDiagramModel_v1.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_subdomains(tmp_path)
        assert len(result) == 1
        assert result[0].component_ids == []

    def test_trash_domain_folder_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        trash_domain = fa_dir / 'trash_dir'
        _write_folder_xml(trash_domain, 'Trash')
        sub = trash_domain / 'retail'
        _write_folder_xml(sub, 'Retail')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_empty_domain_name_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'empty_domain'
        _write_folder_xml(domain_dir, '')
        sub = domain_dir / 'sub1'
        _write_folder_xml(sub, 'Sub')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_malformed_domain_folder_xml_in_subdomains(self, tmp_path, caplog):
        import logging
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        bad_domain = fa_dir / 'bad_domain'
        bad_domain.mkdir(parents=True)
        (bad_domain / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_subdomains(tmp_path)
        assert result == []

    def test_non_dir_subdomain_skipped(self, tmp_path):
        """Files inside domain dir are skipped when looking for subdomains."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        (domain_dir / 'not_a_dir.txt').write_text('file', encoding='utf-8')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_subdomain_dir_without_folder_xml_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        sub = domain_dir / 'no_fxml'
        sub.mkdir(parents=True)
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_trash_diagram_in_subdomain_skipped(self, tmp_path):
        """Diagrams inside trash subdirectories of a subdomain are skipped."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        sub = domain_dir / 'retail_sub'
        _write_folder_xml(sub, 'Retail')
        trash_in_sub = sub / 'old'
        _write_folder_xml(trash_in_sub, 'Trash')
        _write_diagram_with_components(
            trash_in_sub / 'ArchimateDiagramModel_v1.xml',
            'old view', component_ids=['sys-old'],
        )
        result = parse_subdomains(tmp_path)
        assert len(result) == 1
        assert result[0].component_ids == []

    def test_non_dir_in_fa_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        (fa_dir / 'file.txt').write_text('not a dir', encoding='utf-8')
        result = parse_subdomains(tmp_path)
        assert result == []

    def test_domain_without_folder_xml_skipped(self, tmp_path):
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        no_fxml = fa_dir / 'no_fxml_domain'
        no_fxml.mkdir(parents=True)
        result = parse_subdomains(tmp_path)
        assert result == []


class TestParseLocationEdgeCases:
    """Cover lines 659, 661, 672: folder.xml skip, trash, empty name."""

    def test_folder_xml_in_other_skipped(self, tmp_path):
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'folder.xml').write_text('<folder name="other"/>', encoding='utf-8')
        result = parse_location_elements(tmp_path)
        assert result == []

    def test_trash_location_skipped(self, tmp_path):
        other_dir = tmp_path / 'other'
        trash = other_dir / 'old'
        _write_folder_xml(trash, 'Trash')
        (trash / 'Location_loc1.xml').write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="OldDC" id="loc-1"/>', encoding='utf-8')
        result = parse_location_elements(tmp_path)
        assert result == []

    def test_empty_name_skipped(self, tmp_path):
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_loc1.xml').write_text(
            '<archimate:Location xmlns:archimate="http://www.archimatetool.com/archimate"'
            ' name="" id="loc-1"/>', encoding='utf-8')
        result = parse_location_elements(tmp_path)
        assert result == []


class TestParseSolutionViewsEdgeCases:
    """Cover lines 700, 725-728, 732, 767-781, 806, 808."""

    def test_no_diagrams_dir_returns_empty(self, tmp_path):
        result = parse_solution_views(tmp_path)
        assert result == []

    def test_deployment_target_pattern(self, tmp_path):
        """deployment_target.X is matched as deployment view."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_d1.xml',
            'deployment_target.MyService',
            elements=['n-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert result[0].view_type == 'deployment'

    def test_empty_diagram_name_skipped(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(diagrams_dir / 'ArchimateDiagramModel_v1.xml', '')
        result = parse_solution_views(tmp_path)
        assert result == []

    def test_duplicate_diagram_merged(self, tmp_path):
        """Duplicate diagrams (same folder, type, name) get merged."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        diagrams_dir.mkdir(parents=True)
        # First diagram
        (diagrams_dir / 'ArchimateDiagramModel_f1.xml').write_text(
            '<archimate:ArchimateDiagramModel '
            'xmlns:archimate="http://www.archimatetool.com/archimate" '
            'name="functional_architecture.Pay" id="v-1">'
            '<child><archimateElement href="x.xml#sys-1"/></child>'
            '<child><archimateRelationship href="r.xml#rel-1"/></child>'
            '</archimate:ArchimateDiagramModel>', encoding='utf-8')
        # Duplicate with different elements
        (diagrams_dir / 'ArchimateDiagramModel_f2.xml').write_text(
            '<archimate:ArchimateDiagramModel '
            'xmlns:archimate="http://www.archimatetool.com/archimate" '
            'name="functional_architecture.Pay" id="v-2">'
            '<child><archimateElement href="x.xml#sys-2"/></child>'
            '<child><archimateRelationship href="r.xml#rel-2"/></child>'
            '</archimate:ArchimateDiagramModel>', encoding='utf-8')
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert 'sys-1' in result[0].element_archi_ids
        assert 'sys-2' in result[0].element_archi_ids
        assert 'rel-1' in result[0].relationship_archi_ids
        assert 'rel-2' in result[0].relationship_archi_ids

    def test_duplicate_deployment_nesting_merged(self, tmp_path):
        """Duplicate deployment diagrams merge visual nesting too."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        diagrams_dir.mkdir(parents=True)
        # First deployment diagram with nesting
        (diagrams_dir / 'ArchimateDiagramModel_d1.xml').write_text(
            '<archimate:ArchimateDiagramModel '
            'xmlns:archimate="http://www.archimatetool.com/archimate" '
            'name="deployment_architecture.Pay" id="v-1">'
            '<children><archimateElement href="x.xml#parent-1"/>'
            '<children><archimateElement href="x.xml#child-1"/></children>'
            '</children>'
            '</archimate:ArchimateDiagramModel>', encoding='utf-8')
        # Duplicate deployment
        (diagrams_dir / 'ArchimateDiagramModel_d2.xml').write_text(
            '<archimate:ArchimateDiagramModel '
            'xmlns:archimate="http://www.archimatetool.com/archimate" '
            'name="deployment_architecture.Pay" id="v-2">'
            '<children><archimateElement href="x.xml#parent-2"/>'
            '<children><archimateElement href="x.xml#child-2"/></children>'
            '</children>'
            '</archimate:ArchimateDiagramModel>', encoding='utf-8')
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert ('parent-1', 'child-1') in result[0].visual_nesting
        assert ('parent-2', 'child-2') in result[0].visual_nesting

    def test_all_malformed_solution_views_raises(self, tmp_path):
        """All solution diagram XMLs malformed → ParseError."""
        from archi2likec4.exceptions import ParseError as PE
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        diagrams_dir.mkdir(parents=True)
        (diagrams_dir / 'ArchimateDiagramModel_bad.xml').write_text(
            '<broken<xml', encoding='utf-8')
        with pytest.raises(PE, match='solution diagram'):
            parse_solution_views(tmp_path)

    def test_partial_malformed_solution_views_ok(self, tmp_path, caplog):
        """Some malformed + valid solution views → returns valid, logs warning."""
        import logging
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        diagrams_dir.mkdir(parents=True)
        (diagrams_dir / 'ArchimateDiagramModel_bad.xml').write_text(
            '<broken<xml', encoding='utf-8')
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_ok.xml',
            'functional_architecture.GoodService',
            elements=['sys-1'],
        )
        with caplog.at_level(logging.WARNING):
            result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert any('could not be parsed' in r.message for r in caplog.records)


class TestFindFunctionalAreasDirEdgeCases:
    """Cover lines 486, 489, 495-496: _find_functional_areas_dir edge cases."""

    def test_non_dir_entries_skipped(self, tmp_path):
        from archi2likec4.parsers import _find_functional_areas_dir
        diagrams_dir = tmp_path / 'diagrams'
        diagrams_dir.mkdir()
        (diagrams_dir / 'some_file.txt').write_text('not a dir', encoding='utf-8')
        assert _find_functional_areas_dir(diagrams_dir) is None

    def test_dir_without_folder_xml_skipped(self, tmp_path):
        from archi2likec4.parsers import _find_functional_areas_dir
        diagrams_dir = tmp_path / 'diagrams'
        no_fxml = diagrams_dir / 'no_folder_xml'
        no_fxml.mkdir(parents=True)
        assert _find_functional_areas_dir(diagrams_dir) is None

    def test_malformed_folder_xml_skipped(self, tmp_path, caplog):
        import logging

        from archi2likec4.parsers import _find_functional_areas_dir
        diagrams_dir = tmp_path / 'diagrams'
        bad_dir = diagrams_dir / 'bad'
        bad_dir.mkdir(parents=True)
        (bad_dir / 'folder.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            assert _find_functional_areas_dir(diagrams_dir) is None
