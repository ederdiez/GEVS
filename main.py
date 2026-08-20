"""Entry point: start the simulation.

Run with: python main.py
"""

from sim.loop import run
from sim.window import create_window


def main() -> None:
    screen = create_window()
    run(screen)


if __name__ == "__main__":
    main()
