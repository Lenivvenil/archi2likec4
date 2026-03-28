#!/usr/bin/env python3
"""Diagnostic script: orphan data entities, bad solution views, view hierarchy."""

import sys
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter, defaultdict

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archi2likec4.config import load_config
from archi2likec4.pipeline import _parse, _build

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

MODEL_ROOT = Path('architectural_repository/model')
config = load_config(Path('.archi2likec4.yaml'))
config.model_root = MODEL_ROOT.resolve()

print('=' * 80)
print('DIAGNOSTIC: archi2likec4 — orphan entities, bad views, view hierarchy')
print('=' * 80)

# ── Run pipeline ──────────────────────────────────────────────────────────
parsed = _parse(config.model_root, config)
built = _build(parsed, config)

# ══════════════════════════════════════════════════════════════════════════
# PART A: Orphan data entities (0 access links)
# ══════════════════════════════════════════════════════════════════════════
print('\n' + '=' * 80)
print('PART A: ORPHAN DATA ENTITIES (0 access links)')
print('=' * 80)

# Which entities have access links?
entities_with_access = set()
for da in built.data_access:
    entities_with_access.add(da.entity_id)

orphan_entities = [e for e in built.entities if e.c4_id not in entities_with_access]
linked_entities = [e for e in built.entities if e.c4_id in entities_with_access]

print(f'\nTotal data entities: {len(built.entities)}')
print(f'Entities WITH access links: {len(linked_entities)}')
print(f'Orphan entities (0 links): {len(orphan_entities)}')

# Now check WHY they are orphans — do AccessRelationships exist for them in raw rels?
entity_by_archi = {e.archi_id: e for e in built.entities}

# Collect ALL AccessRelationship involving DataObject
all_access_rels = [r for r in parsed.relationships if r.rel_type == 'AccessRelationship']
access_rels_with_dataobj = [
    r for r in all_access_rels
    if r.source_type == 'DataObject' or r.target_type == 'DataObject'
]

print(f'\nTotal AccessRelationship in parsed: {len(all_access_rels)}')
print(f'  involving DataObject: {len(access_rels_with_dataobj)}')

# For each access rel involving a DataObject, check if entity resolves + component resolves
comp_c4_path = {}
for sys in built.systems:
    if sys.archi_id:
        comp_c4_path[sys.archi_id] = sys.c4_id
    for eid in sys.extra_archi_ids:
        comp_c4_path[eid] = sys.c4_id
    for sub in sys.subsystems:
        if sub.archi_id:
            comp_c4_path[sub.archi_id] = f'{sys.c4_id}.{sub.c4_id}'

# Classify access rels
access_stats = Counter()
orphan_archi_ids = {e.archi_id for e in orphan_entities}
# Track which orphan entities have raw relationships that fail
orphan_with_failed_rels = defaultdict(list)  # entity_archi_id -> list of failure reasons

for rel in access_rels_with_dataobj:
    if rel.source_type == 'ApplicationComponent' and rel.target_type == 'DataObject':
        comp_id, do_id = rel.source_id, rel.target_id
    elif rel.source_type == 'DataObject' and rel.target_type == 'ApplicationComponent':
        comp_id, do_id = rel.target_id, rel.source_id
    else:
        # Non AppComponent <-> DataObject access (e.g., SystemSoftware <-> DataObject)
        access_stats['non_appcomp_access'] += 1
        # Check if the DataObject is an orphan entity
        do_id_check = rel.source_id if rel.source_type == 'DataObject' else rel.target_id
        if do_id_check in orphan_archi_ids:
            other_type = rel.target_type if rel.source_type == 'DataObject' else rel.source_type
            orphan_with_failed_rels[do_id_check].append(
                f'AccessRel with {other_type} (not AppComponent) — skipped by build_data_access'
            )
        continue

    entity = entity_by_archi.get(do_id)
    comp_resolved = comp_id in comp_c4_path
    # Also check promoted parents
    comp_promoted = comp_id in built.promoted_parents

    if not entity:
        access_stats['entity_not_found'] += 1
    elif not comp_resolved and not comp_promoted:
        access_stats['comp_not_resolved'] += 1
        if do_id in orphan_archi_ids:
            orphan_with_failed_rels[do_id].append(
                f'AppComponent {comp_id} not in comp_c4_path (not a known system/subsystem)'
            )
    else:
        access_stats['fully_resolved'] += 1

print(f'\nAccessRelationship resolution breakdown (AppComp <-> DataObj):')
for key, count in sorted(access_stats.items()):
    print(f'  {key}: {count}')

# Check: are there AccessRelationships involving DataObjects but NOT AppComponents?
other_access = [
    r for r in all_access_rels
    if not (
        (r.source_type == 'ApplicationComponent' and r.target_type == 'DataObject') or
        (r.source_type == 'DataObject' and r.target_type == 'ApplicationComponent')
    )
]
other_type_pairs = Counter()
for r in other_access:
    pair = f'{r.source_type} -> {r.target_type}'
    other_type_pairs[pair] += 1

if other_type_pairs:
    print(f'\nNon-AppComponent AccessRelationships (skipped by build_data_access):')
    for pair, count in other_type_pairs.most_common():
        print(f'  {pair}: {count}')

# How many orphan entities have relationships that FAILED to resolve?
orphans_with_rels = len(orphan_with_failed_rels)
orphans_truly_zero = len(orphan_entities) - orphans_with_rels
print(f'\nOrphan entity breakdown:')
print(f'  Truly zero relationships in raw data: {orphans_truly_zero}')
print(f'  Have relationships that failed to resolve: {orphans_with_rels}')

if orphan_with_failed_rels:
    print(f'\n  Examples of failed resolutions:')
    for archi_id, reasons in list(orphan_with_failed_rels.items())[:10]:
        entity = entity_by_archi[archi_id]
        print(f'    "{entity.name}" ({archi_id}):')
        for reason in reasons[:3]:
            print(f'      - {reason}')

# List ALL orphan entity names
print(f'\n--- All {len(orphan_entities)} orphan entity names ---')
for i, e in enumerate(sorted(orphan_entities, key=lambda x: x.name), 1):
    # Check if it has any raw relationships at all
    has_raw = e.archi_id in orphan_with_failed_rels
    marker = ' [has failed rels]' if has_raw else ''
    print(f'  {i:3d}. {e.name}{marker}')


# ══════════════════════════════════════════════════════════════════════════
# PART B: Bad solution views — worst 5 by unresolved rate
# ══════════════════════════════════════════════════════════════════════════
print('\n' + '=' * 80)
print('PART B: BAD SOLUTION VIEWS (worst by unresolved rate)')
print('=' * 80)

# Rebuild element type index from parsed data
all_element_types = {}
# Application layer
for ac in parsed.components:
    all_element_types[ac.archi_id] = 'ApplicationComponent'
for iface in parsed.interfaces:
    all_element_types[iface.archi_id] = 'ApplicationInterface'
for do in parsed.data_objects:
    all_element_types[do.archi_id] = 'DataObject'
for fn in parsed.functions:
    all_element_types[fn.archi_id] = 'ApplicationFunction'
# Technology layer
for te in parsed.tech_elements:
    all_element_types[te.archi_id] = te.tech_type

# Also build a name lookup
all_element_names = {}
for ac in parsed.components:
    all_element_names[ac.archi_id] = ac.name
for iface in parsed.interfaces:
    all_element_names[iface.archi_id] = iface.name
for do in parsed.data_objects:
    all_element_names[do.archi_id] = do.name
for fn in parsed.functions:
    all_element_names[fn.archi_id] = fn.name
for te in parsed.tech_elements:
    all_element_names[te.archi_id] = te.name

# Per-view stats
view_stats = []
for sv in parsed.solution_views:
    total = len(sv.element_archi_ids)
    resolved = 0
    unresolved_items = []
    for aid in sv.element_archi_ids:
        if sv.view_type == 'deployment':
            if (built.tech_archi_to_c4 and aid in built.tech_archi_to_c4) or aid in built.archi_to_c4:
                resolved += 1
            else:
                unresolved_items.append(aid)
        else:
            if aid in built.archi_to_c4:
                resolved += 1
            elif built.promoted_archi_to_c4 and aid in built.promoted_archi_to_c4:
                resolved += 1
            else:
                unresolved_items.append(aid)

    unresolved = total - resolved
    rate = unresolved / total if total > 0 else 0
    view_stats.append({
        'name': sv.name,
        'view_type': sv.view_type,
        'solution': sv.solution,
        'total': total,
        'unresolved': unresolved,
        'rate': rate,
        'unresolved_aids': unresolved_items,
    })

# Sort by unresolved count descending
view_stats.sort(key=lambda x: (-x['unresolved'], -x['rate']))

# Show all views summary first
print(f'\nAll solution views ranked by unresolved count:')
print(f'{"#":>3} {"View Name":<55} {"Type":<12} {"Total":>5} {"Unres":>5} {"Rate":>6}')
print('-' * 90)
for i, vs in enumerate(view_stats, 1):
    print(f'{i:3d} {vs["name"][:55]:<55} {vs["view_type"]:<12} {vs["total"]:5d} {vs["unresolved"]:5d} {vs["rate"]:5.0%}')

# Detailed analysis of worst 5 (by unresolved count)
print(f'\n--- Detailed: Top 5 worst views ---')
for vs in view_stats[:5]:
    if vs['unresolved'] == 0:
        continue
    print(f'\n  VIEW: {vs["name"]}')
    print(f'  Type: {vs["view_type"]}, Total elements: {vs["total"]}, '
          f'Unresolved: {vs["unresolved"]} ({vs["rate"]:.0%})')

    # Classify unresolved elements
    type_counts = Counter()
    for aid in vs['unresolved_aids']:
        etype = all_element_types.get(aid, 'UNKNOWN')
        type_counts[etype] += 1

    print(f'  Unresolved by element type:')
    for etype, count in type_counts.most_common():
        print(f'    {etype}: {count}')

    # Show specific unresolved elements (first 15)
    print(f'  Unresolved elements (up to 15):')
    for aid in vs['unresolved_aids'][:15]:
        etype = all_element_types.get(aid, 'UNKNOWN')
        ename = all_element_names.get(aid, '???')
        in_archi_map = 'in archi_to_c4' if aid in built.archi_to_c4 else 'NOT in archi_to_c4'
        in_tech_map = 'in tech_map' if built.tech_archi_to_c4 and aid in built.tech_archi_to_c4 else 'NOT in tech_map'
        print(f'    - [{etype}] "{ename}" ({aid}) — {in_archi_map}, {in_tech_map}')


# ══════════════════════════════════════════════════════════════════════════
# PART C: View hierarchy — original ArchiMate folder structure vs output
# ══════════════════════════════════════════════════════════════════════════
print('\n' + '=' * 80)
print('PART C: VIEW HIERARCHY — ORIGINAL vs OUTPUT')
print('=' * 80)

diagrams_dir = config.model_root / 'diagrams'


def get_folder_name(folder_dir: Path) -> str:
    """Read folder.xml to get the display name."""
    folder_xml = folder_dir / 'folder.xml'
    if folder_xml.exists():
        try:
            tree = ET.parse(folder_xml)
            return tree.getroot().get('name', folder_dir.name)
        except ET.ParseError:
            pass
    return folder_dir.name


def build_diagram_tree(base_dir: Path, prefix: str = '') -> list[tuple[str, str, str]]:
    """Walk the diagrams directory and return (path, name, diagram_name) tuples."""
    entries = []
    if not base_dir.is_dir():
        return entries

    folder_name = get_folder_name(base_dir)
    current_path = f'{prefix}/{folder_name}' if prefix else folder_name

    # Find diagrams in this folder
    for xml_path in sorted(base_dir.glob('ArchimateDiagramModel_*.xml')):
        try:
            tree = ET.parse(xml_path)
            diagram_name = tree.getroot().get('name', xml_path.stem)
            entries.append((current_path, diagram_name, xml_path.name))
        except ET.ParseError:
            pass

    # Recurse into subdirectories
    for child in sorted(base_dir.iterdir()):
        if child.is_dir() and child.name != '.git':
            entries.extend(build_diagram_tree(child, current_path))

    return entries


print('\n--- Original ArchiMate diagram folder structure ---')
print('(showing only folders containing solution views)\n')

import re
func_pat = re.compile(r'^(?:functional_architecture|fucntional_architecture)\.(.+)$', re.IGNORECASE)
integ_pat = re.compile(r'^integration_architecture\.(.+)$', re.IGNORECASE)
func_pat_ru = re.compile(r'^Функциональная архитектура[.\s]+(.+)$', re.IGNORECASE)
integ_pat_ru = re.compile(r'^Интеграционная архитектура[.\s]+(.+)$', re.IGNORECASE)
deploy_pat = re.compile(r'^(?:deployment_architecture|deployment_target)\.(.+)$', re.IGNORECASE)
deploy_pat_ru = re.compile(r'^Схема разв[её]ртывания[.\s]+(.+)$', re.IGNORECASE)

all_pats = [func_pat, integ_pat, func_pat_ru, integ_pat_ru, deploy_pat, deploy_pat_ru]

diagram_tree = build_diagram_tree(diagrams_dir)

# Filter to only solution-relevant views
solution_diagrams = []
non_solution_diagrams = []
for path, diagram_name, xml_file in diagram_tree:
    is_solution = any(p.match(diagram_name) for p in all_pats)
    if is_solution:
        solution_diagrams.append((path, diagram_name))
    else:
        non_solution_diagrams.append((path, diagram_name))

# Group by folder path
from collections import OrderedDict
by_folder = OrderedDict()
for path, diagram_name in solution_diagrams:
    by_folder.setdefault(path, []).append(diagram_name)

for folder, diagrams in by_folder.items():
    print(f'  {folder}/')
    for d in diagrams:
        print(f'    - {d}')

print(f'\nTotal solution diagrams found: {len(solution_diagrams)}')
print(f'Total non-solution diagrams: {len(non_solution_diagrams)}')

# Show the UNIQUE folder paths (depth) to illustrate hierarchy
folder_depths = Counter()
for path, _ in solution_diagrams:
    depth = path.count('/')
    folder_depths[depth] += 1

print(f'\nFolder depth distribution:')
for depth, count in sorted(folder_depths.items()):
    print(f'  depth {depth}: {count} diagrams')

# Show what the output looks like
print('\n--- Current output structure ---')
print('  output/views/solutions/')
output_solutions = Path('output/views/solutions')
if output_solutions.exists():
    for f in sorted(output_solutions.iterdir()):
        print(f'    {f.name}')
else:
    print('  (output directory not found — showing what WOULD be generated)')
    from archi2likec4.generators import generate_solution_views
    _sys_subdomain = {
        s.c4_id: s.subdomain
        for d_sys_list in built.domain_systems.values()
        for s in d_sys_list
        if s.subdomain
    }
    sv_files, _, _ = generate_solution_views(
        parsed.solution_views, built.archi_to_c4, built.sys_domain,
        parsed.relationships,
        promoted_archi_to_c4=built.promoted_archi_to_c4,
        tech_archi_to_c4=built.tech_archi_to_c4,
        entity_archi_ids={e.archi_id for e in built.entities},
        deployment_map=built.deployment_map,
        sys_subdomain=_sys_subdomain or None,
        deployment_env=config.deployment_env,
    )
    for slug in sorted(sv_files.keys()):
        print(f'    {slug}.c4')

# Hierarchy loss analysis
print('\n--- Hierarchy loss analysis ---')
print('\nOriginal folder hierarchy has these groupings:')
top_level_groups = set()
for path, _ in solution_diagrams:
    parts = path.split('/')
    # Show the 2nd and 3rd level (after "diagrams")
    if len(parts) >= 2:
        top_level_groups.add(parts[1] if len(parts) > 1 else parts[0])

for group in sorted(top_level_groups):
    count = sum(1 for p, _ in solution_diagrams if group in p.split('/'))
    # Show subfolders
    subfolders = set()
    for p, _ in solution_diagrams:
        parts = p.split('/')
        if len(parts) > 2 and parts[1] == group:
            subfolders.add(parts[2])
    if subfolders:
        print(f'\n  {group}/ ({count} diagrams)')
        for sf in sorted(subfolders):
            sub_count = sum(1 for p, _ in solution_diagrams if f'{group}/{sf}' in p)
            print(f'    {sf}/ ({sub_count} diagrams)')
    else:
        print(f'\n  {group}/ ({count} diagrams, no subfolders)')

print('\nCurrent output: ALL views are FLAT in output/views/solutions/*.c4')
print('  - No folder grouping by solution/product/project')
print('  - Naming convention uses slug: "functional_{slug}.c4" as view ID inside the file')
print('  - Original groupings (e.g., by product/project) are lost')

# Show specific example of hierarchy loss
print('\nExample of hierarchy loss:')
for folder, diagrams in list(by_folder.items())[:3]:
    print(f'  Original: {folder}/')
    for d in diagrams[:3]:
        # What slug does this become?
        for pat, vtype in [(func_pat, 'functional'), (integ_pat, 'integration'),
                           (func_pat_ru, 'functional'), (integ_pat_ru, 'integration'),
                           (deploy_pat, 'deployment'), (deploy_pat_ru, 'deployment')]:
            m = pat.match(d)
            if m:
                from archi2likec4.utils import make_id
                slug = make_id(m.group(1).strip())
                print(f'    "{d}" -> views/solutions/{slug}.c4')
                break

print('\n' + '=' * 80)
print('END OF DIAGNOSTIC')
print('=' * 80)
