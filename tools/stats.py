#!/usr/bin/env python3
"""Deep statistics for the archi2likec4 converter pipeline.

Usage: python3 tools/stats.py [model_root] [--config path]

Runs parse + build phases and prints detailed analytics about
systems, integrations, data access, solution views, and deployment.
"""

import argparse
import logging
import statistics
import sys
from collections import Counter
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from archi2likec4.config import load_config
from archi2likec4.pipeline import _parse, _build
from archi2likec4.utils import flatten_deployment_nodes
from archi2likec4.builders import _build_comp_c4_path

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


# ── Formatting helpers ────────────────────────────────────────────────────

def hline(char='─', width=80):
    return char * width


def section(title):
    print()
    print(hline('═'))
    print(f'  {title}')
    print(hline('═'))


def subsection(title):
    print()
    print(f'  ── {title} ' + '─' * max(1, 72 - len(title)))


def kv(key, value, indent=4):
    print(f'{" " * indent}{key + ":":<42} {value}')


def table(headers, rows, indent=4):
    """Print a simple aligned table."""
    if not rows:
        print(f'{" " * indent}(none)')
        return
    col_widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        str_row = [str(c) for c in row]
        str_rows.append(str_row)
        for i, c in enumerate(str_row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(c))
    pad = ' ' * indent
    fmt = '  '.join(f'{{:<{w}}}' for w in col_widths)
    print(pad + fmt.format(*headers))
    print(pad + '  '.join('─' * w for w in col_widths))
    for sr in str_rows:
        # Pad short rows
        while len(sr) < len(headers):
            sr.append('')
        print(pad + fmt.format(*sr))


def pct(part, total):
    if total == 0:
        return '0.0%'
    return f'{part / total * 100:.1f}%'


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='archi2likec4 deep statistics')
    parser.add_argument('model_root', nargs='?',
                        default='architectural_repository/model',
                        help='Path to coArchi model directory')
    parser.add_argument('--config', type=Path, default=None, dest='config_file')
    args = parser.parse_args()

    config = load_config(args.config_file)
    config.model_root = Path(args.model_root).resolve()
    if not config.model_root.is_dir():
        print(f'ERROR: model root not found: {config.model_root}', file=sys.stderr)
        sys.exit(2)

    print(f'Model root: {config.model_root}')
    print('Running parse + build pipeline...')

    parsed = _parse(config.model_root, config)
    built = _build(parsed, config)

    # ═══════════════════════════════════════════════════════════════════════
    #  1. OVERALL PARSED ELEMENTS
    # ═══════════════════════════════════════════════════════════════════════
    section('1. PARSED ELEMENTS (from ArchiMate XML)')

    kv('ApplicationComponents', len(parsed.components))
    kv('ApplicationFunctions', len(parsed.functions))
    kv('ApplicationInterfaces', len(parsed.interfaces))
    kv('DataObjects', len(parsed.data_objects))
    kv('TechElements (Node, SW, Device, ...)', len(parsed.tech_elements))
    total_elements = (len(parsed.components) + len(parsed.functions) +
                      len(parsed.interfaces) + len(parsed.data_objects) +
                      len(parsed.tech_elements))
    kv('TOTAL parsed elements', total_elements)

    subsection('Relationships by type')
    rel_type_counts = Counter(r.rel_type for r in parsed.relationships)
    rel_rows = sorted(rel_type_counts.items(), key=lambda x: -x[1])
    table(['Relationship Type', 'Count', '%'],
          [(t, c, pct(c, len(parsed.relationships))) for t, c in rel_rows])
    kv('TOTAL relationships', len(parsed.relationships))

    subsection('Technology elements by type')
    tech_type_counts = Counter(te.tech_type for te in parsed.tech_elements)
    table(['Tech Type', 'Count'],
          sorted(tech_type_counts.items(), key=lambda x: -x[1]))

    # ═══════════════════════════════════════════════════════════════════════
    #  2. SYSTEMS
    # ═══════════════════════════════════════════════════════════════════════
    section('2. SYSTEMS & SUBSYSTEMS')

    systems = built.systems
    total_sys = len(systems)
    total_sub = sum(len(s.subsystems) for s in systems)
    kv('Total systems', total_sys)
    kv('Total subsystems', total_sub)

    subsection('Systems per domain')
    domain_rows = []
    for d_id, d_list in sorted(built.domain_systems.items(), key=lambda x: -len(x[1])):
        if d_list:
            domain_rows.append((d_id, len(d_list), pct(len(d_list), total_sys)))
    table(['Domain', 'Systems', '%'], domain_rows)

    subsection('Top-10 largest systems (by subsystem count)')
    by_sub = sorted(systems, key=lambda s: -len(s.subsystems))[:10]
    table(['System', 'Subsystems', 'Functions', 'Domain'],
          [(s.name, len(s.subsystems),
            len(s.functions) + sum(len(sub.functions) for sub in s.subsystems),
            s.domain or 'unassigned') for s in by_sub])

    subsection('Systems with 0 functions (empty shells)')
    empty_fn = [s for s in systems
                if len(s.functions) == 0 and all(len(sub.functions) == 0 for sub in s.subsystems)]
    kv('Count', f'{len(empty_fn)} / {total_sys} ({pct(len(empty_fn), total_sys)})')
    if empty_fn:
        # Show first 15
        for s in sorted(empty_fn, key=lambda x: x.name)[:15]:
            print(f'        - {s.name} [{s.domain or "unassigned"}]')
        if len(empty_fn) > 15:
            print(f'        ... and {len(empty_fn) - 15} more')

    # Systems with 0 integrations (isolated)
    sys_c4_ids = {s.c4_id for s in systems}
    intg_sources = set()
    intg_targets = set()
    for intg in built.integrations:
        # paths are domain.system after apply_domain_prefix
        src_sys = intg.source_path.split('.')[1] if '.' in intg.source_path else intg.source_path
        tgt_sys = intg.target_path.split('.')[1] if '.' in intg.target_path else intg.target_path
        intg_sources.add(src_sys)
        intg_targets.add(tgt_sys)
    connected = intg_sources | intg_targets
    isolated = [s for s in systems if s.c4_id not in connected]

    subsection('Systems with 0 integrations (isolated)')
    kv('Count', f'{len(isolated)} / {total_sys} ({pct(len(isolated), total_sys)})')
    if isolated:
        for s in sorted(isolated, key=lambda x: x.name)[:20]:
            sub_info = f' ({len(s.subsystems)} subs)' if s.subsystems else ''
            print(f'        - {s.name}{sub_info} [{s.domain or "unassigned"}]')
        if len(isolated) > 20:
            print(f'        ... and {len(isolated) - 20} more')

    # ═══════════════════════════════════════════════════════════════════════
    #  3. INTEGRATIONS (key focus)
    # ═══════════════════════════════════════════════════════════════════════
    section('3. INTEGRATIONS (dead integration analysis)')

    kv('Total eligible relationships (non-structural)', built.intg_total_eligible)
    kv('Successfully resolved integrations', len(built.integrations))
    kv('Skipped/unresolvable', f'{built.intg_skipped} ({pct(built.intg_skipped, built.intg_total_eligible)})')

    # Deeper analysis: WHY were relationships skipped?
    # Re-run resolution logic to categorize skip reasons
    subsection('Skip reason breakdown')

    from archi2likec4.builders import _build_comp_c4_path as build_paths
    comp_c4_path, comp_system_id = build_paths(systems)
    iface_c4_path = built.iface_c4_path

    skip_no_source = 0
    skip_no_target = 0
    skip_no_both = 0
    skip_self_loop = 0
    total_raw_before_dedup = 0
    for rel in parsed.relationships:
        if rel.rel_type == 'AccessRelationship':
            continue
        if rel.rel_type in ('CompositionRelationship', 'AggregationRelationship',
                            'RealizationRelationship', 'AssignmentRelationship'):
            continue
        if rel.source_type == 'ApplicationFunction' or rel.target_type == 'ApplicationFunction':
            continue

        # Resolve source
        src_ok = False
        if rel.source_type == 'ApplicationComponent':
            src_ok = rel.source_id in comp_c4_path or (
                built.promoted_parents and rel.source_id in built.promoted_parents)
        elif rel.source_type == 'ApplicationInterface':
            src_ok = rel.source_id in iface_c4_path

        # Resolve target
        tgt_ok = False
        if rel.target_type == 'ApplicationComponent':
            tgt_ok = rel.target_id in comp_c4_path or (
                built.promoted_parents and rel.target_id in built.promoted_parents)
        elif rel.target_type == 'ApplicationInterface':
            tgt_ok = rel.target_id in iface_c4_path

        if not src_ok and not tgt_ok:
            skip_no_both += 1
        elif not src_ok:
            skip_no_source += 1
        elif not tgt_ok:
            skip_no_target += 1
        else:
            # Both resolved — count self-loops (same system)
            # Get src and tgt system ids
            src_paths = []
            if rel.source_type == 'ApplicationComponent':
                p = comp_c4_path.get(rel.source_id)
                if p:
                    src_paths = [p]
                elif built.promoted_parents and rel.source_id in built.promoted_parents:
                    src_paths = list(built.promoted_parents[rel.source_id])
            elif rel.source_type == 'ApplicationInterface':
                p = iface_c4_path.get(rel.source_id)
                if p:
                    src_paths = [p]

            tgt_paths = []
            if rel.target_type == 'ApplicationComponent':
                p = comp_c4_path.get(rel.target_id)
                if p:
                    tgt_paths = [p]
                elif built.promoted_parents and rel.target_id in built.promoted_parents:
                    tgt_paths = list(built.promoted_parents[rel.target_id])
            elif rel.target_type == 'ApplicationInterface':
                p = iface_c4_path.get(rel.target_id)
                if p:
                    tgt_paths = [p]

            all_self = True
            cross_count = 0
            for sp in src_paths:
                sp_sys = sp.split('.')[0]
                for tp in tgt_paths:
                    tp_sys = tp.split('.')[0]
                    if sp_sys != tp_sys:
                        all_self = False
                        cross_count += 1
                    else:
                        skip_self_loop += 1
            total_raw_before_dedup += cross_count

    kv('Missing source endpoint', skip_no_source)
    kv('Missing target endpoint', skip_no_target)
    kv('Both endpoints missing', skip_no_both)
    kv('Self-loops (same system, filtered)', skip_self_loop)
    kv('Raw cross-system pairs (before dedup)', total_raw_before_dedup)
    kv('After dedup (final integrations)', len(built.integrations))
    duplicates_removed = total_raw_before_dedup - len(built.integrations)
    kv('Duplicates removed', f'{duplicates_removed}')

    # Integration density
    subsection('Integration density per system')
    sys_intg_out = Counter()
    sys_intg_in = Counter()
    for intg in built.integrations:
        src_sys = intg.source_path.split('.')[1] if '.' in intg.source_path else intg.source_path
        tgt_sys = intg.target_path.split('.')[1] if '.' in intg.target_path else intg.target_path
        sys_intg_out[src_sys] += 1
        sys_intg_in[tgt_sys] += 1

    all_intg_counts = []
    for s in systems:
        total_intg = sys_intg_out.get(s.c4_id, 0) + sys_intg_in.get(s.c4_id, 0)
        all_intg_counts.append(total_intg)
    if all_intg_counts:
        kv('Average integrations/system', f'{statistics.mean(all_intg_counts):.1f}')
        kv('Median integrations/system', f'{statistics.median(all_intg_counts):.1f}')
        kv('Max integrations/system', max(all_intg_counts))
    else:
        kv('No systems found', 0)

    subsection('Top-10 integration SOURCES (outgoing)')
    top_src = sys_intg_out.most_common(10)
    c4_to_name = {s.c4_id: s.name for s in systems}
    table(['System', 'c4_id', 'Outgoing', 'Domain'],
          [(c4_to_name.get(cid, cid), cid, cnt,
            next((s.domain for s in systems if s.c4_id == cid), '?'))
           for cid, cnt in top_src])

    subsection('Top-10 integration TARGETS (incoming)')
    top_tgt = sys_intg_in.most_common(10)
    table(['System', 'c4_id', 'Incoming', 'Domain'],
          [(c4_to_name.get(cid, cid), cid, cnt,
            next((s.domain for s in systems if s.c4_id == cid), '?'))
           for cid, cnt in top_tgt])

    # Integrations where both endpoints are in "unassigned" domain
    subsection('Integrations in "unassigned" domain (both sides)')
    unassigned_intg = [
        intg for intg in built.integrations
        if intg.source_path.startswith('unassigned.') and intg.target_path.startswith('unassigned.')
    ]
    kv('Count', f'{len(unassigned_intg)} / {len(built.integrations)}')
    if unassigned_intg:
        for intg in sorted(unassigned_intg, key=lambda i: i.source_path)[:10]:
            src_name = c4_to_name.get(intg.source_path.split('.')[1], intg.source_path)
            tgt_name = c4_to_name.get(intg.target_path.split('.')[1], intg.target_path)
            label = f' "{intg.name}"' if intg.name else ''
            print(f'        {src_name} -> {tgt_name}{label}')
        if len(unassigned_intg) > 10:
            print(f'        ... and {len(unassigned_intg) - 10} more')

    # One-way integrations
    subsection('One-way integrations (A->B but no B->A)')
    directed = set()
    for intg in built.integrations:
        src = intg.source_path.split('.')[1] if '.' in intg.source_path else intg.source_path
        tgt = intg.target_path.split('.')[1] if '.' in intg.target_path else intg.target_path
        directed.add((src, tgt))
    one_way = [(a, b) for (a, b) in directed if (b, a) not in directed]
    two_way = [(a, b) for (a, b) in directed if (b, a) in directed and a < b]
    kv('One-way pairs', len(one_way))
    kv('Two-way (bidirectional) pairs', len(two_way))
    kv('One-way percentage', pct(len(one_way), len(directed)))

    # ═══════════════════════════════════════════════════════════════════════
    #  4. DATA ACCESS
    # ═══════════════════════════════════════════════════════════════════════
    section('4. DATA ACCESS')

    kv('Total data entities', len(built.entities))
    kv('Total data access links', len(built.data_access))

    # Entities with 0 access links (orphan data)
    accessed_entity_ids = {da.entity_id for da in built.data_access}
    orphan_entities = [e for e in built.entities if e.c4_id not in accessed_entity_ids]

    subsection('Orphan data entities (0 access links)')
    kv('Count', f'{len(orphan_entities)} / {len(built.entities)} ({pct(len(orphan_entities), len(built.entities))})')
    if orphan_entities:
        for e in sorted(orphan_entities, key=lambda x: x.name)[:15]:
            print(f'        - {e.name} ({e.c4_id})')
        if len(orphan_entities) > 15:
            print(f'        ... and {len(orphan_entities) - 15} more')

    subsection('Systems accessing most entities (top-10)')
    sys_entity_count = Counter()
    for da in built.data_access:
        sys_id = da.system_path.split('.')[1] if '.' in da.system_path else da.system_path
        sys_entity_count[sys_id] += 1
    top_data = sys_entity_count.most_common(10)
    table(['System', 'Entities Accessed'],
          [(c4_to_name.get(cid, cid), cnt) for cid, cnt in top_data])

    # ═══════════════════════════════════════════════════════════════════════
    #  5. SOLUTION VIEWS
    # ═══════════════════════════════════════════════════════════════════════
    section('5. SOLUTION VIEWS')

    solution_views = built.solution_views
    kv('Total solution views', len(solution_views))

    total_view_elements = sum(len(sv.element_archi_ids) for sv in solution_views)
    kv('Total element refs on views', total_view_elements)

    # Per-view resolution
    archi_to_c4 = built.archi_to_c4
    tech_archi_to_c4 = built.tech_archi_to_c4
    promoted_archi_to_c4 = built.promoted_archi_to_c4

    view_stats = []
    grand_resolved = 0
    grand_total = 0
    for sv in solution_views:
        resolved = 0
        for eid in sv.element_archi_ids:
            if eid in archi_to_c4 or eid in tech_archi_to_c4 or eid in promoted_archi_to_c4:
                resolved += 1
        total_e = len(sv.element_archi_ids)
        grand_resolved += resolved
        grand_total += total_e
        unresolved = total_e - resolved
        res_pct = pct(resolved, total_e) if total_e else '100.0%'
        view_stats.append((sv.name, sv.view_type, total_e, resolved, unresolved, res_pct))

    kv('Total view elements', grand_total)
    kv('Resolved', f'{grand_resolved} ({pct(grand_resolved, grand_total)})')
    kv('Unresolved', f'{grand_total - grand_resolved} ({pct(grand_total - grand_resolved, grand_total)})')

    subsection('Views with worst resolution rate (bottom-10)')
    worst = sorted(view_stats, key=lambda x: (x[3] / x[2] if x[2] else 1.0))[:10]
    table(['View Name', 'Type', 'Total', 'Resolved', 'Unresolved', 'Rate'],
          worst)

    # ═══════════════════════════════════════════════════════════════════════
    #  6. DEPLOYMENT
    # ═══════════════════════════════════════════════════════════════════════
    section('6. DEPLOYMENT')

    deployment_nodes = built.deployment_nodes
    all_dn = flatten_deployment_nodes(deployment_nodes)
    kv('Root deployment nodes', len(deployment_nodes))
    kv('Total deployment nodes (all levels)', len(all_dn))
    kv('Deployment mappings (app <-> infra)', len(built.deployment_map))
    kv('DataStore-Entity links', len(built.datastore_entity_links))

    # Deployment node kinds
    subsection('Deployment nodes by kind')
    kind_counts = Counter(dn.kind for dn in all_dn)
    table(['Kind', 'Count'], sorted(kind_counts.items(), key=lambda x: -x[1]))

    # Systems without deployment mapping
    mapped_sys_c4_ids = set()
    for app_path, _node_path in built.deployment_map:
        parts = app_path.split('.')
        if len(parts) >= 2:
            mapped_sys_c4_ids.add(parts[1])

    assigned_systems = [s for s in systems if s.domain and s.domain != 'unassigned']
    unmapped = [s for s in assigned_systems if s.c4_id not in mapped_sys_c4_ids]

    subsection('Systems WITHOUT deployment mapping')
    kv('Count', f'{len(unmapped)} / {len(assigned_systems)} assigned systems '
       f'({pct(len(unmapped), len(assigned_systems))})')
    if unmapped:
        for s in sorted(unmapped, key=lambda x: x.name)[:20]:
            print(f'        - {s.name} [{s.domain}]')
        if len(unmapped) > 20:
            print(f'        ... and {len(unmapped) - 20} more')

    # Deployment nodes without any mapped systems
    mapped_node_paths = set()
    for _app_path, node_path in built.deployment_map:
        mapped_node_paths.add(node_path)
        # Also mark parent paths as used
        parts = node_path.split('.')
        for i in range(1, len(parts)):
            mapped_node_paths.add('.'.join(parts[:i]))

    # Build node path index
    from archi2likec4.builders import _build_deployment_path_index
    path_index = _build_deployment_path_index(deployment_nodes)
    inv_path = {v: k for k, v in path_index.items()}

    orphan_nodes = []
    for dn in all_dn:
        dn_path = path_index.get(dn.archi_id, dn.c4_id)
        if dn_path not in mapped_node_paths and dn.kind in ('infraNode', 'infraSoftware'):
            orphan_nodes.append((dn.name, dn.kind, dn_path))

    subsection('Deployment nodes WITHOUT any mapped systems')
    kv('Count', f'{len(orphan_nodes)} / {len(all_dn)}')
    if orphan_nodes:
        for name, kind, path in sorted(orphan_nodes)[:20]:
            print(f'        - {name} ({kind}) @ {path}')
        if len(orphan_nodes) > 20:
            print(f'        ... and {len(orphan_nodes) - 20} more')

    # ═══════════════════════════════════════════════════════════════════════
    #  SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    section('SUMMARY')
    kv('Parsed elements', total_elements)
    kv('Parsed relationships', len(parsed.relationships))
    kv('Systems', total_sys)
    kv('Subsystems', total_sub)
    kv('Domains', len([d for d, sl in built.domain_systems.items() if sl]))
    kv('Integrations (resolved)', len(built.integrations))
    kv('Integrations (skipped)', built.intg_skipped)
    kv('Integration loss rate', pct(built.intg_skipped, built.intg_total_eligible))
    kv('Data entities', len(built.entities))
    kv('Orphan entities', len(orphan_entities))
    kv('Solution views', len(solution_views))
    kv('View resolution rate', pct(grand_resolved, grand_total))
    kv('Deployment nodes', len(all_dn))
    kv('Deployment mappings', len(built.deployment_map))
    kv('Isolated systems (0 integrations)', len(isolated))

    print()
    print(hline('═'))
    print('  Done.')
    print(hline('═'))


if __name__ == '__main__':
    main()
