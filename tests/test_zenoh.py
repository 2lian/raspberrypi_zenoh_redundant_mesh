import asyncio
import json
import os
import subprocess
import time
from contextlib import suppress
from typing import Awaitable, Dict, Optional

import asyncio_for_robotics.textio as afor_textio
import asyncio_for_robotics.zenoh as afor
import foxglove
import foxglove.schemas as schemas
import pytest
import zenoh
from colorama import Fore

# from mcap.well_known import MessageEncoding, SchemaEncoding
# from mcap.writer import Writer
from test_base import loop_it

from elian_experiment.adv_sub import AdvancedSub

ID = "mesh_1"


@pytest.fixture(scope="module")
def bag():
    dir = "output"
    os.makedirs(dir, exist_ok=True)
    mcap_file = f"{dir}/data.mcap"
    print("starting foxglove")
    with foxglove.open_mcap(mcap_file, allow_overwrite=True):
        server = foxglove.start_server()
        print("server")
        yield
        server.stop()


@pytest.fixture(scope="module")
def stdout_topic(bag):
    print("stdout_topic")
    return foxglove.Channel(
        "/stdout",
        schema=schemas.Log.get_schema(),
        message_encoding=schemas.Log.get_schema().encoding,
    )


def find_zenoh_log_lvl(msg: str) -> int:
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "FATAL"]
    found_lvls = [l for l in levels if l in msg[: min(len(msg), 500)]]
    lvl = found_lvls[-1] if found_lvls != [] else "INFO"
    lvl = levels.index(lvl) + 1
    return lvl


def make_mcap_log(
    msg,
    timestamp: Optional[int] = None,
    lvl: schemas.LogLevel | int = schemas.LogLevel.Unknown,
    name: str = "No name",
):
    if timestamp is None:
        timestamp = time.time_ns()

    return schemas.Log(
        timestamp=schemas.Timestamp(
            sec=int(timestamp // 1e9),
            nsec=int(timestamp % 1e9),
        ),
        level=schemas.LogLevel.Info,
        message=msg,
        name=name,
        line=0,
    ).encode()


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

    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        print(msg)
        now = time.time_ns()
        lvl = find_zenoh_log_lvl(msg)
        stdout_topic.log(
            msg=make_mcap_log(msg, timestamp=now, lvl=lvl, name="node1 router"),
            log_time=now,
        )

    stdout_sub.asap_callback.append(log_it)
    yield
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

    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        # print(msg)
        now = time.time_ns()
        lvl = find_zenoh_log_lvl(msg)
        stdout_topic.log(
            msg=make_mcap_log(msg, timestamp=now, lvl=lvl, name="node2 router"),
            log_time=now,
        )

    stdout_sub.asap_callback.append(log_it)
    yield
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

    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        # print(msg)
        now = time.time_ns()
        lvl = find_zenoh_log_lvl(msg)
        stdout_topic.log(
            msg=make_mcap_log(msg, timestamp=now, lvl=lvl, name="central router"),
            log_time=now,
        )

    print("central")
    stdout_sub.asap_callback.append(log_it)
    yield
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

    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        now = time.time_ns()
        lvl = find_zenoh_log_lvl(msg)
        print(msg)
        stdout_topic.log(
            log_time=now,
            msg=make_mcap_log(msg, timestamp=now, lvl=lvl, name="mirror"),
        )

    # stdout_sub.asap_callback.append(log_it)
    print("mirror")
    yield
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


@pytest.fixture
def log_payload(stdout_topic: foxglove.Channel):

    def log_it(msg: str, count: int):
        now = time.time_ns()
        if msg is None:
            return
        if msg == "":
            return
        pong = json.loads(msg)
        pong["payload_size"] = len(pong["source"]["data"])
        try:
            del pong["source"]["data"]
        except KeyError:
            pass
        pong["total_size"] = len(msg)
        pong["half_trip"] = int(pong["target"]["time"]) - int(pong["source"]["time"])
        pong["round_trip"] = now - int(pong["source"]["time"])
        print(pong)
        foxglove.log(
            topic="measurement",
            log_time=now,
            message=pong,
        )

    yield log_it


async def test_debug(
    sub,
    pub,
    log_node1_router_stdout,
    log_node2_router_stdout,
    log_central_router_stdout,
    log_mirror_stdout,
    log_payload,
    stdout_topic: foxglove.Channel,
):
    await afor.soft_wait_for(loop_it(sub, pub, log_payload), 120)
