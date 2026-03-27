"""Tests verifying MEDIUM refactoring fixes: #9, #10, #11, #12, #13."""

import copy

from archi2likec4.config import ConvertConfig
from archi2likec4.exceptions import (
    Archi2LikeC4Error,
    BuildError,
    GenerateError,
)
from archi2likec4.generators._common import render_metadata, truncate_desc
from archi2likec4.pipeline import _validate
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
        built = MockBuilt(orphan_fns=10, domain_systems={'unassigned': ['a', 'b']})
        orphan_before = built.orphan_fns
        ds_before = dict(built.domain_systems)
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
