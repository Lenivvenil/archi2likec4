"""Tests for archi2likec4.i18n module."""

from archi2likec4.i18n import get_msg, get_qa10_issue, get_audit_label


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
        from tests.helpers import MockConfig, MockBuilt
        from archi2likec4.audit_data import compute_audit_incidents
        from archi2likec4.models import System

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
        config.language = 'en'
        summary, incidents = compute_audit_incidents(built, 0, 0, config)
        qa1 = next(i for i in incidents if i.qa_id == 'QA-1')
        assert qa1.title == 'Systems without domain'

    def test_ru_default(self):
        from tests.helpers import MockConfig, MockBuilt
        from archi2likec4.audit_data import compute_audit_incidents
        from archi2likec4.models import System

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
