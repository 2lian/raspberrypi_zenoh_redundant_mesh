import asyncio
from pprint import pprint
import base64
import json
import os
import time
from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict

import asyncio_for_robotics.zenoh as afor
import foxglove
import zenoh
from colorama import Fore

from elian_experiment.adv_sub import AdvancedSub

ID = "mesh_1"


async def chatter_loop(pub: Callable[[str], Any], payload_size: int = 1_000):
    count = 0
    _payload = os.urandom(payload_size)
    heavy_data = base64.b64encode(_payload).decode("ascii")
    print("loop starting")
    async for t in afor.Rate(frequency=1000).listen_reliable():
        dic = {
            "source": {
                "time": time.time_ns(),
                "count": count,
                "data": heavy_data,
            }
        }
        # pprint(dic)
        pub(json.dumps(dic))
        _payload = os.urandom(payload_size)
        heavy_data = base64.b64encode(_payload).decode("ascii")
        count += 1


async def main():
    config = zenoh.Config.from_file(
        os.path.expanduser(
            "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/node_client.json5"
        )
    )
    ses = zenoh.open(config)
    afor.set_auto_session(ses)
    # pub = ses.declare_publisher(f"{ID}/response")
    pub = zenoh.ext.declare_advanced_publisher(
        ses,
        f"{ID}/response",
        cache=zenoh.ext.CacheConfig(max_samples=100),
        sample_miss_detection=zenoh.ext.MissDetectionConfig(
            heartbeat=1, sporadic_heartbeat=None
        ),
        publisher_detection=True,
    )
    print("pub created")

    def pub_func(msg: str):
        pub.put(msg)

    try:
        await chatter_loop(pub_func)
    finally:
        pub.undeclare()
        ses.close()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
