import time

import asyncio_for_robotics.textio as afor_textio
import foxglove
import foxglove.schemas as schemas
import pytest
import zenoh

from elian_experiment.adv_sub import AdvancedSub

def find_zenoh_log_lvl(msg: str) -> schemas.LogLevel:
    levels = {
            "UNKNOWN": schemas.LogLevel.Unknown,
            "DEBUG": schemas.LogLevel.Debug,
            "INFO": schemas.LogLevel.Info,
            "WARNING": schemas.LogLevel.Warning,
            "ERROR": schemas.LogLevel.Error,
            "FATAL": schemas.LogLevel.Fatal,
    }
    found_lvls = [l for l in levels.keys() if l in msg[: min(len(msg), 500)]]
    lvl: str = found_lvls[-1] if found_lvls != [] else "UNKNOWN"
    fox_level = levels[lvl]
    return fox_level

def foxlog_zenoh_stdout(
    stdout: afor_textio.Sub[str], topic: foxglove.Channel, log_title: str
):

    def log_it(msg: str):
        if msg is None:
            return
        if msg == "":
            return
        # print(msg)
        now = time.time_ns()
        lvl = find_zenoh_log_lvl(msg)
        topic.log(
            msg=schemas.Log(
                timestamp=schemas.Timestamp.now(),
                level=lvl,
                message=msg,
                name=log_title,
            ).encode(),
            log_time=now,
        )

    stdout.asap_callback.append(log_it)


