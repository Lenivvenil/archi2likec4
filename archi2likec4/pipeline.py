"""Pipeline: main() orchestration — parse, map, generate."""

import shutil
import sys
from pathlib import Path

from .models import EXTRA_DOMAIN_PATTERNS, PROMOTE_CHILDREN, DomainInfo
from .parsers import (
    parse_application_components,
    parse_application_functions,
    parse_application_interfaces,
    parse_data_objects,
    parse_domain_mapping,
    parse_relationships,
    parse_solution_views,
)
from .builders import (
    apply_domain_prefix,
    assign_domains,
    attach_functions,
    attach_interfaces,
    build_archi_to_c4_map,
    build_data_access,
    build_data_entities,
    build_integrations,
    build_systems,
)
from .generators import (
    generate_domain_c4,
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_entities,
    generate_landscape_view,
    generate_persistence_map,
    generate_relationships,
    generate_solution_views,
    generate_spec,
    generate_system_detail_c4,
)
from .federation import generate_federate_script, generate_federation_registry


def main():
    import argparse
    parser = argparse.ArgumentParser(
        prog='archi2likec4',
        description='Convert coArchi XML repository to LikeC4 .c4 files',
    )
    parser.add_argument('model_root', nargs='?', default='architectural_repository/model',
                        help='Path to coArchi model directory (default: architectural_repository/model)')
    parser.add_argument('output_dir', nargs='?', default='output',
                        help='Output directory for .c4 files (default: output)')
    args = parser.parse_args()
    model_root = Path(args.model_root)
    output_dir = Path(args.output_dir)

    print('archi2likec4 — Iteration 5: appFunction + solution views')
    print(f'  Input:  {model_root}')
    print(f'  Output: {output_dir}')
    print()

    # ── Parse ──────────────────────────────────────────────
    print('Parsing ApplicationComponents...')
    components = parse_application_components(model_root)
    print(f'  Found {len(components)} ApplicationComponent elements')

    print('Parsing ApplicationFunctions...')
    functions = parse_application_functions(model_root)
    print(f'  Found {len(functions)} ApplicationFunction elements')

    print('Parsing ApplicationInterfaces...')
    interfaces = parse_application_interfaces(model_root)
    print(f'  Found {len(interfaces)} ApplicationInterface elements')

    print('Parsing DataObjects...')
    data_objects = parse_data_objects(model_root)
    print(f'  Found {len(data_objects)} DataObject elements')

    print('Parsing relationships...')
    relationships = parse_relationships(model_root)
    print(f'  Found {len(relationships)} relevant relationships')

    print('Parsing domain mapping from views...')
    domains_info = parse_domain_mapping(model_root)
    for d in domains_info:
        print(f'  {d.name}: {len(d.archi_ids)} AppComponent refs on views')

    print('Parsing solution views...')
    solution_views = parse_solution_views(model_root)
    func_views = sum(1 for v in solution_views if v.view_type == 'functional')
    integ_views = sum(1 for v in solution_views if v.view_type == 'integration')
    print(f'  Found {len(solution_views)} solution views ({func_views} functional, {integ_views} integration)')

    # ── Map ────────────────────────────────────────────────
    print('Building system hierarchy...')
    systems, promoted_parents = build_systems(components)
    total_subsystems = sum(len(s.subsystems) for s in systems)
    print(f'  {len(systems)} systems, {total_subsystems} subsystems')

    print('Attaching functions to systems/subsystems...')
    orphan_fns = attach_functions(systems, functions, relationships, promoted_parents)
    total_attached = sum(
        len(s.functions) + sum(len(sub.functions) for sub in s.subsystems)
        for s in systems
    )
    print(f'  {total_attached} functions attached, {orphan_fns} orphans')

    # Collect all used IDs (to avoid collisions with data entities)
    all_ids: set[str] = set()
    for s in systems:
        all_ids.add(s.c4_id)
        for sub in s.subsystems:
            all_ids.add(f'{s.c4_id}.{sub.c4_id}')

    print('Building data entities...')
    entities = build_data_entities(data_objects, all_ids)
    print(f'  {len(entities)} data entities')

    print('Attaching interfaces...')
    iface_c4_path = attach_interfaces(systems, interfaces, relationships)
    linked = sum(1 for s in systems if s.api_interfaces)
    print(f'  {len(iface_c4_path)} interfaces attached to {linked} systems')

    print('Building integrations...')
    integrations = build_integrations(systems, relationships, iface_c4_path, promoted_parents)
    print(f'  {len(integrations)} unique system-to-system integrations')

    print('Building data access relationships...')
    data_access = build_data_access(systems, entities, relationships, promoted_parents)
    print(f'  {len(data_access)} system-to-entity access links')

    print('Assigning systems to domains...')
    domain_systems = assign_domains(systems, domains_info, PROMOTE_CHILDREN)
    for d_id, d_sys_list in domain_systems.items():
        if d_sys_list:
            print(f'  {d_id}: {len(d_sys_list)} systems')

    # Build sys_id → domain_id map for prefixing paths
    sys_domain: dict[str, str] = {s.c4_id: s.domain for s in systems}

    # Apply domain prefix to integrations and data access paths
    apply_domain_prefix(integrations, data_access, sys_domain)

    # Build complete archi_id → c4_path map (for solution views)
    archi_to_c4 = build_archi_to_c4_map(systems, sys_domain, iface_c4_path)
    print(f'  {len(archi_to_c4)} elements in archi→c4 map')

    # Build promoted parent → full c4 paths map (for solution views fan-out)
    promoted_archi_to_c4: dict[str, list[str]] = {}
    for parent_aid, child_c4_ids in promoted_parents.items():
        paths = []
        for c4_id in child_c4_ids:
            domain = sys_domain.get(c4_id, 'unassigned')
            paths.append(f'{domain}.{c4_id}')
        promoted_archi_to_c4[parent_aid] = paths

    # ── Generate ───────────────────────────────────────────
    print('Generating files...')

    # Clean & create dirs (with safety checks)
    if output_dir.exists():
        resolved = output_dir.resolve()
        # Guard against dangerous paths
        if resolved == Path.cwd().resolve() or resolved == Path.home().resolve():
            raise SystemExit(f'FATAL: refusing to rmtree dangerous path: {resolved}')
        if resolved == Path('/') or str(resolved).count('/') <= 1:
            raise SystemExit(f'FATAL: refusing to rmtree root-level path: {resolved}')
        if not (resolved / 'specification.c4').exists() and any(resolved.iterdir()):
            raise SystemExit(
                f'FATAL: {resolved} does not look like a converter output dir '
                f'(missing specification.c4). Refusing to delete.')
        shutil.rmtree(resolved)
    output_dir.mkdir(parents=True, exist_ok=True)
    domains_dir = output_dir / 'domains'
    domains_dir.mkdir(exist_ok=True)
    systems_dir = output_dir / 'systems'
    systems_dir.mkdir(exist_ok=True)
    views_dir = output_dir / 'views'
    views_dir.mkdir(exist_ok=True)
    views_domains_dir = views_dir / 'domains'
    views_domains_dir.mkdir(exist_ok=True)
    views_solutions_dir = views_dir / 'solutions'
    views_solutions_dir.mkdir(exist_ok=True)
    scripts_dir = output_dir / 'scripts'
    scripts_dir.mkdir(exist_ok=True)

    file_count = 0

    # Root files
    (output_dir / 'specification.c4').write_text(generate_spec(), encoding='utf-8')
    file_count += 1
    (output_dir / 'relationships.c4').write_text(generate_relationships(integrations), encoding='utf-8')
    file_count += 1
    (output_dir / 'entities.c4').write_text(generate_entities(entities, data_access), encoding='utf-8')
    file_count += 1

    # Domain files + views
    all_domain_meta: dict[str, DomainInfo] = {d.c4_id: d for d in domains_info}
    for extra in EXTRA_DOMAIN_PATTERNS:
        if extra['c4_id'] not in all_domain_meta:
            all_domain_meta[extra['c4_id']] = DomainInfo(
                c4_id=extra['c4_id'], name=extra['name'])
    if domain_systems.get('unassigned'):
        all_domain_meta['unassigned'] = DomainInfo(c4_id='unassigned', name='Unassigned')

    domain_count = 0
    view_count = 0
    system_detail_count = 0

    for domain_id, domain_sys_list in domain_systems.items():
        if not domain_sys_list:
            continue
        d_info = all_domain_meta.get(domain_id)
        if not d_info:
            continue

        # Domain model file
        (domains_dir / f'{domain_id}.c4').write_text(
            generate_domain_c4(domain_id, d_info.name, domain_sys_list),
            encoding='utf-8')
        file_count += 1
        domain_count += 1

        # System detail files (extend blocks with subsystems + functions)
        for s in domain_sys_list:
            if s.subsystems or s.functions:
                (systems_dir / f'{s.c4_id}.c4').write_text(
                    generate_system_detail_c4(domain_id, s),
                    encoding='utf-8')
                file_count += 1
                system_detail_count += 1

        # Domain view files
        domain_views_dir = views_domains_dir / domain_id
        domain_views_dir.mkdir(exist_ok=True)
        (domain_views_dir / 'functional.c4').write_text(
            generate_domain_functional_view(domain_id, d_info.name),
            encoding='utf-8')
        file_count += 1
        view_count += 1
        (domain_views_dir / 'integration.c4').write_text(
            generate_domain_integration_view(domain_id, d_info.name),
            encoding='utf-8')
        file_count += 1
        view_count += 1

    # Solution views (functional + integration from Archi diagrams)
    solution_view_files, sv_unresolved, sv_total = generate_solution_views(
        solution_views, archi_to_c4, sys_domain, relationships,
        promoted_archi_to_c4=promoted_archi_to_c4,
    )
    for sol_slug, content in solution_view_files.items():
        (views_solutions_dir / f'{sol_slug}.c4').write_text(content, encoding='utf-8')
        file_count += 1
        view_count += 1
    print(f'  {len(solution_view_files)} solution view files generated')
    if sv_total > 0:
        sv_ratio = sv_unresolved / sv_total
        if sv_ratio > 0.5:
            print(f'  ERROR: {sv_unresolved}/{sv_total} ({sv_ratio:.0%}) solution view elements '
                  f'unresolved — likely data model mismatch')
            sys.exit(1)

    # Top-level views
    (views_dir / 'landscape.c4').write_text(generate_landscape_view(), encoding='utf-8')
    file_count += 1
    view_count += 1
    (views_dir / 'persistence-map.c4').write_text(generate_persistence_map(), encoding='utf-8')
    file_count += 1
    view_count += 1

    # Scripts
    (scripts_dir / 'federate.py').write_text(generate_federate_script(), encoding='utf-8')
    file_count += 1
    (scripts_dir / 'federation-registry.yaml').write_text(
        generate_federation_registry(), encoding='utf-8')
    file_count += 1

    print(f'  {file_count} files written to {output_dir}/')
    print(f'    specification.c4, relationships.c4, entities.c4')
    print(f'    domains/ ({domain_count} .c4 files)')
    print(f'    systems/ ({system_detail_count} .c4 detail files)')
    print(f'    views/ ({view_count} view files)')
    print(f'    scripts/ (federate.py + federation-registry.yaml)')
    print()
    print('Done! Run: cd output && npx likec4 serve')
