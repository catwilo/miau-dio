"""Tests for _local_ipv4_addresses (task: --host Tailscale support)."""
import unittest
from unittest import mock

from miau_dio.strudel import server as srvmod


class _Base(unittest.TestCase):
    def setUp(self):
        # Silence the helper's internal imports; we mock subprocess.run and
        # shutil.which per test.
        self._patch_run = mock.patch.object(srvmod, "_local_ipv4_addresses",
                                            srvmod._local_ipv4_addresses)
        self._patch_run.start()
        self.addCleanup(self._patch_run.stop)


class TestTailscaleFirst(unittest.TestCase):
    def test_uses_tailscale_when_available(self):
        def fake_which(name):
            return "/usr/bin/tailscale" if name == "tailscale" else None

        def fake_run(cmd, **kw):
            if cmd[0].endswith("tailscale"):
                return mock.Mock(stdout="100.64.0.1\n100.64.0.2\n", returncode=0)
            return mock.Mock(stdout="", returncode=0)

        with mock.patch("shutil.which", side_effect=fake_which):
            with mock.patch("subprocess.run", side_effect=fake_run):
                out = srvmod._local_ipv4_addresses()
        self.assertEqual(out, ["100.64.0.1", "100.64.0.2"])


class TestIfconfigFallback(unittest.TestCase):
    def test_parses_ifconfig_output(self):
        ifconfig_text = """\
lo: flags=73<UP,LOOPBACK,RUNNING>
        inet 127.0.0.1  netmask 255.0.0.0
tun0: flags=81<UP,POINTOPOINT,RUNNING>
        inet 100.103.104.19  netmask 255.255.255.255
wlan0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>
        inet 192.168.1.6  netmask 255.255.255.0
"""
        def fake_which(name):
            return "/usr/bin/ifconfig" if name == "ifconfig" else None

        def fake_run(cmd, **kw):
            return mock.Mock(stdout=ifconfig_text, returncode=0)

        with mock.patch("shutil.which", side_effect=fake_which):
            with mock.patch("subprocess.run", side_effect=fake_run):
                out = srvmod._local_ipv4_addresses()
        self.assertEqual(out, ["100.103.104.19", "192.168.1.6"])

    def test_dedupes_repeated_addresses(self):
        ifconfig_text = """\
eth0: inet 10.0.0.5  netmask 255.255.255.0
eth1: inet 10.0.0.5  netmask 255.255.255.0
eth2: inet 10.0.0.6  netmask 255.255.255.0
"""
        with mock.patch("shutil.which",
                        side_effect=lambda n: "/usr/bin/ifconfig" if n == "ifconfig" else None):
            with mock.patch("subprocess.run",
                            side_effect=lambda c, **k: mock.Mock(stdout=ifconfig_text)):
                out = srvmod._local_ipv4_addresses()
        self.assertEqual(out, ["10.0.0.5", "10.0.0.6"])


class TestHostnameFallback(unittest.TestCase):
    def test_uses_hostname_dash_i(self):
        with mock.patch("shutil.which",
                        side_effect=lambda n: "/bin/hostname" if n == "hostname" else None):
            with mock.patch("subprocess.run",
                            side_effect=lambda c, **k: mock.Mock(stdout="10.1.2.3 10.4.5.6\n")):
                out = srvmod._local_ipv4_addresses()
        self.assertEqual(out, ["10.1.2.3", "10.4.5.6"])


class TestNoTools(unittest.TestCase):
    def test_returns_empty_when_nothing_available(self):
        with mock.patch("shutil.which", return_value=None):
            out = srvmod._local_ipv4_addresses()
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
