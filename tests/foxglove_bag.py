import json
import os
import time

import foxglove
import foxglove.schemas as schemas
import pytest
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
        topic="measurement",
        log_time=now,
        message=pong,
    )
