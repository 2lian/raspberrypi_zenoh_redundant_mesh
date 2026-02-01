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

from .events import wlan_down
from .test_base import conversation, listen
from .variables import REMOTES, SSHTargets
from .zenoh_utils import foxlog_zenoh_stdout

pass  # VVV imports fixtures
from .foxglove_bag import *
from .log_stats import *

ID = "mesh_1"
TEST_DURATION = 25


def zenoh_router_proc(
    ssh_target: str, config_path: str
) -> Generator[subprocess.Popen[str], Any, None]:
    subprocess.Popen(
        ["ssh", ssh_target, "pkill", "zenohd"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            ssh_target,
            "RUST_LOG=debug /home/moonshot/.pixi/bin/pixi run -m ",
            "~/raspberrypi_zenoh_redundant_mesh/pixi.toml ",
            "zenohd -c ",
            config_path,
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
            ["ssh", ssh_target, "pkill", "zenohd"],
        ).wait()
        p.terminate()
        p.wait()


@pytest.fixture
async def node1_zenohd(
    stdout_topic: foxglove.Channel,
) -> AsyncGenerator[afor_textio.Sub[str], None]:
    remote = REMOTES.node1
    for proc in zenoh_router_proc(remote.ssh, remote.zenohd_config):
        stdout_sub = afor_textio.from_proc_stdout(proc)
        foxlog_zenoh_stdout(stdout_sub, stdout_topic, f"{remote.ssh} router")
        yield stdout_sub
        stdout_sub.close()


@pytest.fixture
async def node2_zenohd(
    stdout_topic: foxglove.Channel,
) -> AsyncGenerator[afor_textio.Sub[str], None]:
    remote = REMOTES.node2
    for proc in zenoh_router_proc(remote.ssh, remote.zenohd_config):
        stdout_sub = afor_textio.from_proc_stdout(proc)
        foxlog_zenoh_stdout(stdout_sub, stdout_topic, f"{remote.ssh} router")
        yield stdout_sub
        stdout_sub.close()


@pytest.fixture
async def central_zenohd(
    stdout_topic: foxglove.Channel,
) -> AsyncGenerator[afor_textio.Sub[str], None]:
    remote = REMOTES.central
    for proc in zenoh_router_proc(remote.ssh, remote.zenohd_config):
        stdout_sub = afor_textio.from_proc_stdout(proc)
        foxlog_zenoh_stdout(stdout_sub, stdout_topic, f"{remote.ssh} router")
        yield stdout_sub
        stdout_sub.close()


def mirror_proc() -> Generator[subprocess.Popen[str], Any, None]:
    subprocess.Popen(
        ["ssh", REMOTES.node2.ssh, "pkill -f", "mirror.py"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            REMOTES.node2.ssh,
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
            ["ssh", REMOTES.node2.ssh, "pkill -f", "mirror.py"],
        ).wait()
        p.terminate()
        p.wait()


@pytest.fixture
async def mirror(
    biglog_topic: foxglove.Channel,
) -> AsyncGenerator[afor_textio.Sub[str], None]:
    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        now = time.time_ns()
        biglog_topic.log(
            msg=schemas.Log(
                timestamp=schemas.Timestamp.now(),
                level=schemas.LogLevel.Debug,
                message=msg,
                name="mirror python",
            ).encode(),
            log_time=now,
        )

    for proc in mirror_proc():
        stdout_sub = afor_textio.from_proc_stdout(proc)
        stdout_sub.asap_callback.append(log_it)
        print("mirror ready")
        yield stdout_sub
        stdout_sub.close()


def chatter_proc() -> Generator[subprocess.Popen[str], Any, None]:
    subprocess.Popen(
        ["ssh", REMOTES.node2.ssh, "pkill -f", "chatter.py"],
    ).wait()
    p = subprocess.Popen(
        [
            "ssh",
            REMOTES.node2.ssh,
            "/home/moonshot/.pixi/bin/pixi run -m",
            "~/raspberrypi_zenoh_redundant_mesh/pixi.toml",
            "python3",
            "~/raspberrypi_zenoh_redundant_mesh/elian_experiment/chatter.py",
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
            ["ssh", REMOTES.node2.ssh, "pkill -f", "chatter.py"],
        ).wait()
        p.terminate()
        p.wait()


@pytest.fixture
async def chatter_fix(
    biglog_topic: foxglove.Channel,
) -> AsyncGenerator[afor_textio.Sub[str], None]:
    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        now = time.time_ns()
        print(msg)
        biglog_topic.log(
            msg=schemas.Log(
                timestamp=schemas.Timestamp.now(),
                level=schemas.LogLevel.Debug,
                message=msg,
                name="chatter python",
            ).encode(),
            log_time=now,
        )

    for proc in chatter_proc():
        stdout_sub = afor_textio.from_proc_stdout(proc)
        stdout_sub.asap_callback.append(log_it)
        print("chatter ready")
        yield stdout_sub
        stdout_sub.close()


@pytest.fixture
async def setup_comms(
    node1_zenohd: afor_textio.Sub[str],
    node2_zenohd: afor_textio.Sub[str],
    central_zenohd: afor_textio.Sub[str],
):
    await asyncio.wait(
        [
            asyncio.ensure_future(node1_zenohd.wait_for_value()),
            asyncio.ensure_future(node2_zenohd.wait_for_value()),
            asyncio.ensure_future(central_zenohd.wait_for_value()),
        ]
    )
    print("coms ready")
    yield
    return


@pytest.fixture
async def z_session(setup_comms):
    filepath = os.path.expanduser(
        "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/client.json5"
    )
    config = zenoh.Config.from_file(filepath)
    ses = zenoh.open(config)
    afor.set_auto_session(ses)
    yield ses
    ses.close()


@pytest.fixture
async def setup_monitoring(biglog_topic):
    iter_list = [
        monitor_iwdev(SSHTargets.node1, biglog_topic),
        monitor_iwdev(SSHTargets.node2, biglog_topic),
        monitor_iwdev(SSHTargets.router, biglog_topic),
        monitor_ips(SSHTargets.node1, biglog_topic),
        monitor_ips(SSHTargets.node2, biglog_topic),
        monitor_ips(SSHTargets.router, biglog_topic),
    ]
    for aiterator in iter_list:
        await anext(aiterator)
    print("monitoring ready")
    yield
    for aiterator in iter_list:
        with suppress(StopIteration, StopAsyncIteration):
            await anext(aiterator)
    return


@pytest.fixture
async def advanced_sub(z_session, request):
    print(request.param)
    s = AdvancedSub(f"{ID}/response")
    yield s
    s.close()


@pytest.fixture
def advanced_pub(z_session):
    p = zenoh.ext.declare_advanced_publisher(
        z_session,
        f"{ID}/request",
        cache=zenoh.ext.CacheConfig(max_samples=1000),
        sample_miss_detection=zenoh.ext.MissDetectionConfig(
            heartbeat=1, sporadic_heartbeat=None
        ),
        publisher_detection=True,
    )
    yield lambda x: p.put(x)
    p.undeclare()


@pytest.fixture
def pubsub(z_session, request):
    p = request.param[0](f"{ID}/request")
    s = request.param[1](f"{ID}/response")
    TEST_PARAMS["pubsub"] = request.param[2]
    yield (lambda x: p.put(x), s)
    p.undeclare()
    s.close()


@pytest.mark.parametrize(
    "pubsub",
    [
        (
            lambda topic: zenoh.ext.declare_advanced_publisher(
                afor.auto_session(),
                topic,
                cache=zenoh.ext.CacheConfig(max_samples=100),
                sample_miss_detection=zenoh.ext.MissDetectionConfig(
                    heartbeat=1, sporadic_heartbeat=None
                ),
                publisher_detection=True,
            ),
            AdvancedSub,
            "advanced",
        ),
        (
            lambda topic: afor.auto_session().declare_publisher(
                topic,
                reliability=zenoh.Reliability.BEST_EFFORT,
                congestion_control=zenoh.CongestionControl.DROP,
            ),
            afor.Sub,
            "reliable-drop",
        ),
        (
            lambda topic: afor.auto_session().declare_publisher(
                topic,
                reliability=zenoh.Reliability.BEST_EFFORT,
                congestion_control=zenoh.CongestionControl.BLOCK,
            ),
            afor.Sub,
            "reliable-block",
        ),
        (
            lambda topic: afor.auto_session().declare_publisher(
                topic, reliability=zenoh.Reliability.RELIABLE
            ),
            afor.Sub,
            "best_effort",
        ),
    ],
    indirect=True,
)
@pytest.mark.parametrize("iter", range(1))
async def test_zenoh_conversation(
    pubsub,
    iter,
    mirror,
    setup_comms,
    setup_monitoring,
    bag,
):
    TEST_PARAMS["type"] = "conversation"
    TEST_PARAMS["iter"] = iter
    foxglove.log("/test_params", TEST_PARAMS)
    pub = pubsub[0]
    sub = pubsub[1]

    async def conv():
        await conversation(sub, pub, log_payload)

    async def event():
        await asyncio.sleep(5)
        await wlan_down("node2", 3)

    conv_task = asyncio.create_task(conv())
    await asyncio.wait_for(sub.wait_for_value(), 10)

    event_task = asyncio.create_task(event())
    with suppress(KeyboardInterrupt):
        await afor.soft_wait_for(conv_task, TEST_DURATION)
    event_task.cancel()


@pytest.mark.parametrize(
    "pubsub",
    [
        (
            lambda topic: zenoh.ext.declare_advanced_publisher(
                afor.auto_session(),
                topic,
                cache=zenoh.ext.CacheConfig(max_samples=1000),
                sample_miss_detection=zenoh.ext.MissDetectionConfig(
                    heartbeat=1, sporadic_heartbeat=None
                ),
                publisher_detection=True,
            ),
            AdvancedSub,
            "advanced",
        ),
        (
            lambda topic: afor.auto_session().declare_publisher(
                topic, reliability=zenoh.Reliability.BEST_EFFORT
            ),
            afor.Sub,
            "reliable",
        ),
        # (
        #     lambda topic: afor.auto_session().declare_publisher(
        #         topic, reliability=zenoh.Reliability.RELIABLE
        #     ),
        #     afor.Sub,
        #     "best_effort",
        # ),
    ],
    indirect=True,
)
@pytest.mark.parametrize("iter", range(1))
async def test_zenoh_chat(
    pubsub,
    iter,
    chatter_fix,
    setup_comms,
    setup_monitoring,
    bag,
):
    TEST_PARAMS["type"] = "sensor"
    TEST_PARAMS["iter"] = iter
    foxglove.log("/test_params", TEST_PARAMS)
    sub = pubsub[1]

    async def lis():
        await listen(sub, log_chat)

    async def event():
        await asyncio.sleep(5)
        await wlan_down("node2", 3)

    listen_task = asyncio.create_task(lis())
    await asyncio.wait_for(sub.wait_for_value(), 6)

    event_task = asyncio.create_task(event())
    with suppress(KeyboardInterrupt):
        await afor.soft_wait_for(listen_task, TEST_DURATION)
    event_task.cancel()
