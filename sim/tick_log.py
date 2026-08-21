"""Per-tick logging: one line per simulated tick, written to a run file."""

import os
import time

from sim import config


class TickLogger:
    def __init__(self):
        os.makedirs(config.LOG_DIR, exist_ok=True)
        path = os.path.join(config.LOG_DIR, f"run_{int(time.time())}.log")
        self._file = open(path, "a", buffering=1)
        self._tick = 0

    def log(self, world) -> None:
        self._tick += 1
        self._file.write(
            f"tick={self._tick} day={world.day} time={world.time_sim:.1f} "
            f"pop={len(world.entities)} deaths={world.stats_deaths} "
            f"births={world.stats_births}\n"
        )

    def close(self) -> None:
        self._file.close()
