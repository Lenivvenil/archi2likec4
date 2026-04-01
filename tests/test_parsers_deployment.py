"""Tests for location element parsing from coArchi XML.

Tests parse_location_elements function and related location/deployment element handling.
"""

from pathlib import Path

from archi2likec4.parsers import parse_location_elements

# ── Helpers ──────────────────────────────────────────────────────────────

def _write_folder_xml(folder: Path, name: str):
    """Write a folder.xml with given name."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'folder.xml').write_text(
        f'<folder name="{name}"/>', encoding='utf-8'
    )


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


# ── TestParseLocationEdgeCases ──────────────────────────────────────────

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
