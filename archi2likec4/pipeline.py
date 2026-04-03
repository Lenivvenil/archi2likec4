"""Pipeline: main() orchestration — parse, build, validate, generate."""

import argparse
import copy
import logging
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from .audit_data import compute_audit_incidents
from .builders import (
    BuildDiagnostics,
    BuildResult,
    DeploymentMappingContext,
    SystemBuildConfig,
    apply_domain_prefix,
    assign_domains,
    assign_subdomains,
    attach_functions,
    attach_interfaces,
    build_archi_to_c4_map,
    build_data_access,
    build_data_entities,
    build_datastore_entity_links,
    build_deployment_map,
    build_deployment_topology,
    build_integrations,
    build_systems,
    build_tech_archi_to_c4_map,
    enrich_deployment_from_visual_nesting,
    validate_deployment_tree,
)
from .config import ConvertConfig, load_config
from .exceptions import ConfigError, ParseError, ValidationError
from .federation import generate_federate_script, generate_federation_registry
from .generators import (
    build_view_context,
    generate_audit_md,
    generate_datastore_mapping_c4,
    generate_deployment_overview_view,
    generate_domain_c4,
    generate_domain_functional_view,
    generate_domain_integration_view,
    generate_entities,
    generate_landscape_view,
    generate_persistence_map,
    generate_solution_views,
    generate_spec,
    generate_system_detail_c4,
)
from .generators.deployment import (
    _build_node_kind_map,
    generate_infrastructure_files,
    generate_system_deployment_c4,
)
from .models import (
    DEFAULT_DEPLOYMENT_KIND,
    INSTANCE_ALLOWED_KINDS,
    AppComponent,
    AppFunction,
    AppInterface,
    DataObject,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    RawRelationship,
    SolutionView,
    TechElement,
)
from .parsers import (
    parse_application_components,
    parse_application_functions,
    parse_application_interfaces,
    parse_data_objects,
    parse_domain_mapping,
    parse_location_elements,
    parse_relationships,
    parse_solution_views,
    parse_subdomains,
    parse_technology_elements,
)
from .utils import extract_system_id, flatten_deployment_nodes

logger = logging.getLogger(__name__)


# ── Phase result containers ──────────────────────────────────────────────

class ParseResult(NamedTuple):
    components: list[AppComponent]
    functions: list[AppFunction]
    interfaces: list[AppInterface]
    data_objects: list[DataObject]
    relationships: list[RawRelationship]
    domains_info: list[DomainInfo]
    solution_views: list[SolutionView]
    tech_elements: list[TechElement]
    parsed_subdomains: list[ParsedSubdomain]



@dataclass
class ConvertResult:
    """Result returned by the public :func:`convert` API."""
    systems_count: int
    integrations_count: int
    files_written: int
    warnings: int
    output_dir: Path
    sync_ok: bool = True



# ── Phases ───────────────────────────────────────────────────────────────

def _parse(model_root: Path, config: ConvertConfig) -> ParseResult:
    """Phase 1: parse all XML sources."""
    logger.info('Parsing ApplicationComponents...')
    components = parse_application_components(model_root)
    logger.info('Found %d ApplicationComponent elements', len(components))

    logger.info('Parsing ApplicationFunctions...')
    functions = parse_application_functions(model_root)
    logger.info('Found %d ApplicationFunction elements', len(functions))

    logger.info('Parsing ApplicationInterfaces...')
    interfaces = parse_application_interfaces(model_root)
    logger.info('Found %d ApplicationInterface elements', len(interfaces))

    logger.info('Parsing DataObjects...')
    data_objects = parse_data_objects(model_root)
    logger.info('Found %d DataObject elements', len(data_objects))

    logger.info('Parsing relationships...')
    relationships = parse_relationships(model_root)
    logger.info('Found %d relevant relationships', len(relationships))

    logger.info('Parsing domain mapping from views...')
    domains_info = parse_domain_mapping(model_root, config.domain_renames)
    for d in domains_info:
        logger.info('%s: %d AppComponent refs on views', d.name, len(d.archi_ids))

    logger.info('Parsing solution views...')
    solution_views = parse_solution_views(model_root, config.extra_view_patterns)
    func_views = sum(1 for v in solution_views if v.view_type == 'functional')
    integ_views = sum(1 for v in solution_views if v.view_type == 'integration')
    deploy_views = sum(1 for v in solution_views if v.view_type == 'deployment')
    logger.info('Found %d solution views (%d functional, %d integration, %d deployment)',
                len(solution_views), func_views, integ_views, deploy_views)

    logger.info('Parsing Technology layer...')
    tech_elements = parse_technology_elements(model_root)
    logger.info('Found %d technology elements', len(tech_elements))

    logger.info('Parsing Location elements...')
    location_elements = parse_location_elements(model_root)
    logger.info('Found %d Location elements', len(location_elements))
    tech_elements = tech_elements + location_elements

    logger.info('Parsing subdomains...')
    parsed_subdomains = parse_subdomains(model_root, config.domain_renames)
    logger.info('Found %d subdomain folder(s)', len(parsed_subdomains))

    return ParseResult(
        components=components,
        functions=functions,
        interfaces=interfaces,
        data_objects=data_objects,
        relationships=relationships,
        domains_info=domains_info,
        solution_views=solution_views,
        tech_elements=tech_elements,
        parsed_subdomains=parsed_subdomains,
    )


def _build(parsed: ParseResult, config: ConvertConfig) -> BuildResult:
    """Phase 2: transform parsed elements into the output model."""
    logger.info('Building system hierarchy...')
    sys_build_cfg = SystemBuildConfig(
        promote_children=config.promote_children,
        promote_warn_threshold=config.promote_warn_threshold,
        reviewed_systems=config.reviewed_systems,
        prop_map=config.property_map,
        standard_keys=config.standard_keys,
        trash_folder=config.trash_folder,
    )
    systems, promoted_parents = build_systems(parsed.components, sys_build_cfg)
    total_subsystems = sum(len(s.subsystems) for s in systems)
    logger.info('%d systems, %d subsystems', len(systems), total_subsystems)

    logger.info('Attaching functions to systems/subsystems...')
    orphan_fns = attach_functions(
        systems, parsed.functions, parsed.relationships, promoted_parents)
    total_attached = sum(
        len(s.functions) + sum(len(sub.functions) for sub in s.subsystems)
        for s in systems
    )
    logger.info('%d functions attached, %d orphans', total_attached, orphan_fns)

    # Collect all used IDs (to avoid collisions with data entities)
    all_ids: set[str] = set()
    for s in systems:
        all_ids.add(s.c4_id)
        for sub in s.subsystems:
            all_ids.add(f'{s.c4_id}.{sub.c4_id}')

    logger.info('Building data entities...')
    entities = build_data_entities(parsed.data_objects, all_ids)
    logger.info('%d data entities', len(entities))

    logger.info('Attaching interfaces...')
    iface_c4_path = attach_interfaces(systems, parsed.interfaces, parsed.relationships)
    linked = sum(1 for s in systems if s.api_interfaces)
    logger.info('%d interfaces attached to %d systems', len(iface_c4_path), linked)

    logger.info('Building integrations...')
    integrations, intg_skipped, intg_total_eligible = build_integrations(
        systems, parsed.relationships, iface_c4_path, promoted_parents)
    logger.info('%d unique system-to-system integrations (%d/%d eligible skipped)',
                len(integrations), intg_skipped, intg_total_eligible)

    logger.info('Building data access relationships...')
    data_access = build_data_access(
        systems, entities, parsed.relationships, promoted_parents)
    logger.info('%d system-to-entity access links', len(data_access))

    logger.info('Assigning systems to domains...')
    domain_systems = assign_domains(
        systems, parsed.domains_info, config.promote_children,
        config.extra_domain_patterns, domain_overrides=config.domain_overrides)
    for d_id, d_sys_list in domain_systems.items():
        if d_sys_list:
            logger.info('%s: %d systems', d_id, len(d_sys_list))

    # Build sys_id → domain_id map for prefixing paths
    sys_domain: dict[str, str] = {s.c4_id: s.domain for s in systems}

    # Assign systems to subdomains (Pass 4)
    logger.info('Assigning systems to subdomains...')
    # Validate subdomain_overrides: warn about unknown system names or subdomain ids
    if config.subdomain_overrides:
        sys_by_name = {s.name: s for s in systems}
        sd_ids_by_domain: dict[str, set[str]] = {}
        for psd in parsed.parsed_subdomains:
            sd_ids_by_domain.setdefault(psd.domain_folder, set()).add(psd.archi_id)
        for sys_name, sd_c4_id in config.subdomain_overrides.items():
            if sys_name not in sys_by_name:
                logger.warning('subdomain_overrides: system %r not found, skipping', sys_name)
            else:
                sys_domain_val = sys_by_name[sys_name].domain or ''
                valid_sd_ids = sd_ids_by_domain.get(sys_domain_val, set())
                if sd_c4_id not in valid_sd_ids:
                    logger.warning(
                        'subdomain_overrides: subdomain %r not found in domain %r'
                        ' for system %r, skipping',
                        sd_c4_id, sys_domain_val, sys_name,
                    )

    subdomains, subdomain_systems = assign_subdomains(
        systems, parsed.parsed_subdomains,
        manual_overrides=config.subdomain_overrides or None,
    )
    logger.info('%d subdomain(s) assigned, %d system(s) with subdomain',
                len(subdomains), sum(len(v) for v in subdomain_systems.values()))
    sys_subdomain: dict[str, str] = {s.c4_id: s.subdomain for s in systems if s.subdomain}

    # Apply domain (and subdomain) prefix to integrations and data access paths
    apply_domain_prefix(integrations, data_access, sys_domain, sys_subdomain)

    # Build complete archi_id → c4_path map (for solution views)
    archi_to_c4 = build_archi_to_c4_map(systems, sys_domain, iface_c4_path, sys_subdomain)
    logger.info('%d elements in archi→c4 map', len(archi_to_c4))

    # Build promoted parent → full c4 paths map (for solution views fan-out)
    promoted_archi_to_c4: dict[str, list[str]] = {}
    for parent_aid, child_c4_ids in promoted_parents.items():
        paths = []
        for c4_id in child_c4_ids:
            domain = sys_domain.get(c4_id, 'unassigned')
            sd = sys_subdomain.get(c4_id, '')
            if sd:
                paths.append(f'{domain}.{sd}.{c4_id}')
            else:
                paths.append(f'{domain}.{c4_id}')
        promoted_archi_to_c4[parent_aid] = paths

    # Deployment topology from Technology layer
    logger.info('Building deployment topology...')
    deployment_nodes = build_deployment_topology(
        parsed.tech_elements, parsed.relationships)

    # Enrich topology with visual nesting from deployment diagrams
    all_visual_nesting: list[tuple[str, str]] = []
    for sv in parsed.solution_views:
        if sv.view_type == 'deployment' and sv.visual_nesting:
            all_visual_nesting.extend(sv.visual_nesting)
    reparented = enrich_deployment_from_visual_nesting(
        deployment_nodes, all_visual_nesting)
    if reparented:
        logger.info('Visual nesting enrichment: %d nodes re-parented', reparented)
        # Re-run context-dependent kind resolution after enrichment added new children
        from .builders.deployment import _resolve_context_kinds
        _resolve_context_kinds(deployment_nodes)

    all_dn = flatten_deployment_nodes(deployment_nodes)
    logger.info('%d top-level deployment nodes, %d total',
                len(deployment_nodes), len(all_dn))

    # Diagnostic: report orphan nodes (non-Location/site roots) — candidates for missing visual nesting
    orphan_roots = [dn for dn in deployment_nodes if dn.kind != 'site']
    if orphan_roots:
        orphan_names = ', '.join(dn.name for dn in orphan_roots)
        logger.info('Orphan root nodes (no Location parent): %s', orphan_names)

    # Build tech archi_id → c4_path map (for deployment solution views)
    tech_archi_to_c4 = build_tech_archi_to_c4_map(deployment_nodes)
    logger.info('%d elements in tech archi→c4 map', len(tech_archi_to_c4))

    logger.info('Building deployment mapping...')
    deploy_ctx = DeploymentMappingContext(
        sys_domain=sys_domain,
        sys_subdomain=sys_subdomain,
        promoted_archi_to_c4=promoted_archi_to_c4,
    )
    deployment_map = build_deployment_map(
        systems, deployment_nodes, parsed.relationships, deploy_ctx)
    logger.info('%d app→infrastructure deployment mappings', len(deployment_map))

    # Validate deployment mapping: check all infra paths resolve
    tech_path_values = set(tech_archi_to_c4.values())
    for app_path, infra_path in deployment_map:
        if infra_path not in tech_path_values:
            logger.warning('Dangling deployment mapping: %s -> %s', app_path, infra_path)

    logger.info('Building dataStore→dataEntity links...')
    datastore_entity_links = build_datastore_entity_links(
        deployment_nodes, entities, parsed.relationships)
    logger.info('%d dataStore→dataEntity persistence links', len(datastore_entity_links))

    return BuildResult(
        systems=systems,
        integrations=integrations,
        data_access=data_access,
        entities=entities,
        domain_systems=domain_systems,
        sys_domain=sys_domain,
        archi_to_c4=archi_to_c4,
        promoted_archi_to_c4=promoted_archi_to_c4,
        promoted_parents=promoted_parents,
        iface_c4_path=iface_c4_path,
        diagnostics=BuildDiagnostics(
            orphan_fns=orphan_fns,
            intg_skipped=intg_skipped,
            intg_total_eligible=intg_total_eligible,
        ),
        deployment_nodes=deployment_nodes,
        deployment_map=deployment_map,
        tech_archi_to_c4=tech_archi_to_c4,
        datastore_entity_links=datastore_entity_links,
        subdomains=subdomains,
        subdomain_systems=subdomain_systems,
    )


def _build_solution_view_index(built: BuildResult) -> dict[str, str]:
    """Build sys_subdomain map used by generate_solution_views."""
    return {
        s.c4_id: s.subdomain
        for d_sys_list in built.domain_systems.values()
        for s in d_sys_list
        if s.subdomain
    }


def _validate(built: BuildResult, config: ConvertConfig, sv_unresolved: int, sv_total: int) -> tuple[int, int]:
    """Phase 3: quality gates. Returns (warnings, errors).

    Solution views are pre-generated in convert() before this phase runs.
    This phase remains purely diagnostic — it checks invariants but produces
    no artifacts.
    """
    warnings = 0
    errors = 0

    # Gate 1: Solution view unresolved ratio
    if sv_total > 0:
        sv_ratio = sv_unresolved / sv_total
        if sv_ratio > config.max_unresolved_ratio:
            logger.error('%d/%d (%.0f%%) solution view elements unresolved — '
                         'likely data model mismatch',
                         sv_unresolved, sv_total, sv_ratio * 100)
            errors += 1
        elif sv_ratio > config.max_unresolved_ratio * 0.6:
            logger.warning('%d/%d (%.0f%%) solution view elements unresolved',
                           sv_unresolved, sv_total, sv_ratio * 100)
            warnings += 1
        else:
            logger.info('%d/%d (%.0f%%) solution view elements unresolved',
                        sv_unresolved, sv_total, sv_ratio * 100)

    # Gate 2: Orphan functions
    if built.diagnostics.orphan_fns > config.max_orphan_functions_warn:
        logger.warning('%d orphan functions (threshold: %d)',
                       built.diagnostics.orphan_fns, config.max_orphan_functions_warn)
        warnings += 1

    # Gate 3: Unassigned systems
    unassigned_count = len(built.domain_systems.get('unassigned', []))
    if unassigned_count > config.max_unassigned_systems_warn:
        logger.warning('%d systems in "unassigned" domain (threshold: %d)',
                       unassigned_count, config.max_unassigned_systems_warn)
        warnings += 1

    # Gate 4: Critical QA incidents (strict mode only)
    if config.strict:
        _, audit_incidents = compute_audit_incidents(built, sv_unresolved, sv_total, config)
        critical = [i for i in audit_incidents
                    if i.severity == 'Critical' and not i.suppressed and i.count > 0]
        if critical:
            for inc in critical:
                logger.warning('Critical QA incident: %s %s (%d)',
                               inc.qa_id, inc.title, inc.count)
            warnings += len(critical)

    return warnings, errors


@dataclass
class SolutionViewInfo:
    """Groups pre-generated solution view data for _generate."""

    files: dict[str, str] = field(default_factory=dict)
    unresolved: int = 0
    total: int = 0


def _generate(
    built: BuildResult,
    output_dir: Path,
    config: ConvertConfig,
    domains_info: list[DomainInfo],
    sv_info: SolutionViewInfo | None = None,
) -> int:
    """Phase 4: generate .c4 files."""
    logger.info('Generating files...')

    if sv_info is None:
        sv_info = SolutionViewInfo()

    # Resolve once so all subsequent operations use the same absolute path
    output_dir = output_dir.resolve()

    # Clean & create dirs (with safety checks)
    _OUTPUT_MARKER = '.archi2likec4-output'
    if output_dir.exists():
        if output_dir == Path.cwd().resolve() or output_dir == Path.home().resolve():
            raise ConfigError(f'FATAL: refusing to rmtree dangerous path: {output_dir}')
        if len(output_dir.parts) <= 2:  # root or one level (e.g. /tmp, C:\Users)
            raise ConfigError(f'FATAL: refusing to rmtree root-level path: {output_dir}')
        has_marker = (output_dir / _OUTPUT_MARKER).exists()
        if not has_marker and any(output_dir.iterdir()):
            raise ConfigError(
                f'FATAL: {output_dir} does not look like a converter output dir '
                f'(missing {_OUTPUT_MARKER}). Refusing to delete.')
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / _OUTPUT_MARKER).write_text('', encoding='utf-8')
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
    # Collect system tag IDs from ALL systems (needed for model element tags)
    _sys_ids = set(built.sys_domain.keys())
    _sys_subdomain: dict[str, str] = {s.c4_id: s.subdomain for s in built.systems if s.subdomain}
    system_ids = sorted({s.c4_id.replace('-', '_') for s in built.systems})
    (output_dir / 'specification.c4').write_text(
        generate_spec(config, system_ids=system_ids), encoding='utf-8')
    file_count += 1
    # Build per-system integration index for inline relationships in model.c4
    _sys_integrations: dict[str, list[Integration]] = {}
    for intg in built.integrations:
        sid = extract_system_id(intg.source_path, _sys_subdomain, _sys_ids, built.sys_domain)
        _sys_integrations.setdefault(sid, []).append(intg)

    (output_dir / 'entities.c4').write_text(
        generate_entities(built.entities, built.data_access), encoding='utf-8')
    file_count += 1

    # Domain files + views
    all_domain_meta: dict[str, DomainInfo] = {d.c4_id: d for d in domains_info}
    for extra in config.extra_domain_patterns:
        if extra['c4_id'] not in all_domain_meta:
            all_domain_meta[extra['c4_id']] = DomainInfo(
                c4_id=extra['c4_id'], name=extra['name'])
    if built.domain_systems.get('unassigned'):
        all_domain_meta['unassigned'] = DomainInfo(c4_id='unassigned', name='Unassigned')

    # Auto-create DomainInfo for domain ids introduced by domain_overrides /
    # promote_children fallback that have no DomainInfo yet (prevents silent data loss).
    for domain_id in built.domain_systems:
        if domain_id not in all_domain_meta and built.domain_systems[domain_id]:
            all_domain_meta[domain_id] = DomainInfo(
                c4_id=domain_id, name=domain_id.replace('_', ' ').title())
            logger.warning('Auto-created DomainInfo for unknown domain "%s" '
                           '(%d systems)', domain_id, len(built.domain_systems[domain_id]))

    domain_count = 0
    view_count = 0
    system_detail_count = 0

    for domain_id, domain_sys_list in built.domain_systems.items():
        if not domain_sys_list:
            continue
        d_info = all_domain_meta.get(domain_id)
        if not d_info:
            continue

        # Domain model file
        (domains_dir / f'{domain_id}.c4').write_text(
            generate_domain_c4(domain_id, d_info.name, domain_sys_list, built.subdomains),
            encoding='utf-8')
        file_count += 1
        domain_count += 1

        # System detail files: systems/{c4_id}/model.c4
        for s in domain_sys_list:
            outgoing = _sys_integrations.get(s.c4_id.replace('-', '_'), [])
            if s.subsystems or s.functions or outgoing:
                sys_subdir = systems_dir / s.c4_id
                sys_subdir.mkdir(exist_ok=True)
                (sys_subdir / 'model.c4').write_text(
                    generate_system_detail_c4(domain_id, s, outgoing=outgoing),
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

    # Solution views (pre-generated in convert())
    for sol_slug, content in sv_info.files.items():
        (views_solutions_dir / f'{sol_slug}.c4').write_text(content, encoding='utf-8')
        file_count += 1
        view_count += 1
    logger.info('%d solution view files generated', len(sv_info.files))

    # Top-level views
    (views_dir / 'landscape.c4').write_text(generate_landscape_view(), encoding='utf-8')
    file_count += 1
    view_count += 1
    (views_dir / 'persistence-map.c4').write_text(generate_persistence_map(), encoding='utf-8')
    file_count += 1
    view_count += 1

    # Deployment
    deploy_system_count = 0
    if built.deployment_nodes:
        # Infrastructure files: per-site .c4 files with node definitions only
        infrastructure_dir = output_dir / 'infrastructure'
        infrastructure_dir.mkdir(exist_ok=True)
        infra_files = generate_infrastructure_files(
            built.deployment_nodes, env=config.deployment_env)
        for fname, content in infra_files.items():
            (infrastructure_dir / fname).write_text(content, encoding='utf-8')
            file_count += 1

        # Per-system deployment.c4: instanceOf placements + targeted deployment views
        # Build per-system deployment map: system_c4_id → [(app_path, infra_path)]
        _node_kinds = _build_node_kind_map(built.deployment_nodes)
        _sys_deploy_map: dict[str, list[tuple[str, str]]] = {}
        if built.deployment_map:
            for app_path, infra_path in built.deployment_map:
                node_kind = _node_kinds.get(infra_path, DEFAULT_DEPLOYMENT_KIND)
                if node_kind not in INSTANCE_ALLOWED_KINDS:
                    continue
                sid = extract_system_id(app_path, _sys_subdomain, _sys_ids, built.sys_domain)
                _sys_deploy_map.setdefault(sid, []).append((app_path, infra_path))

        # Build system name lookup
        _sys_name_lookup: dict[str, str] = {}
        for s in built.systems:
            tag_id = s.c4_id.replace('-', '_')
            _sys_name_lookup[tag_id] = s.name

        for sid, entries in sorted(_sys_deploy_map.items()):
            sys_name = _sys_name_lookup.get(sid, sid)
            deploy_content = generate_system_deployment_c4(
                system_c4_id=sid,
                system_name=sys_name,
                deploy_entries=entries,
                env=config.deployment_env,
            )
            if deploy_content:
                sys_subdir = systems_dir / sid
                sys_subdir.mkdir(exist_ok=True)
                (sys_subdir / 'deployment.c4').write_text(deploy_content, encoding='utf-8')
                file_count += 1
                deploy_system_count += 1

        # Post-generation structural validation of deployment tree
        tree_violations = validate_deployment_tree(built.deployment_nodes)
        for v in tree_violations:
            logger.warning('Deployment tree violation: %s', v)
        if built.datastore_entity_links:
            deployment_dir = output_dir / 'deployment'
            deployment_dir.mkdir(exist_ok=True)
            (deployment_dir / 'datastore-mapping.c4').write_text(
                generate_datastore_mapping_c4(built.datastore_entity_links),
                encoding='utf-8')
            file_count += 1
        (views_dir / 'deployment-architecture.c4').write_text(
            generate_deployment_overview_view(
                nodes=built.deployment_nodes, env=config.deployment_env),
            encoding='utf-8')
        file_count += 1
        view_count += 1
        logger.info('  infrastructure/ (%d files)', len(infra_files))
        logger.info('  systems/ (%d deployment.c4 files)', deploy_system_count)

    # Scripts
    (scripts_dir / 'federate.py').write_text(generate_federate_script(), encoding='utf-8')
    file_count += 1
    (scripts_dir / 'federation-registry.yaml').write_text(
        generate_federation_registry(), encoding='utf-8')
    file_count += 1

    # Quality audit
    audit = generate_audit_md(built, sv_info.unresolved, sv_info.total, config)
    (output_dir / 'AUDIT.md').write_text(audit, encoding='utf-8')
    file_count += 1

    logger.info('%d files written to %s/', file_count, output_dir)
    logger.info('  specification.c4, entities.c4')
    logger.info('  domains/ (%d .c4 files)', domain_count)
    logger.info('  systems/ (%d system directories with model.c4)', system_detail_count)
    logger.info('  views/ (%d view files)', view_count)
    logger.info('  scripts/ (federate.py + federation-registry.yaml)')
    logger.info('Done! Run: cd %s && npx likec4 serve', output_dir)
    return file_count


# ── Sync step ────────────────────────────────────────────────────────────

def _sync_output(config: ConvertConfig) -> bool:
    """Copy output_dir to sync_target, skipping protected files.

    Returns ``True`` on success, ``False`` when sync was skipped due to
    invalid configuration (target nested inside or equal to output_dir).
    """
    if config.sync_target is None:
        return True

    src = config.output_dir.resolve()
    dst = config.sync_target.resolve()

    # Guard: prevent infinite recursion if target is same as or nested under source
    try:
        dst.relative_to(src)
        logger.error('sync_target %s is inside output_dir %s — skipping sync', dst, src)
        return False
    except ValueError:
        pass  # dst is not under src — safe to proceed
    if dst == src:
        logger.error('sync_target equals output_dir %s — skipping sync', src)
        return False

    protected_top = config.sync_protected_top
    protected_paths = config.sync_protected_paths
    copied = 0

    def _copy_tree(source: Path, target: Path) -> None:
        nonlocal copied
        for item in source.iterdir():
            rel = item.relative_to(src).as_posix()
            top = item.name
            # Skip protected top-level items
            if source == src and top in protected_top:
                continue
            # Skip specific protected sub-paths
            if rel in protected_paths:
                continue
            dest_item = target / item.name
            if item.is_symlink():
                continue  # Skip symlinks to prevent following them into unintended paths
            if item.is_dir():
                if dest_item.is_symlink():
                    dest_item.unlink()
                dest_item.mkdir(parents=True, exist_ok=True)
                _copy_tree(item, dest_item)
            else:
                # Unlink any pre-existing symlink in target to prevent following it
                if dest_item.is_symlink():
                    dest_item.unlink()
                shutil.copy2(item, dest_item)
                copied += 1

    dst.mkdir(parents=True, exist_ok=True)
    _copy_tree(src, dst)
    logger.info('Synced %d file(s) to %s', copied, dst)
    return True


# ── Config validation ────────────────────────────────────────────────────

def _validate_config_runtime(config: ConvertConfig) -> None:
    """Validate runtime-critical config fields.

    Called from :func:`convert` to catch invalid values in pre-built configs
    that bypassed the YAML loading path.  Silently skips validation when
    *config* is not a real :class:`ConvertConfig` (e.g. test mocks).
    """
    if not isinstance(config, ConvertConfig):
        return

    import re as _re

    _C4_ID_RE = _re.compile(r'^[a-z][a-z0-9_-]*$')

    if config.deployment_env is None:
        raise ConfigError("deployment_env: must not be None")
    env = str(config.deployment_env).strip()
    if not env:
        raise ConfigError("deployment_env: must not be empty")
    if not _C4_ID_RE.match(env):
        raise ConfigError(
            f"deployment_env: invalid C4 identifier {env!r} "
            f"(must match [a-z][a-z0-9_-]*)")
    config.deployment_env = env

    if not isinstance(config.extra_view_patterns, list):
        raise ConfigError(
            f"extra_view_patterns: expected list, got {type(config.extra_view_patterns).__name__}")
    for i, entry in enumerate(config.extra_view_patterns):
        if not isinstance(entry, dict):
            raise ConfigError(
                f"extra_view_patterns[{i}]: expected mapping, got {type(entry).__name__}")
        for key in ('pattern', 'view_type'):
            if key not in entry:
                raise ConfigError(
                    f"extra_view_patterns[{i}]: missing required key '{key}'")
        if not isinstance(entry['pattern'], str):
            raise ConfigError(
                f"extra_view_patterns[{i}]['pattern']: expected string, got {type(entry['pattern']).__name__}")
        try:
            _re.compile(entry['pattern'])
        except _re.error as err:
            raise ConfigError(
                f"extra_view_patterns[{i}]['pattern']: invalid regex: {err}") from err
        if entry.get('view_type') not in ('functional', 'integration', 'deployment'):
            raise ConfigError(
                f"extra_view_patterns[{i}]['view_type']: must be 'functional', "
                f"'integration', or 'deployment', got '{entry.get('view_type')}'")

    # Validate spec_colors
    from .config import _DEFAULT_SPEC_SHAPES as _KNOWN_SHAPES
    if not isinstance(config.spec_colors, dict):
        raise ConfigError(f"spec_colors: expected mapping, got {type(config.spec_colors).__name__}")
    for k, v in config.spec_colors.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ConfigError(f"spec_colors: keys and values must be strings, got {k!r}: {v!r}")
        if not _C4_ID_RE.match(k):
            raise ConfigError(
                f"spec_colors: invalid C4 identifier {k!r} "
                f"(must match [a-z][a-z0-9_-]*)")

    # Validate spec_shapes
    if not isinstance(config.spec_shapes, dict):
        raise ConfigError(f"spec_shapes: expected mapping, got {type(config.spec_shapes).__name__}")
    for k, v in config.spec_shapes.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ConfigError(f"spec_shapes: keys and values must be strings, got {k!r}: {v!r}")
        if k not in _KNOWN_SHAPES:
            raise ConfigError(
                f"spec_shapes: unknown element kind {k!r} "
                f"(must be one of: {', '.join(sorted(_KNOWN_SHAPES))})")

    # Validate spec_tags
    if not isinstance(config.spec_tags, list):
        raise ConfigError(f"spec_tags: expected list, got {type(config.spec_tags).__name__}")
    for item in config.spec_tags:
        if not isinstance(item, str):
            raise ConfigError(f"spec_tags: all items must be strings, got {type(item).__name__}: {item!r}")
        if not _C4_ID_RE.match(item):
            raise ConfigError(f"spec_tags: invalid C4 identifier {item!r} (must match [a-z][a-z0-9_-]*)")

# ── Public API ───────────────────────────────────────────────────────────

def convert(
    model_root: str | Path,
    output_dir: str | Path = 'output',
    *,
    config: ConvertConfig | None = None,
    config_path: str | Path | None = None,
    dry_run: bool = False,
) -> ConvertResult:
    """Convert a coArchi XML repository to LikeC4 .c4 files.

    Parameters
    ----------
    model_root:
        Path to the coArchi model directory.
    output_dir:
        Destination directory for generated .c4 files.
    config:
        Pre-built :class:`ConvertConfig` instance. When provided, *config_path*
        is ignored. ``model_root``, ``output_dir``, and ``dry_run`` always
        override the corresponding fields in *config*.
    config_path:
        Path to a YAML config file. Loaded only when *config* is ``None``.
    dry_run:
        When ``True``, parse and validate but do not write any files.

    Returns
    -------
    ConvertResult

    Raises
    ------
    FileNotFoundError
        If *model_root* does not exist or is not a directory.
    ConfigError
        If the configuration file is invalid or cannot be read.
    ParseError
        If all XML files in a required directory fail to parse.
    ValidationError
        If quality gates fail, or if strict mode is active and warnings > 0.
    """
    model_root_path = Path(model_root).resolve()
    output_dir_path = Path(output_dir)

    if not model_root_path.is_dir():
        raise FileNotFoundError(f'Model root directory does not exist: {model_root_path}')

    if config is None:
        config = load_config(Path(config_path) if config_path else None)

    config = copy.deepcopy(config)
    config.model_root = model_root_path
    config.output_dir = output_dir_path
    config.dry_run = dry_run

    _validate_config_runtime(config)

    parsed = _parse(model_root_path, config)
    built = _build(parsed, config)

    # Compute solution views once — metrics go to _validate, files go to _generate
    sys_subdomain = _build_solution_view_index(built)
    view_ctx = build_view_context(
        archi_to_c4=built.archi_to_c4,
        sys_domain=built.sys_domain,
        relationships=parsed.relationships,
        promoted_archi_to_c4=built.promoted_archi_to_c4,
        tech_archi_to_c4=built.tech_archi_to_c4,
        entity_archi_ids={e.archi_id for e in built.entities},
        deployment_map=built.deployment_map,
        sys_subdomain=sys_subdomain or None,
        deployment_env=config.deployment_env,
    )
    sv_files, sv_unresolved, sv_total = generate_solution_views(
        parsed.solution_views, view_ctx,
    )

    gate_warnings, gate_errors = _validate(built, config, sv_unresolved, sv_total)

    if gate_errors > 0:
        raise ValidationError(f'Quality gates failed with {gate_errors} error(s)')
    if config.strict and gate_warnings > 0:
        raise ValidationError(
            f'{gate_warnings} quality-gate warning(s) treated as errors in strict mode')

    files_written = 0
    sync_ok = True
    if not config.dry_run:
        sv_info = SolutionViewInfo(files=sv_files, unresolved=sv_unresolved, total=sv_total)
        files_written = _generate(
            built, output_dir_path, config, parsed.domains_info, sv_info,
        )
        if config.sync_target is not None:
            sync_ok = _sync_output(config)

    return ConvertResult(
        systems_count=len(built.systems),
        integrations_count=len(built.integrations),
        files_written=files_written,
        warnings=gate_warnings,
        output_dir=output_dir_path,
        sync_ok=sync_ok,
    )


# ── CLI entry point ──────────────────────────────────────────────────────

def main() -> None:
    from . import __version__

    # Subcommand dispatch for 'web' (before argparse — backward compatible)
    if len(sys.argv) > 1 and sys.argv[1] == 'web':
        sys.argv.pop(1)
        from .web import run_web_cli
        run_web_cli()
        return

    parser = argparse.ArgumentParser(
        prog='archi2likec4',
        description='Convert coArchi XML repository to LikeC4 .c4 files',
        epilog='Subcommands:\n  web    Launch the Flask audit web dashboard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('model_root', nargs='?', default='architectural_repository/model',
                        help='Path to coArchi model directory (default: architectural_repository/model)')
    parser.add_argument('output_dir', nargs='?', default='output',
                        help='Output directory for .c4 files (default: output)')
    parser.add_argument('--config', type=Path, default=None, dest='config_file',
                        help='Config YAML file (default: .archi2likec4.yaml if exists)')
    parser.add_argument('--strict', action='store_true',
                        help='Treat quality-gate warnings as errors')
    parser.add_argument('--verbose', action='store_true',
                        help='Verbose output (DEBUG level logging)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Parse and validate only — do not generate files')
    parser.add_argument('--sync-target', type=Path, default=None, dest='sync_target',
                        help='Directory to sync output into after generation (overrides YAML)')
    args = parser.parse_args()

    # Fallback logging — before config is loaded
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
    )

    try:
        config = load_config(args.config_file)
    except (FileNotFoundError, ConfigError, OSError) as e:
        logger.error('Configuration error: %s', e)
        sys.exit(2)

    config.model_root = Path(args.model_root).resolve()
    config.output_dir = Path(args.output_dir)
    if not config.model_root.is_dir():
        logger.error('Model root directory does not exist: %s', config.model_root)
        sys.exit(2)
    if args.strict:
        config.strict = True
    if args.verbose:
        config.verbose = True
    if args.sync_target is not None:
        target = args.sync_target.expanduser().resolve()
        if not target.exists():
            logger.error('--sync-target directory does not exist: %s', target)
            sys.exit(2)
        if not target.is_dir():
            logger.error('--sync-target is not a directory: %s', target)
            sys.exit(2)
        config.sync_target = target

    # Reconfigure logging if verbose
    if config.verbose:
        logging.getLogger(__name__.split('.')[0]).setLevel(logging.DEBUG)

    logger.info('archi2likec4 v%s', __version__)
    logger.info('Input:  %s', config.model_root)
    logger.info('Output: %s', config.output_dir)

    try:
        result = convert(
            config.model_root,
            config.output_dir,
            config=config,
            dry_run=args.dry_run,
        )
        if result.files_written == 0 and args.dry_run:
            logger.info('Dry run complete — no files generated')
        else:
            logger.info('Conversion complete: %d systems, %d integrations, %d files',
                        result.systems_count, result.integrations_count, result.files_written)

    except ValidationError as e:
        logger.error('%s', e)
        sys.exit(1)
    except ConfigError as e:
        logger.error('Configuration error: %s', e)
        sys.exit(2)
    except FileNotFoundError as e:
        logger.error('Input not found: %s', e)
        sys.exit(2)
    except ParseError as e:
        logger.error('Parse error: %s', e)
        sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:
        logger.error('Unexpected error: %s', e)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
