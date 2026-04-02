"""Tests for spec generation in archi2likec4.generators.spec."""

from archi2likec4.generators import generate_spec
from tests.helpers import MockConfig

# ── generate_spec ────────────────────────────────────────────────────────

class TestGenerateSpec:
    def test_contains_kinds(self):
        spec = generate_spec()
        assert 'element domain' in spec
        assert 'element system' in spec
        assert 'element subsystem' in spec
        assert 'element appFunction' in spec
        assert 'element dataEntity' in spec

    def test_specification_contains_subdomain_kind(self):
        spec = generate_spec()
        assert 'element subdomain' in spec
        # subdomain should appear between domain and system
        idx_domain = spec.index('element domain')
        idx_subdomain = spec.index('element subdomain')
        idx_system = spec.index('element system')
        assert idx_domain < idx_subdomain < idx_system

    def test_contains_tags(self):
        spec = generate_spec()
        assert 'tag to_review' in spec
        assert 'tag external' in spec

    def test_contains_colors(self):
        spec = generate_spec()
        assert 'color archi-app' in spec

    def test_custom_colors_from_config(self):
        cfg = MockConfig(spec_colors={
            'archi-app': '#FF0000',
            'archi-app-light': '#BDE0F0',
            'archi-data': '#F0D68A',
            'archi-store': '#B0B0B0',
            'archi-tech': '#93D275',
            'archi-tech-light': '#C5E6B8',
        })
        spec = generate_spec(cfg)
        assert 'color archi-app #FF0000' in spec
        assert '#7EB8DA' not in spec

    def test_custom_shapes_from_config(self):
        cfg = MockConfig(spec_shapes={
            'domain': 'hexagon',
            'subdomain': 'rectangle',
            'system': 'component',
            'subsystem': 'component',
            'appFunction': 'rectangle',
            'dataEntity': 'document',
            'dataStore': 'cylinder',
            'site': 'rectangle',
            'segment': 'rectangle',
            'cluster': 'rectangle',
            'server': 'rectangle',
            'vm': 'rectangle',
            'namespace': 'rectangle',
            'infraSoftware': 'cylinder',
        })
        spec = generate_spec(cfg)
        # domain should use hexagon now
        domain_idx = spec.index('element domain')
        domain_block = spec[domain_idx:spec.index('}', spec.index('}', domain_idx) + 1) + 1]
        assert 'shape hexagon' in domain_block

    def test_custom_tags_from_config(self):
        cfg = MockConfig(spec_tags=['custom_tag', 'another_tag'])
        spec = generate_spec(cfg)
        assert 'tag custom_tag' in spec
        assert 'tag another_tag' in spec
        # Built-in tags are always present (generators emit them)
        assert 'tag to_review' in spec
        assert 'tag external' in spec
        assert 'tag entity' in spec

    def test_custom_tags_from_real_config(self):
        """ConvertConfig (not MockConfig) preserves built-in tags when spec_tags are set."""
        from archi2likec4.config import ConvertConfig
        cfg = ConvertConfig(spec_tags=['custom_tag', 'another_tag'])
        spec = generate_spec(cfg)
        assert 'tag custom_tag' in spec
        assert 'tag another_tag' in spec
        assert 'tag to_review' in spec
        assert 'tag external' in spec
        assert 'tag entity' in spec

    def test_config_none_uses_defaults(self):
        spec_default = generate_spec()
        spec_none = generate_spec(None)
        assert spec_default == spec_none


# ── generate_spec_infra_kinds ────────────────────────────────────────────

class TestGenerateSpec_InfraKinds:
    def test_spec_includes_environment_kind(self):
        spec = generate_spec()
        assert 'deploymentNode environment' in spec

    def test_spec_includes_deployment_kinds(self):
        spec = generate_spec()
        assert 'deploymentNode site' in spec
        assert 'deploymentNode segment' in spec
        assert 'deploymentNode cluster' in spec
        assert 'deploymentNode server' in spec
        assert 'deploymentNode vm' in spec
        assert 'deploymentNode namespace' in spec
        assert 'deploymentNode infraSoftware' in spec

    def test_spec_excludes_old_kinds(self):
        spec = generate_spec()
        assert 'deploymentNode infraNode' not in spec
        assert 'deploymentNode infraZone' not in spec
        assert 'deploymentNode infraLocation' not in spec
        assert 'deploymentNode host' not in spec

    def test_spec_segment_style(self):
        spec = generate_spec()
        # segment should have dotted border
        seg_idx = spec.index('deploymentNode segment')
        seg_block = spec[seg_idx:spec.index('}', spec.index('}', seg_idx) + 1) + 1]
        assert 'border dotted' in seg_block

    def test_spec_site_style(self):
        spec = generate_spec()
        # site should have dashed border
        site_idx = spec.index('deploymentNode site')
        site_block = spec[site_idx:spec.index('}', spec.index('}', site_idx) + 1) + 1]
        assert 'border dashed' in site_block

    def test_spec_no_deployed_on(self):
        spec = generate_spec()
        assert 'relationship deployedOn' not in spec

    def test_spec_includes_infra_tags(self):
        spec = generate_spec()
        assert 'tag infrastructure' in spec
        assert 'tag cluster' in spec
