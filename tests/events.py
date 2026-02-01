import asyncio
import json
import os
import subprocess
import time
from contextlib import suppress
from typing import Any, AsyncGenerator, Awaitable, Dict, Generator, Optional

import asyncio_for_robotics.textio as afor_textio
import asyncio_for_robotics.zenoh as afor
import foxglove
import foxglove.schemas as schemas
import pytest
import zenoh

from elian_experiment.adv_sub import AdvancedSub

from .test_base import conversation
from .variables import REMOTES, SSHTargets
from .zenoh_utils import foxlog_zenoh_stdout


def foxlog_event(string: str):
    print(string)
    foxglove.log(
        "/events_log", schemas.Log(timestamp=schemas.Timestamp.now(), message=string, name="")
    )


async def _ssh_cmd(ssh_target: str, label: str, cmd: str):
    foxlog_event(f"[START] {label}")
    proc = await asyncio.subprocess.create_subprocess_shell(f"ssh {ssh_target} '{cmd}'")
    rc = await proc.wait()
    foxlog_event(f"[DONE] {label} (rc={rc})")
    return rc


async def wlan_down(ssh_target: str, downtime: float):
    try:
        await _ssh_cmd(ssh_target, "wlanAP down", "sudo ip link set wlanAP down")

        foxlog_event(f"[WAIT] sleeping {downtime}s")
        await asyncio.sleep(downtime)
    finally:
        await _ssh_cmd(ssh_target, "wlanAP up", "sudo ip link set wlanAP up")
        await _ssh_cmd(
            ssh_target,
            "disable wlanAP powersave",
            "sudo /usr/sbin/iw dev wlanAP set power_save off",
        )
        await _ssh_cmd(
            ssh_target,
            "disable wlanMESH powersave",
            "sudo /usr/sbin/iw dev wlanMESH set power_save off",
        )
