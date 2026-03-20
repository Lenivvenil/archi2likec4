# Releasing archi2likec4

Step-by-step checklist for publishing a new release to PyPI and Homebrew.

---

## Prerequisites

Before your first release, configure the following once:

### TestPyPI trusted publisher (OIDC)

1. Go to https://test.pypi.org/manage/account/publishing/
2. Add a new publisher:
   - Repository owner: `Lenivvenil`
   - Repository name: `archi2likec4`
   - Workflow name: `test-publish.yml`
   - Environment name: `testpypi`
3. In GitHub repo → Settings → Environments, create environment `testpypi`

### PyPI trusted publisher (OIDC)

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new publisher:
   - Repository owner: `Lenivvenil`
   - Repository name: `archi2likec4`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. GitHub environment `pypi` must already exist in repo Settings → Environments

### HOMEBREW_TAP_TOKEN (GitHub PAT)

The `update-homebrew` job in `publish.yml` pushes to the tap repo
`Lenivvenil/homebrew-archi2likec4`. It needs a Personal Access Token with
`repo` (or `contents: write`) scope for that repository.

1. Go to https://github.com/settings/tokens → "Fine-grained tokens" → Generate new token
2. Set resource owner: `Lenivvenil`
3. Repository access: only `homebrew-archi2likec4`
4. Permissions → Contents: **Read and write**
5. Copy the token value
6. Go to `archi2likec4` repo → Settings → Secrets and variables → Actions
7. Create secret `HOMEBREW_TAP_TOKEN` with the token value

---

## Release steps

1. Update `CHANGELOG.md`: rename `[Unreleased]` → `[X.Y.Z] — YYYY-MM-DD`, add a
   new empty `[Unreleased]` section above it.

2. Bump version in `pyproject.toml`:
   ```
   version = "X.Y.Z"
   ```
   Also update fallback version in `archi2likec4/__init__.py` if present.

3. Commit:
   ```bash
   git commit -am "release: vX.Y.Z"
   ```

4. Tag:
   ```bash
   git tag vX.Y.Z
   ```

5. Push branch and tag:
   ```bash
   git push origin main --tags
   ```

6. Create GitHub Release:
   - Go to https://github.com/Lenivvenil/archi2likec4/releases/new
   - Choose tag `vX.Y.Z`
   - Title: `vX.Y.Z`
   - Body: paste the `[X.Y.Z]` section from `CHANGELOG.md`
   - Click **Publish release**

7. CI runs automatically (`publish.yml`):
   - Version consistency check (tag vs `pyproject.toml`)
   - `python -m build`
   - `twine check dist/*`
   - `archi2likec4 --version` smoke-test
   - Publish to PyPI (OIDC)
   - Update Homebrew tap Formula (SHA256 + URL)

8. Verify:
   ```bash
   pip install archi2likec4==X.Y.Z
   archi2likec4 --version
   brew upgrade archi2likec4   # or: brew install Lenivvenil/archi2likec4/archi2likec4
   ```

---

## Dry-run via TestPyPI

To test the build and publish process without touching production PyPI:

1. Go to https://github.com/Lenivvenil/archi2likec4/actions/workflows/test-publish.yml
2. Click **Run workflow**
3. Verify the package appears on https://test.pypi.org/project/archi2likec4/
