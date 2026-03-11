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
)
from .i18n import get_audit_label
from .utils import escape_str

if TYPE_CHECKING:
    from .config import ConvertConfig


# Maximum description length before truncation (characters).
_MAX_DESC_LEN = 500
_MAX_FN_DESC_LEN = 300

# ── Renderers (internal) ────────────────────────────────────────────────

def _render_system(sys: System, lines: list[str], indent: int = 2) -> None:
    pad = ' ' * indent
    title = escape_str(sys.name)
    lines.append(f"{pad}{sys.c4_id} = system '{title}' {{")
    for tag in sys.tags:
        lines.append(f'{pad}  #{tag}')
    if sys.documentation:
        desc = escape_str(sys.documentation)
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
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
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
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
        if len(desc) > _MAX_FN_DESC_LEN:
            desc = desc[:_MAX_FN_DESC_LEN - 3] + '...'
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
      shape rectangle
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
    """Generate the top-level landscape view.

    Shows only domain→system nesting. Subsystems and appFunctions are
    excluded to keep the landscape readable — they are accessible via
    drill-down into per-system detail views.
    """
    return """\
views {

  view index {
    title 'Application Landscape'
    include *
    exclude * where kind is subsystem
    exclude * where kind is appFunction
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
    fn_archi_ids: set[str] | None = None,
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
            system_c4_ids: set[str] = set()  # track unique systems

            if sv.view_type == 'deployment':
                # Deployment views resolve via tech_archi_to_c4, not archi_to_c4
                # Skip appFunction elements — only systems/subsystems are relevant
                infra_c4_paths: set[str] = set()  # paths needing .* wildcard
                relevant_ids = [aid for aid in sv.element_archi_ids
                                if not (fn_archi_ids and aid in fn_archi_ids)]
                total_elements += len(relevant_ids)
                for aid in relevant_ids:
                    if tech_archi_to_c4 and aid in tech_archi_to_c4:
                        path = tech_archi_to_c4[aid]
                        c4_paths.append(path)
                        infra_c4_paths.add(path)
                    elif aid in archi_to_c4:
                        c4_paths.append(archi_to_c4[aid])
                    else:
                        unresolved += 1
            else:
                total_elements += len(sv.element_archi_ids)
                for aid in sv.element_archi_ids:
                    c4_path = archi_to_c4.get(aid)
                    if c4_path:
                        c4_paths.append(c4_path)
                        parts = c4_path.split('.')
                        if len(parts) >= 2:
                            system_c4_ids.add(parts[1])
                        # single-segment paths (e.g. dataEntity) are top-level
                    elif promoted_archi_to_c4 and aid in promoted_archi_to_c4:
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
            base_title = f'{view_type_label} Architecture: {solution_label}'
            # Add folder hierarchy to title for LikeC4 navigation tree
            if sv.folder_display_path:
                title = f'{sv.folder_display_path} / {base_title}'
            else:
                title = base_title

            if sv.view_type == 'functional':
                # Functional view: include specific elements (systems + children)
                # Find unique system-level paths (domain.system) and top-level elements
                system_paths: list[str] = []
                toplevel_paths: list[str] = []
                seen_sys: set[str] = set()
                for p in unique_paths:
                    parts = p.split('.')
                    if len(parts) >= 2:
                        sys_path = f'{parts[0]}.{parts[1]}'
                        if sys_path not in seen_sys:
                            seen_sys.add(sys_path)
                            system_paths.append(sys_path)
                    elif len(parts) == 1 and p not in seen_sys:
                        seen_sys.add(p)
                        toplevel_paths.append(p)

                if len(system_paths) == 1 and not toplevel_paths:
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
                    for tp in toplevel_paths:
                        lines.append(f"      {tp},")
                    # Remove trailing comma from last line
                    if lines[-1].endswith(','):
                        lines[-1] = lines[-1][:-1]
                    lines.append(f"  }}")

            elif sv.view_type == 'integration':
                # Integration view: system-level with specific relationships from diagram
                system_paths = []
                toplevel_paths = []
                seen_sys = set()
                for p in unique_paths:
                    parts = p.split('.')
                    if len(parts) >= 2:
                        sys_path = f'{parts[0]}.{parts[1]}'
                        if sys_path not in seen_sys:
                            seen_sys.add(sys_path)
                            system_paths.append(sys_path)
                    elif len(parts) == 1 and p not in seen_sys:
                        seen_sys.add(p)
                        toplevel_paths.append(p)

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
                for tp in toplevel_paths:
                    lines.append(f"      {tp},")
                if rel_pairs:
                    # Use specific relationship pairs from diagram
                    for src, tgt in rel_pairs:
                        lines.append(f"      {src} -> {tgt},")
                # Remove trailing comma
                if lines[-1].endswith(','):
                    lines[-1] = lines[-1][:-1]
                lines.append(f"  }}")

            elif sv.view_type == 'deployment':
                # Deployment view: c4_paths already resolved via tech_archi_to_c4 above
                resolved_unique = list(dict.fromkeys(c4_paths))
                if resolved_unique:
                    lines.append(f"  view {view_id} {{")
                    lines.append(f"    title '{escape_str(title)}'")
                    lines.append(f"    include")
                    for rp in resolved_unique:
                        lines.append(f"      {rp},")
                        # Wildcard only for infra elements (resolved via tech_archi_to_c4)
                        # App elements (domain.system.subsystem) must NOT expand
                        # to children — that pulls in appFunction noise
                        if rp in infra_c4_paths:
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
            # Use folder_path from first view to build nested file key
            folder_path = views[0].folder_path if views[0].folder_path else ''
            file_key = f'{folder_path}/{solution_slug}' if folder_path else solution_slug
            files[file_key] = content

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
        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + '...'
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


def generate_audit_md(
    built: object,
    sv_unresolved: int,
    sv_total: int,
    config: ConvertConfig,
) -> str:
    """Generate AUDIT.md — quality incident register for ArchiMate repository owners.

    Delegates all logic to compute_audit_incidents() (audit_data.py) as the
    single source of truth, then renders results as markdown. Respects
    config.audit_suppress_incidents to skip entire QA categories.
    Fully bilingual (ru/en) via config.language.
    """
    from . import __version__
    from .audit_data import compute_audit_incidents

    lang: str = getattr(config, 'language', 'ru')
    summary, all_incidents = compute_audit_incidents(built, sv_unresolved, sv_total, config)

    # Filter out suppressed and zero-count incidents (keep for suppressed_count tracking)
    incidents = [inc for inc in all_incidents if not inc.suppressed and inc.count > 0]

    _L = lambda k, **kw: get_audit_label(k, lang, **kw)  # noqa: E731

    # ── Header ────────────────────────────────────────────────────────
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    header = (
        f'# {_L("title")}\n\n'
        f'> {_L("auto_generated", version=__version__, date=now)}\n'
        f'> {_L("fix_prompt")}\n'
    )

    # ── Summary table ─────────────────────────────────────────────────
    total_sys = summary.total_systems
    assigned_pct = round(summary.assigned_count / total_sys * 100) if total_sys else 0
    summary_md = (
        f'## {_L("summary_heading")}\n\n'
        f'| {_L("metric")} | {_L("value")} |\n'
        '|---------|----------|\n'
        f'| {_L("systems")} | {total_sys} |\n'
        f'| {_L("subsystems")} | {summary.total_subsystems} |\n'
        f'| {_L("meta_completeness")} | {summary.meta_completeness_pct}% |\n'
        f'| {_L("domain_assigned")} | {summary.assigned_count} / {total_sys} ({assigned_pct}%) |\n'
        f'| {_L("integrations")} | {summary.total_integrations} |\n'
        f'| {_L("data_entities")} | {summary.total_entities} |\n'
        f'| {_L("deploy_mappings")} | {summary.deployment_mappings} |\n'
    )

    # ── Render incident sections ──────────────────────────────────────
    sections: list[str] = []
    suppressed_total = sum(inc.suppressed_count for inc in all_incidents)

    for inc in incidents:
        section = f'## {inc.qa_id}. [{inc.severity}] {inc.title} ({inc.count})\n\n'
        section += f'**{_L("problem")}:** {inc.description}\n\n'
        section += f'**{_L("impact_label")}:** {inc.impact}\n\n'
        section += f'**{_L("recommendation")}:**\n{inc.remediation}\n'

        if inc.affected:
            section += '\n'
            section += _render_affected_table(inc, lang)

        sections.append(section)

    # ── Assemble ──────────────────────────────────────────────────────
    suppressed_qa_ids = [inc.qa_id for inc in all_incidents if inc.suppressed]
    has_suppression = suppressed_total > 0 or suppressed_qa_ids
    suppress_note = ''
    if suppressed_total > 0:
        suppress_note = _L('suppressed_note', count=suppressed_total)
    if suppressed_qa_ids:
        suppress_note += _L('suppressed_qa_note', ids=', '.join(suppressed_qa_ids))
    if not sections:
        return (
            header + '\n'
            + summary_md + '\n'
            + f'{_L("no_incidents")}{suppress_note}\n'
        )

    body = '\n---\n\n'.join(sections)
    footer_text = _L('footer', qa_num=len(incidents),
                      suppress_note=suppress_note, version=__version__)
    footer = f'\n---\n\n*{footer_text}*\n'
    return header + '\n' + summary_md + '\n---\n\n' + body + footer


def _render_affected_table(inc: 'AuditIncident', lang: str) -> str:
    """Render incident's affected items as a markdown table."""
    _L = lambda k, **kw: get_audit_label(k, lang, **kw)  # noqa: E731

    if not inc.affected:
        return ''

    # Determine columns from first affected item
    keys = list(inc.affected[0].keys())

    # QA-2 has special rendering with field_stats sub-tables
    if inc.qa_id == 'QA-2':
        return _render_qa2_table(inc, lang)

    # QA-10 has element/kind/issue columns
    if inc.qa_id == 'QA-10':
        header = f'| {_L("col_num")} | {_L("col_element")} | {_L("col_kind")} | {_L("col_issue")} |\n'
        header += '|---|---------|------|----------|\n'
        rows = []
        for i, item in enumerate(inc.affected, 1):
            rows.append(f'| {i} | {item.get("name", "")} | {item.get("kind", "")} | {item.get("issue", "")} |')
        return header + '\n'.join(rows) + '\n'

    # Generic table based on keys
    col_map = {
        'name': _L('col_system'),
        'tags': _L('col_tags'),
        'domain': _L('col_domain'),
        'subsystem_count': _L('col_subsystems'),
    }
    col_headers = [_L('col_num')] + [col_map.get(k, k) for k in keys]
    header = '| ' + ' | '.join(col_headers) + ' |\n'
    header += '|' + '|'.join('---' for _ in col_headers) + '|\n'

    shown = inc.affected
    suffix = ''
    if inc.count > len(shown):
        suffix = _L('shown_first', n=len(shown), total=inc.count)

    rows = []
    for i, item in enumerate(shown, 1):
        vals = [str(i)] + [str(item.get(k, '')) for k in keys]
        rows.append('| ' + ' | '.join(vals) + ' |')

    return header + '\n'.join(rows) + suffix + '\n'


def _render_qa2_table(inc: 'AuditIncident', lang: str) -> str:
    """Render QA-2 metadata gap tables (field completeness + top systems)."""
    _L = lambda k, **kw: get_audit_label(k, lang, **kw)  # noqa: E731

    # Top-N systems with most empty fields
    top_n = min(20, len(inc.affected))
    top_header = f'| {_L("col_num")} | {_L("col_system")} | {_L("col_domain")} | {_L("col_empty_fields")} |\n'
    top_header += '|---|---------|-------|--------------|\n'
    rows = []
    for i, item in enumerate(inc.affected[:top_n], 1):
        rows.append(f'| {i} | {item["name"]} | {item.get("domain", "")} '
                    f'| {item["tbd_count"]} / {item.get("total_fields", "")} |')

    return (
        f'\n**{_L("top_systems", n=top_n)}:**\n\n'
        + top_header + '\n'.join(rows) + '\n'
    )
