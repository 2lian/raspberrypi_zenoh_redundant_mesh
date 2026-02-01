import json
import os
from pprint import pprint
import time
from typing import Dict

import foxglove
import foxglove.schemas as schemas
import numpy as np
import pytest

from elian_experiment.adv_sub import AdvancedSub

ID = "mesh_1"
TEST_PARAMS = {
    "pubsub": "paused",
    "iter": None,
}


@pytest.fixture(autouse=True)
def test_params_memory():
    global TEST_PARAMS
    yield
    foxglove.log("/test_params", TEST_PARAMS)
    TEST_PARAMS = {
        "pubsub": "paused",
        "iter": None,
    }
    foxglove.log("/test_params", TEST_PARAMS)


@pytest.fixture(scope="module")
def bag():
    dir = "output"
    os.makedirs(dir, exist_ok=True)
    mcap_file = f"{dir}/data.mcap"
    print("starting foxglove")
    with foxglove.open_mcap(mcap_file, allow_overwrite=True):
        server = foxglove.start_server()
        server.clear_session()
        time.sleep(0.5)
        server.broadcast_time(time.time_ns())
        time.sleep(0.5)
        print("server")
        yield
        time.sleep(1)
        server.stop()


@pytest.fixture(scope="module")
def biglog_topic(bag):
    return foxglove.Channel(
        "/biglog",
        schema=schemas.Log.get_schema(),
        message_encoding=schemas.Log.get_schema().encoding,
    )


@pytest.fixture(scope="module")
def stdout_topic(bag):
    return foxglove.Channel(
        "/stdout",
        schema=schemas.Log.get_schema(),
        message_encoding=schemas.Log.get_schema().encoding,
    )


def log_payload(msg: str, count: int):
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
    source_time = int(pong["source"]["time"])
    target_time = int(pong["target"]["time"])
    pong["source"]["timestamp"] = {
        "sec": int(source_time // 1e9),
        "nsec": int(source_time % 1e9),
    }
    pong["target"]["timestamp"] = {
        "sec": int(target_time // 1e9),
        "nsec": int(target_time % 1e9),
    }
    pong["total_size"] = len(msg)
    pong["half_trip"] = target_time - source_time
    pong["round_trip"] = now - source_time
    pong["current_count"] = count
    # print(pong)
    foxglove.log(
        topic="/measurement",
        log_time=now,
        message=pong,
    )


def log_chat(msg: Dict):
    if msg is None:
        return
    if msg == "":
        return
    msg["payload_size"] = len(msg["source"]["data"])
    try:
        del msg["source"]["data"]
    except KeyError:
        pass
    source_time = int(msg["source"]["time"])
    target_time = int(msg["target"]["time"])
    now = target_time
    msg["source"]["timestamp"] = {
        "sec": int(source_time // 1e9),
        "nsec": int(source_time % 1e9),
    }
    msg["target"]["timestamp"] = {
        "sec": int(target_time // 1e9),
        "nsec": int(target_time % 1e9),
    }
    msg["total_size"] = len(msg)
    msg["half_trip"] = target_time - source_time
    foxglove.log(
        topic="/measurement",
        log_time=now,
        message=msg,
    )
