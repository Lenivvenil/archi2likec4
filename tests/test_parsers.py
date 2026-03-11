"""Tests for archi2likec4.parsers — XML parsing from coArchi model.

Uses temporary directories with minimal XML files to test parser logic
without depending on the real architectural_repository.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from archi2likec4.parsers import (
    _detect_special_folder,
    _extract_folder_path,
    _extract_ref_id,
    _find_parent_component,
    _is_in_trash,
    parse_application_components,
    parse_application_functions,
    parse_application_interfaces,
    parse_application_services,
    parse_data_objects,
    parse_domain_mapping,
    parse_location_elements,
    parse_relationships,
    parse_solution_views,
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

    @pytest.mark.parametrize('folder_name', ['Archive', 'old', 'Deprecated', '_old'])
    def test_extended_trash_names(self, tmp_path, folder_name):
        base = tmp_path / 'application'
        folder = base / 'subfolder'
        _write_folder_xml(folder, folder_name)
        xml = folder / 'SomeFile.xml'
        xml.touch()
        assert _is_in_trash(xml, base) is True

    def test_custom_trash_names(self, tmp_path):
        """Custom trash_names parameter overrides defaults."""
        base = tmp_path / 'application'
        folder = base / 'subfolder'
        _write_folder_xml(folder, 'old')
        xml = folder / 'SomeFile.xml'
        xml.touch()
        # 'old' is NOT in the custom set
        assert _is_in_trash(xml, base, trash_names=frozenset({'trash'})) is False
        # 'old' IS in this custom set
        assert _is_in_trash(xml, base, trash_names=frozenset({'old'})) is True


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


# ── parse_application_services ────────────────────────────────────────────

class TestParseApplicationServices:
    def test_basic(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'ApplicationService_svc1.xml',
            archi_id='svc-1', name='Mastercard',
            documentation='OCTO',
        )
        result = parse_application_services(tmp_path)
        assert len(result) == 1
        assert result[0].name == 'Mastercard'
        assert result[0].archi_id == 'svc-1'

    def test_empty_name_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        app_dir.mkdir()
        _write_component(
            app_dir / 'ApplicationService_svc2.xml',
            archi_id='svc-2', name='',
        )
        result = parse_application_services(tmp_path)
        assert len(result) == 0

    def test_trash_skipped(self, tmp_path):
        app_dir = tmp_path / 'application'
        trash_dir = app_dir / 'trash_folder'
        trash_dir.mkdir(parents=True)
        (trash_dir / 'folder.xml').write_text(
            '<?xml version="1.0"?><folder:Folder name="trash" '
            'xmlns:folder="http://www.archimatetool.com/archimate"/>')
        _write_component(
            trash_dir / 'ApplicationService_svc3.xml',
            archi_id='svc-3', name='TrashService',
        )
        result = parse_application_services(tmp_path)
        assert len(result) == 0


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
        result = parse_solution_views(tmp_path)
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

    def test_folder_path_preserved(self, tmp_path):
        """Solution view folder_path captures parent folder hierarchy."""
        diagrams_dir = tmp_path / 'diagrams'
        fa_dir = diagrams_dir / 'fa_folder'
        _write_folder_xml(fa_dir, 'functional_areas')
        channels_dir = fa_dir / 'channels_folder'
        _write_folder_xml(channels_dir, 'Channels')
        _write_diagram(
            channels_dir / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.AutoRepay',
            elements=['sys-1'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 1
        assert 'functional_areas' in result[0].folder_path
        assert 'channels' in result[0].folder_path

    def test_func_integ_same_solution_share_slug(self, tmp_path):
        """Functional + integration views of same solution must share slug for grouping."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.PaymentFlow',
            elements=['sys-1'],
        )
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_i1.xml',
            'integration_architecture.PaymentFlow',
            elements=['sys-1', 'sys-2'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 2
        slugs = {r.solution for r in result}
        assert len(slugs) == 1, f'Expected same slug, got {slugs}'
        assert result[0].solution == 'paymentflow'

    def test_different_solutions_get_different_slugs(self, tmp_path):
        """Views for different solutions must have different slugs."""
        diagrams_dir = tmp_path / 'diagrams' / 'sub'
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f1.xml',
            'functional_architecture.Alpha',
            elements=['sys-1'],
        )
        _write_diagram(
            diagrams_dir / 'ArchimateDiagramModel_f2.xml',
            'functional_architecture.Beta',
            elements=['sys-2'],
        )
        result = parse_solution_views(tmp_path)
        assert len(result) == 2
        slugs = {r.solution for r in result}
        assert len(slugs) == 2


# ── _extract_folder_path ──────────────────────────────────────────────

class TestExtractFolderPath:
    def test_builds_slug_path(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams'
        fa_dir = diagrams_dir / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        ch_dir = fa_dir / 'ch'
        _write_folder_xml(ch_dir, 'Channels')
        xml = ch_dir / 'ArchimateDiagramModel_x.xml'
        xml.touch()
        result = _extract_folder_path(xml, diagrams_dir)
        assert result == 'functional_areas/channels'

    def test_no_folders(self, tmp_path):
        diagrams_dir = tmp_path / 'diagrams'
        diagrams_dir.mkdir()
        xml = diagrams_dir / 'ArchimateDiagramModel_x.xml'
        xml.touch()
        result = _extract_folder_path(xml, diagrams_dir)
        assert result == ''
