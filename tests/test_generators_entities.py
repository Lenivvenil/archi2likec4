"""Tests for entity and audit generation in archi2likec4.generators."""

from archi2likec4.generators._common import render_metadata, truncate_desc
from archi2likec4.generators.audit import generate_audit_md
from archi2likec4.generators.deployment import generate_datastore_mapping_c4
from archi2likec4.generators.entities import generate_entities
from archi2likec4.models import DataAccess, DataEntity, DeploymentNode, Subsystem, System
from tests.helpers import MockBuilt, MockConfig

# ── generate_entities ────────────────────────────────────────────────────

class TestGenerateEntities:
    def test_empty(self):
        result = generate_entities([], [])
        assert '// No data entities found' in result

    def test_with_entity(self):
        entity = DataEntity(c4_id='de_account', name='Account',
                            archi_id='do-1', documentation='Customer account')
        result = generate_entities([entity], [])
        assert "de_account = dataEntity 'Account'" in result
        assert '#entity' in result
        assert "description 'Customer account'" in result

    def test_with_data_access(self):
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        da = DataAccess(system_path='channels.efs', entity_id='de_account', name='reads')
        result = generate_entities([entity], [da])
        assert "channels.efs -> de_account 'reads'" in result


# ── generate_datastore_mapping ───────────────────────────────────────────

class TestGenerateDatastoreMapping:
    def test_generates_persists_relationships(self):
        links = [('srv.pg', 'de_users'), ('srv.pg', 'de_orders')]
        content = generate_datastore_mapping_c4(links)
        assert 'persists' in content
        assert 'srv.pg -[persists]-> de_users' in content
        assert 'srv.pg -[persists]-> de_orders' in content

    def test_empty_links(self):
        content = generate_datastore_mapping_c4([])
        assert 'persists' not in content


# ── generate_audit_md ───────────────────────────────────────────────────


class TestGenerateAuditMd:
    def test_summary_present(self):
        built = MockBuilt(systems=[
            System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels'),
        ])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '## Сводка' in result
        assert '| Систем | 1 |' in result

    def test_unassigned_listed(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        s2 = System(c4_id='efs', name='EFS', archi_id='s2', metadata={}, domain='channels')
        built = MockBuilt(
            systems=[s1, s2],
            domain_systems={'unassigned': [s1], 'channels': [s2]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[Critical] Системы без домена (1)' in result
        assert '| 1 | AD |' in result

    def test_metadata_completeness(self):
        meta_full = {k: 'filled' for k in [
            'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        meta_empty = {k: 'TBD' for k in meta_full}
        s_good = System(c4_id='a', name='A', archi_id='s1', metadata=dict(meta_full), domain='d')
        s_bad = System(c4_id='b', name='B', archi_id='s2', metadata=dict(meta_empty), domain='d')
        built = MockBuilt(systems=[s_good, s_bad])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[High] Незаполненные карточки' in result
        assert '| 1 | B |' in result

    def test_to_review_listed(self):
        s = System(c4_id='x', name='ReviewMe', archi_id='s1', metadata={},
                   tags=['to_review'], domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[High] Системы на разборе (1)' in result
        assert 'ReviewMe' in result

    def test_promote_candidates(self):
        subs = [Subsystem(c4_id=f'sub{i}', name=f'S{i}', archi_id=f'sub-{i}', metadata={})
                for i in range(12)]
        s = System(c4_id='big', name='BigParent', archi_id='s1',
                   metadata={}, subsystems=subs, domain='d')
        built = MockBuilt(systems=[s])
        result = generate_audit_md(built, 0, 0, MockConfig(promote_warn_threshold=10))
        assert '[Medium] Кандидаты на декомпозицию (1)' in result
        assert 'BigParent' in result
        assert '| 1 | BigParent | 12 |' in result

    def test_section_omitted_when_zero(self):
        meta = {k: 'filled' for k in [
            'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        s = System(c4_id='a', name='A', archi_id='s1', metadata=dict(meta),
                   domain='d', documentation='Has docs')
        built = MockBuilt(systems=[s], domain_systems={'d': [s]})
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Системы без домена' not in result
        assert 'Системы на разборе' not in result
        assert 'Осиротевшие функции' not in result

    def test_no_infra_mapping(self):
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = MockBuilt(systems=[s], deployment_map=[])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[Medium] Системы без инфраструктурной привязки' in result
        assert 'EFS' in result

    def test_orphan_fns_shown(self):
        from archi2likec4.builders._result import BuildDiagnostics
        built = MockBuilt(diagnostics=BuildDiagnostics(orphan_fns=3, intg_skipped=0, intg_total_eligible=0))
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert '[Low] Осиротевшие функции (3)' in result

    def test_solution_view_coverage(self):
        built = MockBuilt()
        result = generate_audit_md(built, 100, 500, MockConfig())
        assert 'Покрытие solution views' in result
        assert '100' in result

    def test_suppress_excludes_from_unassigned(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        s2 = System(c4_id='legacy', name='Legacy', archi_id='s2', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s1, s2],
            domain_systems={'unassigned': [s1, s2]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig(audit_suppress=['Legacy']))
        assert '[Critical] Системы без домена (1)' in result
        assert 'AD' in result
        assert 'Legacy' not in result.split('Сводка')[1]  # not in incident tables

    def test_suppress_hides_section_when_all_suppressed(self):
        s = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig(audit_suppress=['AD']))
        assert 'Системы без домена' not in result

    def test_suppress_footer_count(self):
        s = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig(audit_suppress=['AD']))
        assert 'audit_suppress' in result
        assert '1' in result

    def test_qa10_floating_software(self):
        sw = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                            tech_type='SystemSoftware', kind='infraSoftware')
        built = MockBuilt(deployment_nodes=[sw])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Проблемы иерархии развёртывания' in result
        assert 'PostgreSQL' in result
        assert 'root' in result.lower()

    def test_qa10_clean_hierarchy(self):
        """No QA-10 when all nodes are properly nested."""
        child = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                               tech_type='Node', kind='infraNode')
        parent = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                                tech_type='Location', kind='infraLocation',
                                children=[child])
        built = MockBuilt(deployment_nodes=[parent])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Проблемы иерархии развёртывания' not in result

    def test_qa10_infra_zone_root_without_location(self):
        """QA-10 should flag root infraZone not under infraLocation."""
        loc = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                             tech_type='Location', kind='infraLocation',
                             children=[])
        zone = DeploymentNode(c4_id='lan', name='LAN', archi_id='cn-1',
                              tech_type='CommunicationNetwork', kind='infraZone')
        built = MockBuilt(deployment_nodes=[loc, zone])
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Проблемы иерархии развёртывания' in result
        assert 'LAN' in result

    def test_qa10_infra_zone_under_location_ok(self):
        """QA-10 should NOT flag infraZone nested under infraLocation."""
        zone = DeploymentNode(c4_id='lan', name='LAN', archi_id='cn-1',
                              tech_type='CommunicationNetwork', kind='infraZone')
        loc = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                             tech_type='Location', kind='infraLocation',
                             children=[zone])
        built = MockBuilt(deployment_nodes=[loc])
        result = generate_audit_md(built, 0, 0, MockConfig())
        # LAN is nested under DC, should not be flagged — no QA-10 section at all
        assert 'Проблемы иерархии развёртывания' not in result


    def test_stable_qa_ids(self):
        """QA IDs in AUDIT.md use inc.qa_id, not sequential numbering."""
        s = System(c4_id='x', name='ReviewMe', archi_id='s1', metadata={},
                   tags=['to_review'], domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        # QA-1 (unassigned) and QA-3 (to_review) should use actual QA IDs
        assert '## QA-1.' in result
        assert '## QA-3.' in result
        # Should NOT have QA-2 as second section (sequential numbering would)
        assert '## QA-2. [High] Системы на разборе' not in result

    def test_suppress_incident_qa_note(self):
        """When QA category suppressed, AUDIT.md footer mentions suppressed QA-IDs."""
        s = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s],
            domain_systems={'unassigned': [s]},
        )
        result = generate_audit_md(built, 0, 0,
                                   MockConfig(audit_suppress_incidents=['QA-1']))
        assert 'Системы без домена' not in result
        assert 'QA-1' in result  # mentioned in suppressed note

    def test_qa9_subsystem_mapping_not_false_positive(self):
        """QA-9 should not flag system when subsystem has deployment mapping."""
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels',
                   subsystems=[Subsystem(c4_id='core', name='EFS.Core', archi_id='sub1', metadata={})])
        # Mapping is on subsystem level: channels.efs.core → server
        built = MockBuilt(
            systems=[s],
            deployment_map=[('channels.efs.core', 'server1')],
        )
        result = generate_audit_md(built, 0, 0, MockConfig())
        assert 'Системы без инфраструктурной привязки' not in result


# ── truncate_desc ────────────────────────────────────────────────────────

class TestTruncateDesc:
    def test_empty_string(self):
        assert truncate_desc('') == ''

    def test_short_string_unchanged(self):
        assert truncate_desc('hello') == 'hello'

    def test_string_at_boundary(self):
        s = 'a' * 500
        assert truncate_desc(s) == s

    def test_long_string_truncated(self):
        s = 'a' * 501
        result = truncate_desc(s)
        assert result.endswith('...')
        assert len(result) == 500

    def test_newlines_preserved(self):
        s = 'line1\nline2\nline3'
        assert truncate_desc(s) == s

    def test_custom_max_len(self):
        result = truncate_desc('abcdefghij', max_len=7)
        assert result == 'abcd...'
        assert len(result) == 7


# ── render_metadata ──────────────────────────────────────────────────────

class TestRenderMetadata:
    def test_archi_id_only(self):
        lines: list[str] = []
        render_metadata(lines, 'id-123', '  ')
        assert lines == [
            "    metadata {",
            "      archi_id 'id-123'",
            "    }",
        ]

    def test_with_extra_fields(self):
        lines: list[str] = []
        render_metadata(lines, 'id-1', '', extra={'tech': 'Java', 'version': '17'})
        assert "    tech 'Java'" in lines
        assert "    version '17'" in lines

    def test_empty_extra_dict(self):
        lines: list[str] = []
        render_metadata(lines, 'id-1', '', extra={})
        assert len(lines) == 3  # metadata { + archi_id + }

    def test_none_extra(self):
        lines: list[str] = []
        render_metadata(lines, 'id-1', '', extra=None)
        assert len(lines) == 3
