import asyncio
from contextlib import suppress
import os
import time
import json
import zenoh
import asyncio_for_robotics.zenoh as afor

from elian_experiment.adv_sub import AdvancedSub

ID = "mesh_1"

async def mirror_echo(sub: afor.Sub, pub: zenoh.Publisher):
    count = 0
    async for msg in sub.listen_reliable():
        data = json.loads(msg.payload.to_bytes())
        data["target"] = {"time": time.time_ns(), "count": count}
        count += 1
        print("got: \n", json.dumps(data, indent=2))
        reply = json.dumps(data)
        pub.put(reply)

async def main():
    config = zenoh.Config.from_file(
        os.path.expanduser("~/raspberrypi_zenoh_redundant_mesh/zenoh_config/client.json5")
    )
    ses = zenoh.open(config)
    afor.set_auto_session(ses)
    # sub = afor.Sub(f"{ID}/request")
    sub = AdvancedSub(f"{ID}/request")
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
    try:
        await mirror_echo(sub, pub)
    finally:
        pub.undeclare()
        sub.close()

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
