"""Tests for archi2likec4.models — dataclasses, constants, mapping tables."""

from archi2likec4.models import (
    NS,
    AppComponent,
    AppFunction,
    AppInterface,
    DataAccess,
    DataEntity,
    DataObject,
    DeploymentNode,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    RawRelationship,
    SolutionView,
    Subdomain,
    Subsystem,
    System,
    TechElement,
)

# ── Constants ──────────────────────────────────────────────────────────────

class TestNS:
    def test_has_archimate_key(self):
        assert 'archimate' in NS

    def test_archimate_namespace_value(self):
        assert NS['archimate'] == 'http://www.archimatetool.com/archimate'


# ── Simple dataclasses ─────────────────────────────────────────────────────

class TestAppComponent:
    def test_required_fields(self):
        c = AppComponent(archi_id='a-1', name='MyApp')
        assert c.archi_id == 'a-1'
        assert c.name == 'MyApp'

    def test_defaults(self):
        c = AppComponent(archi_id='a-1', name='MyApp')
        assert c.documentation == ''
        assert c.properties == {}
        assert c.source_folder == ''

    def test_mutable_defaults_not_shared(self):
        c1 = AppComponent(archi_id='a-1', name='A')
        c2 = AppComponent(archi_id='a-2', name='B')
        c1.properties['key'] = 'val'
        assert c2.properties == {}


class TestAppInterface:
    def test_required_fields(self):
        i = AppInterface(archi_id='i-1', name='REST API')
        assert i.archi_id == 'i-1'
        assert i.name == 'REST API'
        assert i.documentation == ''


class TestDataObject:
    def test_construction(self):
        d = DataObject(archi_id='do-1', name='Account')
        assert d.archi_id == 'do-1'
        assert d.name == 'Account'
        assert d.documentation == ''


class TestRawRelationship:
    def test_all_fields_required(self):
        r = RawRelationship(
            rel_id='r-1', rel_type='FlowRelationship', name='data flow',
            source_type='ApplicationComponent', source_id='s-1',
            target_type='ApplicationComponent', target_id='t-1',
        )
        assert r.rel_id == 'r-1'
        assert r.rel_type == 'FlowRelationship'
        assert r.source_id == 's-1'
        assert r.target_id == 't-1'


class TestAppFunction:
    def test_required_fields(self):
        f = AppFunction(archi_id='fn-1', name='DoStuff')
        assert f.archi_id == 'fn-1'
        assert f.name == 'DoStuff'

    def test_defaults(self):
        f = AppFunction(archi_id='fn-1', name='DoStuff')
        assert f.c4_id == ''
        assert f.documentation == ''
        assert f.parent_archi_id == ''


class TestSubsystem:
    def test_required_fields(self):
        s = Subsystem(c4_id='sub1', name='SubName', archi_id='s-1')
        assert s.c4_id == 'sub1'

    def test_defaults(self):
        s = Subsystem(c4_id='sub1', name='SubName', archi_id='s-1')
        assert s.documentation == ''
        assert s.metadata == {}
        assert s.tags == []
        assert s.links == []
        assert s.functions == []


class TestSystem:
    def test_construction(self):
        s = System(c4_id='sys1', name='SysName', archi_id='a-1')
        assert s.c4_id == 'sys1'
        assert s.name == 'SysName'
        assert s.archi_id == 'a-1'

    def test_defaults(self):
        s = System(c4_id='sys1', name='SysName', archi_id='a-1')
        assert s.documentation == ''
        assert s.metadata == {}
        assert s.tags == []
        assert s.subsystems == []
        assert s.links == []
        assert s.functions == []
        assert s.api_interfaces == []
        assert s.domain == ''
        assert s.subdomain == ''
        assert s.extra_archi_ids == []

    def test_mutable_defaults_not_shared(self):
        s1 = System(c4_id='s1', name='A', archi_id='a-1')
        s2 = System(c4_id='s2', name='B', archi_id='a-2')
        s1.tags.append('tag')
        assert s2.tags == []


class TestParsedSubdomain:
    def test_construction(self):
        ps = ParsedSubdomain(archi_id='ps-1', name='Payments', domain_folder='channels')
        assert ps.archi_id == 'ps-1'
        assert ps.name == 'Payments'
        assert ps.domain_folder == 'channels'
        assert ps.component_ids == []


class TestSubdomain:
    def test_construction(self):
        sd = Subdomain(c4_id='sd1', name='Cards', domain_id='channels')
        assert sd.c4_id == 'sd1'
        assert sd.system_ids == []


class TestDomainInfo:
    def test_construction(self):
        di = DomainInfo(c4_id='d1', name='Channels')
        assert di.c4_id == 'd1'
        assert di.name == 'Channels'
        assert di.archi_ids == set()

    def test_archi_ids_is_set(self):
        di = DomainInfo(c4_id='d1', name='D', archi_ids={'a-1', 'a-2'})
        assert len(di.archi_ids) == 2


class TestDataEntity:
    def test_construction(self):
        de = DataEntity(c4_id='de1', name='Account', archi_id='do-1')
        assert de.c4_id == 'de1'
        assert de.documentation == ''


class TestIntegration:
    def test_construction(self):
        intg = Integration(
            source_path='channels.alpha', target_path='core.beta',
            name='sync', rel_type='FlowRelationship',
        )
        assert intg.source_path == 'channels.alpha'
        assert intg.target_path == 'core.beta'


class TestDataAccess:
    def test_construction(self):
        da = DataAccess(system_path='channels.efs', entity_id='de1', name='reads')
        assert da.system_path == 'channels.efs'
        assert da.entity_id == 'de1'


class TestSolutionView:
    def test_construction(self):
        sv = SolutionView(name='Auto_1.0', view_type='functional', solution='auto')
        assert sv.name == 'Auto_1.0'
        assert sv.view_type == 'functional'
        assert sv.solution == 'auto'

    def test_defaults(self):
        sv = SolutionView(name='X', view_type='integration', solution='x')
        assert sv.element_archi_ids == []
        assert sv.relationship_archi_ids == []
        assert sv.visual_nesting == []


class TestTechElement:
    def test_construction(self):
        te = TechElement(archi_id='n-1', name='Server 1', tech_type='Node')
        assert te.archi_id == 'n-1'
        assert te.tech_type == 'Node'
        assert te.documentation == ''


class TestDeploymentNode:
    def test_construction(self):
        dn = DeploymentNode(
            c4_id='node1', name='Server 1', archi_id='n-1', tech_type='Node',
        )
        assert dn.c4_id == 'node1'
        assert dn.kind == 'infraNode'
        assert dn.children == []

    def test_nested_children(self):
        child = DeploymentNode(c4_id='child1', name='Child', archi_id='n-2', tech_type='Node')
        parent = DeploymentNode(
            c4_id='parent1', name='Parent', archi_id='n-1', tech_type='Node',
            children=[child],
        )
        assert len(parent.children) == 1
        assert parent.children[0].c4_id == 'child1'

    def test_kind_options(self):
        for kind in ('infraNode', 'infraZone', 'infraSoftware', 'infraLocation'):
            dn = DeploymentNode(
                c4_id='n', name='N', archi_id='a', tech_type='Node', kind=kind,
            )
            assert dn.kind == kind
