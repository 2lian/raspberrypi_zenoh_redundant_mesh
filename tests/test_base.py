import asyncio
import base64
import json
import os
import time
from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict

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

_payload = os.urandom(int(0 * KB))
DATA = base64.b64encode(_payload).decode("ascii")
del _payload


def print_return(pong_raw: str, count: int):
    pong = json.loads(pong_raw)
    pong["payload_size"] = len(pong["source"]["data"])
    pong["total_size"] = len(pong_raw)
    pong["half_trip"] = int(pong["target"]["time"]) - int(pong["source"]["time"])
    pong["round_trip"] = time.time_ns() - int(pong["source"]["time"])
    for k in pong.values():
        try:
            k["time"] = f"{int(k["time"]):_}"
        except:
            pass
    try:
        del pong["source"]["data"]
    except KeyError:
        pass
    print("returned: \n", json.dumps(pong, indent=2))
    if pong["source"]["count"] != count - 1:
        print(f"{Fore.YELLOW}COUNT DISCREPENCY{Fore.RESET}")


async def loop_it(
    sub: afor.Sub,
    pub: Callable[[str], Any],
    callback: Callable[[str, int], Any] = print_return,
):
    count = 0

    def send_payload():
        nonlocal count, pub
        data = {}
        data["source"] = {
            "time": time.time_ns(),
            "count": count,
            "data": DATA,
        }
        # print(json.dumps(data, indent=2))
        request = json.dumps(data)
        pub(request)
        count += 1

    async def send_when_stale():
        nonlocal sub
        while 1:
            result = await afor.soft_wait_for(sub.wait_for_next(), 2)
            if isinstance(result, TimeoutError):
                print(f"{Fore.RED}Stale, sending new payload.{Fore.RESET}")
                send_payload()

    async def loop():
        nonlocal sub, count
        async for msg_raw in sub.listen_reliable():
            msg = json.loads(msg_raw.payload.to_bytes())
            if msg["source"]["count"] != count - 1:
                print(f"{Fore.CYAN}Stale payload received :) yey.{Fore.RESET}")
                continue
            asyncio.get_event_loop().call_soon(
                callback, msg_raw.payload.to_string(), count
            )
            send_payload()
            # callback(msg_raw.payload.to_string(), count)

    loop_task = asyncio.create_task(loop())
    unstale_task = asyncio.create_task(send_when_stale())
    send_payload()
    try:
        await asyncio.wait(
            [loop_task, unstale_task], return_when=asyncio.FIRST_COMPLETED
        )
        print("ruh ho")
        print(loop_task.done())
        print(unstale_task.done())
    finally:
        loop_task.cancel()
        unstale_task.cancel()
        await asyncio.wait([loop_task, unstale_task])
