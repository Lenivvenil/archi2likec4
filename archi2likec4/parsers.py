"""Parsers: extract ArchiMate elements from coArchi XML files."""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger('archi2likec4')

from .models import (
    NS,
    DOMAIN_RENAMES,
    AppComponent,
    AppFunction,
    AppInterface,
    AppService,
    DataObject,
    DomainInfo,
    RawRelationship,
    SolutionView,
    TechElement,
)
from .utils import make_id


# ── Helpers ──────────────────────────────────────────────────────────────

def _detect_special_folder(xml_path: Path) -> str:
    """Walk up from *xml_path* looking for a folder whose name starts with '!'."""
    current = xml_path.parent
    model_root = None
    for parent in xml_path.parents:
        if (parent / 'folder.xml').exists() and parent.name == 'application':
            model_root = parent
            break
        if (parent / 'application').is_dir():
            model_root = parent / 'application'
            break
    current = xml_path.parent
    while current != model_root and current.name != 'application':
        folder_xml = current / 'folder.xml'
        if folder_xml.exists():
            try:
                tree = ET.parse(folder_xml)
                root = tree.getroot()
                folder_name = root.get('name', '')
                if folder_name.startswith('!'):
                    return folder_name
            except ET.ParseError:
                logger.debug('Failed to parse folder.xml: %s', folder_xml)
        current = current.parent
    return ''


DEFAULT_TRASH_NAMES: frozenset[str] = frozenset({'trash', 'archive', 'old', 'deprecated', '_old'})


def _is_in_trash(
    xml_path: Path,
    base_dir: Path,
    trash_names: frozenset[str] | None = None,
) -> bool:
    """Return True if *xml_path* is inside a folder named 'trash' (or similar).

    *trash_names* defaults to DEFAULT_TRASH_NAMES.  Pass a custom set or
    ``frozenset({'trash'})`` to restore conservative behaviour.
    """
    if trash_names is None:
        trash_names = DEFAULT_TRASH_NAMES
    current = xml_path.parent
    while current != base_dir:
        folder_xml = current / 'folder.xml'
        if folder_xml.exists():
            try:
                tree = ET.parse(folder_xml)
                root = tree.getroot()
                name = root.get('name', '').strip().lower()
                if name in trash_names:
                    return True
            except ET.ParseError:
                logger.debug('Failed to parse folder.xml: %s', folder_xml)
        current = current.parent
    return False


def _find_parent_component(xml_path: Path, app_dir: Path) -> str:
    """Walk up directories from xml_path to find the nearest ApplicationComponent.

    Returns the archi_id of the nearest parent ApplicationComponent, or '' if none.
    Only matches folders with exactly ONE ApplicationComponent (deterministic).
    Folders with multiple components are ambiguous and skipped.
    """
    current = xml_path.parent
    while current != app_dir.parent:
        ac_xmls = list(current.glob('ApplicationComponent_*.xml'))
        if len(ac_xmls) == 1:
            try:
                tree = ET.parse(ac_xmls[0])
                root = tree.getroot()
                archi_id = root.get('id', '')
                if archi_id:
                    return archi_id
            except ET.ParseError:
                logger.debug('Skipping malformed XML: %s', ac_xmls[0])
        elif len(ac_xmls) > 1:
            # Multiple components: try to match by folder name
            folder_xml = current / 'folder.xml'
            folder_name = ''
            if folder_xml.exists():
                try:
                    ft = ET.parse(folder_xml)
                    folder_name = ft.getroot().get('name', '').strip().lower()
                except ET.ParseError:
                    logger.debug('Skipping malformed folder.xml: %s', folder_xml)
            if folder_name:
                for ac_xml in ac_xmls:
                    try:
                        tree = ET.parse(ac_xml)
                        root = tree.getroot()
                        ac_name = root.get('name', '').strip().lower()
                        archi_id = root.get('id', '')
                        if ac_name == folder_name and archi_id:
                            return archi_id
                    except ET.ParseError:
                        logger.debug('Skipping malformed XML: %s', ac_xml)
            # Still ambiguous — skip and walk up
        current = current.parent
    return ''


def _extract_ref_id(href: str) -> str:
    """Extract the fragment (archi_id) from an href like 'file.xml#id-xxx'."""
    if '#' in href:
        return href.split('#', 1)[1]
    return ''


def _extract_app_component_refs(element, result: set[str]):
    """Recursively extract ApplicationComponent IDs from diagram XML."""
    for child in element:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'archimateElement':
            xsi_type = child.get('{http://www.w3.org/2001/XMLSchema-instance}type', '')
            if xsi_type == 'archimate:ApplicationComponent':
                href = child.get('href', '')
                archi_id = _extract_ref_id(href)
                if archi_id:
                    result.add(archi_id)
        _extract_app_component_refs(child, result)


def _extract_folder_path(xml_path: Path, diagrams_dir: Path) -> str:
    """Build a slug path from folder.xml names between xml_path and diagrams_dir.

    E.g. diagrams/fa/channels/aim/Diagram.xml → "functional_areas/channels/aim"
    """
    parts: list[str] = []
    current = xml_path.parent
    while current != diagrams_dir and current != diagrams_dir.parent:
        folder_xml = current / 'folder.xml'
        if folder_xml.exists():
            try:
                tree = ET.parse(folder_xml)
                name = tree.getroot().get('name', '').strip()
                if name:
                    parts.append(make_id(name))
            except ET.ParseError:
                logger.debug('Failed to parse folder.xml: %s', folder_xml)
        current = current.parent
    parts.reverse()
    return '/'.join(parts)


_VIEW_TYPE_FOLDER_NAMES = frozenset({
    'functional_architecture', 'integration_architecture',
    'deployment_architecture', 'functional architecture',
    'integration architecture', 'deployment architecture',
})


def _extract_folder_display_path(xml_path: Path, diagrams_dir: Path) -> str:
    """Extract human-readable folder path from Archi diagrams folder hierarchy.

    E.g. diagrams/fa/channels/aim/Diagram.xml → "Functional Areas / Channels / AIM"
    Uses original folder names (not slugs) for LikeC4 view navigation.
    Strips view-type folder names (functional_architecture, etc.) since they
    duplicate the view_type label in the title.
    """
    parts: list[str] = []
    current = xml_path.parent
    while current != diagrams_dir and current != diagrams_dir.parent:
        folder_xml = current / 'folder.xml'
        if folder_xml.exists():
            try:
                tree = ET.parse(folder_xml)
                name = tree.getroot().get('name', '').strip()
                if name and name.lower() not in _VIEW_TYPE_FOLDER_NAMES:
                    parts.append(name)
            except ET.ParseError:
                pass
        current = current.parent
    parts.reverse()
    return ' / '.join(parts)


def _extract_all_element_refs(element, element_ids: list[str], relationship_ids: list[str]):
    """Recursively extract all archimateElement and archimateRelationship IDs from a diagram."""
    for child in element:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'archimateElement':
            href = child.get('href', '')
            archi_id = _extract_ref_id(href)
            if archi_id:
                element_ids.append(archi_id)
        elif tag == 'archimateRelationship':
            href = child.get('href', '')
            archi_id = _extract_ref_id(href)
            if archi_id:
                relationship_ids.append(archi_id)
        _extract_all_element_refs(child, element_ids, relationship_ids)


# ── Parsers ──────────────────────────────────────────────────────────────

def parse_application_components(model_root: Path) -> list[AppComponent]:
    app_dir = model_root / 'application'
    if not app_dir.is_dir():
        raise FileNotFoundError(f'No application/ directory in {model_root}')

    results: list[AppComponent] = []
    for xml_path in sorted(app_dir.rglob('ApplicationComponent_*.xml')):
        if _is_in_trash(xml_path, app_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as e:
            logger.warning('Cannot parse %s: %s', xml_path, e)
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue
        props: dict[str, str] = {}
        for prop_el in root.findall('properties', NS) + root.findall('properties'):
            key = prop_el.get('key', '')
            value = prop_el.get('value', '')
            if key:
                props[key] = value
        source_folder = _detect_special_folder(xml_path)
        results.append(AppComponent(
            archi_id=archi_id, name=name, documentation=documentation,
            properties=props, source_folder=source_folder,
        ))
    return results


def parse_application_interfaces(model_root: Path) -> list[AppInterface]:
    app_dir = model_root / 'application'
    if not app_dir.is_dir():
        return []
    results: list[AppInterface] = []
    parse_errors = 0
    for xml_path in sorted(app_dir.rglob('ApplicationInterface_*.xml')):
        if _is_in_trash(xml_path, app_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue
        results.append(AppInterface(archi_id=archi_id, name=name, documentation=documentation))
    if parse_errors:
        logger.warning('%d ApplicationInterface XML file(s) could not be parsed', parse_errors)
    return results


def parse_application_services(model_root: Path) -> list[AppService]:
    """Parse all ApplicationService XML files from application/.

    ApplicationService elements represent external service endpoints
    (payment systems, government APIs, etc.).
    """
    app_dir = model_root / 'application'
    if not app_dir.is_dir():
        return []
    results: list[AppService] = []
    parse_errors = 0
    for xml_path in sorted(app_dir.rglob('ApplicationService_*.xml')):
        if _is_in_trash(xml_path, app_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue
        results.append(AppService(archi_id=archi_id, name=name, documentation=documentation))
    if parse_errors:
        logger.warning('%d ApplicationService XML file(s) could not be parsed', parse_errors)
    return results


def parse_data_objects(model_root: Path) -> list[DataObject]:
    """Parse all DataObject XML files from application/."""
    app_dir = model_root / 'application'
    if not app_dir.is_dir():
        return []
    results: list[DataObject] = []
    parse_errors = 0
    for xml_path in sorted(app_dir.rglob('DataObject_*.xml')):
        if _is_in_trash(xml_path, app_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue
        results.append(DataObject(archi_id=archi_id, name=name, documentation=documentation))
    if parse_errors:
        logger.warning('%d DataObject XML file(s) could not be parsed', parse_errors)
    return results


def parse_application_functions(model_root: Path) -> list[AppFunction]:
    """Parse all ApplicationFunction XML files and resolve parent component."""
    app_dir = model_root / 'application'
    if not app_dir.is_dir():
        return []

    results: list[AppFunction] = []
    parse_errors = 0
    for xml_path in sorted(app_dir.rglob('ApplicationFunction_*.xml')):
        if _is_in_trash(xml_path, app_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue

        parent_id = _find_parent_component(xml_path, app_dir)
        results.append(AppFunction(
            archi_id=archi_id, name=name,
            documentation=documentation, parent_archi_id=parent_id,
        ))
    if parse_errors:
        logger.warning('%d ApplicationFunction XML file(s) could not be parsed', parse_errors)
    return results


_TECH_PREFIXES = (
    'Node_', 'SystemSoftware_', 'Device_', 'TechnologyCollaboration_',
    'TechnologyService_', 'Artifact_', 'CommunicationNetwork_', 'Path_',
)


def parse_technology_elements(model_root: Path) -> list[TechElement]:
    """Parse Technology layer elements from technology/ directory."""
    tech_dir = model_root / 'technology'
    if not tech_dir.is_dir():
        return []

    results: list[TechElement] = []
    parse_errors = 0
    for xml_path in sorted(tech_dir.rglob('*.xml')):
        if xml_path.name == 'folder.xml':
            continue
        if not any(xml_path.name.startswith(p) for p in _TECH_PREFIXES):
            continue
        if _is_in_trash(xml_path, tech_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue

        # Extract tech_type from XML tag: 'archimate:Node' → 'Node'
        tag = root.tag
        tech_type = tag.split('}')[-1] if '}' in tag else tag
        tech_type = tech_type.replace('archimate:', '')
        # Fallback: extract from filename prefix
        if not tech_type or tech_type == root.tag:
            tech_type = xml_path.name.split('_', 1)[0]

        results.append(TechElement(
            archi_id=archi_id, name=name,
            tech_type=tech_type, documentation=documentation,
        ))
    if parse_errors:
        logger.warning('%d technology XML file(s) could not be parsed', parse_errors)
    return results


def parse_relationships(model_root: Path) -> list[RawRelationship]:
    """Parse relationship XML files. Includes AccessRelationship for data."""
    rel_dir = model_root / 'relations'
    if not rel_dir.is_dir():
        return []

    relevant_types = {
        'FlowRelationship', 'CompositionRelationship',
        'RealizationRelationship', 'ServingRelationship',
        'AccessRelationship', 'AssignmentRelationship',
        'TriggeringRelationship',
        'AggregationRelationship',
    }
    relevant_element_types = {
        # Application layer
        'archimate:ApplicationComponent', 'archimate:ApplicationInterface',
        'archimate:DataObject', 'archimate:ApplicationFunction',
        'archimate:ApplicationService',
        # Technology layer
        'archimate:Node', 'archimate:SystemSoftware', 'archimate:Device',
        'archimate:TechnologyCollaboration', 'archimate:TechnologyService',
        'archimate:Artifact', 'archimate:CommunicationNetwork', 'archimate:Path',
        # Other
        'archimate:Location',
    }

    results: list[RawRelationship] = []
    parse_errors = 0
    for xml_path in sorted(rel_dir.rglob('*.xml')):
        if xml_path.name == 'folder.xml':
            continue
        fname = xml_path.stem
        rel_type = fname.split('_', 1)[0] if '_' in fname else ''
        if rel_type not in relevant_types:
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        rel_id = root.get('id', '')
        name = root.get('name', '')
        source_el = root.find('source')
        target_el = root.find('target')
        if source_el is None or target_el is None:
            continue
        source_type = source_el.get('{http://www.w3.org/2001/XMLSchema-instance}type', '')
        target_type = target_el.get('{http://www.w3.org/2001/XMLSchema-instance}type', '')
        if source_type not in relevant_element_types or target_type not in relevant_element_types:
            continue
        source_id = _extract_ref_id(source_el.get('href', ''))
        target_id = _extract_ref_id(target_el.get('href', ''))
        if not source_id or not target_id:
            continue
        results.append(RawRelationship(
            rel_id=rel_id, rel_type=rel_type, name=name,
            source_type=source_type.replace('archimate:', ''),
            source_id=source_id,
            target_type=target_type.replace('archimate:', ''),
            target_id=target_id,
        ))
    if parse_errors:
        logger.warning('%d relationship XML file(s) could not be parsed', parse_errors)
    return results


def parse_domain_mapping(
    model_root: Path,
    domain_renames: dict[str, tuple[str, str]] | None = None,
) -> list[DomainInfo]:
    """Parse Archi view hierarchy to extract domain → AppComponent mapping.

    Scans diagrams/functional_areas/{domain}/ for ArchimateDiagramModel_*.xml
    files and extracts ApplicationComponent references (view membership).
    """
    diagrams_dir = model_root / 'diagrams'
    if not diagrams_dir.is_dir():
        return []

    # Find the functional_areas folder by reading folder.xml names
    func_areas_dir = None
    for child in sorted(diagrams_dir.iterdir()):
        if not child.is_dir():
            continue
        folder_xml = child / 'folder.xml'
        if not folder_xml.exists():
            continue
        try:
            tree = ET.parse(folder_xml)
            name = tree.getroot().get('name', '').strip()
            if name.lower().replace(' ', '_') == 'functional_areas':
                func_areas_dir = child
                break
        except ET.ParseError:
            logger.debug('Skipping malformed folder.xml: %s', folder_xml)

    if not func_areas_dir:
        logger.warning('functional_areas folder not found in diagrams/')
        return []

    domains: list[DomainInfo] = []
    for domain_dir in sorted(func_areas_dir.iterdir()):
        if not domain_dir.is_dir():
            continue
        folder_xml = domain_dir / 'folder.xml'
        if not folder_xml.exists():
            continue
        try:
            tree = ET.parse(folder_xml)
            domain_name = tree.getroot().get('name', '').strip()
        except ET.ParseError:
            logger.debug('Skipping malformed folder.xml: %s', folder_xml)
            continue
        if not domain_name:
            continue

        domain_c4_id = make_id(domain_name)

        # Recursively find all diagram XMLs and extract AppComponent refs
        archi_ids: set[str] = set()
        for view_xml in domain_dir.rglob('ArchimateDiagramModel_*.xml'):
            try:
                tree = ET.parse(view_xml)
            except ET.ParseError:
                logger.debug('Skipping malformed diagram XML: %s', view_xml)
                continue
            _extract_app_component_refs(tree.getroot(), archi_ids)

        # Apply domain renames
        renames = domain_renames if domain_renames is not None else DOMAIN_RENAMES
        if domain_c4_id in renames:
            new_id, new_name = renames[domain_c4_id]
            domain_c4_id = new_id
            domain_name = new_name

        domains.append(DomainInfo(
            c4_id=domain_c4_id, name=domain_name, archi_ids=archi_ids,
        ))

    return domains


def parse_location_elements(model_root: Path) -> list[TechElement]:
    """Parse Location elements from model/other/ directory."""
    other_dir = model_root / 'other'
    if not other_dir.is_dir():
        return []

    results: list[TechElement] = []
    for xml_path in sorted(other_dir.rglob('Location_*.xml')):
        if xml_path.name == 'folder.xml':
            continue
        if _is_in_trash(xml_path, other_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            logger.debug('Skipping malformed Location XML: %s', xml_path)
            continue
        root = tree.getroot()
        name = root.get('name', '').strip()
        archi_id = root.get('id', '')
        documentation = root.get('documentation', '')
        if not name:
            continue
        results.append(TechElement(
            archi_id=archi_id, name=name,
            tech_type='Location', documentation=documentation,
        ))
    return results


def parse_solution_views(model_root: Path) -> list[SolutionView]:
    """Parse solution-level views (functional_architecture, integration_architecture).

    Scans diagrams/ recursively for ArchimateDiagramModel_*.xml files whose name
    attribute matches known view type patterns.
    """
    diagrams_dir = model_root / 'diagrams'
    if not diagrams_dir.is_dir():
        return []

    # Pattern: functional_architecture.{solution} or fucntional_architecture.{solution}
    func_pat = re.compile(r'^(?:functional_architecture|fucntional_architecture)\.(.+)$', re.IGNORECASE)
    integ_pat = re.compile(r'^integration_architecture\.(.+)$', re.IGNORECASE)
    # Also handle Russian patterns
    func_pat_ru = re.compile(r'^Функциональная архитектура[.\s]+(.+)$', re.IGNORECASE)
    integ_pat_ru = re.compile(r'^Интеграционная архитектура[.\s]+(.+)$', re.IGNORECASE)
    deploy_pat = re.compile(r'^(?:deployment_architecture|deployment_target)\.(.+)$', re.IGNORECASE)
    deploy_pat_ru = re.compile(r'^Схема разв[её]ртывания[.\s]+(.+)$', re.IGNORECASE)

    results: list[SolutionView] = []
    seen_names: dict[str, int] = {}  # dedup_key → index in results
    seen_slugs: set[str] = set()  # track used slugs for collision avoidance
    parse_errors = 0

    for xml_path in sorted(diagrams_dir.rglob('ArchimateDiagramModel_*.xml')):
        if _is_in_trash(xml_path, diagrams_dir):
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            parse_errors += 1
            continue
        root = tree.getroot()
        diagram_name = root.get('name', '').strip()
        if not diagram_name:
            continue

        # Determine view type and solution name
        view_type = ''
        solution_name = ''
        for pat, vtype in [(func_pat, 'functional'), (integ_pat, 'integration'),
                           (func_pat_ru, 'functional'), (integ_pat_ru, 'integration'),
                           (deploy_pat, 'deployment'), (deploy_pat_ru, 'deployment')]:
            m = pat.match(diagram_name)
            if m:
                view_type = vtype
                solution_name = m.group(1).strip()
                break
        if not view_type:
            continue

        # Extract element and relationship references
        element_ids: list[str] = []
        relationship_ids: list[str] = []
        _extract_all_element_refs(root, element_ids, relationship_ids)

        solution_slug = make_id(solution_name)
        folder_path = _extract_folder_path(xml_path, diagrams_dir)
        folder_display_path = _extract_folder_display_path(xml_path, diagrams_dir)

        # Merge duplicates — scoped by folder_path to avoid cross-folder merging
        dedup_key = f'{folder_path}:{view_type}:{solution_name}'
        if dedup_key in seen_names:
            existing = results[seen_names[dedup_key]]
            existing_elem_set = set(existing.element_archi_ids)
            existing_rel_set = set(existing.relationship_archi_ids)
            new_elems = [e for e in element_ids if e not in existing_elem_set]
            new_rels = [r for r in relationship_ids if r not in existing_rel_set]
            existing.element_archi_ids.extend(new_elems)
            existing.relationship_archi_ids.extend(new_rels)
            logger.warning('Duplicate %s diagram "%s" — merged %d new elements, %d new relationships',
                           view_type, diagram_name, len(new_elems), len(new_rels))
            continue
        seen_names[dedup_key] = len(results)

        # Avoid slug collisions: "A B" and "A_B" → same slug
        unique_slug = solution_slug
        counter = 2
        while unique_slug in seen_slugs:
            unique_slug = f'{solution_slug}_{counter}'
            counter += 1
        seen_slugs.add(unique_slug)

        results.append(SolutionView(
            name=diagram_name,
            view_type=view_type,
            solution=unique_slug,
            element_archi_ids=element_ids,
            relationship_archi_ids=relationship_ids,
            folder_path=folder_path,
            folder_display_path=folder_display_path,
        ))

    if parse_errors:
        logger.warning('%d solution diagram XML file(s) could not be parsed', parse_errors)

    return results
