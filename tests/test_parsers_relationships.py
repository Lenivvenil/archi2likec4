"""Tests for relationship and technology element parsing from coArchi XML.

Tests parse_relationships and parse_technology_elements functions, including
relationship type filtering, technology layer support, and edge cases.
"""

from pathlib import Path

from archi2likec4.parsers import (
    parse_relationships,
    parse_technology_elements,
)

# Namespace used in coArchi XML (must be declared for valid XML)
_NS_DECL = 'xmlns:archimate="http://www.archimatetool.com/archimate"'
_XSI_DECL = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'


# ── Helpers ──────────────────────────────────────────────────────────────

def _write_folder_xml(folder: Path, name: str):
    """Write a folder.xml with given name."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'folder.xml').write_text(
        f'<folder name="{name}"/>', encoding='utf-8'
    )


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


# ── parse_relationships ──────────────────────────────────────────────────

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


# ── TestRelationshipsExpanded ────────────────────────────────────────────

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


# ── TestParseTechElementsEdgeCases ───────────────────────────────────────

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


# ── TestParseRelationshipsEdgeCases ──────────────────────────────────────

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
