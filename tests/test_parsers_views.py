"""Tests for solution views, domain mapping, and subdomain parsing from coArchi XML.

Tests parse_solution_views, parse_domain_mapping, parse_subdomains functions,
and related diagram helpers. Includes deployment, functional, and integration view patterns.
"""

from pathlib import Path

import pytest

from archi2likec4.parsers import (
    parse_domain_mapping,
    parse_solution_views,
    parse_subdomains,
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


# ── parse_solution_views: deployment patterns ────────────────────────────

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


# ── TestParseDomainMappingEdgeCases ──────────────────────────────────────

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

    def test_trash_subfolder_inside_domain_skipped(self, tmp_path):
        """Diagrams inside a trash subfolder within a domain are excluded."""
        diagrams = tmp_path / 'diagrams'
        fa_dir = diagrams / 'fa'
        _write_folder_xml(fa_dir, 'functional_areas')
        domain_dir = fa_dir / 'channels_dir'
        _write_folder_xml(domain_dir, 'Channels')
        # Valid diagram — should be counted
        _write_diagram_with_components(
            domain_dir / 'ArchimateDiagramModel_v1.xml',
            'Channels view', component_ids=['sys-1'],
        )
        # Trash subfolder inside the domain — should be skipped
        trash = domain_dir / 'old_stuff'
        _write_folder_xml(trash, 'Trash')
        _write_diagram_with_components(
            trash / 'ArchimateDiagramModel_v2.xml',
            'Deleted view', component_ids=['sys-deleted'],
        )
        result = parse_domain_mapping(tmp_path)
        assert len(result) == 1
        assert 'sys-1' in result[0].archi_ids
        assert 'sys-deleted' not in result[0].archi_ids

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


# ── TestParseSubdomainsEdgeCases ─────────────────────────────────────────

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


# ── TestParseSolutionViewsEdgeCases ──────────────────────────────────────

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


# ── TestFindFunctionalAreasDirEdgeCases ──────────────────────────────────

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
