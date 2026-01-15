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

from elian_experiment.adv_sub import AdvancedSub

ID = "mesh_1"
scaling = 1 / 1
BB = 1024**0 * scaling
KB = 1024**1 * scaling
MB = 1024**2 * scaling
GB = 1024**3 * scaling


async def loop_it(sub: afor.Sub, pub: zenoh.Publisher):
    count = 0

    def send_payload():
        nonlocal count, pub
        data = {}
        payload = os.urandom(int(40 * KB))
        data["source"] = {
            "time": time.time_ns(),
            "count": count,
            "data": base64.b64encode(payload).decode("ascii"),
        }
        # print(json.dumps(data, indent=2))
        request = json.dumps(data)
        pub.put(request)

    async def send_when_stale():
        nonlocal sub, count
        while 1:
            result = await afor.soft_wait_for(sub.wait_for_next(), 2)
            if isinstance(result, TimeoutError):
                print(f"{Fore.RED}Stale, sending new payload.{Fore.RESET}")
                send_payload()

    async def print_return():
        nonlocal sub, count
        async for pong_raw in sub.listen_reliable():
            pong = json.loads(pong_raw.payload.to_bytes())
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
            print("round-trip: ", pong["return"]["time"])
            # print("returned: \n", json.dumps(pong, indent=2))
            if pong["source"]["count"] != count:
                print(f"{Fore.YELLOW}COUNT DISCREPENCY{Fore.RESET}")

    async def loop():
        nonlocal sub, count
        async for msg in sub.listen_reliable():
            msg = json.loads(msg.payload.to_bytes())
            if msg["source"]["count"] != count:
                print(f"{Fore.CYAN}Stale payload received :) yey.{Fore.RESET}")
                continue
            count += 1
            send_payload()

    loop_task = asyncio.create_task(loop())
    print_task = asyncio.create_task(print_return())
    unstale_task = asyncio.create_task(send_when_stale())
    try:
        await asyncio.wait(
        [loop_task, print_task, unstale_task], return_when=asyncio.FIRST_COMPLETED
    )
    finally:
        loop_task.cancel()
        print_task.cancel()
        unstale_task.cancel()



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
    _freq = 30
    async for t in afor.Rate(_freq).listen_reliable():
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
    sub = AdvancedSub(f"{ID}/response")
    # pub = ses.declare_publisher(f"{ID}/request")
    pub = zenoh.ext.declare_advanced_publisher(
        ses,
        f"{ID}/request",
        cache=zenoh.ext.CacheConfig(max_samples=100),
        sample_miss_detection=zenoh.ext.MissDetectionConfig(
            heartbeat=1, sporadic_heartbeat=None
        ),
        publisher_detection=True,
    )
    try:
        await loop_it(sub, pub)
    finally:
        pub.undeclare()
        sub.close()
        # ses.close()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
