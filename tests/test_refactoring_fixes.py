"""Tests verifying MEDIUM refactoring fixes: #9, #10, #11, #12, #13."""

import ast
import copy
import importlib
import inspect

from archi2likec4.config import ConvertConfig
from archi2likec4.exceptions import (
    Archi2LikeC4Error,
    BuildError,
    GenerateError,
)
from archi2likec4.generators._common import render_metadata, truncate_desc
from archi2likec4.pipeline import _validate, convert
from tests.helpers import MockBuilt, MockConfig

# --- Issue #9: _validate has no side effects ---

class TestValidateNoSideEffects:
    """_validate must be purely diagnostic: no file I/O, no mutation."""

    def test_validate_returns_tuple(self) -> None:
        built = MockBuilt()
        config = MockConfig()
        result = _validate(built, config, sv_unresolved=0, sv_total=0)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_validate_does_not_mutate_built(self) -> None:
        import copy
        built = MockBuilt(orphan_fns=10, domain_systems={'unassigned': ['a', 'b']})
        orphan_before = built.orphan_fns
        ds_before = copy.deepcopy(built.domain_systems)
        _validate(built, MockConfig(), sv_unresolved=0, sv_total=10)
        assert built.orphan_fns == orphan_before
        assert built.domain_systems == ds_before

    def test_validate_zero_counts_on_clean_data(self) -> None:
        built = MockBuilt()
        config = MockConfig()
        warnings, errors = _validate(built, config, sv_unresolved=0, sv_total=10)
        assert warnings == 0
        assert errors == 0

    def test_validate_error_on_high_unresolved(self) -> None:
        built = MockBuilt()
        config = MockConfig(max_unresolved_ratio=0.3)
        warnings, errors = _validate(built, config, sv_unresolved=8, sv_total=10)
        assert errors >= 1


# --- Issue #10: config is not mutated in-place ---

class TestConfigCopy:
    """convert() must copy config before mutating it."""

    def test_copy_copy_produces_independent_instance(self) -> None:
        original = ConvertConfig()
        copied = copy.copy(original)
        copied.dry_run = True
        assert original.dry_run is False

    def test_convert_config_is_mutable_dataclass(self) -> None:
        cfg = ConvertConfig()
        cfg.dry_run = True
        assert cfg.dry_run is True

    def test_convert_does_not_mutate_caller_config(self, tmp_path) -> None:
        """Regression: convert() must copy the config object, not mutate the caller's."""

        model = tmp_path / 'model'
        app = model / 'application'
        app.mkdir(parents=True)
        (app / 'ApplicationComponent_s1.xml').write_text(
            '<element id="s-1" name="Sys1"/>', encoding='utf-8',
        )
        (model / 'relations').mkdir()
        (model / 'diagrams').mkdir()

        original = ConvertConfig(
            promote_children={},
            domain_renames={},
            extra_domain_patterns=[],
        )
        dry_run_before = original.dry_run
        model_root_before = original.model_root
        output_dir_before = original.output_dir

        convert(model, tmp_path / 'out', config=original, dry_run=True)

        assert original.dry_run is dry_run_before
        assert original.model_root == model_root_before
        assert original.output_dir == output_dir_before


# --- Issue #11: BuildError and GenerateError exist ---

class TestExceptionHierarchy:
    """exceptions.py must contain BuildError and GenerateError."""

    def test_build_error_inherits_base(self) -> None:
        assert issubclass(BuildError, Archi2LikeC4Error)

    def test_generate_error_inherits_base(self) -> None:
        assert issubclass(GenerateError, Archi2LikeC4Error)

    def test_build_error_can_be_raised(self) -> None:
        try:
            raise BuildError('test')
        except Archi2LikeC4Error:
            pass

    def test_generate_error_can_be_raised(self) -> None:
        try:
            raise GenerateError('test')
        except Archi2LikeC4Error:
            pass


# --- Issue #12: truncate_desc helper ---

class TestTruncateDesc:
    """_common.py must provide truncate_desc used by all generators."""

    def test_short_text_unchanged(self) -> None:
        assert truncate_desc('hello') == 'hello'

    def test_long_text_truncated(self) -> None:
        result = truncate_desc('a' * 600)
        assert len(result) == 500
        assert result.endswith('...')

    def test_custom_max_len(self) -> None:
        result = truncate_desc('a' * 20, max_len=10)
        assert len(result) == 10
        assert result.endswith('...')

    def test_exact_length_unchanged(self) -> None:
        text = 'a' * 500
        assert truncate_desc(text) == text

    def test_generators_use_truncate_desc(self) -> None:
        """Regression: generators must import AND call truncate_desc, with no local re-implementation."""
        _GENERATOR_MODULES = ['domains', 'systems', 'entities', 'deployment']
        for name in _GENERATOR_MODULES:
            mod = importlib.import_module(f'archi2likec4.generators.{name}')
            source = inspect.getsource(mod)
            tree = ast.parse(source)
            imports_truncate = any(
                isinstance(node, ast.ImportFrom)
                and node.module == '_common'
                and any(alias.name == 'truncate_desc' for alias in node.names)
                for node in ast.walk(tree)
            )
            assert imports_truncate, (
                f'archi2likec4/generators/{name}.py must import truncate_desc from ._common'
            )
            calls_truncate = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'truncate_desc'
                for node in ast.walk(tree)
            )
            assert calls_truncate, (
                f'archi2likec4/generators/{name}.py must actually call truncate_desc()'
            )
            local_defs = [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == 'truncate_desc'
            ]
            assert not local_defs, (
                f'archi2likec4/generators/{name}.py must not redefine truncate_desc locally'
            )


# --- Issue #13: render_metadata helper ---

class TestRenderMetadata:
    """_common.py must provide render_metadata used by all generators."""

    def test_basic_metadata_block(self) -> None:
        lines: list[str] = []
        render_metadata(lines, 'id-123', '  ')
        assert lines == [
            "    metadata {",
            "      archi_id 'id-123'",
            "    }",
        ]

    def test_metadata_with_extra(self) -> None:
        lines: list[str] = []
        render_metadata(lines, 'id-456', '', extra={'tech': 'Java'})
        assert lines == [
            "  metadata {",
            "    archi_id 'id-456'",
            "    tech 'Java'",
            "  }",
        ]

    def test_metadata_appends_to_existing(self) -> None:
        lines = ['existing line']
        render_metadata(lines, 'id-789', '')
        assert lines[0] == 'existing line'
        assert len(lines) == 4

    def test_generators_use_render_metadata(self) -> None:
        """Regression: generators must import AND call render_metadata, with no local re-implementation."""
        _GENERATOR_MODULES = ['domains', 'systems', 'entities', 'deployment']
        for name in _GENERATOR_MODULES:
            mod = importlib.import_module(f'archi2likec4.generators.{name}')
            source = inspect.getsource(mod)
            tree = ast.parse(source)
            imports_render = any(
                isinstance(node, ast.ImportFrom)
                and node.module == '_common'
                and any(alias.name == 'render_metadata' for alias in node.names)
                for node in ast.walk(tree)
            )
            assert imports_render, (
                f'archi2likec4/generators/{name}.py must import render_metadata from ._common'
            )
            calls_render = any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'render_metadata'
                for node in ast.walk(tree)
            )
            assert calls_render, (
                f'archi2likec4/generators/{name}.py must actually call render_metadata()'
            )
            local_defs = [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == 'render_metadata'
            ]
            assert not local_defs, (
                f'archi2likec4/generators/{name}.py must not redefine render_metadata locally'
            )
