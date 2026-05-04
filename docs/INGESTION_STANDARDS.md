# Ingestion Standards & Model Hygiene

**Status:** Draft v0.1 (skeleton — to be reviewed and extended).
**Audience:** architects preparing a coArchi/ArchiMate model for ingestion via `archi2likec4`, and contributors maintaining the converter.
**Goal:** consolidate every rule, convention, and known gap learned across iterations 1–17 (see [`NOTES.md`](../NOTES.md)) so a fresh model can be re-ingested cleanly, and so source-side mistakes are caught at the model — not in the generated `.c4` files.

---

## How to use this document

1. **Architects:** before the next ingestion, walk the [Pre-ingest checklist](#8-pre-ingest-checklist-for-the-architect) against your repository. Fix issues in Archi, not in the converter.
2. **Contributors:** when adding a new parser/builder, register the rule here as well — the document is normative, not descriptive.
3. **Model owners:** the [Lessons from prior ingestions](#7-lessons-from-prior-ingestions-gaps-to-fix-at-the-source) section is the running record of what historically broke. New incidents append here.

> Anything in this document that disagrees with `NOTES.md` is a draft inconsistency — flag it on the PR.

---

## 1. Source-of-truth rules

These are the foundational invariants. Everything else derives from them.

| # | Rule | Why |
|---|---|---|
| R1 | **Folders in coArchi are noise.** Truth lives in element type + name. | Authors put the same `ApplicationComponent` under arbitrary folders; folder structure is administrative, not architectural. |
| R2 | **Hierarchy is encoded in dot notation in `name`.** `EFS` = system; `EFS.Client_Service` = subsystem of EFS. Max two levels (System, System.Subsystem). | Two levels are enough for L3/L4; deeper nesting belongs in `appFunction`. |
| R3 | **`profiles` (ArchiMate specializations) are ignored.** | "Дурная иерархия, не тащи." Specializations cross-cut the L1–L5 hierarchy and create ambiguity. |
| R4 | **Special folder semantics:** `trash/` = skip entirely. `!РАЗБОР/` = ingest + tag `#to_review`. `!External_services/` = ingest + tag `#external`. | Established convention from the source repository. |

---

## 2. What we parse — capture matrix

Reference: `NOTES.md` §"Инвентаризация coArchi-модели" (lines 822–990).

### 2.1 Application Layer (parsed in full)

| ArchiMate type | Output | Notes |
|---|---|---|
| `ApplicationComponent` | `system` / `subsystem` | Hierarchy via dot notation (R2). |
| `ApplicationFunction` | `appFunction` | L5 — child of system or subsystem. |
| `ApplicationInterface` | enriches owning system: `link` + `api_interfaces` metadata | NOT a LikeC4 element kind. See §3. |
| `ApplicationService` | resolved like `ApplicationInterface` (planned V2-S1) | **Historical gap — see §7.** |
| `DataObject` | `dataEntity` | Linked to `dataStore` via AccessRelationship. |

### 2.2 Technology Layer (parsed since iteration 13)

| ArchiMate type | Output |
|---|---|
| `Node`, `Device`, `TechnologyCollaboration`, `CommunicationNetwork`, `Path` | `infraNode` |
| `SystemSoftware`, `TechnologyService`, `Artifact` | `infraSoftware` |

Detection of `dataStore`: `SystemSoftware` whose name matches a database keyword (PostgreSQL, Oracle, Redis, MongoDB, …) — see `builders/deployment.py`.

### 2.3 Relationships

| Type | Used for |
|---|---|
| `FlowRelationship` | system↔system integrations |
| `RealizationRelationship` | structural parent + cross-layer App→Tech (deployment) |
| `CompositionRelationship` | parent resolution (function→component, interface→component) |
| `ServingRelationship` | integrations |
| `AggregationRelationship` | `infraNode`/`infraSoftware` deployment topology nesting |
| `AccessRelationship` | data access (`accessType` not yet extracted) |
| `TriggeringRelationship` | integrations |
| `AssignmentRelationship` | structural parent only — cross-layer App→Business is dropped |

### 2.4 Properties — 10 mandatory keys (mapped to metadata)

| ArchiMate key | LikeC4 metadata key | Default if missing |
|---|---|---|
| `CI` | `ci` | `'TBD'` |
| `Full name` | `full_name` | element `name` |
| `LC stage` | `lc_stage` | `'TBD'` |
| `Criticality` | `criticality` | `'TBD'` |
| `Target` | `target_state` | `'TBD'` |
| `Business owner dep` | `business_owner_dep` | `'TBD'` |
| `Dev team` | `dev_team` | `'TBD'` |
| `Architect full name` | `architect` | `'TBD'` |
| `IS-officer full name` | `is_officer` | `'TBD'` |
| `External/Internal` OR `placement` | `placement` | `'TBD'` |

> All 10 keys are **mandatory** on every system/subsystem in the generated output. `target` was renamed to `target_state` because `target` is a LikeC4 reserved word.

---

## 3. What we skip (and why)

| Skipped | Reason | Re-evaluate? |
|---|---|---|
| `ApplicationService` | Historically not parsed — caused ~276 lost integrations. Planned for V2-S1. | **Yes — see §7.** |
| `ApplicationInteraction`, `ApplicationEvent` | Microscopic counts (5, 3) — noise. | No |
| Business Layer (BusinessService, BusinessActor, …) | 121 elements — out of L1–L5 scope today. Backlog item F1. | Future |
| Strategy Layer (Capability, ValueStream) | 96 elements. `Capability.Domain` property could one day map to our domains. | Future |
| Other (Grouping, Junction, Location) | 22 elements. `Grouping` could feed deployment zones (DMZ, internal). | Future |
| Motivation, Implementation/Migration layers | Empty in source model. | If populated |
| `AssociationRelationship` (161) | Generic cross-layer links, hard to interpret. | No |
| `SpecializationRelationship` (72) | DataObject inheritance — not modelled in LikeC4. | No |
| `accessType` on AccessRelationship | Not extracted — read/write distinction lost. | TODO |
| Diagrams: `technology/`, `conceptual_architecture.*`, `value_stream.*` (~71 of 125) | Not part of the generated solution view set. | Selective |

---

## 4. Output format & file layout

Reference: `NOTES.md` §"Реструктуризация output" + per-system structure introduced in 1.1.

```
output/
  specification.c4           kinds, colors, tags
  views.c4                   landscape + global views
  relationships.c4           cross-system integrations
  domains/{id}.c4            domain group view
  systems/{id}/model.c4      system + subsystems + functions + links + metadata
  systems/{id}/deployment.c4 per-system deployment view (star-chain includes)
  systems/{id}.yaml          spec skeleton with api_contracts
  infrastructure/            extracted technology layer
  deployment/                global deployment topology
  MATURITY.md                GAP-based maturity report
  maturity.json              structured maturity data
  CLAUDE.md                  conventions for the generated repo
```

LikeC4 reads all `.c4` files recursively and merges them into one model.

### 4.1 Identifier rules (`make_id()`, `utils.py`)

- Cyrillic transliterated to Latin.
- Spaces and special chars → `_`.
- Lowercase only. Pattern: `[a-z][a-z0-9_]*`.
- **No hyphens** — LikeC4 parses `-` as a minus operator.
- Must not start with a digit (prefix with `n` if it does).
- Collisions get suffix `_2`, `_3`, …
- Dot in source name separates system from subsystem; the dot itself is **not** part of the id.

### 4.2 Reserved words (cannot be used as ids or metadata keys)

`target`, `component`, `specification`, `model`, `views`, `deployment`, `extend`, `element`, `tag`, `include`, `exclude`, `style`, `color`, `shape`, `technology`, `description`, `title`, `it`, `this`, … (extend list as encountered).

### 4.3 View titles drive sidebar grouping

LikeC4 builds the sidebar tree from `/` in view `title`:

```
title 'Functional areas / Channels / AIM / Functional architecture'
```

The `folder_path` from coArchi must be turned into a readable, slash-separated title — not a slug.

---

## 5. Tags

Stable tag vocabulary used in generated output:

| Tag | Applied to | Source |
|---|---|---|
| `#to_review` | systems under `!РАЗБОР/` | folder convention |
| `#external` | systems under `!External_services/` | folder convention |
| `#system_<id>` | per-system deployment scoping | generated |
| (extend as new tags appear) | | |

---

## 6. Validation gates & quality

- Coverage gate: tests at ≥ 85% (`pytest --cov-fail-under=85`).
- Maturity audit: 10 GAP detectors (`GAP-DEPLOY`, `GAP-ZONE`, `GAP-DOMAIN`, …) with penalty scoring → `MATURITY.md`.
- Validation phase raises `ValidationError` when `gate_errors > 0` (or in `--strict` mode, on warnings).
- Diagnostic CLI flags: `--dry-run`, `--strict`, `--verbose`.

---

## 7. Lessons from prior ingestions (gaps to fix at the source)

> **This is the most important section for re-ingestion.** Each entry: what we observed, why it happened, what to fix in the model (or in the converter).

### 7.1 ApplicationService not parsed → 276 lost integrations

- **Observed:** 93% of dropped integrations had an `ApplicationService` endpoint. 343 unresolved view refs.
- **Cause:** `ApplicationService_*.xml` files were never indexed.
- **Action:** ingest like `ApplicationInterface` (planned V2-S1). Resolve owner via `RealizationRelationship`. Surface as `link`/metadata, not as a new LikeC4 kind.

### 7.2 108 unassigned systems (37.4%)

- **Cause:** "псевдосистемы" — placeholder subsystems drawn by contractors before the modelling notation was approved.
- **Source-side fix:** architect re-classifies them. Add to `domain_overrides` in `.archi2likec4.yaml`.
- **Converter-side mitigation:** auto-inherit domain via Composition (future).

### 7.3 70 orphan data entities (22.7%)

- **Cause:** 67 of 70 simply lack an `AccessRelationship` in the source. Three (HUMO/UzCard/MasterCard Cards) will be fixed by §7.1.
- **Source-side fix:** every persistent `DataObject` must have at least one `AccessRelationship` from a consuming `ApplicationComponent` or `ApplicationService`.

### 7.4 Trash filter only scanned model tree

- **Observed:** 6 trash views leaked into output.
- **Cause:** `_is_in_trash()` checked the model XML tree only, not the diagrams tree.
- **Fix:** extended in commit `9605fd2` (closes #56). Document: `trash/` exclusion applies to **both** model and diagrams subtrees.

### 7.5 Windows MAX_PATH (260 chars)

- **Observed:** `ET.parse()` fails silently on deeply nested coArchi paths under Windows.
- **Fix:** `_to_str()` helper prepends `\\?\` extended-path prefix on Windows (commit `4498ba3`).
- **Implication:** safe to nest deeply; no need to flatten the model on Windows hosts.

### 7.6 LikeC4 deployment views — `.**` wildcard broken

- **Observed:** deep wildcard `app.**` in deployment views silently rendered nothing.
- **Fix:** replaced with explicit star-chain includes (commit `1c35063`).
- **Document:** for any deployment view, prefer `prod.<path>.*` chains over `.**`.

### 7.7 Missing properties on 92.7% of components

- **Observed:** 368 of 397 ApplicationComponents had no properties at all.
- **Source-side action:** the architect populates the 10 mandatory keys (§2.4). Converter fills `'TBD'` so the gap is visible in `MATURITY.md`.

### 7.8 Cross-layer relationships dropped

- **Observed:** ~840 App→Business, ~200 App→Node, 462 Node→SystemSoftware filtered out by `relevant_element_types`.
- **Status:** App→Tech (deployment) restored in iteration 13. App→Business still dropped.

### 7.9 Hyphens in ids

- **Observed:** identifiers with `-` parsed as subtraction by LikeC4.
- **Fix:** `make_id()` substitutes `_` (Unreleased changelog).

### 7.10 Reserved word `target`

- **Observed:** ArchiMate property `Target` collided with LikeC4 reserved word.
- **Fix:** mapped to metadata key `target_state`.

> **New entries:** append here whenever an ingestion run surfaces a new class of model defect.

---

## 8. Pre-ingest checklist for the architect

Run this against the model **before** invoking `archi2likec4`. Each unchecked box is a known root cause of data loss.

- [ ] No element lives under a `trash/` subfolder (in either model or diagrams tree).
- [ ] Every `ApplicationComponent` name follows `System` or `System.Subsystem`. No three-level dots.
- [ ] All 10 mandatory properties (§2.4) are populated. `'TBD'` is acceptable but visible in the maturity report.
- [ ] Every `ApplicationInterface` has a `CompositionRelationship` to its owning `ApplicationComponent`.
- [ ] Every `ApplicationService` has a `RealizationRelationship` to an `ApplicationComponent` (otherwise it will be orphaned — see §7.1).
- [ ] Every persistent `DataObject` has at least one `AccessRelationship` from a consumer (see §7.3).
- [ ] No identifier or metadata key collides with a LikeC4 reserved word (§4.2).
- [ ] No `-` in any name fragment that becomes an id (§4.1).
- [ ] Domain assignment: every system either lives under `functional_areas/{domain}/...` or has a `domain_override` in `.archi2likec4.yaml`.
- [ ] `!РАЗБОР/` and `!External_services/` are used only with their documented semantics (§1, R4).

---

## 9. Platform constraints

| Constraint | Mitigation |
|---|---|
| Windows `MAX_PATH` (260 chars) | `\\?\` prefix in `_to_str()` (commit `4498ba3`). |
| LikeC4 deployment `.**` wildcard | Use star-chain includes. |
| PyYAML / Flask | Optional extras (`pip install "archi2likec4[web]"`). Core is zero-runtime-dep. |
| Coverage gate | 85% — keep `tests/` synced when adding parsers/builders. |
| Python | 3.10–3.13 supported (CI matrix). |

---

## 10. Open questions

Items intentionally left for the next review pass:

1. **Document the GAP detector catalogue.** Today only the names exist; we need a table of GAP-id → trigger condition → remediation hint.
2. **`accessType` on AccessRelationship** — should we extract read/write to enrich `dataEntity` views?
3. **Business Layer ingestion (epic F1)** — when this lands, expand §2 and §3 accordingly.
4. **View-naming policy** — formalise the `/`-separated title format (§4.3) into a generator rule with a test.
5. **External vs Internal `placement`** — confirm the merge rule survives once we add a third value (e.g. `partner`).
6. **Federation** — multi-repo ingestion (`scripts/federate_template.py`) deserves its own subsection here.

---

## 11. References

- [`NOTES.md`](../NOTES.md) — full iteration history (RU), source of truth for everything above.
- [`CLAUDE.md`](../CLAUDE.md) — developer guide, coding standards, architecture overview.
- [`CHANGELOG.md`](../CHANGELOG.md) — versioned record of changes.
- [`ROADMAP.md`](./ROADMAP.md) — forward-looking work.
- LikeC4 docs: <https://likec4.dev/>
- coArchi: <https://github.com/archimatetool/archi-modelrepository-plugin>
