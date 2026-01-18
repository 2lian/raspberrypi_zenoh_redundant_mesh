import asyncio
import json
import re
import subprocess
import time

import asyncio_for_robotics.textio as afor_textio
import foxglove
import pytest
from foxglove import schemas
from foxglove.channel import Channel
from foxglove.schemas import Log
from foxglove_bag import bag, stdout_topic


def parse_iwdev(text: str) -> dict:
    interfaces = {}
    current_iface = None
    current_section = None

    lines = text.splitlines()

    for line in lines:
        raw = line.rstrip()
        stripped = raw.strip()

        if stripped.startswith("stamp: "):
            now = int(stripped.removeprefix("stamp: "))
            interfaces["header"] = {}
            interfaces["header"]["time"] = now
            interfaces["header"]["timestamp"] = {
                "sec": int(now // 1e9),
                "nsec": int(now % 1e9),
            }

        # Start of a new interface
        m = re.match(r"Interface\s+(\S+)", stripped)
        if m:
            current_iface = m.group(1)
            interfaces[current_iface] = {}
            current_section = None
            continue

        if current_iface is None:
            continue

        # Section headers (e.g. "multicast TXQ:", "MLD with links:")
        if stripped.endswith(":"):
            section = stripped[:-1]
            interfaces[current_iface][section] = []
            current_section = section
            continue

        # MLD link lines
        if current_section == "MLD with links" and stripped.startswith("-"):
            interfaces[current_iface][current_section].append(stripped.split(" ")[-1])
            continue

        # TXQ table rows (titles)
        if (
            current_section == "multicast TXQ"
            and stripped
            and not stripped[0].isdigit()
        ):
            interfaces[current_iface][current_section].append(
                list(filter(None, stripped.split("\t")))
            )
            continue
        # TXQ table rows (numbers)
        if current_section == "multicast TXQ" and stripped and stripped[0].isdigit():
            interfaces[current_iface][current_section].append(
                list(filter(None, stripped.split("\t")))
            )
            interfaces[current_iface][current_section] = dict(
                zip(
                    interfaces[current_iface][current_section][0],
                    interfaces[current_iface][current_section][1],
                )
            )
            current_section = None
            continue

        # Key-value lines
        if stripped:
            parts = stripped.split(None, 1)
            if len(parts) == 2:
                interfaces[current_iface][parts[0]] = parts[1]

    return interfaces


async def monitor_iwdev(ssh_target: str, stdout_topic: Channel):
    p = subprocess.Popen(
        [
            "ssh",
            ssh_target,
            r"""while :; do printf "stamp: %s\n%s\n" "$(date +%s%N)" "$(/usr/sbin/iw dev)"; sleep 1; done""",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
    )
    sub = afor_textio.from_proc_stdout(p, pre_process=lambda x: x)

    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        now = time.time_ns()
        # print(json.dumps(parse_iwdev(msg)))
        foxglove.log(
            topic=f"/iwdev/{ssh_target}",
            message=parse_iwdev(msg),
            log_time=now,
        )

    def log_log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        now = time.time_ns()
        stdout_topic.log(
            msg=schemas.Log(
                timestamp=schemas.Timestamp.now(),
                level=schemas.LogLevel.Debug,
                message=msg,
                name=f"iwdev {ssh_target}",
            ).encode(),
            log_time=now,
        )

    async def accumlate(sub: afor_textio.Sub):
        buffer = []
        async for line in sub.listen_reliable():
            if line.startswith("stamp: "):
                if buffer != []:
                    text = "".join(buffer)
                    log_log_it(text)
                    log_it(text)
                    buffer = []
            buffer.append(line)

    accumulate_task = asyncio.create_task(accumlate(sub))

    try:
        yield p
    finally:
        p.terminate()
        p.wait()
        accumulate_task.cancel()


@pytest.fixture
async def log_node1_iwdev(stdout_topic):
    async for _ in monitor_iwdev("pe1", stdout_topic):
        yield


def _just_print():
    res = parse_iwdev(
        """---###---
stamp: 1768721505997425749
phy#2
        Interface wlanMESH
                ifindex 6
                wdev 0x200000001
                addr 24:ec:99:bf:c8:4a
                type mesh point
                channel 1 (2412 MHz), width: 20 MHz (no HT), center1: 2412 MHz
                txpower 30.00 dBm
                multicast TXQ:
                        qsz-byt qsz-pkt flows   drops   marks   overlmt hashcol tx-bytes        tx-packets
                        0       0       9509    0       0       0       0       877252          9515
phy#1
        Interface wlanAP
                ifindex 5
                wdev 0x100000001
                addr 5c:b4:7e:8c:0c:8a
                ssid 2lian-lab
                type managed
                multicast TXQ:
                        qsz-byt qsz-pkt flows   drops   marks   overlmt hashcol tx-bytes        tx-packets
                        0       0       0       0       0       0       0       0               0
                MLD with links:
                 - link ID  0 link addr 1a:a9:99:62:99:0a
                 - link ID  1 link addr 26:06:32:6d:7b:42
                 - link ID  2 link addr 62:01:a0:27:73:01
                   channel 37 (6135 MHz), width: 160 MHz, center1: 6185 MHz
phy#0
        Unnamed/non-netdev interface
                wdev 0x2
                addr 2e:cf:67:43:02:ea
                type P2P-device
                txpower 31.00 dBm
        Interface wlan0
                ifindex 4
                wdev 0x1
                addr 2c:cf:67:43:02:ea
                type managed
                channel 36 (5180 MHz), width: 20 MHz, center1: 5180 MHz
                txpower 31.00 dBm"""
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    pass
