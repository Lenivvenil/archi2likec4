"""Tests for archi2likec4.utils — transliteration, ID generation, escaping."""


from archi2likec4.models import AppComponent, DeploymentNode
from archi2likec4.utils import build_metadata, escape_str, flatten_deployment_nodes, make_id, transliterate

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

    def test_replaces_hyphens(self):
        assert make_id('compliance-reports') == 'compliance_reports'
        assert make_id('risk-assessment-ui') == 'risk_assessment_ui'
        assert make_id('sap_scc-ui_2_14') == 'sap_scc_ui_2_14'


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

    def test_custom_prop_map(self):
        ac = AppComponent(archi_id='id-1', name='TestSys', properties={'MyProp': 'myval'})
        custom_map = {'MyProp': 'my_key'}
        meta = build_metadata(ac, prop_map=custom_map, standard_keys=['my_key'])
        assert meta == {'my_key': 'myval'}

    def test_custom_standard_keys_tbd_for_missing(self):
        ac = AppComponent(archi_id='id-1', name='TestSys')
        meta = build_metadata(ac, prop_map={}, standard_keys=['status', 'owner'])
        assert meta == {'status': 'TBD', 'owner': 'TBD'}

    def test_custom_standard_keys_full_name_defaults_to_name(self):
        ac = AppComponent(archi_id='id-1', name='MySys')
        meta = build_metadata(ac, prop_map={}, standard_keys=['full_name'])
        assert meta == {'full_name': 'MySys'}

    def test_none_params_use_defaults(self):
        ac = AppComponent(archi_id='id-1', name='TestSys')
        meta_default = build_metadata(ac)
        meta_none = build_metadata(ac, prop_map=None, standard_keys=None)
        assert meta_default == meta_none


# ── flatten_deployment_nodes ─────────────────────────────────────────────

def _dn(c4_id: str, children: list | None = None) -> DeploymentNode:
    return DeploymentNode(
        c4_id=c4_id, name=c4_id, archi_id=c4_id, tech_type='Node',
        children=children or [],
    )


class TestFlattenDeploymentNodes:
    def test_empty_list(self):
        assert flatten_deployment_nodes([]) == []

    def test_flat_list(self):
        nodes = [_dn('a'), _dn('b'), _dn('c')]
        result = flatten_deployment_nodes(nodes)
        assert [n.c4_id for n in result] == ['a', 'b', 'c']

    def test_single_level_nesting(self):
        child = _dn('child')
        parent = _dn('parent', children=[child])
        result = flatten_deployment_nodes([parent])
        assert len(result) == 2
        ids = {n.c4_id for n in result}
        assert ids == {'parent', 'child'}

    def test_deep_nesting(self):
        leaf = _dn('leaf')
        mid = _dn('mid', children=[leaf])
        root = _dn('root', children=[mid])
        result = flatten_deployment_nodes([root])
        assert len(result) == 3
        assert result[0].c4_id == 'root'
        assert result[1].c4_id == 'mid'
        assert result[2].c4_id == 'leaf'

    def test_multiple_roots_with_children(self):
        root1 = _dn('r1', children=[_dn('r1c1'), _dn('r1c2')])
        root2 = _dn('r2', children=[_dn('r2c1')])
        result = flatten_deployment_nodes([root1, root2])
        assert len(result) == 5
        ids = [n.c4_id for n in result]
        assert ids == ['r1', 'r1c1', 'r1c2', 'r2', 'r2c1']
