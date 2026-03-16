# archi2likec4 Roadmap

Post-1.1 ideas and planned improvements. Not committed, not prioritised — just a reference for future decisions.

---

## Near-term

### Pydantic config validation

Replace the hand-rolled `config.py` type checks with a Pydantic v2 model. Benefits:
- Precise error messages with field paths (`promote_children.EFS: expected str, got int`)
- Free JSON Schema export for editor autocompletion
- Easier to add new fields without forgetting validation

### JSON / YAML output format

Add `--format json` / `--format yaml` output mode alongside the current `.c4` files.
Enables downstream tooling that doesn't speak LikeC4 syntax (dashboards, custom renderers).

---

## Medium-term

### CI auto-generation pipeline

A GitHub Actions / GitLab CI template that:
1. Checks out the coArchi repository
2. Runs `archi2likec4`
3. Commits generated `.c4` files to a target branch
4. Opens a PR / MR if there are changes

Includes a staleness check (`scripts/check_staleness.py`) that fails CI if the model was updated but the generated files were not regenerated.

### Plugin architecture

Allow users to register custom parsers and generators as Python entry points:

```toml
[project.entry-points."archi2likec4.parsers"]
my_parser = "mypackage.parsers:CustomParser"
```

This would decouple bank-specific logic (domain patterns, promote rules) from the core library.

---

## Web UI

### Server-Sent Events (SSE) progress stream

Replace the blocking `/run` endpoint with an SSE stream so the browser shows live progress (parse → build → validate → generate) without polling.

### Diff view

After regeneration, show a unified diff of the generated `.c4` files in the Web UI before committing to disk.

### Dark theme

CSS custom properties for light/dark toggle. The Flask UI currently ships with a light-only stylesheet.

---

## Longer-term / speculative

- **Incremental generation**: track file mtimes, skip regeneration for unchanged domains
- **LikeC4 schema validation**: run `likec4 check` as part of the quality gate
- **Export to C4-PlantUML**: alternative backend for teams already using C4-PlantUML
- **ArchiMate 3.2 elements**: extend parsers to cover Motivation and Strategy layers
