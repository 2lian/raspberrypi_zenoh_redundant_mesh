import asyncio
import base64
import json
import os
import time
from typing import Any, Awaitable, Callable, Dict, Set

import asyncio_for_robotics.zenoh as afor
import foxglove
from colorama import Fore

ID = "mesh_1"
scaling = 1 / 1
BB = 1024**0 * scaling
KB = 1024**1 * scaling
MB = 1024**2 * scaling
GB = 1024**3 * scaling
DEFAULT_PAYLOAD_SIZE = int(4 * KB)


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


async def conversation(
    sub: afor.Sub,
    pub: Callable[[str], Any],
    callback: Callable[[str, int], Any] = print_return,
    payload_size: int = DEFAULT_PAYLOAD_SIZE,
):
    count = 0
    missed = 0
    late = 0

    def missed_react():
        nonlocal missed
        print(f"{Fore.RED}Stale, sending new payload.{Fore.RESET}")
        send_payload()
        missed += 1
        report_errors()

    def late_react():
        nonlocal missed, late
        print(f"{Fore.CYAN}Stale payload received :) yey.{Fore.RESET}")
        missed -= 1
        late += 1
        report_errors()

    def report_errors():
        foxglove.log(
            topic="/measurments/errors", message={"missed": missed, "late": late}
        )

    report_errors()

    def send_payload():
        nonlocal count, pub, payload_size
        data = {}
        _payload = os.urandom(payload_size)
        heavy_data = base64.b64encode(_payload).decode("ascii")

        data["source"] = {
            "time": time.time_ns(),
            "count": count,
            "data": heavy_data,
        }
        # print(json.dumps(data, indent=2))
        request = json.dumps(data)
        pub(request)
        count += 1

    async def send_when_stale():
        nonlocal sub
        while 1:
            result = await afor.soft_wait_for(sub.wait_for_next(), 1)
            if isinstance(result, TimeoutError):
                if sub.alive.is_set():  # don't log the very firsts ones as missed
                    missed_react()

    async def loop():
        nonlocal sub, count, payload_size
        async for msg_raw in sub.listen_reliable():
            msg = json.loads(msg_raw.payload.to_bytes())
            if msg["source"]["count"] != count - 1:
                late_react()
                continue
            asyncio.get_event_loop().call_soon(
                callback, msg_raw.payload.to_string(), count
            )
            send_payload()
            report_errors()
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


async def listen(
    sub: afor.Sub,
    callback: Callable[[Dict], Any],
):
    missed: Set[int] = set()
    late: Set[int] = set()
    duplicated: Set[int] = set()

    def report_errors():
        foxglove.log(
            topic="/measurments/errors",
            message={
                "missed": len(missed),
                "late": len(late),
                "duplicated": len(duplicated),
            },
        )

    report_errors()

    async def loop():
        nonlocal sub, missed, late, duplicated
        index = None
        async for msg_raw in sub.listen_reliable():
            msg = json.loads(msg_raw.payload.to_bytes())
            source_count = msg["source"]["count"]
            if index is None:
                index = source_count
            msg["target"] = {
                "time": time.time_ns(),
                "count": index,
            }
            asyncio.get_event_loop().call_soon(callback, msg)

            if index == source_count:
                index += 1
                report_errors()
                continue

            if index in missed:
                if index in late:
                    duplicated.add(index)
                else:
                    late.add(index)
                report_errors()
                continue


            jumped = set(range(index, source_count))
            missed = missed | (jumped - late)

            report_errors()
            index = source_count + 1

    loop_task = asyncio.create_task(loop())
    try:
        await asyncio.wait([loop_task], return_when=asyncio.FIRST_COMPLETED)
        print("ruh ho")
        print(loop_task.done())
    finally:
        loop_task.cancel()
        await asyncio.wait([loop_task])
