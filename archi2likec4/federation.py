"""Federation: generators for federate.py script and registry."""

from importlib import resources


def generate_federate_script() -> str:
    """Return the content of the federate.py script template.

    The script is stored as a real .py file under ``archi2likec4/scripts/``
    so it can be linted, tested, and read by IDEs.
    """
    ref = resources.files('archi2likec4.scripts').joinpath('federate_template.py')
    return ref.read_text(encoding='utf-8')


def generate_federation_registry() -> str:
    """Generate federation-registry.yaml template."""
    return """\
# Federation Registry
# Lists all project repositories that contribute system.c4 files.
#
# To add your project:
# 1. Create docs/system.c4 in your repo (use specification.c4 from root)
# 2. Optionally create docs/system.yaml with your system spec
# 3. Add an entry below and submit MR

projects: []

# Template for new projects:
#  - name: your-service-name
#    repo: https://gitlab.example.com/YOUR_GROUP/your-repo.git
#    branch: main
#    sha: ""            # pin to specific commit (optional, overrides branch HEAD)
#    c4_path: docs/system.c4
#    yaml_path: docs/system.yaml
#    domain: your-domain
#    owner: Your Department
#    contact: your-email@example.com
"""
