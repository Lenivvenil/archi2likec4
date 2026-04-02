"""Tests for builders/data.py module."""

from archi2likec4.builders import (
    build_data_access,
    build_data_entities,
    build_datastore_entity_links,
    build_deployment_topology,
)
from archi2likec4.models import (
    DataEntity,
    DataObject,
    DeploymentNode,
    RawRelationship,
    System,
    TechElement,
)


class TestBuildDataEntities:
    def test_basic(self):
        objs = [DataObject(archi_id='do-1', name='Account')]
        entities = build_data_entities(objs, set())
        assert len(entities) == 1
        assert entities[0].c4_id == 'de_account'

    def test_unique_ids(self):
        objs = [
            DataObject(archi_id='do-1', name='Account'),
            DataObject(archi_id='do-2', name='Account'),
        ]
        entities = build_data_entities(objs, set())
        ids = [e.c4_id for e in entities]
        assert len(set(ids)) == 2

    def test_avoids_used_ids(self):
        objs = [DataObject(archi_id='do-1', name='Account')]
        used = {'de_account'}
        entities = build_data_entities(objs, used)
        assert entities[0].c4_id == 'de_account_2'


# ── assign_domains ───────────────────────────────────────────────────────

class TestDataAccessFanOut:
    """Tests for promoted parent fan-out in build_data_access."""

    def test_source_fans_out_to_all_children(self):
        """Data access from promoted parent → entity fans out to all children."""
        sys_a = System(c4_id='child_a', name='P.A', archi_id='id-a')
        sys_b = System(c4_id='child_b', name='P.B', archi_id='id-b')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='reads',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        promoted = {'id-parent': ['child_a', 'child_b']}
        accesses = build_data_access([sys_a, sys_b], [entity], rels, promoted)
        paths = sorted(da.system_path for da in accesses)
        assert 'child_a' in paths
        assert 'child_b' in paths

    def test_no_fanout_without_promoted(self):
        """Without promoted_parents, unresolvable endpoints are skipped."""
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='reads',
                source_type='ApplicationComponent', source_id='id-parent',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        accesses = build_data_access([], [entity], rels)
        assert len(accesses) == 0


# ── Deployment topology ─────────────────────────────────────────────────

class TestDataStoreDetection:
    def test_postgresql_becomes_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='PostgreSQL 15', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_oracle_becomes_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Oracle DB', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_redis_becomes_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Redis Cluster', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_mongo_becomes_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Mongo DB', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_nginx_stays_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Nginx', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_eureka_stays_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Eureka', tech_type='TechnologyService')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_node_never_datastore(self):
        """Even if Node name contains 'database', it stays a compute kind (server)."""
        elems = [TechElement(archi_id='n-1', name='Database Server', tech_type='Node')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'server'

    def test_stage_db_becomes_infrasoftware(self):
        elems = [TechElement(archi_id='sw-1', name='Stage DB', tech_type='SystemSoftware')]
        roots = build_deployment_topology(elems, [])
        assert roots[0].kind == 'infraSoftware'

    def test_unknown_tech_type_fallback_kind(self):
        """Elements with known tech_types get their mapped kinds."""
        elems = [
            TechElement(archi_id='tf-1', name='Backup Job', tech_type='TechnologyFunction'),
            TechElement(archi_id='tp-1', name='ETL Process', tech_type='TechnologyProcess'),
            TechElement(archi_id='ti-1', name='Sync', tech_type='TechnologyInteraction'),
        ]
        roots = build_deployment_topology(elems, [])
        by_name = {r.name: r for r in roots}
        # TechnologyFunction/TechnologyProcess → vm (mapped kind)
        assert by_name['Backup Job'].kind == 'vm'
        assert by_name['ETL Process'].kind == 'vm'
        # TechnologyInteraction → cluster
        assert by_name['Sync'].kind == 'cluster'

    def test_node_named_like_db_stays_compute(self):
        """Node with DB-like name stays a compute kind — Node/Device are always containers."""
        elems = [
            TechElement(archi_id='n-1', name='PostgreSQL Cluster', tech_type='Node'),
            TechElement(archi_id='d-1', name='Oracle Database Server', tech_type='Device'),
        ]
        roots = build_deployment_topology(elems, [])
        by_name = {r.name: r for r in roots}
        assert by_name['PostgreSQL Cluster'].kind == 'server'  # top-level Node → server
        assert by_name['Oracle Database Server'].kind == 'server'  # Device → server

    def test_db_named_systemsoftware_becomes_infrasoftware(self):
        """DB-named SystemSoftware elements become infraSoftware regardless of name."""
        for name in ['POSTGRESQL', 'postgreSQL', 'PostgreSQL', 'postgresql']:
            elems = [TechElement(archi_id='sw-1', name=name, tech_type='SystemSoftware')]
            roots = build_deployment_topology(elems, [])
            assert roots[0].kind == 'infraSoftware', f'{name} should be infraSoftware'

    def test_all_systemsoftware_names_become_infrasoftware(self):
        """All SystemSoftware elements become infraSoftware regardless of name."""
        names = [
            'Nginx', 'Eureka', 'Consul', 'HAProxy', 'Apache HTTP',
            'RabbitMQ', 'Kafka', 'MinIO', 'Zookeeper', 'Prometheus',
        ]
        for name in names:
            elems = [TechElement(archi_id='sw-1', name=name, tech_type='SystemSoftware')]
            roots = build_deployment_topology(elems, [])
            assert roots[0].kind == 'infraSoftware', f'{name} should be infraSoftware'


# ── build_datastore_entity_links ─────────────────────────────────────────


class TestBuildDatastoreEntityLinks:
    def test_access_relationship_creates_link(self):
        """AccessRelationship SystemSoftware→DataObject creates dataStore→entity link."""
        child = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                               tech_type='SystemSoftware', kind='infraSoftware')
        parent = DeploymentNode(c4_id='srv', name='Server', archi_id='n-1',
                                tech_type='Node', children=[child])
        entities = [DataEntity(c4_id='de_users', name='Users', archi_id='do-1')]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_datastore_entity_links([parent], entities, rels)
        assert len(result) == 1
        assert result[0] == ('srv.pg', 'de_users')

    def test_no_access_relationships(self):
        child = DeploymentNode(c4_id='pg', name='PostgreSQL', archi_id='sw-1',
                               tech_type='SystemSoftware', kind='infraSoftware')
        entities = [DataEntity(c4_id='de_users', name='Users', archi_id='do-1')]
        result = build_datastore_entity_links([child], entities, [])
        assert result == []

    def test_empty_inputs(self):
        assert build_datastore_entity_links([], [], []) == []

    def test_reverse_direction(self):
        """DataObject→SystemSoftware direction also works."""
        node = DeploymentNode(c4_id='redis', name='Redis', archi_id='sw-1',
                              tech_type='SystemSoftware', kind='infraSoftware')
        entities = [DataEntity(c4_id='de_cache', name='Cache', archi_id='do-1')]
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='DataObject', source_id='do-1',
                target_type='SystemSoftware', target_id='sw-1',
            ),
        ]
        result = build_datastore_entity_links([node], entities, rels)
        assert len(result) == 1
        assert result[0] == ('redis', 'de_cache')


# ── assign_subdomains ────────────────────────────────────────────────────

class TestBuildDataAccessEdgeCases:
    """Tests for build_data_access edge cases — skipping, reverse direction, dedup."""

    def test_non_access_relationship_skipped(self):
        """Non-AccessRelationship is silently skipped."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='flow',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_data_access([sys], [entity], rels)
        assert result == []

    def test_reverse_direction_data_object_to_component(self):
        """DataObject→ApplicationComponent direction creates data access."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='reads',
                source_type='DataObject', source_id='do-1',
                target_type='ApplicationComponent', target_id='sys-1',
            ),
        ]
        result = build_data_access([sys], [entity], rels)
        assert len(result) == 1
        assert result[0].system_path == 'crm'
        assert result[0].entity_id == 'de_account'

    def test_unknown_entity_skipped(self):
        """AccessRelationship with unknown DataObject archi_id is skipped."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='do-unknown',
            ),
        ]
        result = build_data_access([sys], [entity], rels)
        assert result == []

    def test_direct_path_resolution(self):
        """Component directly resolved via comp_c4_path (not promoted)."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='writes',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_data_access([sys], [entity], rels)
        assert len(result) == 1
        assert result[0].system_path == 'crm'

    def test_duplicate_pair_deduplicated(self):
        """Same (system, entity, name) pair from two rels only produces one DataAccess."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='do-1',
            ),
            RawRelationship(
                rel_id='r-2', rel_type='AccessRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_data_access([sys], [entity], rels)
        assert len(result) == 1

    def test_other_type_pair_skipped(self):
        """AccessRelationship between non-Component/DataObject types is skipped."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        entity = DataEntity(c4_id='de_account', name='Account', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='Node', source_id='n-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_data_access([sys], [entity], rels)
        assert result == []


class TestBuildDatastoreEntityLinksEdgeCases:
    """Tests for build_datastore_entity_links edge cases."""

    def test_non_access_relationship_skipped(self):
        """Non-AccessRelationship is skipped in datastore link building."""
        node = DeploymentNode(c4_id='pg', name='PG', archi_id='sw-1',
                              tech_type='SystemSoftware', kind='infraSoftware')
        entity = DataEntity(c4_id='de_users', name='Users', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='FlowRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_datastore_entity_links([node], [entity], rels)
        assert result == []

    def test_non_sw_do_types_skipped(self):
        """AccessRelationship between non-SystemSoftware/DataObject types is skipped."""
        node = DeploymentNode(c4_id='pg', name='PG', archi_id='sw-1',
                              tech_type='SystemSoftware', kind='infraSoftware')
        entity = DataEntity(c4_id='de_users', name='Users', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='ApplicationComponent', source_id='sys-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_datastore_entity_links([node], [entity], rels)
        assert result == []

    def test_unresolvable_sw_or_entity_skipped(self):
        """When SystemSoftware not in deployment tree or entity unknown, pair is skipped."""
        node = DeploymentNode(c4_id='pg', name='PG', archi_id='sw-1',
                              tech_type='SystemSoftware', kind='infraSoftware')
        entity = DataEntity(c4_id='de_users', name='Users', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-unknown',
                target_type='DataObject', target_id='do-1',
            ),
            RawRelationship(
                rel_id='r-2', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='do-unknown',
            ),
        ]
        result = build_datastore_entity_links([node], [entity], rels)
        assert result == []

    def test_duplicate_pairs_deduplicated(self):
        """Same (tech_path, entity_c4_id) pair from multiple rels produces one result."""
        node = DeploymentNode(c4_id='pg', name='PG', archi_id='sw-1',
                              tech_type='SystemSoftware', kind='infraSoftware')
        entity = DataEntity(c4_id='de_users', name='Users', archi_id='do-1')
        rels = [
            RawRelationship(
                rel_id='r-1', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='do-1',
            ),
            RawRelationship(
                rel_id='r-2', rel_type='AccessRelationship', name='',
                source_type='SystemSoftware', source_id='sw-1',
                target_type='DataObject', target_id='do-1',
            ),
        ]
        result = build_datastore_entity_links([node], [entity], rels)
        assert len(result) == 1


# ── build_comp_c4_path ───────────────────────────────────────────────────

