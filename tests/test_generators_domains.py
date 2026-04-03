"""Tests for domain and system generation in archi2likec4.generators."""

from archi2likec4.generators import (
    generate_domain_c4,
    generate_system_detail_c4,
)
from archi2likec4.models import (
    AppFunction,
    Integration,
    Subdomain,
    Subsystem,
    System,
)

# ── generate_domain_c4 ──────────────────────────────────────────────────

class TestGenerateDomainC4:
    def test_basic_structure(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     metadata={'ci': 'CI-1', 'full_name': 'EFS'})
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert "channels = domain 'Channels'" in result
        assert "efs = system 'EFS'" in result
        assert 'model {' in result

    def test_system_metadata(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     metadata={'ci': 'CI-42'})
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert "archi_id 'sys-1'" in result
        assert "ci 'CI-42'" in result

    def test_system_tags(self):
        sys = System(c4_id='ext', name='ExtSvc', archi_id='sys-1',
                     tags=['external'], metadata={})
        result = generate_domain_c4('platform', 'Platform', [sys])
        assert '#external' in result

    def test_systems_sorted_by_name(self):
        sys1 = System(c4_id='zebra', name='Zebra', archi_id='s1', metadata={})
        sys2 = System(c4_id='alpha', name='Alpha', archi_id='s2', metadata={})
        result = generate_domain_c4('d', 'D', [sys1, sys2])
        idx_alpha = result.index('Alpha')
        idx_zebra = result.index('Zebra')
        assert idx_alpha < idx_zebra

    def test_domain_file_contains_subdomain_block(self):
        sd = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                       system_ids=['efs'])
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     subdomain='payments')
        result = generate_domain_c4('channels', 'Channels', [sys], subdomains=[sd])
        assert "payments = subdomain 'Payments'" in result
        assert 'model {' in result

    def test_system_nested_in_subdomain(self):
        sd = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                       system_ids=['efs'])
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     subdomain='payments')
        result = generate_domain_c4('channels', 'Channels', [sys], subdomains=[sd])
        # system block should come after subdomain opening
        idx_sd = result.index("payments = subdomain")
        idx_sys = result.index("efs = system")
        assert idx_sd < idx_sys

    def test_system_without_subdomain_at_domain_root(self):
        sd = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                       system_ids=['efs'])
        sys_in_sd = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                           subdomain='payments')
        sys_no_sd = System(c4_id='crm', name='CRM', archi_id='s2', metadata={},
                           subdomain='')
        result = generate_domain_c4('channels', 'Channels', [sys_in_sd, sys_no_sd],
                                    subdomains=[sd])
        # CRM should be present and not inside subdomain block
        assert "crm = system 'CRM'" in result
        # EFS inside subdomain
        assert "payments = subdomain" in result
        idx_sd_close = result.index('    }')
        idx_crm = result.index("crm = system")
        # CRM rendered after subdomain block closes
        assert idx_crm > idx_sd_close

    def test_system_with_documentation(self):
        # Covers _render_system documentation branch (lines 23-26)
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     documentation='An enterprise file system')
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert "description 'An enterprise file system'" in result

    def test_system_long_documentation_truncated(self):
        # Covers _render_system documentation truncation (lines 24-25)
        long_doc = 'z' * 600
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     documentation=long_doc)
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert '...' in result

    def test_system_with_links(self):
        # Covers _render_system links (line 28)
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     links=[('https://docs.example.com', 'Docs')])
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert 'https://docs.example.com' in result

    def test_system_with_api_interfaces(self):
        # Covers _render_system api_interfaces (lines 34-35)
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     api_interfaces=['REST', 'gRPC'])
        result = generate_domain_c4('channels', 'Channels', [sys])
        assert 'api_interfaces' in result
        assert 'REST' in result

    def test_subdomain_with_no_systems_skipped(self):
        # Covers line 80: subdomain skipped when it has no systems assigned
        sd_empty = Subdomain(c4_id='empty_sd', name='EmptySD', domain_id='channels',
                             system_ids=[])
        sd_full = Subdomain(c4_id='payments', name='Payments', domain_id='channels',
                            system_ids=['efs'])
        sys = System(c4_id='efs', name='EFS', archi_id='s1', metadata={},
                     subdomain='payments')
        result = generate_domain_c4('channels', 'Channels', [sys],
                                    subdomains=[sd_empty, sd_full])
        assert 'empty_sd' not in result
        assert 'payments' in result


# ── generate_system_detail_c4 ───────────────────────────────────────────

class TestGenerateSystemDetailC4:
    def test_extend_block(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert 'extend channels.efs {' in result
        assert "core = subsystem 'EFS.Core'" in result

    def test_detail_view(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[], functions=[], metadata={})
        # Need at least something to generate
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff')
        sys.functions.append(fn)
        result = generate_system_detail_c4('channels', sys)
        assert 'view efs_detail of channels.efs' in result
        assert "title 'EFS'" in result
        assert 'include *' in result

    def test_appfunctions_rendered(self):
        fn = AppFunction(archi_id='fn-1', name='CreateAccount', c4_id='create_account',
                         documentation='Creates a new account')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     functions=[fn], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert "create_account = appFunction 'CreateAccount'" in result
        assert "description 'Creates a new account'" in result

    def test_extend_path_includes_subdomain(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={}, subdomain='payments')
        result = generate_system_detail_c4('channels', sys)
        assert 'extend channels.payments.efs {' in result
        assert 'view efs_detail of channels.payments.efs' in result

    def test_extend_path_without_subdomain(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={}, subdomain='')
        result = generate_system_detail_c4('channels', sys)
        assert 'extend channels.efs {' in result
        assert 'view efs_detail of channels.efs' in result

    def test_appfunction_long_doc_truncated(self):
        # Covers _render_appfunction truncation branch (line 18)
        long_doc = 'x' * 400
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff',
                         documentation=long_doc)
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     functions=[fn], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert '...' in result

    def test_subsystem_with_tags_and_doc(self):
        # Covers _render_subsystem tag (line 38) and documentation (lines 40-43)
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        tags=['internal'], documentation='A core subsystem',
                        metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert '#internal' in result
        assert "description 'A core subsystem'" in result

    def test_subsystem_long_doc_truncated(self):
        # Covers _render_subsystem truncation branch (lines 41-42)
        long_doc = 'y' * 600
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        documentation=long_doc, metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert '...' in result

    def test_subsystem_with_links(self):
        # Covers _render_subsystem links (line 45)
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        links=[('https://wiki.example.com', 'Wiki')], metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert 'https://wiki.example.com' in result

    def test_subsystem_with_metadata_items(self):
        # Covers _render_subsystem metadata loop (line 49)
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        metadata={'ci': 'CI-10', 'team': 'platform'})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert "ci 'CI-10'" in result

    def test_subsystem_with_nested_appfunctions(self):
        # Covers _render_subsystem functions block (lines 53-55)
        fn = AppFunction(archi_id='fn-1', name='DoWork', c4_id='do_work')
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1',
                        functions=[fn], metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys)
        assert "do_work = appFunction 'DoWork'" in result

    def test_outgoing_relationships_rendered(self):
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        outgoing = [
            Integration(source_path='channels.efs', target_path='products.abs',
                        name='Payment flow', rel_type=''),
            Integration(source_path='channels.efs', target_path='platform.esb',
                        name='', rel_type=''),
        ]
        result = generate_system_detail_c4('channels', sys, outgoing=outgoing)
        assert "channels.efs -> products.abs 'Payment flow'" in result
        assert 'channels.efs -> platform.esb' in result
        # Relationships should be outside the extend block
        lines = result.split('\n')
        extend_close_idx = next(i for i, line in enumerate(lines) if line.strip() == '}' and i > 3)
        rel_lines = [line for line in lines[extend_close_idx:] if '->' in line]
        assert len(rel_lines) == 2

    def test_no_outgoing_relationships(self):
        sub = Subsystem(c4_id='core', name='Core', archi_id='sub-1', metadata={})
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], metadata={})
        result = generate_system_detail_c4('channels', sys, outgoing=None)
        assert '->' not in result

    def test_outgoing_only_system(self):
        """System with no subsystems/functions but with outgoing relationships."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[], functions=[], metadata={})
        outgoing = [
            Integration(source_path='channels.efs', target_path='products.abs',
                        name='Payment flow', rel_type=''),
        ]
        result = generate_system_detail_c4('channels', sys, outgoing=outgoing)
        assert 'extend channels.efs {' in result
        assert "channels.efs -> products.abs 'Payment flow'" in result
