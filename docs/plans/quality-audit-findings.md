# Quality Audit Findings

Date: 2026-03-30

## 1. mypy --strict (75 errors in 6 files)

| File | Errors | Main issues |
|------|--------|-------------|
| generators/audit.py | 28 | no-untyped-call (calls to untyped functions) |
| web.py | 21 | no-untyped-def (2), no-untyped-call (17), type-arg (3), operator (1) |
| config.py | 8 | unused-ignore (3), type-arg (5) |
| parsers.py | 7 | no-untyped-def (7) — missing type annotations |
| audit_data.py | 6 | type-arg (6) — bare dict/list without type params |
| scripts/federate_template.py | 5 | unused-ignore (1), no-untyped-call (4) |

Key observations:
- audit.py: all 28 errors are no-untyped-call — audit.py calls functions from parsers.py/web.py that lack annotations
- web.py: exempt from disallow_untyped_defs per CLAUDE.md, but --strict catches them anyway
- config.py: 3 unused `# type: ignore` comments (lines 191, 563, 595) — stale suppressions
- parsers.py: exempt from strict typing per CLAUDE.md, 7 missing annotations
- audit_data.py: uses bare `dict` and `list` without type parameters (6 places)

Actionable:
- config.py: remove 3 unused `# type: ignore` (easy fix)
- audit_data.py: add type parameters to 6 bare generics (easy fix)

## 2. ruff extended rules (795 non-quote issues)

Top rules (excluding Q000 quote style):
- PLC0415 import-outside-top-level: 132 (mostly tests with inline imports)
- PLR2004 magic-value-comparison: 93 (numeric/string literals in comparisons)
- TRY003 raise-vanilla-args: 84 (f-strings in exception messages)
- EM102 f-string-in-exception: 82 (overlaps with TRY003)
- TID252 relative-imports: 68 (relative imports — project convention?)
- RUF059 unused-unpacking: 47
- RUF043 pair-equality: 32
- RUF001 ambiguous-unicode: 30 (Cyrillic in i18n.py — expected)
- T201 print: 22 (print statements in production code)
- PLR0913 too-many-arguments: 17
- SLF001 private-member-access: 15

Actionable:
- T201: 22 print() calls — should use logging instead (production code)
- PLR0913: 17 functions with too many args — consider refactoring
- PERF401: 13 manual list comprehensions — easy optimization

## 3. bandit security scan (1 medium, 14 low)

Medium severity:
- B704 markupsafe_markup_xss (web.py:107): Markup() with f-string for CSRF token field
  - Actually safe: html.escape(token) sanitizes the value
  - Consider adding `# nosec B704` with explanation

Low severity (14 issues): not shown at -ll threshold (filtered out)

## 4. pip-audit (1 CVE)

- pygments 2.19.2: CVE-2026-4539 (no fix version listed yet)
  - pygments is a transitive dev dependency (via rich -> bandit)
  - Not a runtime dependency of archi2likec4
  - Action: monitor for pygments update

## 5. vulture dead code (20 items, all 60% confidence)

All vulture findings are false positives:
- web.py: Flask route handlers and decorators detected as "unused" (18 items) — false positive, Flask uses decorators
- i18n.py: get_web_msg() — used by web.py via import
- web.py: secret_key — Flask config attribute

No real dead code found.

## Summary of actionable findings

### EASY FIXES (can do now):
1. config.py: 3 unused `# type: ignore` comments (lines 191, 563, 595)
2. audit_data.py: 6 bare `dict`/`list` without type params

### MEDIUM (worth filing as issues):
3. T201: 22 print() in production code — should use logging
4. PLR0913: 17 functions with too many parameters
5. audit.py: 28 no-untyped-call errors — depends on typing parsers.py/web.py
6. CVE-2026-4539 in pygments (transitive dev dep)

### LOW PRIORITY / BY DESIGN:
7. PLC0415: import-outside-top-level in tests — test convention
8. TRY003/EM102: f-strings in exceptions — project style choice
9. RUF001: Cyrillic chars in i18n.py — expected
10. TID252: relative imports — project convention

---

## 6. Test quality and coverage gaps (Task 2)

### Coverage report (797 tests, 89.70% total)

Modules below 80% coverage:
- `__main__.py`: 0% (2 lines — trivial entry point, no logic to test)
- `web.py`: 71% (89 uncovered lines — POST route handlers, error handler, cache invalidation)

All other modules >= 81%.

### web.py POST route coverage

10 POST routes exist in web.py:
1. `/suppress/system` — covered (CSRF, open redirect tests)
2. `/unsuppress/system` — NOT covered -> ADDED
3. `/suppress/incident` — NOT covered -> ADDED
4. `/unsuppress/incident` — NOT covered -> ADDED
5. `/assign-domain` — covered (XSS validation tests)
6. `/undo-assign-domain` — NOT covered -> ADDED
7. `/mark-reviewed` — NOT covered -> ADDED
8. `/undo-mark-reviewed` — NOT covered -> ADDED
9. `/promote-system` — covered (XSS validation test)
10. `/undo-promote` — NOT covered -> ADDED

Edge cases added: empty name/qa_id fields, missing form data.

### test_config.py coverage

All new fields from refactoring are covered:
- `deployment_env`: TestDeploymentEnv class (default, override, empty validation)
- `spec_colors`, `spec_shapes`, `spec_tags`: TestSpecCustomization class
- `sync_target`, `sync_protected_paths`, `sync_protected_top`: TestSyncConfig class
- `language`: tested in TestLanguageConfig
- `reviewed_systems`: tested in TestReviewedSystems

No gaps found.

### test_pipeline_e2e.py coverage

- No test with `deployment_env` config -> ADDED (test_deployment_env_passed_through)
- Existing tests cover: basic pipeline, domain_overrides, dry_run, validation thresholds

### `# type: ignore` and `# noqa` in tests

Found 10 occurrences:
- `tests/test_config.py` (9x): `import yaml  # noqa: F401` — used in pytest.importorskip pattern to check yaml availability. Legitimate use.
- `tests/test_cli.py` (1x): `import tomli as tomllib  # type: ignore[no-redef]` — conditional import for Python <3.11 compat. Legitimate use.

No problematic suppressions found.

---

## 7. Manual code review — architecture and API surface (Task 3)

### pipeline.py

- All public functions (`convert`, `main`) and private phase functions (`_parse`, `_build`, `_validate`, `_generate`) have full type annotations with return types.
- `ParseResult` is a NamedTuple with all 9 fields typed. `ConvertResult` is a dataclass with all 6 fields typed.
- No global mutable state — only module-level `logger` and imports.
- `convert()` has complete docstring with Parameters, Returns, Raises sections.
- No issues found.

### parsers.py

- Uses `defusedxml.ElementTree` for safe XML parsing (no XXE attacks).
- Every parser catches `ET.ParseError` gracefully with warning and continues.
- Empty/missing attributes handled via `.get('name', '').strip()` + `if not name: continue`.
- Empty archi_id: logged as warning, element skipped.
- Unicode in names: no issues — Python handles natively.
- Recursive XML traversal functions (`_extract_app_component_refs`, `_extract_all_element_refs`, `_extract_visual_nesting`) have no depth limit. Theoretical stack overflow on deeply nested XML, but ArchiMate diagrams are shallow in practice. Low risk.
- No issues requiring code changes.

### web.py

- CSRF token protection on all 10 POST routes via `_csrf_check` before_request hook.
- Open redirect prevention via `_safe_redirect` (rejects empty, non-`/` prefix, `//` prefix).
- Error handler (line 196): returns 500 with `html.escape(str(error))`. Properly escapes HTML but `ConfigError`/`ParseError` messages may contain filesystem paths (e.g. `/Users/.../model/`). Acceptable for internal tool, but noted as low-priority finding.
- POST routes return redirect (302) on success. Invalid domain returns 400 with `html.escape(domain)`.
- Secret key: uses `FLASK_SECRET_KEY` env var or `secrets.token_hex(32)`.
- Cache uses `time.monotonic()` — correct for elapsed time measurement.
- All HTTP status codes correct: 200 (GET), 302 (POST success), 400 (validation), 403 (CSRF), 500 (server error).

### builders/

All builder functions are deterministic (same input → same output):

- `build_systems()`: iterates `sorted(system_acs.items())`, returns `sorted(systems.values(), key=name)`.
- `assign_domains()`: uses `min()` with tie-breaking `(-count, name)` for consistent domain selection.
- `assign_subdomains()`: majority vote uses `min()` with deterministic tie-breaking.
- `build_integrations()`: `_dedup_integrations` uses `sorted(pair_flows.items())`.
- `build_data_entities()`: returns `sorted(entities, key=name)`.
- `build_data_access()`: returns `sorted(results, key=...)`.
- `build_deployment_topology()`: `roots.sort(key=name)`.
- `build_deployment_map()`: `result.sort()`.

No non-deterministic patterns (no `set()` iteration without sorting, no `dict()` iteration without sorting).

### models.py

- All 14 dataclasses have fully typed fields.
- All mutable defaults use `field(default_factory=...)`: `dict`, `list`, `set` — no bare mutable defaults.
- `DomainInfo.archi_ids` correctly uses `field(default_factory=set)`.
- No issues found.

### Summary of Task 3 findings

No critical or high-priority issues found. The codebase is well-structured:

1. **LOW**: web.py error handler may expose filesystem paths in 500 responses. Internal tool — acceptable risk.
2. **LOW**: Recursive XML traversal in parsers.py has no depth guard. ArchiMate XML is shallow — negligible risk.
3. **POSITIVE**: All builders are deterministic. All dataclass fields typed. No mutable default bugs. Full type annotations on pipeline API. defusedxml for safe parsing. CSRF + open redirect protection in web UI.
