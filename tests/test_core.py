import unittest

from dns_proxy.cache import TtlCache
from dns_proxy.domain import domain_matches, is_valid_domain, normalize_domain
from dns_proxy.lists import DomainList
from dns_proxy.models import DecisionSource, ResponseStatus, UpstreamReply
from dns_proxy.resolver import Resolver


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class CoreTests(unittest.TestCase):
    def test_domain_rules(self):
        self.assertEqual(normalize_domain(" ADS.Example.COM. "), "ads.example.com")
        self.assertTrue(is_valid_domain("a.example.com"))
        self.assertTrue(is_valid_domain("example.com."))
        self.assertFalse(is_valid_domain("bad domain.com"))
        self.assertTrue(domain_matches("sub.example.com", "example.com"))
        self.assertFalse(domain_matches("notexample.com", "example.com"))

    def test_ttl_cache_expires_and_evicts(self):
        clock = Clock()
        cache = TtlCache(clock=clock, max_entries=2)
        cache.put("one.example.net", "198.51.100.1", 5)
        clock.value = 1.1
        self.assertEqual(cache.get("one.example.net"), ("198.51.100.1", 3))
        cache.put("two.example.net", "198.51.100.2", 30)
        cache.put("three.example.net", "198.51.100.3", 30)
        self.assertIsNone(cache.get("one.example.net"))

    def test_resolver_priority_and_upstream_call(self):
        class Upstream:
            def __init__(self):
                self.calls = []

            def query(self, domain):
                self.calls.append(domain)
                return UpstreamReply(ResponseStatus.OK, "198.51.100.7", 5)

        ad = DomainList("config/ad_list.txt")
        sanction = DomainList("config/sanction_list.txt")
        ad.reload()
        sanction.reload()
        upstream = Upstream()
        resolver = Resolver("0.0.0.0", "192.0.2.10", 60, ad, sanction, TtlCache(), upstream)
        self.assertIs(resolver.resolve("BOTH.EXAMPLE.COM.").source, DecisionSource.AD_BLOCK)
        self.assertIs(resolver.resolve("service.example.org").source, DecisionSource.SANCTION)
        self.assertIs(resolver.resolve("normal.example.net").source, DecisionSource.UPSTREAM)
        self.assertIs(resolver.resolve("normal.example.net").source, DecisionSource.CACHE)
        self.assertEqual(upstream.calls, ["normal.example.net"])

    def test_invalid_input_does_not_call_upstream(self):
        class Upstream:
            def query(self, domain):
                raise AssertionError("unexpected upstream call")

        ad = DomainList("config/ad_list.txt")
        sanction = DomainList("config/sanction_list.txt")
        ad.reload()
        sanction.reload()
        resolver = Resolver("0.0.0.0", "192.0.2.10", 60, ad, sanction, TtlCache(), Upstream())
        result = resolver.resolve("bad domain.com")
        self.assertIs(result.status, ResponseStatus.INVALID_INPUT)


if __name__ == "__main__":
    unittest.main()
