import asyncio
from typing import Awaitable, Dict
from colorama import Fore
import json
import time
from contextlib import suppress

import asyncio_for_robotics.zenoh as afor
import zenoh

ID = "mesh_1"


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
            print("returned: \n", json.dumps(pong, indent=2))
            timedout = False
            if pong["source"]["count"] != count:
                print(f"{Fore.YELLOW}COUNT DISCREPENCY{Fore.RESET}")
        except:
            print(f"{Fore.RED}DATA DROPPED{Fore.RESET}")

    print_task = asyncio.create_task(asyncio.sleep(0))
    async for t in afor.Rate(50).listen():
        print_task.cancel()
        count += 1
        data = {}
        data["source"] = {"time": time.time_ns(), "count": count}
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
    pub = ses.declare_publisher(f"{ID}/request")
    try:
        await ping_it(sub, pub)
    finally:
        pub.undeclare()
        sub.close()
        # ses.close()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
