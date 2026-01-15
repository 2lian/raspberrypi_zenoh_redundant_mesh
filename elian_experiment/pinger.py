import asyncio
import base64
import json
import os
import time
from contextlib import suppress
from typing import Awaitable, Dict

import asyncio_for_robotics.zenoh as afor
import zenoh
from colorama import Fore

ID = "mesh_1"
scaling=1/1
BB = 1024**0 * scaling
KB = 1024**1 * scaling
MB = 1024**2 * scaling
GB = 1024**3 * scaling


async def ping_it(sub: afor.Sub, pub: zenoh.Publisher):
    count = 0

    async def print_return(pong_aw: Awaitable[zenoh.Sample], count: int):
        try:
            pong = json.loads((await pong_aw).payload.to_bytes())
            pong["target"]["time"] = int(pong["target"]["time"]) - int(
                pong["source"]["time"]
            )
            pong["return"] = {"time": time.time_ns() - int(pong["source"]["time"])}
            for k in pong.values():
                k["time"] = f"{int(k["time"]):_}"
            try:
                del pong["source"]["data"]
            except KeyError:
                pass
            print("returned: \n", json.dumps(pong, indent=2))
            timedout = False
            if pong["source"]["count"] != count:
                print(f"{Fore.YELLOW}COUNT DISCREPENCY{Fore.RESET}")
        except asyncio.CancelledError:
            print(f"{Fore.RED}DATA DROPPED{Fore.RESET}")

    print_task = asyncio.create_task(asyncio.sleep(0))
    _freq = 100
    async for t in afor.Rate(_freq).listen():
        print_task.cancel()
        await print_task
        count += 1
        data = {}
        payload = os.urandom(int(5 * MB / _freq))
        data["source"] = {
            "time": time.time_ns(),
            "count": count,
            "data": base64.b64encode(payload).decode("ascii"),
        }
        # print("sent: \n", json.dumps(data, indent=2))
        request = json.dumps(data)
        pong = sub.wait_for_next()
        pub.put(request)
        print_task = asyncio.create_task(print_return(pong, count))


async def main():
    config = zenoh.Config.from_file(
        "/home/elian/raspberrypi_zenoh_redundant_mesh/zenoh_config/client.json5"
    )
    ses = zenoh.open(config)
    afor.set_auto_session(ses)
    sub = afor.Sub(f"{ID}/response")
    # pub = ses.declare_publisher(f"{ID}/request")
    pub = zenoh.ext.declare_advanced_publisher(
        ses,
        f"{ID}/request",
        cache=zenoh.ext.CacheConfig(max_samples=100),
        sample_miss_detection=zenoh.ext.MissDetectionConfig(
            heartbeat=5, sporadic_heartbeat=5
        ),
        publisher_detection=True,
    )
    try:
        await ping_it(sub, pub)
    finally:
        pub.undeclare()
        sub.close()
        # ses.close()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
