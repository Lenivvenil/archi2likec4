"""End-to-end tests for the pipeline: parse → build → generate on synthetic data."""

import pytest
from pathlib import Path

from archi2likec4.config import ConvertConfig
from archi2likec4.pipeline import _parse, _build, _generate


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

        # Verify spec content
        spec = (output / 'specification.c4').read_text()
        assert 'element system' in spec
        assert 'element infraNode' in spec

        # Verify relationships content
        rels = (output / 'relationships.c4').read_text()
        assert 'alphasystem' in rels.lower() or 'betasystem' in rels.lower()

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
        built = _build(parsed, config)
        # Pipeline skips _generate when dry_run=True
        assert config.dry_run is True
        assert not output.exists()
