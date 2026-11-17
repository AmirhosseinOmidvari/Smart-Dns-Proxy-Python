from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from dns_proxy.app import main
from dns_proxy.config import AppConfig, ConfigError


class StartupTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.config = self.root / "config.txt"
        self.base = (
            "upstream_ip=127.0.0.1\nupstream_port=5354\n"
            "sinkhole_ip=0.0.0.0\nproxy_ip=192.0.2.10\n"
            "ad_list_file=ads.txt\nsanction_list_file=sanctions.txt\n"
        )
        self.config.write_text(self.base, encoding="utf-8")
        (self.root / "ads.txt").write_text("bad domain.com\nads.example.com\n", encoding="utf-8")
        (self.root / "sanctions.txt").write_text("also invalid\n", encoding="utf-8")

    def test_main_prints_both_list_warnings_before_prompt(self):
        output = StringIO()
        config = AppConfig.load(self.config)
        with patch("dns_proxy.app.AppConfig.load", return_value=config):
            with patch("sys.stdin", StringIO("exit\n")), redirect_stdout(output):
                main()
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "Warning: bad line in ads.txt: bad domain.com",
                "Warning: bad line in sanctions.txt: also invalid",
                "DNS Proxy ready.",
                "Enter domain (or exit): Bye.",
            ],
        )

    def test_port_bounds_and_non_finite_timeout(self):
        for setting in ("upstream_port=0", "upstream_port=65536", "upstream_timeout_sec=nan",
                        "upstream_timeout_sec=inf", "upstream_timeout_sec=-inf"):
            with self.subTest(setting=setting):
                self.config.write_text(self.base + setting + "\n", encoding="utf-8")
                with self.assertRaises(ConfigError):
                    AppConfig.load(self.config)
        self.config.write_text(self.base.replace("5354", "65535"), encoding="utf-8")
        self.assertEqual(AppConfig.load(self.config).upstream_port, 65535)
