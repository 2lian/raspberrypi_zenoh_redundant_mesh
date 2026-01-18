from contextlib import suppress
import json
import os
import subprocess
import time
from typing import Awaitable, Dict, Optional

import asyncio_for_robotics.textio as afor_textio
import asyncio_for_robotics.zenoh as afor
import foxglove
import foxglove.schemas as schemas
import pytest
import zenoh
from colorama import Fore
from test_base import loop_it

from elian_experiment.adv_sub import AdvancedSub
from zenoh_utils import foxlog_zenoh_stdout

pass  # VVV imports fixtures
from foxglove_bag import bag, log_payload, stdout_topic
from log_stats import log_node1_iwdev, log_node1_ips

ID = "mesh_1"

@pytest.fixture
def node1_router_proc():
    subprocess.Popen(
        ["ssh", "pe1", "pkill", "zenohd"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            "pe1",
            "RUST_LOG=debug /home/moonshot/.pixi/bin/pixi run -m ",
            "~/raspberrypi_zenoh_redundant_mesh/pixi.toml ",
            "zenohd -c ",
            "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/node_router.json5",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
    )

    try:
        yield p
    finally:
        subprocess.Popen(
            ["ssh", "pe1", "pkill", "zenohd"],
        ).wait()
        p.terminate()
        p.wait()



@pytest.fixture
async def log_node1_router_stdout(
    node1_router_proc: subprocess.Popen[str], stdout_topic: foxglove.Channel
):
    print("node 1")
    stdout_sub = afor_textio.from_proc_stdout(node1_router_proc)
    foxlog_zenoh_stdout(stdout_sub, stdout_topic, "node1 router")
    yield stdout_sub
    stdout_sub.close()


@pytest.fixture
def node2_router_proc():
    subprocess.Popen(
        ["ssh", "pe2", "pkill", "zenohd"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            "pe2",
            "RUST_LOG=debug /home/moonshot/.pixi/bin/pixi run -m ",
            "~/raspberrypi_zenoh_redundant_mesh/pixi.toml ",
            "zenohd -c ",
            "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/node_router.json5",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
    )

    try:
        yield p
    finally:
        subprocess.Popen(
            ["ssh", "pe2", "pkill", "zenohd"],
        ).wait()
        p.terminate()
        p.wait()


@pytest.fixture
async def log_node2_router_stdout(
    node2_router_proc: subprocess.Popen[str], stdout_topic: foxglove.Channel
):
    print("node 2")
    stdout_sub = afor_textio.from_proc_stdout(node2_router_proc)
    foxlog_zenoh_stdout(stdout_sub, stdout_topic, "node2 router")
    yield stdout_sub
    stdout_sub.close()


@pytest.fixture
def central_router_proc():
    subprocess.Popen(
        ["ssh", "unifi", "pkill", "zenohd"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            "unifi",
            "RUST_LOG=debug /home/moonshot/.pixi/bin/pixi run -m ",
            "~/raspberrypi_zenoh_redundant_mesh/pixi.toml ",
            "zenohd -c ",
            "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/router.json5",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
    )

    try:
        yield p
    finally:
        subprocess.Popen(
            ["ssh", "unifi", "pkill", "zenohd"],
        ).wait()
        p.terminate()
        p.wait()


@pytest.fixture
async def log_central_router_stdout(
    central_router_proc: subprocess.Popen[str], stdout_topic: foxglove.Channel
):
    stdout_sub = afor_textio.from_proc_stdout(central_router_proc)
    foxlog_zenoh_stdout(stdout_sub, stdout_topic, "central router")
    yield stdout_sub
    stdout_sub.close()

@pytest.fixture
def mirror_proc(node2_router_proc):
    subprocess.Popen(
        ["ssh", "pe2", "pkill -f", "mirror.py"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            "pe2",
            "/home/moonshot/.pixi/bin/pixi run -m",
            "~/raspberrypi_zenoh_redundant_mesh/pixi.toml",
            "python3",
            "~/raspberrypi_zenoh_redundant_mesh/elian_experiment/mirror.py",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
    )

    try:
        yield p
    finally:
        subprocess.Popen(
            ["ssh", "pe2", "pkill -f", "mirror.py"],
        ).wait()
        p.terminate()
        p.wait()


@pytest.fixture
async def log_mirror_stdout(
    mirror_proc: subprocess.Popen[str], stdout_topic: foxglove.Channel
):
    stdout_sub = afor_textio.from_proc_stdout(mirror_proc)
    foxlog_zenoh_stdout(stdout_sub, stdout_topic, "mirror router")
    yield stdout_sub
    stdout_sub.close()


@pytest.fixture
async def z_session(central_router_proc):
    filepath = os.path.expanduser(
        "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/client.json5"
    )
    config = zenoh.Config.from_file(filepath)
    ses = zenoh.open(config)
    afor.set_auto_session(ses)
    yield ses
    ses.close()


@pytest.fixture
async def sub(z_session):
    s = AdvancedSub(f"{ID}/response")
    yield s
    s.close()


@pytest.fixture
def pub(z_session):
    p = zenoh.ext.declare_advanced_publisher(
        z_session,
        f"{ID}/request",
        cache=zenoh.ext.CacheConfig(max_samples=100),
        sample_miss_detection=zenoh.ext.MissDetectionConfig(
            heartbeat=1, sporadic_heartbeat=None
        ),
        publisher_detection=True,
    )
    yield lambda x: p.put(x)
    p.undeclare()



async def test_debug(
    sub,
    pub,
    log_node1_router_stdout,
    log_node2_router_stdout,
    log_central_router_stdout,
    log_mirror_stdout,
    log_node1_iwdev,
    log_node1_ips,
    stdout_topic: foxglove.Channel,
):
    with suppress(KeyboardInterrupt):
        await afor.soft_wait_for(loop_it(sub, pub, log_payload), 120)
