"""Logging: one line per simulated second, written to a run file."""

import os
import time

from sim import config


class TickLogger:
    def __init__(self):
        os.makedirs(config.LOG_DIR, exist_ok=True)
        path = os.path.join(config.LOG_DIR, f"run_{int(time.time())}.log")
        self._file = open(path, "a", buffering=1)
        self._elapsed = 0.0

    def log(self, world, dt: float) -> None:
        self._elapsed += dt
        if self._elapsed < config.LOG_INTERVAL_S:
            return
        self._elapsed = 0.0
        self._file.write(
            f"day={world.day} time={world.time_sim:.1f} "
            f"pop={len(world.entities)} deaths={world.stats_deaths} "
            f"births={world.stats_births}\n"
        )

    def close(self) -> None:
        self._file.close()
