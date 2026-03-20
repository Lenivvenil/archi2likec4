# Plan: Publish to Homebrew and PyPI

## Overview

Настроить полноценную публикацию archi2likec4 в PyPI и Homebrew. PyPI publish уже работает (OIDC trusted publishing, `.github/workflows/publish.yml`), но требует hardening: проверка версии, TestPyPI dry-run, build verification. Homebrew отсутствует полностью — нужно создать tap-репозиторий `homebrew-archi2likec4` с Formula и автоматическим обновлением при релизе.

## Validation Commands
- `uv run pytest tests/ -v --tb=short`
- `ruff check archi2likec4/ tests/`
- `uv run mypy archi2likec4/ --ignore-missing-imports`

---

### Task 1: Harden PyPI Publish Workflow

Текущий `publish.yml` публикует на PyPI при создании GitHub Release, но не проверяет собранный пакет и не тестирует на TestPyPI. Добавить проверки перед публикацией.

- [x] Прочитать `.github/workflows/publish.yml` — текущий workflow: checkout → setup-python → build → publish (OIDC)
- [x] `.github/workflows/publish.yml`: добавить шаг `Verify package` после `python -m build`: запустить `pip install twine && twine check dist/*` для валидации метаданных sdist/wheel
- [x] `.github/workflows/publish.yml`: добавить шаг `Install and smoke-test` после build: `pip install dist/*.whl && archi2likec4 --version` — убедиться что CLI запускается из собранного wheel
- [x] `.github/workflows/publish.yml`: добавить шаг `Version consistency check`: `python -c "import tomllib; v=tomllib.load(open('pyproject.toml','rb'))['project']['version']; assert f'v{v}' == '${{ github.event.release.tag_name }}', f'Tag mismatch: v{v} != ${{ github.event.release.tag_name }}'"` — tag должен совпадать с версией в `pyproject.toml`
- [x] Создать `.github/workflows/test-publish.yml`: новый workflow, trigger `workflow_dispatch` — собирает пакет и публикует на TestPyPI (`repository-url: https://test.pypi.org/legacy/`); добавить `environment: testpypi` и настроить OIDC trusted publisher для TestPyPI в GitHub repo settings (документировать в `RELEASING.md`)
- [x] Add/update tests: `tests/test_cli.py` — добавить `test_version_matches_pyproject` (прочитать версию из `pyproject.toml` через `tomllib`/`tomli`, сравнить с `archi2likec4.__version__`)
- [x] Mark completed

---

### Task 2: Create Homebrew Tap Repository Structure

Создать отдельный GitHub-репозиторий `homebrew-archi2likec4` с Formula. Homebrew tap позволяет устанавливать через `brew install Lenivvenil/archi2likec4/archi2likec4`.

- [ ] На GitHub создать публичный репозиторий `Lenivvenil/homebrew-archi2likec4` (пустой, с README)
- [ ] Клонировать репозиторий локально: `git clone https://github.com/Lenivvenil/homebrew-archi2likec4.git`
- [ ] Создать `Formula/archi2likec4.rb` — Homebrew Formula на Ruby:
  - `desc "Convert coArchi XML (ArchiMate) to LikeC4 .c4 files"`
  - `homepage "https://github.com/Lenivvenil/archi2likec4"`
  - `url "https://files.pythonhosted.org/packages/source/a/archi2likec4/archi2likec4-{VERSION}.tar.gz"` — URL на PyPI sdist
  - `sha256 "{HASH}"` — SHA256 хеш sdist-архива (вычислить через `shasum -a 256`)
  - `license "MIT"`
  - `depends_on "python@3.12"`
  - Использовать `include Language::Python::Virtualenv` + `virtualenv_install_with_resources` паттерн
  - `def install`: `virtualenv_install_with_resources`
  - `test do`: `system bin/"archi2likec4", "--version"`
- [ ] Создать `README.md` в tap-репозитории: инструкции `brew tap Lenivvenil/archi2likec4 && brew install archi2likec4`
- [ ] Опубликовать текущую версию (1.3.0): скачать sdist с PyPI, вычислить SHA256, подставить в Formula, commit и push
- [ ] Add/update tests: в tap-репозитории запустить `brew audit --strict Formula/archi2likec4.rb` и `brew test archi2likec4` для валидации формулы
- [ ] Mark completed

---

### Task 3: Automated Formula Bump on Release

Автоматизировать обновление Homebrew Formula при каждом PyPI-релизе. При создании GitHub Release в основном репозитории — GitHub Action обновляет version и SHA256 в tap-репозитории.

- [ ] Прочитать `.github/workflows/publish.yml` — найти место для добавления шага после успешной PyPI публикации
- [ ] `.github/workflows/publish.yml`: добавить job `update-homebrew` (needs: `publish`) с шагами:
  - Checkout tap repo: `actions/checkout@v4` с `repository: Lenivvenil/homebrew-archi2likec4`, `token: ${{ secrets.HOMEBREW_TAP_TOKEN }}`
  - Вычислить SHA256 sdist: `curl -sL "https://files.pythonhosted.org/packages/source/a/archi2likec4/archi2likec4-${VERSION}.tar.gz" | shasum -a 256`
  - Обновить `Formula/archi2likec4.rb`: заменить `url` и `sha256` через `sed` (или Python-скрипт)
  - Commit и push: `git commit -am "archi2likec4 ${VERSION}" && git push`
- [ ] Документировать необходимость создания GitHub PAT `HOMEBREW_TAP_TOKEN` с правом `repo` для `homebrew-archi2likec4` — добавить инструкцию в `RELEASING.md`
- [ ] Альтернативно: создать `.github/workflows/bump-formula.yml` в tap-репозитории с trigger `repository_dispatch` — основной репозиторий отправляет event через `peter-evans/repository-dispatch` action после публикации
- [ ] Add/update tests: после push в tap-repo, GitHub Actions в tap-репозитории запускают `brew audit --strict Formula/archi2likec4.rb` (создать `.github/workflows/audit.yml` в tap-репозитории)
- [ ] Mark completed

---

### Task 4: Installation Documentation and Release Checklist

Обновить документацию проекта: инструкции по установке через pip и brew, `RELEASING.md` с пошаговым чеклистом выпуска новой версии.

- [ ] Прочитать `README.md` — найти текущую секцию установки
- [ ] `README.md`: обновить секцию "Installation" — три способа: `pip install archi2likec4` (PyPI), `brew install Lenivvenil/archi2likec4/archi2likec4` (Homebrew), `pip install archi2likec4[web]` (с Flask UI); добавить badges: PyPI version, Homebrew tap, Python versions, License
- [ ] Создать `RELEASING.md` в корне проекта — пошаговый чеклист:
  1. Обновить `[Unreleased]` → `[X.Y.Z] — YYYY-MM-DD` в `CHANGELOG.md`
  2. Bump version в `pyproject.toml` и fallback в `__init__.py`
  3. Commit: `git commit -am "release: vX.Y.Z"`
  4. Tag: `git tag vX.Y.Z`
  5. Push: `git push origin main --tags`
  6. Создать GitHub Release (tag → Release notes из CHANGELOG)
  7. CI автоматически: build → twine check → smoke test → PyPI publish → Homebrew tap update
  8. Проверить: `pip install archi2likec4==X.Y.Z` и `brew upgrade archi2likec4`
- [ ] `CHANGELOG.md`: добавить запись в `[Unreleased]` про Homebrew tap, TestPyPI workflow, publish hardening
- [ ] Add/update tests: `tests/test_cli.py` — убедиться что `test_version_flag` и `test_help_shows_web` проходят (существующие тесты); добавить `test_version_matches_pyproject` если не добавлен в Task 1
- [ ] Mark completed
