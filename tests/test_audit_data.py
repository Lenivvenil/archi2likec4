"""Tests for archi2likec4.audit_data module."""

from archi2likec4.audit_data import AuditSummary, AuditIncident, compute_audit_incidents
from archi2likec4.models import DeploymentNode, System, Subsystem, RawRelationship

from tests.helpers import MockConfig, MockBuilt


class TestComputeAuditIncidents:
    def test_returns_summary(self):
        s1 = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = MockBuilt(systems=[s1])
        summary, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        assert isinstance(summary, AuditSummary)
        assert summary.total_systems == 1
        assert summary.total_subsystems == 0

    def test_qa1_unassigned(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        s2 = System(c4_id='efs', name='EFS', archi_id='s2', metadata={}, domain='channels')
        built = MockBuilt(
            systems=[s1, s2],
            domain_systems={'unassigned': [s1], 'channels': [s2]},
        )
        summary, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa1 = next((i for i in incidents if i.qa_id == 'QA-1'), None)
        assert qa1 is not None
        assert qa1.severity == 'Critical'
        assert qa1.count == 1
        assert qa1.affected[0]['name'] == 'AD'

    def test_suppress_filters_systems(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s1],
            domain_systems={'unassigned': [s1]},
        )
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              MockConfig(audit_suppress=['AD']))
        qa1 = next((i for i in incidents if i.qa_id == 'QA-1'), None)
        assert qa1 is not None
        assert qa1.count == 0
        assert qa1.suppressed_count == 1
        assert qa1.affected == []

    def test_suppress_incidents_marks_suppressed(self):
        s1 = System(c4_id='ad', name='AD', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(
            systems=[s1],
            domain_systems={'unassigned': [s1]},
        )
        _, incidents = compute_audit_incidents(
            built, 0, 0,
            MockConfig(audit_suppress_incidents=['QA-1']),
        )
        qa1 = next((i for i in incidents if i.qa_id == 'QA-1'), None)
        assert qa1 is not None
        assert qa1.suppressed is True
        assert qa1.count == 1

    def test_empty_model_no_incidents(self):
        built = MockBuilt()
        summary, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        assert summary.total_systems == 0
        assert incidents == []

    def test_qa7_lost_integrations(self):
        s1 = System(c4_id='a', name='A', archi_id='s1', metadata={}, domain='d1')
        rels = [
            RawRelationship(rel_id='r1', rel_type='FlowRelationship',
                            name='flow', source_type='AC', source_id='src',
                            target_type='AC', target_id='tgt'),
        ]
        built = MockBuilt(
            systems=[s1],
            integrations=[],
            relationships=rels,
            intg_skipped=1,
            intg_total_eligible=1,
        )
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa7 = next((i for i in incidents if i.qa_id == 'QA-7'), None)
        assert qa7 is not None
        assert qa7.severity == 'Critical'
        assert qa7.count == 1


class TestQA2MetadataGaps:
    """Tests for QA-2: metadata completeness."""

    def test_all_tbd_triggers_qa2(self):
        meta = {k: 'TBD' for k in [
            'ci', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        s = System(c4_id='x', name='X', archi_id='s1', metadata=dict(meta), domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa2 = next((i for i in incidents if i.qa_id == 'QA-2'), None)
        assert qa2 is not None
        assert qa2.severity == 'High'
        assert qa2.count == 1

    def test_partial_tbd_no_qa2(self):
        """Systems with at least one filled field should NOT trigger QA-2."""
        meta = {k: 'TBD' for k in [
            'ci', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        meta['ci'] = 'CI-42'  # one field filled
        s = System(c4_id='x', name='X', archi_id='s1', metadata=dict(meta), domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa2 = next((i for i in incidents if i.qa_id == 'QA-2'), None)
        assert qa2 is None

    def test_all_filled_no_qa2(self):
        meta = {k: 'filled' for k in [
            'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        s = System(c4_id='x', name='X', archi_id='s1', metadata=dict(meta), domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa2 = next((i for i in incidents if i.qa_id == 'QA-2'), None)
        assert qa2 is None

    def test_qa2_suppress_excludes(self):
        meta = {k: 'TBD' for k in [
            'ci', 'lc_stage', 'criticality', 'target_state',
            'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
        ]}
        s = System(c4_id='x', name='X', archi_id='s1', metadata=dict(meta), domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              MockConfig(audit_suppress=['X']))
        qa2 = next((i for i in incidents if i.qa_id == 'QA-2'), None)
        assert qa2 is None


class TestQA3ToReview:
    """Tests for QA-3: systems tagged to_review."""

    def test_to_review_triggers_qa3(self):
        s = System(c4_id='x', name='X', archi_id='s1', metadata={},
                   tags=['to_review'], domain='d')
        built = MockBuilt(systems=[s], domain_systems={'d': [s]})
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa3 = next((i for i in incidents if i.qa_id == 'QA-3'), None)
        assert qa3 is not None
        assert qa3.severity == 'High'
        assert qa3.count == 1
        assert qa3.affected[0]['name'] == 'X'

    def test_no_to_review_no_qa3(self):
        s = System(c4_id='x', name='X', archi_id='s1', metadata={}, domain='d')
        built = MockBuilt(systems=[s], domain_systems={'d': [s]})
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa3 = next((i for i in incidents if i.qa_id == 'QA-3'), None)
        assert qa3 is None

    def test_qa3_suppress_excludes(self):
        s = System(c4_id='x', name='X', archi_id='s1', metadata={},
                   tags=['to_review'], domain='d')
        built = MockBuilt(systems=[s], domain_systems={'d': [s]})
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              MockConfig(audit_suppress=['X']))
        qa3 = next((i for i in incidents if i.qa_id == 'QA-3'), None)
        assert qa3 is None


class TestQA4PromoteCandidates:
    """Tests for QA-4: systems with many subsystems."""

    def test_many_subsystems_triggers_qa4(self):
        subs = [Subsystem(c4_id=f's{i}', name=f'P.S{i}', archi_id=f'sub-{i}', metadata={})
                for i in range(12)]
        s = System(c4_id='p', name='P', archi_id='s1', metadata={},
                   subsystems=subs, domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              MockConfig(promote_warn_threshold=10))
        qa4 = next((i for i in incidents if i.qa_id == 'QA-4'), None)
        assert qa4 is not None
        assert qa4.severity == 'Medium'
        assert qa4.count == 1
        assert qa4.affected[0]['name'] == 'P'
        assert qa4.affected[0]['subsystem_count'] == 12

    def test_few_subsystems_no_qa4(self):
        subs = [Subsystem(c4_id=f's{i}', name=f'P.S{i}', archi_id=f'sub-{i}', metadata={})
                for i in range(3)]
        s = System(c4_id='p', name='P', archi_id='s1', metadata={},
                   subsystems=subs, domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa4 = next((i for i in incidents if i.qa_id == 'QA-4'), None)
        assert qa4 is None

    def test_already_promoted_excluded(self):
        subs = [Subsystem(c4_id=f's{i}', name=f'P.S{i}', archi_id=f'sub-{i}', metadata={})
                for i in range(12)]
        s = System(c4_id='p', name='P', archi_id='s1', metadata={},
                   subsystems=subs, domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(
            built, 0, 0,
            MockConfig(promote_children={'P': 'd'}, promote_warn_threshold=10))
        qa4 = next((i for i in incidents if i.qa_id == 'QA-4'), None)
        assert qa4 is None


class TestQA5NoDocs:
    """Tests for QA-5: systems without documentation."""

    def test_no_docs_triggers_qa5(self):
        s = System(c4_id='x', name='X', archi_id='s1', metadata={}, domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa5 = next((i for i in incidents if i.qa_id == 'QA-5'), None)
        assert qa5 is not None
        assert qa5.severity == 'Medium'
        assert qa5.count == 1

    def test_with_docs_no_qa5(self):
        s = System(c4_id='x', name='X', archi_id='s1', metadata={},
                   domain='d', documentation='Has docs')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa5 = next((i for i in incidents if i.qa_id == 'QA-5'), None)
        assert qa5 is None

    def test_qa5_suppress_excludes(self):
        s = System(c4_id='x', name='X', archi_id='s1', metadata={}, domain='d')
        built = MockBuilt(systems=[s])
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              MockConfig(audit_suppress=['X']))
        qa5 = next((i for i in incidents if i.qa_id == 'QA-5'), None)
        assert qa5 is None


class TestQA6OrphanFunctions:
    """Tests for QA-6: orphan functions."""

    def test_orphans_trigger_qa6(self):
        built = MockBuilt(orphan_fns=5)
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa6 = next((i for i in incidents if i.qa_id == 'QA-6'), None)
        assert qa6 is not None
        assert qa6.severity == 'Low'
        assert qa6.count == 5

    def test_no_orphans_no_qa6(self):
        built = MockBuilt(orphan_fns=0)
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa6 = next((i for i in incidents if i.qa_id == 'QA-6'), None)
        assert qa6 is None


class TestQA8SolutionViews:
    """Tests for QA-8: solution view coverage."""

    def test_unresolved_triggers_qa8(self):
        built = MockBuilt()
        _, incidents = compute_audit_incidents(built, 100, 500, MockConfig())
        qa8 = next((i for i in incidents if i.qa_id == 'QA-8'), None)
        assert qa8 is not None
        assert qa8.severity == 'High'
        assert qa8.count == 100

    def test_all_resolved_no_qa8(self):
        built = MockBuilt()
        _, incidents = compute_audit_incidents(built, 0, 500, MockConfig())
        qa8 = next((i for i in incidents if i.qa_id == 'QA-8'), None)
        assert qa8 is None

    def test_zero_total_no_qa8(self):
        built = MockBuilt()
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa8 = next((i for i in incidents if i.qa_id == 'QA-8'), None)
        assert qa8 is None


class TestQA9NoInfraMapping:
    """Tests for QA-9: systems without infrastructure mapping."""

    def test_unmapped_triggers_qa9(self):
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = MockBuilt(systems=[s], deployment_map=[])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa9 = next((i for i in incidents if i.qa_id == 'QA-9'), None)
        assert qa9 is not None
        assert qa9.severity == 'Medium'
        assert qa9.count == 1
        assert qa9.affected[0]['name'] == 'EFS'

    def test_mapped_no_qa9(self):
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = MockBuilt(systems=[s], deployment_map=[('channels.efs', 'server_1')])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa9 = next((i for i in incidents if i.qa_id == 'QA-9'), None)
        assert qa9 is None

    def test_unassigned_domain_excluded(self):
        """Systems in 'unassigned' domain should not trigger QA-9."""
        s = System(c4_id='x', name='X', archi_id='s1', metadata={}, domain='unassigned')
        built = MockBuilt(systems=[s], deployment_map=[])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa9 = next((i for i in incidents if i.qa_id == 'QA-9'), None)
        assert qa9 is None

    def test_subsystem_mapped_no_qa9(self):
        """System should not trigger QA-9 when its subsystem has deployment mapping."""
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels',
                   subsystems=[Subsystem(c4_id='core', name='EFS.Core', archi_id='sub1', metadata={})])
        built = MockBuilt(
            systems=[s],
            deployment_map=[('channels.efs.core', 'server_1')],
        )
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa9 = next((i for i in incidents if i.qa_id == 'QA-9'), None)
        assert qa9 is None

    def test_qa9_suppress_excludes(self):
        s = System(c4_id='efs', name='EFS', archi_id='s1', metadata={}, domain='channels')
        built = MockBuilt(systems=[s], deployment_map=[])
        _, incidents = compute_audit_incidents(built, 0, 0,
                                              MockConfig(audit_suppress=['EFS']))
        qa9 = next((i for i in incidents if i.qa_id == 'QA-9'), None)
        assert qa9 is None


class TestQA10DeploymentHierarchy:
    """Tests for QA-10: deployment hierarchy issues."""

    def test_floating_software_triggers_qa10(self):
        """SystemSoftware as root node should trigger QA-10."""
        sw = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                            tech_type='SystemSoftware', kind='infraSoftware')
        built = MockBuilt(deployment_nodes=[sw])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa10 = next((i for i in incidents if i.qa_id == 'QA-10'), None)
        assert qa10 is not None
        assert qa10.severity == 'Medium'
        assert qa10.affected[0]['issue'] == 'SystemSoftware как root-нод (плавающее ПО)'

    def test_unused_location_triggers_qa10(self):
        """Location without children should trigger QA-10."""
        loc = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                             tech_type='Location', kind='infraLocation')
        built = MockBuilt(deployment_nodes=[loc])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa10 = next((i for i in incidents if i.qa_id == 'QA-10'), None)
        assert qa10 is not None
        assert any('Location без дочерних нод' in a['issue'] for a in qa10.affected)

    def test_clean_hierarchy_no_qa10(self):
        """Properly nested hierarchy should NOT trigger QA-10."""
        child = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                               tech_type='Node', kind='infraNode')
        parent = DeploymentNode(c4_id='dc', name='DC', archi_id='loc-1',
                                tech_type='Location', kind='infraLocation',
                                children=[child])
        built = MockBuilt(deployment_nodes=[parent])
        _, incidents = compute_audit_incidents(built, 0, 0, MockConfig())
        qa10 = next((i for i in incidents if i.qa_id == 'QA-10'), None)
        assert qa10 is None
