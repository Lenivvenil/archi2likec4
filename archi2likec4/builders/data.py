"""Builders: data entities, data access, and datastore-entity links."""

import logging

from ..models import (
    DataAccess,
    DataEntity,
    DataObject,
    DeploymentNode,
    RawRelationship,
    System,
)
from ..utils import make_id, make_unique_id
from ._paths import build_comp_c4_path, build_deployment_path_index

logger = logging.getLogger(__name__)


def build_data_entities(data_objects: list[DataObject], used_ids: set[str]) -> list[DataEntity]:
    """Convert DataObject to DataEntity with unique IDs (prefixed de_)."""
    entities: list[DataEntity] = []
    for do in data_objects:
        c4_id = make_unique_id(make_id(do.name, prefix='de'), used_ids)
        used_ids.add(c4_id)
        entities.append(DataEntity(
            c4_id=c4_id, name=do.name, archi_id=do.archi_id,
            documentation=do.documentation,
        ))
    return sorted(entities, key=lambda e: e.name)


def build_data_access(  # noqa: C901
    systems: list[System],
    entities: list[DataEntity],
    relationships: list[RawRelationship],
    promoted_parents: dict[str, list[str]] | None = None,
) -> list[DataAccess]:
    """Resolve AccessRelationship: AppComponent → DataObject.

    When a relationship references a promoted parent, fan out to ALL children
    so each child gets a separate data access link.
    """
    comp_c4_path = build_comp_c4_path(systems)

    entity_by_archi: dict[str, DataEntity] = {e.archi_id: e for e in entities}

    results: list[DataAccess] = []
    seen: set[tuple[str, str, str]] = set()
    skipped = 0

    for rel in relationships:
        if rel.rel_type != 'AccessRelationship':
            continue

        # Determine component and entity from relationship direction
        comp_id: str | None = None
        entity: DataEntity | None = None
        if rel.source_type == 'ApplicationComponent' and rel.target_type == 'DataObject':
            comp_id = rel.source_id
            entity = entity_by_archi.get(rel.target_id)
        elif rel.source_type == 'DataObject' and rel.target_type == 'ApplicationComponent':
            comp_id = rel.target_id
            entity = entity_by_archi.get(rel.source_id)
        else:
            continue

        if not entity:
            skipped += 1
            continue

        # Resolve component to c4 paths (fan-out for promoted parents)
        sys_paths: list[str] = []
        if comp_id:
            path = comp_c4_path.get(comp_id)
            if path:
                sys_paths = [path]
            elif promoted_parents and comp_id in promoted_parents:
                sys_paths = list(promoted_parents[comp_id])

        if not sys_paths:
            skipped += 1
            continue

        name = rel.name.strip() if rel.name else ''

        for sp in sys_paths:
            sys_id = sp.split('.')[0]
            pair = (sys_id, entity.c4_id, name)
            if pair in seen:
                continue
            seen.add(pair)
            results.append(DataAccess(
                system_path=sys_id, entity_id=entity.c4_id,
                name=name,
            ))

    if skipped:
        logger.info('Skipped %d data access(es) with unresolvable endpoints', skipped)

    return sorted(results, key=lambda d: (d.system_path, d.entity_id))


def build_datastore_entity_links(
    deployment_nodes: list[DeploymentNode],
    entities: list[DataEntity],
    relationships: list[RawRelationship],
) -> list[tuple[str, str]]:
    """Build (infra_c4_path, dataEntity_c4_id) pairs.

    Links infrastructure software nodes (infraSoftware) to DataEntity via
    AccessRelationship between SystemSoftware and DataObject.  The resulting
    pairs are written to datastore-mapping.c4 as ``persists`` relationships.
    """
    if not deployment_nodes or not entities:
        return []

    tech_path = build_deployment_path_index(deployment_nodes)
    entity_by_archi = {e.archi_id: e for e in entities}

    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for rel in relationships:
        if rel.rel_type != 'AccessRelationship':
            continue

        sw_id: str | None = None
        do_id: str | None = None

        if rel.source_type == 'SystemSoftware' and rel.target_type == 'DataObject':
            sw_id, do_id = rel.source_id, rel.target_id
        elif rel.source_type == 'DataObject' and rel.target_type == 'SystemSoftware':
            sw_id, do_id = rel.target_id, rel.source_id
        else:
            continue

        t = tech_path.get(sw_id)
        entity = entity_by_archi.get(do_id)
        if not t or not entity:
            continue

        pair = (t, entity.c4_id)
        if pair not in seen:
            seen.add(pair)
            result.append(pair)

    result.sort()
    return result
