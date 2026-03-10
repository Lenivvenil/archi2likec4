"""Tests for archi2likec4.utils — transliteration, ID generation, escaping."""

import pytest

from archi2likec4.utils import build_metadata, escape_str, make_id, sanitize_path_segment, transliterate
from archi2likec4.models import AppComponent


# ── transliterate ────────────────────────────────────────────────────────

class TestTransliterate:
    def test_latin_passthrough(self):
        assert transliterate('Hello World') == 'Hello World'

    def test_cyrillic_basic(self):
        assert transliterate('Привет') == 'Privet'

    def test_cyrillic_lowercase(self):
        assert transliterate('привет') == 'privet'

    def test_mixed(self):
        assert transliterate('Сервер ELK') == 'Server ELK'

    def test_complex_chars(self):
        assert transliterate('щука') == 'shchuka'
        assert transliterate('ёж') == 'yozh'

    def test_empty(self):
        assert transliterate('') == ''

    def test_numbers_passthrough(self):
        assert transliterate('123') == '123'

    def test_uppercase_cyrillic(self):
        assert transliterate('БАНК') == 'BANK'


# ── make_id ──────────────────────────────────────────────────────────────

class TestMakeId:
    def test_simple_latin(self):
        assert make_id('EFS') == 'efs'

    def test_with_spaces(self):
        assert make_id('Payment Hub') == 'payment_hub'

    def test_cyrillic(self):
        assert make_id('Каналы') == 'kanaly'

    def test_special_chars(self):
        assert make_id('API (v2.0)') == 'api_v2_0'

    def test_reserved_word(self):
        assert make_id('model') == 'model_el'
        assert make_id('view') == 'view_el'
        assert make_id('specification') == 'specification_el'

    def test_leading_digit(self):
        assert make_id('1C') == 'n1c'

    def test_prefix(self):
        assert make_id('Account', prefix='de') == 'de_account'

    def test_empty_name(self):
        assert make_id('') == 'unnamed'
        assert make_id('   ') == 'unnamed'

    def test_multiple_underscores_collapsed(self):
        result = make_id('Some  --  Name')
        assert '__' not in result

    def test_stripped_underscores(self):
        result = make_id('_test_')
        assert not result.startswith('_')
        assert not result.endswith('_')

    def test_with_dot(self):
        # Dots become underscores
        result = make_id('EFS.Core')
        assert result == 'efs_core'


# ── sanitize_path_segment ────────────────────────────────────────────────

class TestSanitizePathSegment:
    def test_normal_string(self):
        assert sanitize_path_segment('channels') == 'channels'

    def test_path_traversal(self):
        assert '..' not in sanitize_path_segment('../../etc/passwd')

    def test_slashes_replaced(self):
        result = sanitize_path_segment('foo/bar\\baz')
        assert '/' not in result
        assert '\\' not in result

    def test_empty_returns_invalid(self):
        assert sanitize_path_segment('') == 'invalid'
        assert sanitize_path_segment('...') == 'invalid'

    def test_null_bytes_stripped(self):
        assert '\x00' not in sanitize_path_segment('foo\x00bar')

    def test_leading_dots_stripped(self):
        result = sanitize_path_segment('.hidden')
        assert not result.startswith('.')


# ── escape_str ───────────────────────────────────────────────────────────

class TestEscapeStr:
    def test_plain_text(self):
        assert escape_str('Hello World') == 'Hello World'

    def test_single_quotes(self):
        assert escape_str("it's") == "it\\'s"

    def test_backslash(self):
        assert escape_str('path\\to') == 'path\\\\to'

    def test_xml_entities(self):
        assert escape_str('line&#xD;break&#xA;here') == 'linebreakhere'

    def test_whitespace_collapse(self):
        assert escape_str('  too   many   spaces  ') == 'too many spaces'

    def test_newlines(self):
        assert escape_str('line\n\nbreak') == 'line break'

    def test_empty(self):
        assert escape_str('') == ''


# ── build_metadata ───────────────────────────────────────────────────────

class TestBuildMetadata:
    def test_defaults_tbd(self):
        ac = AppComponent(archi_id='id-1', name='TestSys')
        meta = build_metadata(ac)
        assert meta['ci'] == 'TBD'
        assert meta['criticality'] == 'TBD'
        assert meta['full_name'] == 'TestSys'  # defaults to name

    def test_known_properties_mapped(self):
        ac = AppComponent(
            archi_id='id-1', name='TestSys',
            properties={'CI': 'CI-123', 'Criticality': 'High', 'Full name': 'Test System'},
        )
        meta = build_metadata(ac)
        assert meta['ci'] == 'CI-123'
        assert meta['criticality'] == 'High'
        assert meta['full_name'] == 'Test System'

    def test_unknown_properties_ignored(self):
        ac = AppComponent(
            archi_id='id-1', name='TestSys',
            properties={'RandomProp': 'value'},
        )
        meta = build_metadata(ac)
        assert 'RandomProp' not in meta
        assert 'random_prop' not in meta

    def test_all_standard_keys_present(self):
        ac = AppComponent(archi_id='id-1', name='TestSys')
        meta = build_metadata(ac)
        expected_keys = {
            'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        }
        assert set(meta.keys()) == expected_keys
