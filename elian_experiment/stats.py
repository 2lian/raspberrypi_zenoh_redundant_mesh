import asyncio
import json
import subprocess
import time
from contextlib import suppress
from typing import Awaitable, Dict

import asyncio_for_robotics.zenoh as afor
import zenoh
from colorama import Fore


async def main():
    p = subprocess.Popen(
        ["ssh", "unifi"],
        stdin=subprocess.PIPE,
        text=True,
    )

    try:
        while True:
            p.stdin.write("ethtool -S eth0\n")
            p.stdin.flush()
            await asyncio.sleep(1)
    finally:
        p.terminate()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
