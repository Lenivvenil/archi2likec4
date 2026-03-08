"""Tests for archi2likec4.parsers — XML parsing from coArchi model.

Uses temporary directories with minimal XML files to test parser logic
without depending on the real architectural_repository.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from archi2likec4.parsers import (
    _extract_ref_id,
    _is_in_trash,
    parse_application_components,
    parse_application_functions,
    parse_application_interfaces,
    parse_data_objects,
    parse_relationships,
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
            rel_dir / 'AggregationRelationship_r1.xml',
            rel_type='AggregationRelationship', rel_id='r-1', name='',
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
