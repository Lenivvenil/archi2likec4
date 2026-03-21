"""Data model: dataclasses, constants, and mapping tables."""

from dataclasses import dataclass, field

# ── Transliteration table (Cyrillic → Latin) ────────────────────────────

_CYRILLIC_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}

_RESERVED = frozenset({
    'specification', 'model', 'views', 'deployment', 'extend', 'element',
    'tag', 'include', 'exclude', 'style', 'color', 'shape', 'technology',
    'description', 'title', 'link', 'icon', 'metadata', 'navigateto',
    'rectangle', 'component', 'person', 'browser', 'mobile', 'cylinder',
    'storage', 'queue', 'view', 'of', 'where', 'with', 'opacity',
    'border', 'deploymentnode', 'instanceof', 'it', 'this', 'target',
    'global', 'dynamic', 'parallel', 'group', 'autoLayout',
    'relationship',
})


# ── XML namespace ────────────────────────────────────────────────────────

NS = {'archimate': 'http://www.archimatetool.com/archimate'}


# ── Subsystem promotion ──────────────────────────────────────────────────
# Warn about parents with ≥ this many subsystems not listed in promote_children
PROMOTE_WARN_THRESHOLD: int = 10


# ── Metadata mapping ────────────────────────────────────────────────────

DEFAULT_PROP_MAP: dict[str, str] = {
    'CI': 'ci', 'Full name': 'full_name', 'LC stage': 'lc_stage',
    'Criticality': 'criticality', 'Target': 'target_state',
    'Business owner dep': 'business_owner_dep', 'Dev team': 'dev_team',
    'Architect full name': 'architect', 'IS-officer full name': 'is_officer',
    'External/Internal': 'placement', 'placement': 'placement',
}

DEFAULT_STANDARD_KEYS: list[str] = [
    'ci', 'full_name', 'lc_stage', 'criticality', 'target_state',
    'business_owner_dep', 'dev_team', 'architect', 'is_officer', 'placement',
]


# ── Dataclasses ──────────────────────────────────────────────────────────

@dataclass
class AppComponent:
    """Parsed ArchiMate ApplicationComponent."""

    archi_id: str
    name: str
    documentation: str = ''
    properties: dict[str, str] = field(default_factory=dict)
    source_folder: str = ''


@dataclass
class AppInterface:
    """Parsed ArchiMate ApplicationInterface (API endpoint)."""

    archi_id: str
    name: str
    documentation: str = ''


@dataclass
class DataObject:
    """Parsed ArchiMate DataObject (→ dataEntity in LikeC4)."""
    archi_id: str
    name: str
    documentation: str = ''


@dataclass
class RawRelationship:
    """A raw ArchiMate relationship between two elements."""

    rel_id: str
    rel_type: str
    name: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str


@dataclass
class AppFunction:
    """Parsed ArchiMate ApplicationFunction (→ appFunction in LikeC4)."""
    archi_id: str
    name: str
    c4_id: str = ''
    documentation: str = ''
    parent_archi_id: str = ''   # nearest parent ApplicationComponent


@dataclass
class Subsystem:
    c4_id: str
    name: str
    archi_id: str
    documentation: str = ''
    metadata: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    functions: list[AppFunction] = field(default_factory=list)


@dataclass
class System:
    c4_id: str
    name: str
    archi_id: str
    documentation: str = ''
    metadata: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    subsystems: list[Subsystem] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    functions: list[AppFunction] = field(default_factory=list)  # functions w/o subsystem
    api_interfaces: list[str] = field(default_factory=list)
    domain: str = ''
    subdomain: str = ''  # subdomain c4_id if assigned, else ''
    extra_archi_ids: list[str] = field(default_factory=list)  # archi_ids from duplicates


@dataclass
class ParsedSubdomain:
    """Intermediate parse-time structure: a subdomain folder under a domain."""
    archi_id: str        # generated ID (make_id of folder name)
    name: str            # folder name (raw subdomain name)
    domain_folder: str   # domain c4_id this subdomain belongs to
    component_ids: list[str] = field(default_factory=list)  # AppComponent archi_ids in views


@dataclass
class Subdomain:
    """A business subdomain (L2) in the output model."""
    c4_id: str
    name: str
    domain_id: str
    system_ids: list[str] = field(default_factory=list)


@dataclass
class DomainInfo:
    """A business domain extracted from Archi view hierarchy."""
    c4_id: str
    name: str
    archi_ids: set[str] = field(default_factory=set)


@dataclass
class DataEntity:
    """A dataEntity in the output model (from DataObject)."""
    c4_id: str
    name: str
    archi_id: str
    documentation: str = ''


@dataclass
class Integration:
    """A resolved integration (relationship) between two C4 paths."""

    source_path: str
    target_path: str
    name: str
    rel_type: str


@dataclass
class DataAccess:
    """A system/subsystem accessing a data entity."""
    system_path: str    # c4 path, e.g. 'channels.efs'
    entity_id: str      # dataEntity c4_id
    name: str           # relationship name


@dataclass
class SolutionView:
    """A solution-level view extracted from an Archi diagram."""
    name: str              # "Auto_Repayment_1.0.0"
    view_type: str         # "functional" | "integration" | "deployment"
    solution: str          # solution slug for c4_id
    element_archi_ids: list[str] = field(default_factory=list)
    relationship_archi_ids: list[str] = field(default_factory=list)
    # Visual nesting from Archi diagram canvas (parent_archi_id, child_archi_id)
    visual_nesting: list[tuple[str, str]] = field(default_factory=list)


# ── Technology / Deployment ─────────────────────────────────────────────

@dataclass
class TechElement:
    """Parsed ArchiMate technology element (Node, SystemSoftware, Device, etc.)."""
    archi_id: str
    name: str
    tech_type: str          # 'Node', 'SystemSoftware', 'Device', etc.
    documentation: str = ''


@dataclass
class DeploymentNode:
    """A node in the deployment topology tree."""
    c4_id: str
    name: str
    archi_id: str
    tech_type: str          # ArchiMate type
    kind: str = 'infraNode' # LikeC4 element kind: infraNode | infraZone | infraSoftware | infraLocation
    documentation: str = ''
    children: list['DeploymentNode'] = field(default_factory=list)
