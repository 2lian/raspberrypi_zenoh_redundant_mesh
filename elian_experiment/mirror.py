import asyncio
from contextlib import suppress
import time
import json
import zenoh
import asyncio_for_robotics.zenoh as afor

ID = "mesh_1"

async def mirror_echo(sub: afor.Sub, pub: zenoh.Publisher):
    count = 0
    async for msg in sub.listen_reliable():
        data = json.loads(msg.payload.to_bytes())
        data["target"] = {"time": time.time_ns(), "count": count}
        print("got: \n", json.dumps(data, indent=2))
        reply = json.dumps(data)
        pub.put(reply)

async def main():
    ses = afor.auto_session()
    sub = afor.Sub(f"{ID}/request")
    pub = ses.declare_publisher(f"{ID}/response")
    try:
        await mirror_echo(sub, pub)
    finally:
        pub.undeclare()
        sub.close()

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
