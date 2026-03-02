import asyncio
from contextlib import suppress
import zenoh
import asyncio_for_robotics.zenoh as afor
import os

async def listen():
    async for msg in afor.Sub('mesh_1/response').listen():
        print(msg.payload.to_string())

async def main():
    config = zenoh.Config.from_file(
        os.path.expanduser(
            "~/raspberrypi_zenoh_redundant_mesh/zenoh_config/client.json5"
        )
    )
    ses = zenoh.open(config)
    afor.set_auto_session(ses)

    await listen()

if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
