import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yor_network_recovery import RecoveryConfig, RecoveryManager


class FakeRunner:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.commands = []

    def __call__(self, command):
        self.commands.append(command)
        response = self.responses.get(tuple(command), "")
        if isinstance(response, Exception):
            raise response
        return response


class RecoveryManagerTests(unittest.TestCase):
    def run_silently(self, manager):
        with redirect_stdout(StringIO()):
            return manager.run_once()

    def test_normal_wifi_skips_hotspot(self):
        runner = FakeRunner(
            {
                ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"): "wlan0:wifi:connected\n",
            }
        )
        manager = RecoveryManager(RecoveryConfig(wait_seconds=0, poll_seconds=0), runner=runner, sleeper=lambda _: None)

        result = self.run_silently(manager)

        self.assertEqual(result, "normal-network")
        self.assertNotIn(("nmcli", "device", "wifi", "hotspot", "ifname", "wlan0"), [tuple(c[:6]) for c in runner.commands])

    def test_missing_wifi_starts_recovery_hotspot(self):
        runner = FakeRunner(
            {
                ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"): "wlan0:wifi:disconnected\n",
            }
        )
        config = RecoveryConfig(wait_seconds=0, poll_seconds=0, hotspot_ssid="YOR-Setup", hotspot_password="yor-setup-robot")
        manager = RecoveryManager(config, runner=runner, sleeper=lambda _: None)

        result = self.run_silently(manager)

        self.assertEqual(result, "recovery-hotspot")
        self.assertIn(
            (
                "nmcli",
                "device",
                "wifi",
                "hotspot",
                "ifname",
                "wlan0",
                "ssid",
                "YOR-Setup",
                "password",
                "yor-setup-robot",
            ),
            [tuple(command) for command in runner.commands],
        )

    def test_non_wifi_network_counts_as_reachable_for_ssh(self):
        runner = FakeRunner(
            {
                ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"): "eth0:ethernet:connected\nwlan0:wifi:disconnected\n",
            }
        )
        manager = RecoveryManager(RecoveryConfig(wait_seconds=0, poll_seconds=0), runner=runner, sleeper=lambda _: None)

        result = self.run_silently(manager)

        self.assertEqual(result, "normal-network")

    def test_hotspot_password_must_be_valid_wifi_length(self):
        with self.assertRaises(ValueError):
            RecoveryConfig(hotspot_password="short")


if __name__ == "__main__":
    unittest.main()
