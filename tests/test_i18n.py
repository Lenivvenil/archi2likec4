"""Tests for archi2likec4.i18n module."""

from archi2likec4.i18n import get_audit_label, get_msg, get_qa10_issue, get_web_msg


class TestGetMsg:
    def test_ru_title(self):
        assert get_msg('QA-1', 'title', 'ru') == 'Системы без домена'

    def test_en_title(self):
        assert get_msg('QA-1', 'title', 'en') == 'Systems without domain'

    def test_description_with_placeholder(self):
        desc = get_msg('QA-1', 'description', 'en', count=5)
        assert '5 systems' in desc

    def test_description_ru_with_placeholder(self):
        desc = get_msg('QA-1', 'description', 'ru', count=10)
        assert '10 систем' in desc

    def test_unknown_qa_returns_empty(self):
        assert get_msg('QA-99', 'title', 'ru') == ''

    def test_unknown_field_returns_empty(self):
        assert get_msg('QA-1', 'nonexistent', 'ru') == ''

    def test_all_qa_ids_have_both_langs(self):
        for qa_id in [f'QA-{i}' for i in range(1, 11)]:
            for field in ('title', 'description', 'impact', 'remediation'):
                assert get_msg(qa_id, field, 'ru'), f'{qa_id}.{field} missing ru'
                assert get_msg(qa_id, field, 'en'), f'{qa_id}.{field} missing en'


class TestGetQa10Issue:
    def test_floating_sw_ru(self):
        label = get_qa10_issue('floating_sw', 'ru')
        assert 'плавающее' in label

    def test_floating_sw_en(self):
        label = get_qa10_issue('floating_sw', 'en')
        assert 'floating' in label

    def test_unknown_returns_key(self):
        assert get_qa10_issue('unknown_key', 'en') == 'unknown_key'


class TestGetAuditLabel:
    def test_title_ru(self):
        assert 'Реестр' in get_audit_label('title', 'ru')

    def test_title_en(self):
        assert 'Register' in get_audit_label('title', 'en')

    def test_auto_generated_with_params(self):
        label = get_audit_label('auto_generated', 'en', version='1.0', date='2026-01-01')
        assert '1.0' in label
        assert '2026-01-01' in label

    def test_summary_labels(self):
        assert get_audit_label('systems', 'ru') == 'Систем'
        assert get_audit_label('systems', 'en') == 'Systems'


class TestLanguageInAuditData:
    """Verify language parameter flows through audit_data."""

    def test_en_incidents(self):
        from archi2likec4.audit_data import compute_audit_incidents
        from archi2likec4.models import System
        from tests.helpers import MockBuilt, MockConfig

        sys1 = System(c4_id='test', name='TestSys', archi_id='s-1',
                      metadata={'ci': 'TBD', 'full_name': 'Test',
                                'lc_stage': 'TBD', 'criticality': 'TBD',
                                'target_state': 'TBD', 'business_owner_dep': 'TBD',
                                'dev_team': 'TBD', 'architect': 'TBD',
                                'is_officer': 'TBD', 'placement': 'TBD'},
                      domain='')
        built = MockBuilt(
            systems=[sys1],
            domain_systems={'unassigned': [sys1]},
        )
        config = MockConfig(language='en')
        summary, incidents = compute_audit_incidents(built, 0, 0, config)
        qa1 = next(i for i in incidents if i.qa_id == 'QA-1')
        assert qa1.title == 'Systems without domain'

    def test_ru_default(self):
        from archi2likec4.audit_data import compute_audit_incidents
        from archi2likec4.models import System
        from tests.helpers import MockBuilt, MockConfig

        sys1 = System(c4_id='test', name='TestSys', archi_id='s-1',
                      metadata={'ci': 'TBD', 'full_name': 'Test',
                                'lc_stage': 'TBD', 'criticality': 'TBD',
                                'target_state': 'TBD', 'business_owner_dep': 'TBD',
                                'dev_team': 'TBD', 'architect': 'TBD',
                                'is_officer': 'TBD', 'placement': 'TBD'},
                      domain='')
        built = MockBuilt(
            systems=[sys1],
            domain_systems={'unassigned': [sys1]},
        )
        config = MockConfig()
        summary, incidents = compute_audit_incidents(built, 0, 0, config)
        qa1 = next(i for i in incidents if i.qa_id == 'QA-1')
        assert qa1.title == 'Системы без домена'


class TestGetWebMsg:
    def test_known_key_ru(self):
        result = get_web_msg('dashboard', 'ru')
        assert isinstance(result, str)
        assert result != ''

    def test_known_key_en(self):
        result = get_web_msg('dashboard', 'en')
        assert isinstance(result, str)
        assert result != ''

    def test_unknown_key_returns_key(self):
        result = get_web_msg('nonexistent_key_xyz', 'ru')
        assert result == 'nonexistent_key_xyz'

    def test_default_lang_is_ru(self):
        result_explicit = get_web_msg('dashboard', 'ru')
        result_default = get_web_msg('dashboard')
        assert result_explicit == result_default


class TestFormatErrorHandling:
    """Verify that bad kwargs fall back to returning the raw template."""

    def test_get_msg_bad_kwarg_returns_template(self):
        # QA-1 description template uses {count}; passing wrong kwarg triggers KeyError
        result = get_msg('QA-1', 'description', 'en', wrong_key='x')
        # Should return the raw template string (not raise)
        assert isinstance(result, str)
        assert result != ''

    def test_get_audit_label_bad_kwarg_returns_template(self):
        # auto_generated uses {version} and {date}; wrong kwarg triggers KeyError
        result = get_audit_label('auto_generated', 'en', bad_key='x')
        assert isinstance(result, str)
        assert result != ''
