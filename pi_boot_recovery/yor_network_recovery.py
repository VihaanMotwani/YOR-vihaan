#!/usr/bin/env python3
"""Start a Pi recovery hotspot when normal networking is unavailable."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Sequence


Command = Sequence[str]
Runner = Callable[[Command], str]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class RecoveryConfig:
    interface: str = "wlan0"
    hotspot_ssid: str = "YOR-Setup"
    hotspot_password: str = "yor-setup-robot"
    wait_seconds: float = 90.0
    poll_seconds: float = 5.0

    def __post_init__(self) -> None:
        if len(self.hotspot_password) < 8:
            raise ValueError("Hotspot password must be at least 8 characters.")
        if self.wait_seconds < 0:
            raise ValueError("wait_seconds must be non-negative.")
        if self.poll_seconds < 0:
            raise ValueError("poll_seconds must be non-negative.")


def subprocess_runner(command: Command) -> str:
    completed = subprocess.run(
        list(command),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout


class RecoveryManager:
    def __init__(
        self,
        config: RecoveryConfig,
        runner: Runner = subprocess_runner,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self.config = config
        self.runner = runner
        self.sleeper = sleeper

    def run_once(self) -> str:
        if self.wait_for_network():
            print("[yor-network-recovery] normal network is reachable; hotspot not started.")
            return "normal-network"

        self.start_hotspot()
        print(
            "[yor-network-recovery] started recovery hotspot "
            f"'{self.config.hotspot_ssid}' on {self.config.interface}."
        )
        return "recovery-hotspot"

    def wait_for_network(self) -> bool:
        if self.network_is_reachable():
            return True

        if self.config.wait_seconds <= 0:
            return False

        deadline = time.monotonic() + self.config.wait_seconds
        while time.monotonic() < deadline:
            sleep_for = min(self.config.poll_seconds, max(0.0, deadline - time.monotonic()))
            if sleep_for > 0:
                self.sleeper(sleep_for)
            if self.network_is_reachable():
                return True
        return False

    def network_is_reachable(self) -> bool:
        try:
            output = self.runner(("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"))
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(f"[yor-network-recovery] could not read NetworkManager state: {exc}", file=sys.stderr)
            return False

        return any(self._line_is_connected_device(line) for line in output.splitlines())

    @staticmethod
    def _line_is_connected_device(line: str) -> bool:
        parts = line.split(":")
        if len(parts) < 3:
            return False
        _, _, state = parts[:3]
        return state.strip().lower() == "connected"

    def start_hotspot(self) -> None:
        self.runner(
            (
                "nmcli",
                "device",
                "wifi",
                "hotspot",
                "ifname",
                self.config.interface,
                "ssid",
                self.config.hotspot_ssid,
                "password",
                self.config.hotspot_password,
            )
        )


def parse_args(argv: Sequence[str] | None = None) -> RecoveryConfig:
    parser = argparse.ArgumentParser(description="Start a YOR recovery hotspot if normal networking is unavailable.")
    parser.add_argument("--interface", default="wlan0")
    parser.add_argument("--ssid", default="YOR-Setup")
    parser.add_argument("--password", default="yor-setup-robot")
    parser.add_argument("--wait-seconds", type=float, default=90.0)
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    return RecoveryConfig(
        interface=args.interface,
        hotspot_ssid=args.ssid,
        hotspot_password=args.password,
        wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds,
    )


def main(argv: Sequence[str] | None = None) -> int:
    config = parse_args(argv)
    manager = RecoveryManager(config)
    manager.run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
