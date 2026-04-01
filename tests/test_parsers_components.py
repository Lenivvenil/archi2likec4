"""Tests for component, function, interface, and data object parsing from coArchi XML.

Tests parse_application_components, parse_application_functions, parse_application_interfaces,
parse_data_objects, and related helper functions (_extract_ref_id, _is_in_trash,
_detect_special_folder, _find_parent_component). Includes error handling and edge cases.
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
        from archi2likec4.parsers import parse_technology_elements
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

        from archi2likec4.parsers import parse_technology_elements
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
        from archi2likec4.parsers import parse_location_elements
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

        from archi2likec4.parsers import parse_location_elements
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
        from archi2likec4.parsers import parse_technology_elements
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
        from archi2likec4.parsers import parse_location_elements
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

        from archi2likec4.parsers import parse_location_elements
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        (other_dir / 'Location_bad.xml').write_text('<broken<xml', encoding='utf-8')
        with caplog.at_level(logging.WARNING):
            result = parse_location_elements(tmp_path)
        assert result == []
        assert any('Cannot parse' in r.message for r in caplog.records)

    def test_location_partial_malformed_returns_valid(self, tmp_path):
        """parse_location_elements: one malformed + one valid → returns only valid."""
        from archi2likec4.parsers import parse_location_elements
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

    def test_relationship_refs_extracted(self):
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

    def test_visual_nesting_extracted(self):
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
