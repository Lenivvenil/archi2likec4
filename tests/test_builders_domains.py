"""Tests for builders/domains.py module."""

from archi2likec4.builders import (
    apply_domain_prefix,
    assign_domains,
    assign_subdomains,
    build_archi_to_c4_map,
)
from archi2likec4.builders.domains import (
    _apply_collision_guard,
    _apply_domain_overrides,
    _apply_extra_patterns,
    _assign_by_view_membership,
    _assign_subdomain_by_folder,
    _assign_subdomain_by_majority_vote,
    _build_subdomain_lookup,
    _promote_children_domains,
)
from archi2likec4.models import (
    AppFunction,
    DataAccess,
    DomainInfo,
    Integration,
    ParsedSubdomain,
    Subdomain,
    Subsystem,
    System,
)


class TestAssignDomains:
    def test_basic_assignment(self):
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids={'sys-1'})]
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1')
        result = assign_domains([sys], domains)
        assert len(result['channels']) == 1
        assert sys.domain == 'channels'

    def test_unassigned(self):
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids={'other-id'})]
        sys = System(c4_id='crm', name='CRM', archi_id='sys-1')
        result = assign_domains([sys], domains, promote_children={})
        assert len(result['unassigned']) == 1
        assert sys.domain == 'unassigned'

    def test_extra_domain_patterns(self):
        """Systems matching extra_domain_patterns should be assigned."""
        domains = []
        sys = System(c4_id='elk', name='ELK', archi_id='sys-1')
        patterns = [{'c4_id': 'platform', 'name': 'Platform', 'patterns': ['ELK', 'Grafana']}]
        assign_domains([sys], domains, extra_domain_patterns=patterns)
        # ELK matches 'platform' pattern
        assert sys.domain == 'platform'

    def test_most_hits_wins(self):
        d1 = DomainInfo(c4_id='d1', name='D1', archi_ids={'sys-1'})
        d2 = DomainInfo(c4_id='d2', name='D2', archi_ids={'sys-1', 'sub-1'})
        sub = Subsystem(c4_id='sub', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', subsystems=[sub])
        assign_domains([sys], [d1, d2])
        assert sys.domain == 'd2'  # 2 hits vs 1


# ── _apply_domain_overrides ──────────────────────────────────────────────

class TestApplyDomainOverrides:
    def test_override_assigns_and_returns_remaining(self):
        s1 = System(c4_id='efs', name='EFS', archi_id='sys-1')
        s2 = System(c4_id='crm', name='CRM', archi_id='sys-2')
        result: dict[str, list[System]] = {'channels': [], 'unassigned': []}
        remaining = _apply_domain_overrides([s1, s2], {'EFS': 'channels'}, result)
        assert s1.domain == 'channels'
        assert result['channels'] == [s1]
        assert remaining == [s2]

    def test_override_creates_new_domain_key(self):
        s1 = System(c4_id='efs', name='EFS', archi_id='sys-1')
        result: dict[str, list[System]] = {'unassigned': []}
        _apply_domain_overrides([s1], {'EFS': 'new_domain'}, result)
        assert 'new_domain' in result
        assert s1.domain == 'new_domain'

    def test_no_match_returns_all(self):
        s1 = System(c4_id='efs', name='EFS', archi_id='sys-1')
        result: dict[str, list[System]] = {'unassigned': []}
        remaining = _apply_domain_overrides([s1], {'OTHER': 'channels'}, result)
        assert remaining == [s1]


# ── _assign_by_view_membership ──────────────────────────────────────────

class TestAssignByViewMembership:
    def test_assigns_by_hit_count(self):
        sub = Subsystem(c4_id='sub', name='EFS.Core', archi_id='sub-1')
        s1 = System(c4_id='efs', name='EFS', archi_id='sys-1', subsystems=[sub])
        id_to_domains = {'sys-1': ['d1', 'd2'], 'sub-1': ['d2']}
        result: dict[str, list[System]] = {'d1': [], 'd2': [], 'unassigned': []}
        _assign_by_view_membership([s1], id_to_domains, result)
        assert s1.domain == 'd2'  # 2 hits vs 1

    def test_unmatched_goes_to_unassigned(self):
        s1 = System(c4_id='crm', name='CRM', archi_id='sys-1')
        result: dict[str, list[System]] = {'unassigned': []}
        _assign_by_view_membership([s1], {}, result)
        assert s1.domain == 'unassigned'
        assert result['unassigned'] == [s1]

    def test_tie_broken_alphabetically(self):
        s1 = System(c4_id='efs', name='EFS', archi_id='sys-1')
        id_to_domains = {'sys-1': ['beta', 'alpha']}
        result: dict[str, list[System]] = {'alpha': [], 'beta': [], 'unassigned': []}
        _assign_by_view_membership([s1], id_to_domains, result)
        assert s1.domain == 'alpha'


# ── _promote_children_domains ───────────────────────────────────────────

class TestPromoteChildrenDomains:
    def test_promotes_child_to_parent_domain(self):
        s1 = System(c4_id='efs_core', name='EFS.Core', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'channels': [], 'unassigned': [s1]}
        _promote_children_domains(result, {'EFS': 'channels'})
        assert s1.domain == 'channels'
        assert result['channels'] == [s1]
        assert result['unassigned'] == []

    def test_no_match_stays_unassigned(self):
        s1 = System(c4_id='crm', name='CRM', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'unassigned': [s1]}
        _promote_children_domains(result, {'EFS': 'channels'})
        assert s1.domain == 'unassigned'
        assert result['unassigned'] == [s1]

    def test_creates_domain_key_if_missing(self):
        s1 = System(c4_id='efs_core', name='EFS.Core', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'unassigned': [s1]}
        _promote_children_domains(result, {'EFS': 'new_domain'})
        assert 'new_domain' in result
        assert s1.domain == 'new_domain'


# ── _apply_extra_patterns ───────────────────────────────────────────────

class TestApplyExtraPatterns:
    def test_pattern_matches_case_insensitive(self):
        s1 = System(c4_id='elk', name='ELK', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'unassigned': [s1]}
        patterns = [{'c4_id': 'platform', 'patterns': ['elk', 'grafana']}]
        _apply_extra_patterns(result, patterns)
        assert s1.domain == 'platform'
        assert result['platform'] == [s1]
        assert result['unassigned'] == []

    def test_no_match_stays_unassigned(self):
        s1 = System(c4_id='crm', name='CRM', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'unassigned': [s1]}
        patterns = [{'c4_id': 'platform', 'patterns': ['elk']}]
        _apply_extra_patterns(result, patterns)
        assert s1.domain == 'unassigned'
        assert result['unassigned'] == [s1]

    def test_empty_patterns_no_change(self):
        s1 = System(c4_id='crm', name='CRM', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'unassigned': [s1]}
        _apply_extra_patterns(result, [])
        assert result['unassigned'] == [s1]

    def test_multiple_patterns_first_match_wins(self):
        s1 = System(c4_id='elk', name='ELK', archi_id='sys-1', domain='unassigned')
        result: dict[str, list[System]] = {'unassigned': [s1]}
        patterns = [
            {'c4_id': 'infra', 'patterns': ['elk']},
            {'c4_id': 'platform', 'patterns': ['elk']},
        ]
        _apply_extra_patterns(result, patterns)
        assert s1.domain == 'infra'


# ── apply_domain_prefix ──────────────────────────────────────────────────

class TestApplyDomainPrefix:
    def test_integration_paths(self):
        intg = Integration(source_path='efs', target_path='crm', name='flow', rel_type='')
        sys_domain = {'efs': 'channels', 'crm': 'customer_service'}
        apply_domain_prefix([intg], [], sys_domain)
        assert intg.source_path == 'channels.efs'
        assert intg.target_path == 'customer_service.crm'

    def test_data_access_paths(self):
        da = DataAccess(system_path='efs', entity_id='de_account', name='')
        sys_domain = {'efs': 'channels'}
        apply_domain_prefix([], [da], sys_domain)
        assert da.system_path == 'channels.efs'

    def test_unknown_domain_fallback(self):
        intg = Integration(source_path='unknown', target_path='efs', name='', rel_type='')
        sys_domain = {'efs': 'channels'}
        apply_domain_prefix([intg], [], sys_domain)
        assert intg.source_path == 'unassigned.unknown'


# ── build_archi_to_c4_map ───────────────────────────────────────────────

class TestBuildArchiToC4Map:
    def test_system_mapping(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sys-1'] == 'channels.efs'

    def test_subsystem_mapping(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', subsystems=[sub])
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sub-1'] == 'channels.efs.core'

    def test_function_mapping(self):
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', functions=[fn])
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['fn-1'] == 'channels.efs.do_stuff'

    def test_extra_archi_ids(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     extra_archi_ids=['sys-dup'])
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sys-dup'] == 'channels.efs'


# ── promote_children ────────────────────────────────────────────────────

class TestAssignDomainsFallback:
    """Tests for PROMOTE_CHILDREN fallback_domain in assign_domains."""

    def test_promoted_child_gets_fallback_domain(self):
        """Unassigned promoted child should get fallback domain from config."""
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids=set())]
        sys = System(c4_id='efs_card_service', name='EFS.Card_Service', archi_id='s-1')
        result = assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        assert sys.domain == 'channels'
        assert sys in result['channels']

    def test_non_promoted_stays_unassigned(self):
        """System not matching any promote prefix stays unassigned."""
        domains = [DomainInfo(c4_id='channels', name='Channels', archi_ids=set())]
        sys = System(c4_id='crm', name='CRM', archi_id='s-1')
        assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        assert sys.domain != 'channels'

    def test_view_membership_overrides_fallback(self):
        """If system is assigned via view membership, fallback is not used."""
        domains = [
            DomainInfo(c4_id='products', name='Products', archi_ids={'s-1'}),
            DomainInfo(c4_id='channels', name='Channels', archi_ids=set()),
        ]
        sys = System(c4_id='efs_svc', name='EFS.Svc', archi_id='s-1')
        assign_domains([sys], domains, promote_children={'EFS': 'channels'})
        # View membership (products) takes priority over fallback (channels)
        assert sys.domain == 'products'

    def test_custom_extra_domain_patterns(self):
        """Custom extra_domain_patterns override hardcoded EXTRA_DOMAIN_PATTERNS."""
        domains = [DomainInfo(c4_id='core', name='Core', archi_ids=set())]
        sys = System(c4_id='my_grafana', name='Grafana', archi_id='s-1')
        custom_patterns = [
            {'c4_id': 'monitoring', 'name': 'Monitoring', 'patterns': ['Grafana', 'ELK']},
        ]
        result = assign_domains(
            [sys], domains, promote_children={},
            extra_domain_patterns=custom_patterns)
        assert sys.domain == 'monitoring'
        assert sys in result['monitoring']

    def test_empty_extra_domain_patterns(self):
        """Empty extra_domain_patterns means no third-pass assignment."""
        domains = [DomainInfo(c4_id='core', name='Core', archi_ids=set())]
        sys = System(c4_id='my_grafana', name='Grafana', archi_id='s-1')
        result = assign_domains(
            [sys], domains, promote_children={},
            extra_domain_patterns=[])
        # With no patterns, system stays unassigned
        assert sys.domain == 'unassigned'
        assert sys in result['unassigned']


# ── integration fan-out ──────────────────────────────────────────────────

class TestAssignSubdomains:
    def test_system_assigned_to_subdomain(self):
        """System whose archi_id is in ParsedSubdomain.component_ids gets assigned."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'banking'
        assert len(subdomains) == 1
        assert subdomains[0].c4_id == 'banking'
        assert subdomains[0].name == 'Banking'
        assert subdomains[0].domain_id == 'channels'
        assert 'efs' in subdomains[0].system_ids
        assert ('channels', 'banking') in subdomain_systems
        assert 'efs' in subdomain_systems[('channels', 'banking')]

    def test_system_without_subdomain_falls_back(self):
        """System not in any ParsedSubdomain keeps empty subdomain."""
        sys = System(c4_id='crm', name='CRM', archi_id='sys-2', domain='customer_service')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],  # sys-2 not included
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == ''
        assert len(subdomains) == 0

    def test_extra_archi_ids_matched(self):
        """System with matching extra_archi_id also gets assigned to subdomain."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     extra_archi_ids=['sys-dup'], domain='channels')
        psd = ParsedSubdomain(
            archi_id='payments',
            name='Payments',
            domain_folder='channels',
            component_ids=['sys-dup'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'payments'

    def test_cross_domain_subdomains_not_merged(self):
        """Same subdomain name in different domains creates separate Subdomain objects."""
        sys1 = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        sys2 = System(c4_id='crm', name='CRM', archi_id='sys-2', domain='products')
        psd1 = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        psd2 = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='products',
            component_ids=['sys-2'],
        )
        subdomains, _ = assign_subdomains([sys1, sys2], [psd1, psd2])
        assert len(subdomains) == 2
        assert {(s.domain_id, s.c4_id) for s in subdomains} == {
            ('channels', 'core'), ('products', 'core')
        }

    def test_empty_parsed_subdomains(self):
        """No parsed subdomains → no assignments."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        subdomains, subdomain_systems = assign_subdomains([sys], [])
        assert sys.subdomain == ''
        assert subdomains == []
        assert subdomain_systems == {}

    def test_multiple_systems_in_same_subdomain(self):
        """Multiple systems can belong to the same subdomain."""
        sys1 = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        sys2 = System(c4_id='cards', name='Cards', archi_id='sys-2', domain='channels')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1', 'sys-2'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys1, sys2], [psd])
        assert len(subdomains) == 1
        assert sorted(subdomains[0].system_ids) == ['cards', 'efs']
        assert sorted(subdomain_systems[('channels', 'banking')]) == ['cards', 'efs']

    def test_foreign_domain_subdomain_not_assigned(self):
        """System moved to a different domain must not keep the parsed subdomain."""
        # System appears in parsed subdomain for 'channels', but its final domain is 'products'
        # (e.g. moved by domain_overrides). Should not receive the foreign subdomain.
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='products')
        psd = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',  # different domain
            component_ids=['sys-1'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == ''
        assert subdomains == []
        assert subdomain_systems == {}

    def test_merged_system_extra_archi_id_finds_same_domain_subdomain(self):
        """Merged system whose primary archi_id hits a foreign subdomain must
        keep searching extra_archi_ids until a same-domain candidate is found.

        Regression: previously the loop broke on the first match regardless of
        domain, then the outer domain guard skipped the system entirely.
        """
        # Merged system: primary id came from 'products', extra id from 'channels'
        sys = System(
            c4_id='efs',
            name='EFS',
            archi_id='sys-foreign',   # component_id in products/retail
            extra_archi_ids=['sys-correct'],  # component_id in channels/banking
            domain='channels',
        )
        psd_foreign = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='products',   # foreign domain
            component_ids=['sys-foreign'],
        )
        psd_correct = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',   # correct domain
            component_ids=['sys-correct'],
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd_foreign, psd_correct]
        )
        assert sys.subdomain == 'banking', (
            'extra_archi_id hit in same domain must be used when primary id '
            'points to a foreign-domain subdomain'
        )
        assert any(sd.c4_id == 'banking' for sd in subdomains)
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])

    def test_manual_overrides_take_precedence(self):
        """manual_overrides override folder-based auto-detection."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        # Auto-detection would assign to 'retail'
        psd_retail = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        # Manual override targets 'banking'
        psd_banking = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=[],  # no auto components
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd_retail, psd_banking],
            manual_overrides={'EFS': 'banking'},
        )
        assert sys.subdomain == 'banking'
        assert any(sd.c4_id == 'banking' for sd in subdomains)
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])
        assert 'efs' not in subdomain_systems.get(('channels', 'retail'), [])

    def test_manual_overrides_unknown_system_skipped(self):
        """manual_overrides with an unknown system name is silently skipped."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',
            component_ids=[],
        )
        # 'NoSuchSystem' doesn't exist — should not raise
        subdomains, _ = assign_subdomains(
            [sys], [psd],
            manual_overrides={'NoSuchSystem': 'retail'},
        )
        assert sys.subdomain == ''

    def test_manual_overrides_invalid_subdomain_falls_back_to_auto(self):
        """manual_overrides with a non-existent subdomain must not clear auto-detection.

        A bad override like {'EFS': 'missing'} should be ignored so that the system
        still receives its folder-based subdomain assignment instead of getting none.
        """
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        # 'missing' subdomain does not exist — auto-detection should still run
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd],
            manual_overrides={'EFS': 'missing'},
        )
        assert sys.subdomain == 'banking', (
            'invalid override target must not clear auto-detected subdomain'
        )
        assert len(subdomains) == 1
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])

    def test_manual_overrides_cross_domain_collision(self):
        """manual_overrides use domain-scoped lookup to avoid cross-domain collisions.

        When two domains each have a subdomain with the same archi_id (e.g. 'core'),
        the override must assign the system to the subdomain in its own domain,
        not the one from the other domain.
        """
        sys_efs = System(c4_id='efs', name='EFS', archi_id='sys-efs', domain='channels')
        # channels/core — correct target for EFS override
        psd_channels_core = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='channels',
            component_ids=[],
        )
        # products/core — same archi_id in a different domain
        psd_products_core = ParsedSubdomain(
            archi_id='core',
            name='Core',
            domain_folder='products',
            component_ids=[],
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys_efs],
            [psd_channels_core, psd_products_core],
            manual_overrides={'EFS': 'core'},
        )
        assert sys_efs.subdomain == 'core', (
            'EFS should be assigned to channels/core, not left empty due to collision'
        )
        assert 'efs' in subdomain_systems.get(('channels', 'core'), [])
        # Only the channels-domain subdomain should appear (domain_id='channels')
        matching = [sd for sd in subdomains if sd.c4_id == 'core']
        assert len(matching) == 1
        assert matching[0].domain_id == 'channels'

    def test_unassigned_system_not_placed_in_subdomain(self):
        """System with no domain (domain='') must not be assigned to any subdomain."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-1'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == '', 'unassigned system must not receive a subdomain'
        assert subdomains == []
        assert subdomain_systems == {}

    def test_unassigned_system_not_placed_via_manual_override(self):
        """manual_overrides must not assign a subdomain to an unassigned (domain='') system."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='')
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=[],
        )
        subdomains, subdomain_systems = assign_subdomains(
            [sys], [psd],
            manual_overrides={'EFS': 'banking'},
        )
        assert sys.subdomain == '', 'unassigned system must not receive a subdomain via override'
        assert subdomains == []
        assert subdomain_systems == {}

    def test_collision_guard_system_same_name_as_subdomain(self):
        """System whose c4_id equals a subdomain c4_id gets auto-assigned to that subdomain."""
        # Mirrors real-world: system "AIM" and subdomain folder "AIM" → both make_id → 'aim'
        sys = System(c4_id='aim', name='AIM', archi_id='sys-aim', domain='channels')
        psd = ParsedSubdomain(
            archi_id='aim',
            name='AIM',
            domain_folder='channels',
            component_ids=[],  # system NOT in component_ids (no folder membership)
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'aim', 'collision guard must assign system to matching subdomain'
        assert len(subdomains) == 1
        assert subdomains[0].c4_id == 'aim'
        assert 'aim' in subdomains[0].system_ids
        assert ('channels', 'aim') in subdomain_systems
        assert 'aim' in subdomain_systems[('channels', 'aim')]

    def test_collision_guard_only_same_domain(self):
        """Collision guard must NOT fire across different domains."""
        sys = System(c4_id='loan', name='Loan', archi_id='sys-loan', domain='products')
        psd = ParsedSubdomain(
            archi_id='loan',
            name='Loan',
            domain_folder='channels',  # different domain!
            component_ids=[],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == '', 'cross-domain collision guard must not fire'
        assert subdomains == []

    def test_collision_guard_skipped_when_already_assigned(self):
        """Collision guard must not re-assign a system that already has a subdomain."""
        sys = System(c4_id='aim', name='AIM', archi_id='sys-aim', domain='channels')
        psd_banking = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sys-aim'],  # folder membership → assigned via normal path
        )
        psd_aim = ParsedSubdomain(
            archi_id='aim',
            name='AIM',
            domain_folder='channels',
            component_ids=[],
        )
        subdomains, _ = assign_subdomains([sys], [psd_banking, psd_aim])
        assert sys.subdomain == 'banking', 'normal assignment must not be overwritten by collision guard'

    def test_subsystem_fallback_basic(self):
        """System with no archi_id in any subdomain gets assigned via its subsystems' archi_ids."""
        sub1 = Subsystem(c4_id='sub-a', name='Sub A', archi_id='sub-archi-1')
        sub2 = Subsystem(c4_id='sub-b', name='Sub B', archi_id='sub-archi-2')
        sys = System(
            c4_id='efs',
            name='EFS',
            archi_id='sys-not-in-any-subdomain',
            domain='channels',
            subsystems=[sub1, sub2],
        )
        psd = ParsedSubdomain(
            archi_id='banking',
            name='Banking',
            domain_folder='channels',
            component_ids=['sub-archi-1', 'sub-archi-2'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd])
        assert sys.subdomain == 'banking', (
            'system whose own archi_id is absent must be assigned via subsystem archi_ids'
        )
        assert len(subdomains) == 1
        assert 'efs' in subdomain_systems.get(('channels', 'banking'), [])

    def test_subsystem_fallback_majority_vote(self):
        """When subsystems point to two subdomains, the one with more hits wins."""
        # 2 subsystems in 'payments', 1 in 'retail' → 'payments' wins
        subs = [
            Subsystem(c4_id='s1', name='S1', archi_id='sa1'),
            Subsystem(c4_id='s2', name='S2', archi_id='sa2'),
            Subsystem(c4_id='s3', name='S3', archi_id='sa3'),
        ]
        sys = System(
            c4_id='efs',
            name='EFS',
            archi_id='sys-no-match',
            domain='channels',
            subsystems=subs,
        )
        psd_payments = ParsedSubdomain(
            archi_id='payments',
            name='Payments',
            domain_folder='channels',
            component_ids=['sa1', 'sa2'],
        )
        psd_retail = ParsedSubdomain(
            archi_id='retail',
            name='Retail',
            domain_folder='channels',
            component_ids=['sa3'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd_payments, psd_retail])
        assert sys.subdomain == 'payments', (
            'majority-vote must pick the subdomain with the most subsystem hits'
        )
        assert 'efs' in subdomain_systems.get(('channels', 'payments'), [])

    def test_subsystem_fallback_tie_break_alphabetical(self):
        """When subsystem vote is tied, the subdomain with the lower archi_id wins."""
        subs = [
            Subsystem(c4_id='s1', name='S1', archi_id='sa1'),
            Subsystem(c4_id='s2', name='S2', archi_id='sa2'),
        ]
        sys = System(
            c4_id='efs',
            name='EFS',
            archi_id='sys-no-match',
            domain='channels',
            subsystems=subs,
        )
        psd_beta = ParsedSubdomain(
            archi_id='beta',
            name='Beta',
            domain_folder='channels',
            component_ids=['sa1'],
        )
        psd_alpha = ParsedSubdomain(
            archi_id='alpha',
            name='Alpha',
            domain_folder='channels',
            component_ids=['sa2'],
        )
        subdomains, subdomain_systems = assign_subdomains([sys], [psd_beta, psd_alpha])
        assert sys.subdomain == 'alpha', (
            'on equal vote counts, alphabetically earlier subdomain archi_id must win'
        )
        assert 'efs' in subdomain_systems.get(('channels', 'alpha'), [])


# ── _build_subdomain_lookup ────────────────────────────────────────────

class TestBuildSubdomainLookup:
    def test_builds_archi_to_psds_index(self):
        """Component IDs are indexed to their ParsedSubdomain."""
        psd = ParsedSubdomain(archi_id='banking', name='Banking', domain_folder='channels', component_ids=['c1', 'c2'])
        archi_to_psds, _ = _build_subdomain_lookup([psd])
        assert 'c1' in archi_to_psds
        assert 'c2' in archi_to_psds
        assert archi_to_psds['c1'] == [psd]

    def test_builds_sd_id_to_psd_index(self):
        """Domain-scoped (domain_folder, archi_id) index is built."""
        psd = ParsedSubdomain(archi_id='core', name='Core', domain_folder='channels', component_ids=[])
        _, sd_id_to_psd = _build_subdomain_lookup([psd])
        assert ('channels', 'core') in sd_id_to_psd
        assert sd_id_to_psd[('channels', 'core')] is psd

    def test_empty_input(self):
        """No parsed subdomains → empty lookups."""
        archi_to_psds, sd_id_to_psd = _build_subdomain_lookup([])
        assert archi_to_psds == {}
        assert sd_id_to_psd == {}

    def test_duplicate_component_keeps_all_candidates(self):
        """Component appearing in multiple subdomains keeps all candidates."""
        psd1 = ParsedSubdomain(archi_id='a', name='A', domain_folder='d1', component_ids=['c1'])
        psd2 = ParsedSubdomain(archi_id='b', name='B', domain_folder='d2', component_ids=['c1'])
        archi_to_psds, _ = _build_subdomain_lookup([psd1, psd2])
        assert len(archi_to_psds['c1']) == 2


# ── _assign_subdomain_by_folder ───────────────────────────────────────

class TestAssignSubdomainByFolder:
    def test_match_by_primary_archi_id(self):
        """System matched by its own archi_id in the same domain."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(archi_id='banking', name='Banking', domain_folder='channels', component_ids=['sys-1'])
        archi_to_psds, _ = _build_subdomain_lookup([psd])
        result = _assign_subdomain_by_folder(sys, archi_to_psds)
        assert result is psd

    def test_match_by_extra_archi_id(self):
        """System matched by extra_archi_ids when primary doesn't match."""
        sys = System(c4_id='efs', name='EFS', archi_id='no-match', extra_archi_ids=['sys-dup'], domain='channels')
        psd = ParsedSubdomain(archi_id='payments', name='Payments', domain_folder='channels', component_ids=['sys-dup'])
        archi_to_psds, _ = _build_subdomain_lookup([psd])
        result = _assign_subdomain_by_folder(sys, archi_to_psds)
        assert result is psd

    def test_no_match_returns_none(self):
        """No matching archi_id → returns None."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        psd = ParsedSubdomain(archi_id='banking', name='Banking', domain_folder='channels', component_ids=['other'])
        archi_to_psds, _ = _build_subdomain_lookup([psd])
        result = _assign_subdomain_by_folder(sys, archi_to_psds)
        assert result is None

    def test_foreign_domain_not_matched(self):
        """Candidate in a different domain is skipped."""
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='products')
        psd = ParsedSubdomain(archi_id='retail', name='Retail', domain_folder='channels', component_ids=['sys-1'])
        archi_to_psds, _ = _build_subdomain_lookup([psd])
        result = _assign_subdomain_by_folder(sys, archi_to_psds)
        assert result is None


# ── _assign_subdomain_by_majority_vote ─────────────────────────────────

class TestAssignSubdomainByMajorityVote:
    def test_majority_vote_picks_most_hits(self):
        """Subdomain with more subsystem hits wins."""
        subs = [
            Subsystem(c4_id='s1', name='S1', archi_id='sa1'),
            Subsystem(c4_id='s2', name='S2', archi_id='sa2'),
            Subsystem(c4_id='s3', name='S3', archi_id='sa3'),
        ]
        sys = System(c4_id='efs', name='EFS', archi_id='no-match', domain='channels', subsystems=subs)
        psd_pay = ParsedSubdomain(
            archi_id='payments', name='Payments', domain_folder='channels', component_ids=['sa1', 'sa2'],
        )
        psd_ret = ParsedSubdomain(archi_id='retail', name='Retail', domain_folder='channels', component_ids=['sa3'])
        archi_to_psds, _ = _build_subdomain_lookup([psd_pay, psd_ret])
        result = _assign_subdomain_by_majority_vote(sys, archi_to_psds)
        assert result is psd_pay

    def test_tie_break_alphabetical(self):
        """Equal vote counts → alphabetically earlier archi_id wins."""
        subs = [
            Subsystem(c4_id='s1', name='S1', archi_id='sa1'),
            Subsystem(c4_id='s2', name='S2', archi_id='sa2'),
        ]
        sys = System(c4_id='efs', name='EFS', archi_id='no-match', domain='channels', subsystems=subs)
        psd_b = ParsedSubdomain(archi_id='beta', name='Beta', domain_folder='channels', component_ids=['sa1'])
        psd_a = ParsedSubdomain(archi_id='alpha', name='Alpha', domain_folder='channels', component_ids=['sa2'])
        archi_to_psds, _ = _build_subdomain_lookup([psd_b, psd_a])
        result = _assign_subdomain_by_majority_vote(sys, archi_to_psds)
        assert result is psd_a

    def test_no_subsystems_returns_none(self):
        """System without subsystems → returns None."""
        sys = System(c4_id='efs', name='EFS', archi_id='no-match', domain='channels')
        result = _assign_subdomain_by_majority_vote(sys, {})
        assert result is None

    def test_foreign_domain_subsystems_ignored(self):
        """Subsystem hits in a foreign domain are not counted."""
        subs = [Subsystem(c4_id='s1', name='S1', archi_id='sa1')]
        sys = System(c4_id='efs', name='EFS', archi_id='no-match', domain='products', subsystems=subs)
        psd = ParsedSubdomain(archi_id='banking', name='Banking', domain_folder='channels', component_ids=['sa1'])
        archi_to_psds, _ = _build_subdomain_lookup([psd])
        result = _assign_subdomain_by_majority_vote(sys, archi_to_psds)
        assert result is None


# ── _apply_collision_guard ─────────────────────────────────────────────

class TestApplyCollisionGuard:
    def test_collision_guard_assigns_matching_system(self):
        """System whose c4_id equals a subdomain c4_id gets auto-assigned."""
        sys = System(c4_id='aim', name='AIM', archi_id='sys-aim', domain='channels')
        psd = ParsedSubdomain(archi_id='aim', name='AIM', domain_folder='channels', component_ids=[])
        _, sd_id_to_psd = _build_subdomain_lookup([psd])
        subdomains_by_key: dict[tuple[str, str], Subdomain] = {}
        subdomain_systems: dict[tuple[str, str], list[str]] = {}
        _apply_collision_guard([sys], [psd], sd_id_to_psd, subdomains_by_key, subdomain_systems)
        assert sys.subdomain == 'aim'
        assert ('channels', 'aim') in subdomains_by_key
        assert 'aim' in subdomain_systems[('channels', 'aim')]

    def test_collision_guard_skips_already_assigned(self):
        """System that already has a subdomain is not re-assigned."""
        sys = System(c4_id='aim', name='AIM', archi_id='sys-aim', domain='channels')
        sys.subdomain = 'banking'
        psd = ParsedSubdomain(archi_id='aim', name='AIM', domain_folder='channels', component_ids=[])
        _, sd_id_to_psd = _build_subdomain_lookup([psd])
        subdomains_by_key: dict[tuple[str, str], Subdomain] = {}
        subdomain_systems: dict[tuple[str, str], list[str]] = {}
        _apply_collision_guard([sys], [psd], sd_id_to_psd, subdomains_by_key, subdomain_systems)
        assert sys.subdomain == 'banking'

    def test_collision_guard_cross_domain_no_match(self):
        """Collision guard does not fire across different domains."""
        sys = System(c4_id='loan', name='Loan', archi_id='sys-loan', domain='products')
        psd = ParsedSubdomain(archi_id='loan', name='Loan', domain_folder='channels', component_ids=[])
        _, sd_id_to_psd = _build_subdomain_lookup([psd])
        subdomains_by_key: dict[tuple[str, str], Subdomain] = {}
        subdomain_systems: dict[tuple[str, str], list[str]] = {}
        _apply_collision_guard([sys], [psd], sd_id_to_psd, subdomains_by_key, subdomain_systems)
        assert sys.subdomain == ''


# ── apply_domain_prefix with subdomain ──────────────────────────────────

class TestApplyDomainPrefixSubdomain:
    def test_integration_path_includes_subdomain(self):
        """Integration source/target paths include subdomain when assigned."""
        intg = Integration(source_path='efs', target_path='crm', name='flow', rel_type='')
        sys_domain = {'efs': 'channels', 'crm': 'customer_service'}
        sys_subdomain = {'efs': 'banking'}
        apply_domain_prefix([intg], [], sys_domain, sys_subdomain)
        assert intg.source_path == 'channels.banking.efs'
        assert intg.target_path == 'customer_service.crm'  # no subdomain

    def test_data_access_path_includes_subdomain(self):
        da = DataAccess(system_path='efs', entity_id='de_account', name='')
        sys_domain = {'efs': 'channels'}
        sys_subdomain = {'efs': 'banking'}
        apply_domain_prefix([], [da], sys_domain, sys_subdomain)
        assert da.system_path == 'channels.banking.efs'

    def test_no_subdomain_unchanged(self):
        """Without sys_subdomain parameter, behavior is unchanged."""
        intg = Integration(source_path='efs', target_path='crm', name='', rel_type='')
        sys_domain = {'efs': 'channels', 'crm': 'products'}
        apply_domain_prefix([intg], [], sys_domain)
        assert intg.source_path == 'channels.efs'
        assert intg.target_path == 'products.crm'


# ── build_archi_to_c4_map with subdomain ────────────────────────────────

class TestBuildArchiToC4MapSubdomain:
    def test_system_path_includes_subdomain(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     domain='channels', subdomain='banking')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'},
                                       sys_subdomain={'efs': 'banking'})
        assert result['sys-1'] == 'channels.banking.efs'

    def test_subsystem_path_inherits_subdomain(self):
        sub = Subsystem(c4_id='core', name='EFS.Core', archi_id='sub-1')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     subsystems=[sub], domain='channels', subdomain='banking')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'},
                                       sys_subdomain={'efs': 'banking'})
        assert result['sub-1'] == 'channels.banking.efs.core'

    def test_function_path_inherits_subdomain(self):
        fn = AppFunction(archi_id='fn-1', name='DoStuff', c4_id='do_stuff')
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1',
                     functions=[fn], domain='channels', subdomain='banking')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'},
                                       sys_subdomain={'efs': 'banking'})
        assert result['fn-1'] == 'channels.banking.efs.do_stuff'

    def test_no_subdomain_unchanged(self):
        sys = System(c4_id='efs', name='EFS', archi_id='sys-1', domain='channels')
        result = build_archi_to_c4_map([sys], {'efs': 'channels'})
        assert result['sys-1'] == 'channels.efs'


# ── enrich_deployment_from_visual_nesting ────────────────────────────────


