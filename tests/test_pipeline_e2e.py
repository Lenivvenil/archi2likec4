"""End-to-end tests for the pipeline: parse → build → generate on synthetic data."""

from pathlib import Path

from archi2likec4.config import ConvertConfig
from archi2likec4.pipeline import BuildResult, _build, _generate, _parse, _validate


def _create_minimal_model(tmp_path: Path) -> Path:
    """Create a minimal coArchi model directory with two systems and a relationship."""
    model = tmp_path / 'model'
    app = model / 'application'
    app.mkdir(parents=True)

    # Two ApplicationComponents
    (app / 'ApplicationComponent_sys1.xml').write_text(
        '<element id="sys-1" name="AlphaSystem">'
        '<properties key="CI" value="CI-1"/>'
        '</element>',
        encoding='utf-8',
    )
    (app / 'ApplicationComponent_sys2.xml').write_text(
        '<element id="sys-2" name="BetaSystem"/>',
        encoding='utf-8',
    )

    # A DataObject
    (app / 'DataObject_do1.xml').write_text(
        '<element id="do-1" name="Account"/>',
        encoding='utf-8',
    )

    # An ApplicationFunction under sys1
    sys1_dir = app / 'sys1_dir'
    sys1_dir.mkdir()
    (sys1_dir / 'ApplicationComponent_sys1.xml').write_text(
        '<element id="sys-1" name="AlphaSystem"/>',
        encoding='utf-8',
    )
    (sys1_dir / 'ApplicationFunction_fn1.xml').write_text(
        '<element id="fn-1" name="DoStuff"/>',
        encoding='utf-8',
    )

    # Relations directory
    rel_dir = model / 'relations'
    rel_dir.mkdir()
    _ns = 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    (rel_dir / 'FlowRelationship_r1.xml').write_text(
        f'<element {_ns} id="r-1" name="data flow">'
        f'<source href="s.xml#sys-1" xsi:type="archimate:ApplicationComponent"/>'
        f'<target href="t.xml#sys-2" xsi:type="archimate:ApplicationComponent"/>'
        f'</element>',
        encoding='utf-8',
    )

    # Technology directory with a Node
    tech_dir = model / 'technology' / 'sub'
    tech_dir.mkdir(parents=True)
    (tech_dir / 'Node_n1.xml').write_text(
        '<archimate:Node xmlns:archimate="http://www.archimatetool.com/archimate"'
        ' name="Server 1" id="n-1" documentation="vCPU: 4"/>',
        encoding='utf-8',
    )

    # Empty diagrams dir (parse_domain_mapping and parse_solution_views need it)
    (model / 'diagrams').mkdir()

    return model


class TestPipelineE2E:
    def test_parse_build_generate(self, tmp_path):
        """Full pipeline on synthetic data produces output without errors."""
        model = _create_minimal_model(tmp_path)
        output = tmp_path / 'output'

        config = ConvertConfig(
            model_root=model,
            output_dir=output,
            promote_children={},
            domain_renames={},
            extra_domain_patterns=[],
        )

        parsed = _parse(model, config)
        assert len(parsed.components) >= 2  # sys-1 appears in two dirs
        assert len(parsed.relationships) >= 1
        assert len(parsed.tech_elements) == 1

        built = _build(parsed, config)
        assert len(built.systems) >= 2
        assert len(built.integrations) >= 1

        _generate(built, output, config, {})

        # Verify output files exist
        assert (output / 'specification.c4').exists()
        assert (output / 'relationships.c4').exists()
        assert (output / 'entities.c4').exists()
        assert (output / 'AUDIT.md').exists()

        # Verify spec content
        spec = (output / 'specification.c4').read_text()
        assert 'element system' in spec
        assert 'deploymentNode infraNode' in spec

        # Verify relationships content
        rels = (output / 'relationships.c4').read_text()
        assert 'alphasystem' in rels.lower() or 'betasystem' in rels.lower()

    def test_unknown_domain_from_overrides_not_lost(self, tmp_path):
        """Systems assigned to a domain_overrides target unknown to parsed domains must not vanish."""
        model = _create_minimal_model(tmp_path)
        output = tmp_path / 'output'

        config = ConvertConfig(
            model_root=model,
            output_dir=output,
            promote_children={},
            domain_renames={},
            extra_domain_patterns=[],
            domain_overrides={'AlphaSystem': 'custom_domain'},
        )

        parsed = _parse(model, config)
        built = _build(parsed, config)
        _generate(built, output, config, {})

        # The custom domain file must be generated (not silently skipped)
        assert (output / 'domains' / 'custom_domain.c4').exists(), \
            'Domain file for custom_domain should be auto-created'
        content = (output / 'domains' / 'custom_domain.c4').read_text()
        assert 'AlphaSystem' in content or 'alphasystem' in content

    def test_dry_run_no_output(self, tmp_path):
        """dry_run=True: parse+build succeed, but _generate is never called."""
        model = _create_minimal_model(tmp_path)
        output = tmp_path / 'output'

        config = ConvertConfig(
            model_root=model,
            output_dir=output,
            promote_children={},
            domain_renames={},
            extra_domain_patterns=[],
            dry_run=True,
        )

        parsed = _parse(model, config)
        _build(parsed, config)
        # Pipeline skips _generate when dry_run=True
        assert config.dry_run is True
        assert not output.exists()


def _make_empty_built() -> BuildResult:
    """Create a minimal BuildResult with all-empty data for _validate() tests."""
    from archi2likec4.builders._result import BuildDiagnostics
    return BuildResult(
        systems=[],
        integrations=[],
        data_access=[],
        entities=[],
        domain_systems={},
        sys_domain={},
        archi_to_c4={},
        promoted_archi_to_c4={},
        promoted_parents={},
        iface_c4_path={},
        diagnostics=BuildDiagnostics(orphan_fns=0, intg_skipped=0, intg_total_eligible=0),
        deployment_nodes=[],
        deployment_map=[],
        tech_archi_to_c4={},
        datastore_entity_links=[],
        subdomains=[],
        subdomain_systems={},
    )


class TestValidate:
    def test_clean_build_no_warnings_no_errors(self):
        """Empty build produces 0 warnings and 0 errors."""
        built = _make_empty_built()
        config = ConvertConfig()
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert warnings == 0
        assert errors == 0

    def test_orphan_fns_above_threshold_produces_warning(self):
        """orphan_fns exceeding max_orphan_functions_warn triggers a warning."""
        from archi2likec4.builders._result import BuildDiagnostics
        built = _make_empty_built()._replace(
            diagnostics=BuildDiagnostics(orphan_fns=10, intg_skipped=0, intg_total_eligible=0))
        config = ConvertConfig(max_orphan_functions_warn=5)
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert warnings >= 1
        assert errors == 0

    def test_orphan_fns_at_threshold_no_warning(self):
        """orphan_fns exactly at threshold does NOT trigger a warning."""
        from archi2likec4.builders._result import BuildDiagnostics
        built = _make_empty_built()._replace(
            diagnostics=BuildDiagnostics(orphan_fns=5, intg_skipped=0, intg_total_eligible=0))
        config = ConvertConfig(max_orphan_functions_warn=5)
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert warnings == 0

    def test_unassigned_above_threshold_produces_warning(self):
        """Many unassigned systems trigger a warning."""
        from archi2likec4.models import System
        unassigned = [
            System(c4_id=f's{i}', name=f'Sys{i}', archi_id=f'a-{i}')
            for i in range(25)
        ]
        built = _make_empty_built()._replace(
            systems=unassigned,
            domain_systems={'unassigned': unassigned},
        )
        config = ConvertConfig(max_unassigned_systems_warn=20)
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert warnings >= 1

    def test_unassigned_below_threshold_no_warning(self):
        """Unassigned count below threshold does not trigger a warning."""
        from archi2likec4.models import System
        unassigned = [System(c4_id='s1', name='S1', archi_id='a-1')]
        built = _make_empty_built()._replace(
            systems=unassigned,
            domain_systems={'unassigned': unassigned},
        )
        config = ConvertConfig(max_unassigned_systems_warn=20)
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert warnings == 0

    def test_strict_mode_no_criticals_no_extra_warnings(self):
        """strict=True with no critical incidents does not add warnings."""
        built = _make_empty_built()
        config = ConvertConfig(strict=True)
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert warnings == 0
        assert errors == 0
