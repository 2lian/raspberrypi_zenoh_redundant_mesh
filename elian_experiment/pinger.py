import asyncio
import json
import time
from contextlib import suppress

import asyncio_for_robotics.zenoh as afor
import zenoh

ID = "mesh_1"


async def ping_it(sub: afor.Sub, pub: zenoh.Publisher):
    count = 0
    async for t in afor.Rate(2).listen():
        data = {}
        data["source"] = {"time": time.time_ns(), "count": count}
        count += 1
        print("sent: \n", json.dumps(data, indent=2))
        request = json.dumps(data)
        pong = sub.wait_for_next()
        pub.put(request)
        async with afor.soft_timeout(1):
            pong = json.loads((await pong).payload.to_bytes())
            pong["target"]["time"] = int(pong["target"]["time"]) - int(
                pong["source"]["time"]
            )
            pong["return"] = {"time": time.time_ns() - int(pong["source"]["time"])}
            for k in pong.values():
                k["time"] = f"{int(k["time"]):_}"
            print("returned: \n", json.dumps(pong, indent=2))


async def main():
    ses = afor.auto_session()
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
