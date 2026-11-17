import unittest
from io import StringIO

from dns_proxy.cache import TtlCache
from dns_proxy.console import Console
from dns_proxy.lists import DomainList
from dns_proxy.models import ResponseStatus, UpstreamReply
from dns_proxy.resolver import Resolver


class ConsoleTests(unittest.TestCase):
    def test_console_commands_and_result_format(self):
        class Upstream:
            def query(self, domain):
                return UpstreamReply(ResponseStatus.OK, "198.51.100.7", 5)

        ad = DomainList("config/ad_list.txt")
        sanction = DomainList("config/sanction_list.txt")
        ad.reload()
        sanction.reload()
        resolver = Resolver("0.0.0.0", "192.0.2.10", 60, ad, sanction, TtlCache(), Upstream())
        output = StringIO()
        Console(resolver, StringIO("ads.example.com\nstats\nexit\n"), output).run()
        text = output.getvalue()
        self.assertIn("Domain : ads.example.com", text)
        self.assertIn("Source : AD_BLOCK", text)
        self.assertIn("Total: 1 | AD_BLOCK: 1", text)
        self.assertTrue(text.endswith("Bye.\n"))


if __name__ == "__main__":
    unittest.main()
