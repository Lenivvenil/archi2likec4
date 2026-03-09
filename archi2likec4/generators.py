"""Generators: produce LikeC4 .c4 file content from the output model."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .models import (
    AppFunction,
    DataAccess,
    DataEntity,
    DeploymentNode,
    Integration,
    RawRelationship,
    SolutionView,
    Subsystem,
    System,
    _STANDARD_KEYS,
)
from .i18n import get_audit_label, get_msg
from .utils import escape_str

if TYPE_CHECKING:
    from .config import ConvertConfig


# ── Renderers (internal) ────────────────────────────────────────────────

def _render_system(sys: System, lines: list[str], indent: int = 2) -> None:
    pad = ' ' * indent
    title = escape_str(sys.name)
    lines.append(f"{pad}{sys.c4_id} = system '{title}' {{")
    for tag in sys.tags:
        lines.append(f'{pad}  #{tag}')
    if sys.documentation:
        desc = escape_str(sys.documentation)
        if len(desc) > 500:
            desc = desc[:497] + '...'
        lines.append(f"{pad}  description '{desc}'")
    for url, link_title in sys.links:
        lines.append(f"{pad}  link {url} '{escape_str(link_title)}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{sys.archi_id}'")
    for key, value in sys.metadata.items():
        lines.append(f"{pad}    {key} '{escape_str(value)}'")
    if sys.api_interfaces:
        ifaces_str = '; '.join(sys.api_interfaces)
        lines.append(f"{pad}    api_interfaces '{escape_str(ifaces_str)}'")
    lines.append(f'{pad}  }}')
    # Subsystems and functions are rendered in systems/{c4_id}.c4 via extend
    lines.append(f'{pad}}}')


def _render_subsystem(sub: Subsystem, lines: list[str], indent: int = 4) -> None:
    pad = ' ' * indent
    title = escape_str(sub.name)
    lines.append(f"{pad}{sub.c4_id} = subsystem '{title}' {{")
    for tag in sub.tags:
        lines.append(f'{pad}  #{tag}')
    if sub.documentation:
        desc = escape_str(sub.documentation)
        if len(desc) > 500:
            desc = desc[:497] + '...'
        lines.append(f"{pad}  description '{desc}'")
    for url, link_title in sub.links:
        lines.append(f"{pad}  link {url} '{escape_str(link_title)}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{sub.archi_id}'")
    for key, value in sub.metadata.items():
        lines.append(f"{pad}    {key} '{escape_str(value)}'")
    lines.append(f'{pad}  }}')
    # Render nested appFunctions
    if sub.functions:
        lines.append('')
        for fn in sorted(sub.functions, key=lambda f: f.name):
            _render_appfunction(fn, lines, indent=indent + 2)
    lines.append(f'{pad}}}')


def _render_appfunction(fn: AppFunction, lines: list[str], indent: int = 6) -> None:
    pad = ' ' * indent
    title = escape_str(fn.name)
    if fn.documentation:
        desc = escape_str(fn.documentation)
        if len(desc) > 300:
            desc = desc[:297] + '...'
        lines.append(f"{pad}{fn.c4_id} = appFunction '{title}' {{")
        lines.append(f"{pad}  description '{desc}'")
        lines.append(f"{pad}  metadata {{")
        lines.append(f"{pad}    archi_id '{fn.archi_id}'")
        lines.append(f"{pad}  }}")
        lines.append(f'{pad}}}')
    else:
        lines.append(f"{pad}{fn.c4_id} = appFunction '{title}' {{")
        lines.append(f"{pad}  metadata {{")
        lines.append(f"{pad}    archi_id '{fn.archi_id}'")
        lines.append(f"{pad}  }}")
        lines.append(f'{pad}}}')


# ── Generators ───────────────────────────────────────────────────────────

def generate_spec() -> str:
    return """\
specification {

  // ── Colors ──────────────────────────────────────────────
  color archi-app #7EB8DA
  color archi-app-light #BDE0F0
  color archi-data #F0D68A
  color archi-store #B0B0B0

  // ── Business domains ──────────────────────────────────
  element domain {
    style {
      shape rectangle
      color amber
    }
  }

  // ── Application landscape ──────────────────────────────
  element system {
    style {
      shape component
      color archi-app
    }
  }

  element subsystem {
    style {
      shape component
      color archi-app-light
    }
  }

  element appFunction {
    style {
      shape rectangle
      color archi-app-light
    }
  }

  // ── Data layer ─────────────────────────────────────────
  element dataEntity {
    style {
      shape document
      color archi-data
    }
  }

  element dataStore {
    style {
      shape cylinder
      color archi-store
    }
  }

  // ── Infrastructure / Deployment ──────────────────────
  color archi-tech #93D275
  color archi-tech-light #C5E6B8

  element infraNode {
    style {
      shape rectangle
      color archi-tech
    }
  }

  element infraSoftware {
    style {
      shape cylinder
      color archi-tech-light
    }
  }

  element infraLocation {
    style {
      shape rectangle
      color archi-tech
      border dashed
    }
  }

  // ── Relationship kinds ─────────────────────────────────
  relationship persists {
    color archi-store
    line dashed
  }

  relationship deployedOn {
    color archi-tech
    line dashed
  }

  // ── Tags ───────────────────────────────────────────────
  tag to_review
  tag external
  tag entity
  tag store
  tag infrastructure
  tag cluster
  tag device
  tag network
}
"""


def generate_domain_c4(domain_c4_id: str, domain_name: str, systems: list[System]) -> str:
    """Generate a domain .c4 file: domain element with nested systems."""
    lines = [
        f'// ── {domain_name} ──────────────────────────────────────',
        'model {',
        '',
        f"  {domain_c4_id} = domain '{escape_str(domain_name)}' {{",
        '',
    ]
    for sys in sorted(systems, key=lambda s: s.name):
        _render_system(sys, lines, indent=4)
        lines.append('')
    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_system_detail_c4(domain_c4_id: str, sys: System) -> str:
    """Generate systems/{c4_id}.c4 with extend block + scoped detail view.

    The detail view (``view {sys_id}_detail of {domain}.{sys_id}``) enables
    drill-down navigation: clicking a system on the domain-level functional
    view opens this view showing its subsystems and appFunctions.
    """
    full_path = f'{domain_c4_id}.{sys.c4_id}'
    lines = [
        f'// ── {sys.name} (detail) ──────────────────────────────────',
        'model {',
        '',
        f'  extend {full_path} {{',
        '',
    ]

    for sub in sorted(sys.subsystems, key=lambda s: s.name):
        _render_subsystem(sub, lines, indent=4)
        lines.append('')

    # Functions directly on system (no subsystem parent)
    for fn in sorted(sys.functions, key=lambda f: f.name):
        _render_appfunction(fn, lines, indent=4)

    lines.append('  }')
    lines.append('')
    lines.append('}')
    lines.append('')

    # ── Scoped detail view for drill-down navigation ──
    lines.append('views {')
    lines.append('')
    lines.append(f'  view {sys.c4_id}_detail of {full_path} {{')
    lines.append(f"    title '{escape_str(sys.name)}'")
    lines.append(f'    include *')
    lines.append(f'  }}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_relationships(integrations: list[Integration]) -> str:
    """Generate relationships.c4: cross-domain integrations model block."""
    lines = [
        '// ── Cross-domain integrations ──────────────────────────',
        'model {',
        '',
    ]
    if not integrations:
        lines.append('  // No integrations found')
    else:
        for intg in integrations:
            if intg.name:
                label = escape_str(intg.name)
                lines.append(f"  {intg.source_path} -> {intg.target_path} '{label}'")
            else:
                lines.append(f"  {intg.source_path} -> {intg.target_path}")
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_entities(entities: list[DataEntity], data_access: list[DataAccess]) -> str:
    """Generate entities.c4: dataEntity elements + access relationships."""
    lines = [
        '// ── Data Entities ───────────────────────────────────────',
        '//',
        '// Migrated from ArchiMate DataObject as-is.',
        '// Quality is low (Kafka topics, internal structures, etc.).',
        '//',
        '// TODO: Canonical data model (Customer, Account, Loan, etc.)',
        '//       to be designed separately. These migrated entities',
        '//       preserve the original ArchiMate relationships and',
        '//       serve as an inventory for future data governance.',
        '//',
        '// Target pattern (when dataStore is added at container level):',
        '//   dataStore -[persists]-> dataEntity',
        '//',
        '// Current: domain.system -> dataEntity (migrated AccessRelationship)',
        '//',
        '',
        'model {',
        '',
    ]

    if not entities:
        lines.append('  // No data entities found')
    else:
        for entity in entities:
            title = escape_str(entity.name)
            if entity.documentation:
                desc = escape_str(entity.documentation)
                if len(desc) > 300:
                    desc = desc[:297] + '...'
                lines.append(f"  {entity.c4_id} = dataEntity '{title}' {{")
                lines.append(f'    #entity')
                lines.append(f"    description '{desc}'")
                lines.append(f"    metadata {{")
                lines.append(f"      archi_id '{entity.archi_id}'")
                lines.append(f"    }}")
                lines.append(f"  }}")
            else:
                lines.append(f"  {entity.c4_id} = dataEntity '{title}' {{")
                lines.append(f'    #entity')
                lines.append(f"    metadata {{")
                lines.append(f"      archi_id '{entity.archi_id}'")
                lines.append(f"    }}")
                lines.append(f"  }}")
            lines.append('')

    # Access relationships (migrated from ArchiMate AccessRelationship)
    if data_access:
        lines.append('  // ── System → DataEntity access (migrated from ArchiMate) ──')
        lines.append('  // These represent which systems work with which data entities.')
        lines.append('  // To be replaced by: dataStore -[persists]-> dataEntity')
        lines.append('  // when container/store level is modeled.')
        lines.append('')
        for da in data_access:
            if da.name:
                label = escape_str(da.name)
                lines.append(f"  {da.system_path} -> {da.entity_id} '{label}'")
            else:
                lines.append(f"  {da.system_path} -> {da.entity_id}")
        lines.append('')

    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_landscape_view() -> str:
    """Generate the top-level landscape view."""
    return """\
views {

  view index {
    title 'Application Landscape'
    include *
    exclude * where kind is dataEntity
  }

}
"""


def generate_domain_functional_view(domain_c4_id: str, domain_name: str) -> str:
    """Generate a domain functional architecture view.

    Shows only system-level elements inside the domain.  Each system is
    clickable and navigates to its own detail view that shows subsystems
    and appFunctions.
    """
    return f"""\
views {{

  view {domain_c4_id}_functional of {domain_c4_id} {{
    title '{escape_str(domain_name)} - Functional Architecture'
    include *
    exclude * where kind is subsystem
    exclude * where kind is appFunction
    exclude * where kind is dataEntity
  }}

}}
"""


def generate_domain_integration_view(domain_c4_id: str, domain_name: str) -> str:
    """Generate a domain integration architecture view."""
    return f"""\
views {{

  view {domain_c4_id}_integration of {domain_c4_id} {{
    title '{escape_str(domain_name)} - Integration Architecture'
    include
      {domain_c4_id},
      -> {domain_c4_id} ->
  }}

}}
"""


def generate_persistence_map() -> str:
    """Generate persistence-map view."""
    return """\
// ── Persistence Map ────────────────────────────────────────
//
// Shows which systems access which data entities.
// To be refined when dataStore (container level) is modeled:
//   - Add dataStore elements inside systems
//   - Replace system -> dataEntity with dataStore -[persists]-> dataEntity
//   - Use 'include element.kind = dataStore' for focused views
//

views {

  view persistence_map {
    title 'Data Persistence Map'
    include
      element.kind = system,
      element.kind = dataEntity,
      * -> element.kind = dataEntity
  }

}
"""


def generate_solution_views(
    solution_views: list[SolutionView],
    archi_to_c4: dict[str, str],
    sys_domain: dict[str, str],
    relationships: list[RawRelationship] | None = None,
    promoted_archi_to_c4: dict[str, list[str]] | None = None,
    tech_archi_to_c4: dict[str, str] | None = None,
) -> tuple[dict[str, str], int, int]:
    """Generate solution view .c4 files.

    Returns (files, total_unresolved, total_elements) where:
      - files: dict filename → file content string
      - total_unresolved: count of diagram elements that could not be resolved
      - total_elements: total diagram elements processed
    Groups functional and integration views for the same solution into one file.
    Uses actual diagram relationships for integration views when available.
    When a promoted parent archi_id appears, fans out to all children.
    """
    # Build relationship lookup: rel_archi_id → (source_archi_id, target_archi_id, rel_type)
    rel_lookup: dict[str, tuple[str, str, str]] = {}
    # Structural rel types excluded from integration views (consistent with build_integrations)
    _structural_types = {'CompositionRelationship', 'RealizationRelationship', 'AssignmentRelationship'}
    if relationships:
        for rel in relationships:
            rel_lookup[rel.rel_id] = (rel.source_id, rel.target_id, rel.rel_type)
    # Group views by solution slug
    by_solution: dict[str, list[SolutionView]] = {}
    for sv in solution_views:
        by_solution.setdefault(sv.solution, []).append(sv)

    files: dict[str, str] = {}
    used_view_ids: set[str] = set()
    total_unresolved = 0
    total_elements = 0
    for solution_slug, views in sorted(by_solution.items()):
        lines = [
            f'// ── Solution: {views[0].name.split(".", 1)[-1] if "." in views[0].name else views[0].name} ──',
            '',
            'views {',
            '',
        ]

        for sv in sorted(views, key=lambda v: v.view_type):
            # Resolve element archi_ids to c4 paths
            c4_paths: list[str] = []
            unresolved = 0
            total_elements += len(sv.element_archi_ids)
            system_c4_ids: set[str] = set()  # track unique systems
            for aid in sv.element_archi_ids:
                c4_path = archi_to_c4.get(aid)
                if c4_path:
                    c4_paths.append(c4_path)
                    # Extract system c4_id (domain.system → system)
                    parts = c4_path.split('.')
                    if len(parts) >= 2:
                        system_c4_ids.add(parts[1])
                elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
                    # Fan-out: promoted parent → all children
                    for child_path in promoted_archi_to_c4[aid]:
                        c4_paths.append(child_path)
                        parts = child_path.split('.')
                        if len(parts) >= 2:
                            system_c4_ids.add(parts[1])
                else:
                    unresolved += 1
            total_unresolved += unresolved

            if not c4_paths and sv.view_type != 'deployment':
                continue

            # Deduplicate paths
            unique_paths = list(dict.fromkeys(c4_paths))

            view_id = f'{sv.view_type}_{solution_slug}'
            if view_id in used_view_ids:
                suffix = 2
                while f'{view_id}_{suffix}' in used_view_ids:
                    suffix += 1
                view_id = f'{view_id}_{suffix}'
            used_view_ids.add(view_id)
            view_type_labels = {'functional': 'Functional', 'integration': 'Integration', 'deployment': 'Deployment'}
            view_type_label = view_type_labels.get(sv.view_type, sv.view_type.title())
            solution_label = sv.name.split('.', 1)[-1] if '.' in sv.name else sv.name
            title = f'{view_type_label} Architecture: {solution_label}'

            if sv.view_type == 'functional':
                # Functional view: include specific elements (systems + children)
                # Find unique system-level paths (domain.system)
                system_paths: list[str] = []
                seen_sys: set[str] = set()
                for p in unique_paths:
                    parts = p.split('.')
                    if len(parts) >= 2:
                        sys_path = f'{parts[0]}.{parts[1]}'
                        if sys_path not in seen_sys:
                            seen_sys.add(sys_path)
                            system_paths.append(sys_path)

                if len(system_paths) == 1:
                    # Scoped view for a single system
                    lines.append(f"  view {view_id} of {system_paths[0]} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append(f"    include *")
                    lines.append(f"  }}")
                else:
                    # Multi-system view with explicit includes
                    lines.append(f"  view {view_id} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append(f"    include")
                    for sp in system_paths:
                        lines.append(f"      {sp},")
                        lines.append(f"      {sp}.*,")
                    # Remove trailing comma from last line
                    if lines[-1].endswith(','):
                        lines[-1] = lines[-1][:-1]
                    lines.append(f"  }}")

            elif sv.view_type == 'integration':
                # Integration view: system-level with specific relationships from diagram
                system_paths = []
                seen_sys = set()
                for p in unique_paths:
                    parts = p.split('.')
                    if len(parts) >= 2:
                        sys_path = f'{parts[0]}.{parts[1]}'
                        if sys_path not in seen_sys:
                            seen_sys.add(sys_path)
                            system_paths.append(sys_path)

                # Resolve diagram relationships to system-level pairs
                rel_pairs: list[tuple[str, str]] = []
                seen_pairs: set[tuple[str, str]] = set()
                for rel_id in sv.relationship_archi_ids:
                    if rel_id not in rel_lookup:
                        continue
                    src_aid, tgt_aid, rtype = rel_lookup[rel_id]
                    # Skip structural relationships (same filter as build_integrations)
                    if rtype in _structural_types or rtype == 'AccessRelationship':
                        continue
                    # Resolve endpoints (fan out promoted parents)
                    src_c4_list: list[str] = []
                    if src_aid in archi_to_c4:
                        src_c4_list = [archi_to_c4[src_aid]]
                    elif promoted_archi_to_c4 and src_aid in promoted_archi_to_c4:
                        src_c4_list = promoted_archi_to_c4[src_aid]

                    tgt_c4_list: list[str] = []
                    if tgt_aid in archi_to_c4:
                        tgt_c4_list = [archi_to_c4[tgt_aid]]
                    elif promoted_archi_to_c4 and tgt_aid in promoted_archi_to_c4:
                        tgt_c4_list = promoted_archi_to_c4[tgt_aid]

                    if not src_c4_list or not tgt_c4_list:
                        continue

                    # Cross-product, lifted to system level (domain.system)
                    for src_c4 in src_c4_list:
                        src_parts = src_c4.split('.')
                        src_sys = f'{src_parts[0]}.{src_parts[1]}' if len(src_parts) >= 2 else src_c4
                        for tgt_c4 in tgt_c4_list:
                            tgt_parts = tgt_c4.split('.')
                            tgt_sys = f'{tgt_parts[0]}.{tgt_parts[1]}' if len(tgt_parts) >= 2 else tgt_c4
                            if src_sys == tgt_sys:
                                continue
                            pair = (src_sys, tgt_sys)
                            if pair not in seen_pairs:
                                seen_pairs.add(pair)
                                rel_pairs.append(pair)

                lines.append(f"  view {view_id} {{")
                lines.append(f"    title '{escape_str(title)}'")
                lines.append(f"    include")
                for sp in system_paths:
                    lines.append(f"      {sp},")
                if rel_pairs:
                    # Use specific relationship pairs from diagram
                    for src, tgt in rel_pairs:
                        lines.append(f"      {src} -> {tgt},")
                else:
                    # Fallback: no resolved relationships, use broad predicates
                    for sp in system_paths:
                        lines.append(f"      {sp} -> *,")
                        lines.append(f"      * -> {sp},")
                # Remove trailing comma
                if lines[-1].endswith(','):
                    lines[-1] = lines[-1][:-1]
                lines.append(f"  }}")

            elif sv.view_type == 'deployment':
                # Deployment view: resolve element IDs via tech_archi_to_c4
                resolved_paths: list[str] = []
                for aid in sv.element_archi_ids:
                    if tech_archi_to_c4 and aid in tech_archi_to_c4:
                        resolved_paths.append(tech_archi_to_c4[aid])
                    elif aid in archi_to_c4:
                        resolved_paths.append(archi_to_c4[aid])
                resolved_unique = list(dict.fromkeys(resolved_paths))
                if resolved_unique:
                    lines.append(f"  view {view_id} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append(f"    include")
                    for rp in resolved_unique:
                        lines.append(f"      {rp},")
                        lines.append(f"      {rp}.*,")
                    if lines[-1].endswith(','):
                        lines[-1] = lines[-1][:-1]
                    lines.append(f"  }}")

            lines.append('')

        lines.append('}')
        lines.append('')
        # Only emit file if it contains at least one view block
        content = '\n'.join(lines)
        if '  view ' in content:
            files[solution_slug] = content

    if total_unresolved:
        _logger = logging.getLogger('archi2likec4')
        resolved = total_elements - total_unresolved
        ratio = total_unresolved / total_elements if total_elements else 0
        _logger.warning('%d/%d diagram element(s) could not be resolved '
                        '(%.0f%% unresolved, %d resolved)',
                        total_unresolved, total_elements, ratio * 100, resolved)
    return files, total_unresolved, total_elements


# ── Deployment generators ───────────────────────────────────────────────

def _render_deployment_node(node: DeploymentNode, lines: list[str], indent: int) -> None:
    """Recursively render a DeploymentNode and its children."""
    pad = ' ' * indent
    title = escape_str(node.name)
    lines.append(f"{pad}{node.c4_id} = {node.kind} '{title}' {{")
    if node.documentation:
        desc = escape_str(node.documentation)
        if len(desc) > 500:
            desc = desc[:497] + '...'
        lines.append(f"{pad}  description '{desc}'")
    lines.append(f'{pad}  metadata {{')
    lines.append(f"{pad}    archi_id '{node.archi_id}'")
    lines.append(f"{pad}    tech_type '{node.tech_type}'")
    lines.append(f'{pad}  }}')
    for child in sorted(node.children, key=lambda c: c.name):
        lines.append('')
        _render_deployment_node(child, lines, indent + 2)
    lines.append(f'{pad}}}')


def generate_deployment_c4(nodes: list[DeploymentNode]) -> str:
    """Generate deployment/topology.c4 with infrastructure nodes and containers."""
    lines = [
        '// ── Deployment Topology ──────────────────────────────────',
        'model {',
        '',
    ]
    for node in sorted(nodes, key=lambda n: n.name):
        _render_deployment_node(node, lines, indent=2)
        lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_deployment_mapping_c4(mapping: list[tuple[str, str]]) -> str:
    """Generate deployment/mapping.c4 with app→infrastructure relationships."""
    lines = [
        '// ── Deployment Mapping (App → Infrastructure) ────────────',
        'model {',
        '',
    ]
    for app_path, node_id in sorted(mapping):
        lines.append(f'  {app_path} -[deployedOn]-> {node_id}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_datastore_mapping_c4(links: list[tuple[str, str]]) -> str:
    """Generate deployment/datastore-mapping.c4 with dataStore→dataEntity relationships."""
    lines = [
        '// ── DataStore → DataEntity (persistence layer) ─────────────',
        'model {',
        '',
    ]
    for store_path, entity_id in sorted(links):
        lines.append(f'  {store_path} -[persists]-> {entity_id}')
    lines.append('')
    lines.append('}')
    lines.append('')
    return '\n'.join(lines)


def generate_deployment_view() -> str:
    """Generate views/deployment-architecture.c4."""
    return """\
views {

  view deployment_architecture {
    title 'Deployment Architecture'

    include
      element.kind = infraLocation,
      element.kind = infraNode,
      element.kind = infraSoftware,
      element.kind = dataStore
  }

}
"""


# ── Audit report ──────────────────────────────────────────────────────────

# Human-readable field labels for metadata completeness table
_FIELD_LABELS: dict[str, str] = {
    'ci': 'CI',
    'full_name': 'Full name',
    'lc_stage': 'LC stage',
    'criticality': 'Criticality',
    'target_state': 'Target state',
    'business_owner_dep': 'Business owner',
    'dev_team': 'Dev team',
    'architect': 'Architect',
    'is_officer': 'IS-officer',
    'placement': 'Placement',
}


def generate_audit_md(
    built: object,
    sv_unresolved: int,
    sv_total: int,
    config: ConvertConfig,
) -> str:
    """Generate AUDIT.md — quality incident register for ArchiMate repository owners.

    Each section is a discrete quality incident with:
    - Problem description
    - Impact assessment
    - Step-by-step remediation in Archi
    - Table of affected elements

    Sections with 0 affected elements are omitted.
    """
    from . import __version__

    lang: str = getattr(config, 'language', 'ru')
    systems: list[System] = built.systems  # type: ignore[attr-defined]
    # Flat list of all systems + subsystems for metadata/doc checks
    all_sys: list[System | Subsystem] = []
    for s in systems:
        all_sys.append(s)
        all_sys.extend(s.subsystems)

    # Suppress-list: system names accepted as risks, excluded from tables
    suppress: set[str] = set(getattr(config, 'audit_suppress', []))

    total_sys = len(systems)
    sections: list[str] = []
    qa_num = 0
    suppressed_total = 0

    # ── Header ────────────────────────────────────────────────────────
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    header = (
        f'# {get_audit_label("title", lang)}\n\n'
        f'> {get_audit_label("auto_generated", lang, version=__version__, date=now)}\n'
        f'> {get_audit_label("fix_prompt", lang)}\n'
    )

    # ── Summary ───────────────────────────────────────────────────────
    unassigned: list[System] = built.domain_systems.get('unassigned', [])  # type: ignore[attr-defined]
    unassigned_count = len(unassigned)
    assigned_count = total_sys - unassigned_count

    # Metadata completeness
    meta_filled_total = 0
    meta_check_keys = [k for k in _STANDARD_KEYS if k != 'full_name']  # full_name always set
    meta_possible = len(all_sys) * len(meta_check_keys)
    for s in all_sys:
        for key in meta_check_keys:
            if s.metadata.get(key, 'TBD') != 'TBD':
                meta_filled_total += 1
    meta_pct = round(meta_filled_total / meta_possible * 100) if meta_possible else 100

    deployment_map: list = built.deployment_map  # type: ignore[attr-defined]
    mapped_sys_paths = {pair[0] for pair in deployment_map}

    _L = lambda k: get_audit_label(k, lang)  # noqa: E731
    summary = (
        f'## {_L("summary_heading")}\n\n'
        f'| {_L("metric")} | {_L("value")} |\n'
        '|---------|----------|\n'
        f'| {_L("systems")} | {total_sys} |\n'
        f'| {_L("subsystems")} | {sum(len(s.subsystems) for s in systems)} |\n'
        f'| {_L("meta_completeness")} | {meta_pct}% |\n'
        f'| {_L("domain_assigned")} | {assigned_count} / {total_sys} ({round(assigned_count / total_sys * 100) if total_sys else 0}%) |\n'
        f'| {_L("integrations")} | {len(built.integrations)} |\n'  # type: ignore[attr-defined]
        f'| {_L("data_entities")} | {len(built.entities)} |\n'  # type: ignore[attr-defined]
        f'| {_L("deploy_mappings")} | {len(deployment_map)} |\n'
    )

    # ── QA-1: Unassigned systems ──────────────────────────────────────
    filtered_unassigned = [s for s in unassigned if s.name not in suppress]
    suppressed_total += unassigned_count - len(filtered_unassigned)
    if filtered_unassigned:
        qa_num += 1
        rows = []
        for i, s in enumerate(sorted(filtered_unassigned, key=lambda x: x.name), 1):
            tags = ', '.join(s.tags) if s.tags else ''
            rows.append(f'| {i} | {s.name} | {tags} |')
        table = '\n'.join(rows)
        sections.append(
            f'## QA-{qa_num}. [Critical] Системы без домена ({len(filtered_unassigned)})\n\n'
            f'**Проблема:** {len(filtered_unassigned)} систем не размещены ни на одной диаграмме '
            'в `functional_areas/`. Конвертер помещает их в домен «unassigned».\n\n'
            '**Влияние:** Системы не отображаются в доменных views, невозможно '
            'понять их бизнес-принадлежность.\n\n'
            '**Рекомендация:**\n'
            '1. Откройте Archi → Views → functional_areas\n'
            '2. Для каждой системы из таблицы определите целевой домен\n'
            '3. Перетащите элемент на соответствующую диаграмму домена\n\n'
            '| # | Система | Теги |\n'
            '|---|---------|------|\n'
            f'{table}\n'
        )

    # ── QA-2: Metadata gaps ───────────────────────────────────────────
    # Per-field completeness
    field_stats: list[tuple[str, int, int]] = []
    for key in meta_check_keys:
        filled = sum(1 for s in all_sys if s.metadata.get(key, 'TBD') != 'TBD')
        field_stats.append((key, filled, len(all_sys)))

    # Systems with most TBD fields
    sys_tbd: list[tuple[str, str, int]] = []
    for s in all_sys:
        if s.name in suppress:
            continue
        tbd_count = sum(1 for key in meta_check_keys if s.metadata.get(key, 'TBD') == 'TBD')
        if tbd_count > 0:
            domain = s.domain if hasattr(s, 'domain') and s.domain else ''
            sys_tbd.append((s.name, domain, tbd_count))
    sys_tbd.sort(key=lambda x: (-x[2], x[0]))

    all_tbd_count = sum(1 for _, _, c in sys_tbd if c == len(meta_check_keys))

    if all_tbd_count > 0:
        qa_num += 1
        field_rows = []
        for key, filled, total in field_stats:
            label = _FIELD_LABELS.get(key, key)
            pct = round(filled / total * 100) if total else 0
            field_rows.append(f'| {label} | {filled} / {total} | {pct}% |')
        field_table = '\n'.join(field_rows)

        top_n = min(20, len(sys_tbd))
        top_rows = []
        for i, (name, domain, tbd_cnt) in enumerate(sys_tbd[:top_n], 1):
            top_rows.append(f'| {i} | {name} | {domain} | {tbd_cnt} / {len(meta_check_keys)} |')
        top_table = '\n'.join(top_rows)

        sections.append(
            f'## QA-{qa_num}. [High] Незаполненные карточки систем\n\n'
            f'**Проблема:** {all_tbd_count} из {len(all_sys)} систем/подсистем не имеют '
            'ни одного заполненного свойства (CI, Criticality, LC stage и др.).\n\n'
            '**Влияние:** Метаданные в архитектурном портале отображаются как '
            '«TBD» — невозможно оценить критичность, ответственных, стадию ЖЦ.\n\n'
            '**Рекомендация:**\n'
            '1. Откройте элемент в Archi → вкладка Properties\n'
            '2. Заполните как минимум: CI, Criticality, Dev team\n'
            '3. Приоритет — системы с наибольшим числом пустых полей (см. таблицу)\n\n'
            '**Заполненность по полям:**\n\n'
            '| Поле | Заполнено | % |\n'
            '|------|-----------|---|\n'
            f'{field_table}\n\n'
            f'**Топ-{top_n} систем с максимальным числом пустых полей:**\n\n'
            '| # | Система | Домен | Пустых полей |\n'
            '|---|---------|-------|--------------|\n'
            f'{top_table}\n'
        )

    # ── QA-3: To-review systems ───────────────────────────────────────
    to_review = [s for s in systems if 'to_review' in s.tags and s.name not in suppress]
    if to_review:
        qa_num += 1
        rows = []
        for i, s in enumerate(sorted(to_review, key=lambda x: x.name), 1):
            domain = s.domain or 'unassigned'
            rows.append(f'| {i} | {s.name} | {domain} |')
        table = '\n'.join(rows)
        sections.append(
            f'## QA-{qa_num}. [High] Системы на разборе ({len(to_review)})\n\n'
            '**Проблема:** Эти системы находятся в папке `!РАЗБОР` — '
            'их статус в модели не определён.\n\n'
            '**Влияние:** Системы помечены тегом `#to_review` и требуют '
            'решения: оставить в модели или удалить.\n\n'
            '**Рекомендация:**\n'
            '1. Для каждой системы определите, является ли она актуальной\n'
            '2. Если актуальна — переместите из `!РАЗБОР` в правильную папку\n'
            '3. Если не актуальна — удалите элемент из модели\n\n'
            '| # | Система | Домен |\n'
            '|---|---------|-------|\n'
            f'{table}\n'
        )

    # ── QA-4: Promote candidates ──────────────────────────────────────
    promote_threshold = getattr(config, 'promote_warn_threshold', 10)
    already_promoted = set(getattr(config, 'promote_children', {}).keys())
    candidates = [
        (s.name, len(s.subsystems))
        for s in systems
        if len(s.subsystems) >= promote_threshold and s.name not in already_promoted
        and s.name not in suppress
    ]
    candidates.sort(key=lambda x: (-x[1], x[0]))
    if candidates:
        qa_num += 1
        rows = []
        for i, (name, cnt) in enumerate(candidates, 1):
            rows.append(f'| {i} | {name} | {cnt} |')
        table = '\n'.join(rows)
        sections.append(
            f'## QA-{qa_num}. [Medium] Кандидаты на декомпозицию ({len(candidates)})\n\n'
            f'**Проблема:** {len(candidates)} систем имеют ≥{promote_threshold} '
            'подсистем — вероятно, их дочерние компоненты являются самостоятельными '
            'микросервисами.\n\n'
            '**Влияние:** Интеграции всех подсистем схлопываются в одну стрелку '
            'родителя, теряется детализация.\n\n'
            '**Рекомендация:**\n'
            '1. Добавьте систему в `promote_children` в `.archi2likec4.yaml`\n'
            '2. Укажите целевой домен: `promote_children: { "Parent": "domain" }`\n'
            '3. Перезапустите конвертер — подсистемы станут самостоятельными системами\n\n'
            '| # | Система | Подсистем |\n'
            '|---|---------|----------|\n'
            f'{table}\n'
        )

    # ── QA-5: No documentation ────────────────────────────────────────
    no_docs = [s for s in systems if not s.documentation and s.name not in suppress]
    if no_docs:
        qa_num += 1
        show = sorted(no_docs, key=lambda x: x.name)[:30]
        rows = []
        for i, s in enumerate(show, 1):
            domain = s.domain or 'unassigned'
            rows.append(f'| {i} | {s.name} | {domain} |')
        table = '\n'.join(rows)
        suffix = f' (показаны первые 30 из {len(no_docs)})' if len(no_docs) > 30 else ''
        sections.append(
            f'## QA-{qa_num}. [Medium] Системы без документации ({len(no_docs)})\n\n'
            '**Проблема:** Эти системы не имеют описания в поле `documentation`.\n\n'
            '**Влияние:** В архитектурном портале отсутствует описание назначения '
            'системы — затруднено понимание её роли.\n\n'
            '**Рекомендация:**\n'
            '1. Откройте элемент в Archi → поле Documentation\n'
            '2. Добавьте краткое описание назначения системы (1-2 предложения)\n\n'
            f'| # | Система | Домен |{suffix}\n'
            '|---|---------|-------|\n'
            f'{table}\n'
        )

    # ── QA-6: Orphan functions ────────────────────────────────────────
    orphan_fns: int = built.orphan_fns  # type: ignore[attr-defined]
    if orphan_fns > 0:
        qa_num += 1
        sections.append(
            f'## QA-{qa_num}. [Low] Осиротевшие функции ({orphan_fns})\n\n'
            f'**Проблема:** {orphan_fns} ApplicationFunction не имеют привязки '
            'к родительскому ApplicationComponent.\n\n'
            '**Влияние:** Функции не отображаются ни в одной системе — '
            'потеряна часть функциональной архитектуры.\n\n'
            '**Рекомендация:**\n'
            '1. Найдите осиротевшие функции в Archi (проверьте лог конвертера с `--verbose`)\n'
            '2. Для каждой добавьте CompositionRelationship к целевому ApplicationComponent\n'
            '3. Или переместите XML-файл функции в папку целевого компонента\n'
        )

    # ── QA-7: Lost integrations ───────────────────────────────────────
    total_flow_rels = sum(
        1 for r in built.relationships  # type: ignore[attr-defined]
        if r.rel_type in ('FlowRelationship', 'ServingRelationship', 'TriggeringRelationship')
    )
    resolved_intg = len(built.integrations)  # type: ignore[attr-defined]
    skipped_intg = total_flow_rels - resolved_intg
    if skipped_intg > 0:
        qa_num += 1
        pct = round(skipped_intg / total_flow_rels * 100) if total_flow_rels else 0
        sections.append(
            f'## QA-{qa_num}. [Critical] Потерянные интеграции ({skipped_intg})\n\n'
            f'**Проблема:** {skipped_intg} из {total_flow_rels} интеграционных связей '
            f'({pct}%) не удалось разрешить — один или оба endpoint не найдены в модели.\n\n'
            '**Влияние:** Часть интеграций между системами не отображается — '
            'неполная картина взаимодействий.\n\n'
            '**Рекомендация:**\n'
            '1. Запустите конвертер с `--verbose` для детального лога\n'
            '2. Проверьте, что source и target каждой связи — валидные ApplicationComponent\n'
            '3. Убедитесь, что связи не ведут на удалённые или перемещённые элементы\n'
        )

    # ── QA-8: Solution view coverage ──────────────────────────────────
    if sv_total > 0 and sv_unresolved > 0:
        qa_num += 1
        sv_resolved = sv_total - sv_unresolved
        sv_pct = round(sv_resolved / sv_total * 100)
        sections.append(
            f'## QA-{qa_num}. [High] Покрытие solution views ({sv_pct}%)\n\n'
            f'**Проблема:** {sv_unresolved} из {sv_total} элементов на solution-диаграммах '
            f'не удалось сопоставить с C4-моделью (разрешено {sv_resolved}, '
            f'не разрешено {sv_unresolved}).\n\n'
            '**Влияние:** Solution views могут отображать неполную картину — '
            'часть элементов диаграмм теряется при конвертации.\n\n'
            '**Рекомендация:**\n'
            '1. Проверьте, что все элементы на solution-диаграммах — '
            'валидные ApplicationComponent\n'
            '2. Удалите с диаграмм элементы других типов (BusinessService, '
            'TechnologyService и т.д.)\n'
            '3. Убедитесь, что элементы не удалены из модели, '
            'но остались на диаграммах как «призраки»\n'
        )

    # ── QA-9: No infrastructure mapping ───────────────────────────────
    unmapped = [s for s in systems if f'{s.domain}.{s.c4_id}' not in mapped_sys_paths
                and s.domain and s.domain != 'unassigned'
                and s.name not in suppress]
    if unmapped:
        qa_num += 1
        show = sorted(unmapped, key=lambda x: x.name)[:30]
        rows = []
        for i, s in enumerate(show, 1):
            rows.append(f'| {i} | {s.name} | {s.domain} |')
        table = '\n'.join(rows)
        suffix = f' (показаны первые 30 из {len(unmapped)})' if len(unmapped) > 30 else ''
        sections.append(
            f'## QA-{qa_num}. [Medium] Системы без инфраструктурной привязки ({len(unmapped)})\n\n'
            f'**Проблема:** {len(unmapped)} систем не имеют связи с инфраструктурными '
            'нодами (Node, SystemSoftware).\n\n'
            '**Влияние:** На deployment view не видно, где развёрнуты эти системы.\n\n'
            '**Рекомендация:**\n'
            '1. Откройте систему в Archi\n'
            '2. Создайте RealizationRelationship к целевому Node '
            '(серверу, кластеру, VM)\n'
            '3. Или добавьте AssignmentRelationship, если используете этот тип\n\n'
            f'| # | Система | Домен |{suffix}\n'
            '|---|---------|-------|\n'
            f'{table}\n'
        )

    # ── QA-10: Deployment hierarchy issues ─────────────────────────
    deployment_nodes: list[DeploymentNode] = built.deployment_nodes  # type: ignore[attr-defined]
    if deployment_nodes:
        from .builders import _flatten_deployment_nodes
        all_dn = _flatten_deployment_nodes(deployment_nodes)
        qa10_issues: list[tuple[str, str, str]] = []  # (name, kind, issue)

        for dn in deployment_nodes:
            if dn.kind == 'infraSoftware':
                qa10_issues.append((dn.name, dn.kind, 'SystemSoftware как root-нод'))

        locations = [dn for dn in all_dn if dn.kind == 'infraLocation']
        if locations:
            for loc in locations:
                if not loc.children:
                    qa10_issues.append((loc.name, loc.kind, 'Location без дочерних нод'))
            location_child_ids: set[str] = set()
            for loc in locations:
                for child in loc.children:
                    location_child_ids.add(child.archi_id)
            for dn in deployment_nodes:
                if dn.kind == 'infraNode' and dn.archi_id not in location_child_ids:
                    qa10_issues.append((dn.name, dn.kind, 'Root Node без привязки к Location'))

        if qa10_issues:
            qa_num += 1
            rows = []
            for i, (name, kind, issue) in enumerate(qa10_issues, 1):
                rows.append(f'| {i} | {name} | {kind} | {issue} |')
            table = '\n'.join(rows)
            sections.append(
                f'## QA-{qa_num}. [Medium] Проблемы иерархии развёртывания ({len(qa10_issues)})\n\n'
                f'**Проблема:** {len(qa10_issues)} проблем в deployment-топологии.\n\n'
                '**Влияние:** Deployment view показывает неструктурированную топологию — '
                'невозможно определить физическое размещение.\n\n'
                '**Рекомендация:**\n'
                '1. SystemSoftware должен быть вложен в Node (AggregationRelationship)\n'
                '2. Location должен содержать хотя бы один Node\n'
                '3. Root Node должен быть вложен в Location\n\n'
                '| # | Элемент | Kind | Проблема |\n'
                '|---|---------|------|----------|\n'
                f'{table}\n'
            )

    # ── Assemble ──────────────────────────────────────────────────────
    suppress_note = (f' Исключено из отчёта (audit_suppress): {suppressed_total} элементов.'
                     if suppressed_total else '')
    if not sections:
        return (
            header + '\n'
            + summary + '\n'
            + f'Инцидентов качества не обнаружено.{suppress_note}\n'
        )

    body = '\n---\n\n'.join(sections)
    footer = (f'\n---\n\n*Всего инцидентов: {qa_num}.{suppress_note} '
              f'Сгенерировано archi2likec4 v{__version__}.*\n')
    return header + '\n' + summary + '\n---\n\n' + body + footer
