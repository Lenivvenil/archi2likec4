# Notification Architecture — Branch `ADR_CNLS_NOT_VISA_001`

**Source branch:** `ADR_CNLS_NOT_VISA_001` in coArchi model repo at `Documents/Archi/model-repository/architectural_repository`.
**Diff against:** `master` — 4,933 raw file changes across 30+ commits, of which **69 elements** are notification-scope.
**Compiled:** 2026-05-04 from raw XML; not yet validated through `archi2likec4` (see §8).

This document captures the new notification architecture introduced on the branch, so that:
1. The change is reviewable independently of unrelated work on the same branch (CashIn, compliance, callcenter, Xfer).
2. The model can be cleaned up against [`INGESTION_STANDARDS.md`](INGESTION_STANDARDS.md) before the next converter run.
3. We have a reference for documenting the resulting `.c4` output once produced.

---

## 1. Executive summary

The branch introduces a **central notification platform** owned by the `EFS_PLT` system, fronted by a message broker, with multiple channel adapters fanning out to push, SMS, web push, Telegram and Huawei. Inbound, a new **`Visa_Event_Ingestion_Service`** brings Visa card events into the platform. A **`Telegram_bot`** component is added as a Telegram channel front-end.

**Topology in one line:**

```
Producers ──> EFS_PLT.Message_Broker ──> EFS_PLT.Notification_Service ──> { Push | SMS | WEB Push | Huawei | Telegram } adapters ──> end users
```

A separate path exists for **synchronous** SMS: producers call `EFS_PLT.Notification_Service` directly, which then calls the legacy `SMS Broker`.

---

## 2. New / changed elements (69 total)

| Layer | Type | Count |
|---|---|---|
| Application | `ApplicationComponent` | 2 (Telegram_bot, Visa_Event_Ingestion_Service) |
| Application | `DataObject` | 2 (push_notifications, sms_notifications) |
| Application | `ApplicationEvent` | 1 (scheduler_expired_notifications_job) |
| Application (folders / subsystems) | `Folder` | 12 |
| Business | `BusinessActor` | 3 (Administrator / Channel Operator / Auditor — all "(Notification)") |
| Business | `BusinessService` | 1 (`Notification_Management (copy)` — see §7.3 below) |
| Strategy | `ValueStream` | 1 (`Notifications`) |
| Technology | `SystemSoftware` | 1 (`Cisco_Instant_Messaging_Presence`) |
| Relations | `FlowRelationship` | 46 |

---

## 3. New components and adapters

### 3.1 New ApplicationComponents

| Name | Path (folder anchor) | Notes |
|---|---|---|
| `Telegram_bot` | `application/.../id-7f45d1cd...` | Telegram channel front-end. Source of `push_event_update` flow into the message broker. |
| `Visa_Event_Ingestion_Service` | `application/.../id-f84d468d...` | Inbound: receives Visa events for downstream notification triggers. |

Neither component currently carries any of the 10 mandatory properties from [INGESTION_STANDARDS §2.4](INGESTION_STANDARDS.md#24-properties--10-mandatory-keys-mapped-to-metadata). They will be filled with `'TBD'` and surface as gaps in `MATURITY.md`.

### 3.2 New / renamed subsystems (folder-level)

These are subsystems of the `EFS` and `EFS_PLT` systems, encoded via the dot-notation rule (R2):

| Subsystem | Role |
|---|---|
| `EFS_PLT.Notification_Service` | Core dispatcher — consumes from message broker, fans out to adapters. |
| `EFS_PLT.Message_Broker` | Event bus (Apache Kafka-style) for async notification flows. |
| `EFS.Notification_Service` | EFS-side counterpart (legacy / domain-specific path?). |
| `EFS.Push_Adapter` | Generic push (FCM-style). |
| `EFS.WEB_Push_Adapter` | Web push channel. |
| `EFS.Huawei_Adapter` | Huawei HMS push channel. |
| `EFS.SMS_Proxy` | Outbound SMS proxy. |
| `EFS.SMS_Adapter` | SMS channel adapter. |

Three additional `Folder` entries with names `Notification` / `Notifications` / `Telegram` exist outside the `application/` tree (in `diagrams/`, `strategy/`) and are used as grouping containers for the value-stream and a notification view.

### 3.3 New Technology element

| Name | Type | Notes |
|---|---|---|
| `Cisco_Instant_Messaging_Presence` | `SystemSoftware` | Likely the on-prem IM&P platform feeding Telegram / staff-channel notifications. Will land as `infraSoftware` per [INGESTION_STANDARDS §2.2](INGESTION_STANDARDS.md#22-technology-layer-parsed-since-iteration-13). |

---

## 4. New DataObjects

| Name | Folder | Will become (in `.c4`) |
|---|---|---|
| `push_notifications` | `application/.../id-33fd74e5...` | `dataEntity push_notifications` |
| `sms_notifications` | same | `dataEntity sms_notifications` |

Both need at least one `AccessRelationship` from the consuming/producing component to avoid joining the orphan-entity backlog ([INGESTION_STANDARDS §7.3](INGESTION_STANDARDS.md#73-70-orphan-data-entities-227)). Branch-side check pending (see §7.5).

---

## 5. Business and strategy layer additions

| Element | Type | Notes |
|---|---|---|
| `Administrator (Notification)` | BusinessActor | Operates the notification platform admin UI. |
| `Chanel Operator (Notification)` | BusinessActor | **Typo**: `Chanel` → `Channel`. See §7.1. |
| `Auditor (Notification)` | BusinessActor | Read-only audit role. |
| `Notification_Management (copy)` | BusinessService | **Defect**: " (copy)" suffix indicates an Archi-side accidental duplication. See §7.3. |
| `Notifications` | ValueStream | Strategic value stream wrapper for the notification capability. Will be **dropped** by the current converter (§3 of standards — Strategy layer not parsed). |

---

## 6. Integration matrix (46 FlowRelationships)

Grouped by integration pattern. Source/target resolution succeeded for all 46 (after enabling `\\?\` long-path support in the indexer — see §7.4).

### 6.1 Async event publication → message broker (16 flows)

All flows below publish to `EFS_PLT.Message_Broker.Api`:

| Producer | Flow name |
|---|---|
| `EFS.Push_Adapter` | `push_event_update` |
| `EFS.WEB_Push_Adapter` | `push_event_update` |
| `EFS.Huawei_Adapter` | `push_event_update` |
| `EFS.SMS_Adapter` | `push_event_update` |
| `Telegram_bot` | `push_event_update` |
| `EFS_PLT.Sample_Service` | `push_event` |
| `EFS_PLT.Notification_Service` | `push_invalidate_token`, `push_message` |
| `Мобильный банк ЮЛ` | `push_update_device`, `push_devices_tokens` |
| `AIM` | `push_update_device` |
| `Col.Data_Processing` | `push_autopay_data` |
| `ARP.Auto_Repayment_Service` | `push_transfer_data` |
| `EFS.Card_Service` | `push_notifications` |
| `EFS.Card_Service.rest_api` | `push_card_balance_enough` |
| `EFS.Transfer_service` | `push_transfer_status`, `push_notifications` |

> Pattern: pub/sub via `EFS_PLT.Message_Broker.Api`. The notification service is decoupled from producers.

### 6.2 Notification service consumes from broker (2 flows)

| Source | Flow | Target |
|---|---|---|
| `EFS_PLT.Message_Broker.Api` | `receive_notifications` | `EFS_PLT.Notification_Service` |
| `EFS_PLT.Message_Broker.Api` | `receive_notifications` | `EFS_PLT.Notification_Service` (duplicate?) |

> Two flows with identical endpoints — likely an accidental duplicate. Worth de-duplicating in the model.

### 6.3 Synchronous SMS path (5 flows)

| Source | Flow | Target |
|---|---|---|
| `EFS_PLT.Notification_Service` | `send_sms`, `save_sms` | `SMS Broker` (×3) |
| `Loan_Orchestrator` | `send_sms` | `EFS_PLT.Notification_Service` |
| `DonoCRM.FE` | `send_insurance_sms` | `DonoCRM.Nginx.proxy` |
| `DonoCRM.Nginx` | `send_insurance_sms` | `DonoCRM.BE.api.telemarketing` |
| `AIM.Xfer_Service` | `sms-send` | `AIM.AsakaESB.rest_api` |
| `DonoCRM.BE` | `sms-send` | `AIM.rest_api` |

### 6.4 SMS template CRUD via API gateway (10 flows)

`EFS.UI` and `EFS_PLT.Api_Gateway` both call the Collection_Service for SMS template lifecycle:

| Caller | Operations |
|---|---|
| `EFS.UI` → `EFS_PLT.Api_Gateway.Api` | `create_sms_template`, `update_sms_template`, `delete_sms_template`, `get_sms_template`, `list_sms_templates` |
| `EFS_PLT.Api_Gateway` → `EFS.Collection_Service.rest_api` | same five ops (forwarded) |

### 6.5 Direct publishes to notification service broker (2 flows)

| Source | Flow | Target |
|---|---|---|
| `Airflow` | `publish_push_notification`, `publish_sms_message` | `EFS_PLT.Notification_Service.broker` |

> `Airflow` bypasses `EFS_PLT.Message_Broker` and calls the notification service's own broker endpoint. May be intentional (scheduled jobs) or an architectural inconsistency — flag for review.

### 6.6 Admin / business flows (3 flows)

| Source | Flow | Target |
|---|---|---|
| `Administrator (Notification)` | `manage_notification_platform` | `EFS_PLT.Notification_Service_Admin_UI` |
| `AIM` | `push_target_for_ use_card` | `Client (Mobile)` (BusinessActor) |
| `Staff` | `push_target_for_ use_card` | `EFS` (ApplicationComponent) |

> Both `push_target_for_ use_card` flows have a stray space in the name. See §7.2.

### 6.7 Other (8 flows)

| Source | Flow | Target | Note |
|---|---|---|---|
| `EFS_PLT.Api_Gateway` | `EFS_PLT.Api_Gateway-EFS.CashIn_Service.rest_api sms` | `EFS.CashIn_Service.api` | Encoded route in name — non-standard. |
| `Paynet` | `Paynet-EFS_PLT.Api_Gateway.rest_api sms` | `EFS_PLT.Api_Gateway.Api` | Same naming pattern. |
| `MasterCard` | `sms_info_import` / `sms_info_export` | `Процессинг Tieto` | Cross-vendor SMS info exchange. |

A new `ApplicationEvent` `scheduler_expired_notifications_job` exists but no flow file references it directly in this 46-set — implies it's wired via a different relationship type (probably `TriggeringRelationship`).

---

## 7. Model defects observed

These are issues to fix **in Archi** before re-ingesting. Each one maps to an entry in [`INGESTION_STANDARDS.md`](INGESTION_STANDARDS.md#7-lessons-from-prior-ingestions-gaps-to-fix-at-the-source).

### 7.1 Typo in BusinessActor name

`Chanel Operator (Notification)` → should be `Channel Operator (Notification)`.

### 7.2 Stray space inside flow name

`push_target_for_ use_card` (×2) — converter normalises to `push_target_for__use_card` via `make_id()`, but the source-side intent is unclear. Decide: `push_target_for_use_card` or `push_target_for_used_card`?

### 7.3 Duplicate BusinessService

`Notification_Management (copy)` — almost certainly an Archi UI accident. The original `Notification_Management` should also exist; the `(copy)` should be deleted.

### 7.4 Long paths hide 30 % of the model

When indexed without the `\\?\` extended-path prefix, only **8,334** of **10,856** elements are visible — a **23 % loss** purely from MAX_PATH. Already mitigated in `archi2likec4/parsers.py` (commit `4498ba3`), but this is a strong reminder that **every** XML-touching tool the team writes must use the prefix on Windows.

### 7.5 DataObject access (to verify)

`push_notifications` and `sms_notifications` need at least one `AccessRelationship` each, otherwise they will join the orphan-entity backlog. **Not yet checked** — to be confirmed in the converter run (§8).

### 7.6 Duplicate `receive_notifications` flow

Two flows with identical source (`EFS_PLT.Message_Broker.Api`) and target (`EFS_PLT.Notification_Service`). De-duplicate.

### 7.7 Inconsistent broker path for Airflow

`Airflow` calls `EFS_PLT.Notification_Service.broker` directly instead of the platform's `EFS_PLT.Message_Broker.Api`. Confirm with the architect whether this is by design.

---

## 8. Pre-converter checklist (against [INGESTION_STANDARDS §8](INGESTION_STANDARDS.md#8-pre-ingest-checklist-for-the-architect))

| Check | Status |
|---|---|
| No element under `trash/` | TBD — not scanned |
| Component names follow `System` or `System.Subsystem` | ✅ for the 2 new components |
| 10 mandatory properties populated | ❌ — both new components have none (will surface as TBD) |
| Every `ApplicationInterface` has `CompositionRelationship` to owner | TBD |
| Every `ApplicationService` has `RealizationRelationship` to owner | N/A — no new ApplicationService on this scope |
| Every persistent `DataObject` has ≥ 1 `AccessRelationship` | TBD — see §7.5 |
| No identifier collides with LikeC4 reserved word | ✅ (no obvious collisions in the 69 names) |
| No `-` in id-bound names | ⚠️ `sms-send` (×2) — converter will substitute `_` |
| Domain assignment | TBD — need to confirm `functional_areas/` placement or `domain_overrides` |
| `!РАЗБОР` / `!External_services` semantics respected | ✅ — none used in this scope |

---

## 9. Converter run results (2026-05-04, archi2likec4 v1.3.0)

```bash
python -m archi2likec4 \
  "C:/Users/kamil_m/Documents/Archi/model-repository/architectural_repository/model" \
  output/notification-branch
```

**Outcome:** Conversion complete. **206 systems, 141 subsystems, 1,517 functions, 230 data entities, 262 integrations, 425 deployment nodes, 153 files** in [`output/notification-branch/`](../output/notification-branch/).

### 9.1 Notification scope — capture verification

All notification work from §3–§5 landed in the generated output:

| Source element | Generated `.c4` location | Status |
|---|---|---|
| `EFS.Notification_Service` | `systems/efs/model.c4` (subsystem) | ✅ |
| `EFS.Push_Adapter` | `systems/efs/model.c4` | ✅ |
| `EFS.WEB_Push_Adapter` | `systems/efs/model.c4` | ✅ |
| `EFS.Huawei_Adapter` | `systems/efs/model.c4` | ✅ |
| `EFS.SMS_Adapter` | `systems/efs/model.c4` | ✅ |
| `EFS.SMS_Proxy` | `systems/efs/model.c4` | ✅ |
| `EFS_PLT.Notification_Service` | `systems/efs_plt/model.c4` | ✅ |
| `EFS_PLT.Message_Broker` | `systems/efs_plt/model.c4` | ✅ |
| `Telegram_bot` | `systems/telegram_bot/model.c4` | ✅ |
| `Visa_Event_Ingestion_Service` | `systems/visa_event_ingestion_service/model.c4` | ✅ |
| `SMS Broker` | `systems/sms_broker/model.c4` | ✅ (target of `send_sms`/`save_sms` flows) |
| `push_notifications`, `sms_notifications` (DataObjects) | `systems/.../model.c4` (dataEntity blocks) | ✅ — but **no `dataStore→dataEntity` links generated** (0 across whole run, see §9.4) |
| `Notifications` (ValueStream) | — | ❌ Strategy layer not parsed (expected — see [INGESTION_STANDARDS §3](INGESTION_STANDARDS.md#3-what-we-skip-and-why)) |
| `Notification_Management (copy)` (BusinessService) | — | ❌ Business layer not parsed (expected) |

### 9.2 Run-wide warnings (model defects, model-side fixes recommended)

| Severity | Warning | Detail |
|---|---|---|
| 🔴 Blocker | **`GAP-DEPLOY`** — 125 systems (61 %) | No deployment mapping. |
| 🔴 Blocker | **`GAP-ZONE`** — 62 systems (30 %) | No deployment zone. |
| 🟠 Degraded | **`GAP-DOMAIN`** — 157 systems (76 %) | No domain assignment — overshoots the threshold of 20. |
| 🟠 Degraded | **`GAP-INTEG`** — 144 systems (70 %) | Below integration threshold. |
| 🟠 Degraded | **`GAP-SHALLOW`** — 145 systems (70 %) | Shallow descriptions. |
| 🟠 Cosmetic | **`GAP-DESC`** — 178 systems (86 %) | Missing descriptions. |
| ⚠️ | **2 unresolved ApplicationInterfaces** | 2 of 206 — interface owner could not be resolved. |
| ⚠️ | **342 skipped integrations** | 12 % of the 2,785 eligible flows have unresolvable endpoints (most likely point at `ApplicationService` — see [INGESTION_STANDARDS §7.1](INGESTION_STANDARDS.md#71-applicationservice-not-parsed--276-lost-integrations)). |
| ⚠️ | **33 skipped data accesses** | Same root cause. |
| ⚠️ | **PROMOTE_CHILDREN candidates** | `AIM` (48), `EFS` (33), `EFS_PLT` (15), `IABS` (15), `RAS` (16) subsystems each — consider adding to `.archi2likec4.yaml`. |
| ⚠️ | **0 dataStore → dataEntity persistence links** | Across the whole model. `push_notifications` and `sms_notifications` are de-facto orphans (§7.5 confirmed). |

### 9.3 Notification-specific subdomain duplicates (NEW defect class)

The converter logged **22 components appearing in multiple subdomain folders**. Notification-related cases:

| Component id | Subdomain folders it appears in |
|---|---|
| `id-8e467f...` (likely `EFS_PLT.Notification_Service`) | `Notification` + `Card_Management` |
| `id-32ac1c...` | `AIM` + `Notification` + `Credit_Card` |
| `id-43cd5a...` | `AIM` + `Notification` + `EG.Audit_Compliance` + `Credit_Card` (**4 places**) |
| `id-c111a6...` | `AIM` + `Notification` + `Credit_Card` |
| `id-6ee926...`, `id-a1a676...`, `id-ade401...` | `AIM` + `Notification` |
| `id-e04a3a...`, `id-f79fc5...` | `Ch.Call_center` + `Notification` |
| `id-4759f5...` | `Notification` + `Card_Management` |

**Implication:** the architect probably copy-linked components into multiple subdomain views (it's possible in Archi via drag-drop). The converter currently keeps **all** assignments. Either:
- Deduplicate in Archi (designate one canonical subdomain), or
- Add a tiebreaker rule to the converter (first-folder-wins, or explicit `domain_overrides`).

### 9.4 New model defects surfaced by the run

| # | Defect | Source-side fix |
|---|---|---|
| 9.4-A | **`EFS_PLT.Customer_ Event_Tracking`** subsystem name has a stray space (same class as §7.2 `push_target_for_ use_card`) | Rename to `Customer_Event_Tracking`. |
| 9.4-B | **3 new top-level systems unassigned** — `telegram_bot`, `visa_event_ingestion_service`, `sms_broker` likely fall into the 157 `GAP-DOMAIN` pile | Place them under `functional_areas/{domain}/...` or add `domain_overrides` in `.archi2likec4.yaml`. |
| 9.4-C | **12 orphan deployment root nodes** (no Location parent): `gitea`, `gitea-postgresql`, `IBM MQ 9.1.0.0`, `WAN`, `WinRAR 6.02`, `Корневой каталог (SAP CRM)`, etc. | Attach each to a `Location` element in Archi. |
| 9.4-D | **`push_notifications` / `sms_notifications` have no `AccessRelationship`** — confirms §7.5 hypothesis. | Add the producer/consumer access edges in Archi. |

### 9.5 Maturity headline

| Metric | Value |
|---|---|
| **Total score** | 14 / 100 (🔴 stub) |
| **Total gaps** | 1,071 |
| **Blockers** | 188 |
| **Tier distribution** | complete 2 · partial 1 · skeletal 152 · stub 51 |
| **Best systems** | `AIM` (100), `RAS` (90), `IBM MQ` (80) |
| **Worst systems** | a long tail of 30-pointers — every notification-domain system inherits the model-wide low maturity |

**To browse the output:**

```bash
cd d:/claude/archi-git/archi2likec4/output/notification-branch
npx likec4 serve
```

---

## 10. References

- [INGESTION_STANDARDS.md](INGESTION_STANDARDS.md) — normative rules and pre-ingest checklist
- [NOTES.md §post-1.0 — Диагностика и устранение потерь](../NOTES.md) — historical loss analysis
- Source branch: `ADR_CNLS_NOT_VISA_001` in the model repo
- Related commits in branch:
  - `1f53933a` Added TG bot
  - `e424b8f5` Added Visa Event Ingestion Service
  - `20902429` Added Device_token_management
  - `a657fd42` Added history for notification service
  - `7397deb8` Update Device Token Service
  - `71cd8150` Added Huawei Adapter
  - `333337c6` Updated Sms Proxy
  - `186a619f` Added web push
