import asyncio
import base64
import json
import os
import time
from contextlib import suppress
from typing import Awaitable, Dict, Union

import asyncio_for_robotics.zenoh as afor
import zenoh
from colorama import Fore


class AdvancedSub(afor.Sub):
    def _resolve_sub(self, key_expr: Union[zenoh.KeyExpr, str]):
        return zenoh.ext.declare_advanced_subscriber(
            self.session,
            key_expr,
            self.callback_for_sub,
            history=zenoh.ext.HistoryConfig(detect_late_publishers=True),
            recovery=zenoh.ext.RecoveryConfig(periodic_queries=None, heartbeat=True),
            subscriber_detection=True,
        )
