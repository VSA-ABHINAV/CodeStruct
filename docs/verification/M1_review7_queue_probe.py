"""Reproduce an old poller's STOP message affecting a new session."""

import queue
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / "thonny-plugin"))
import thonnycontrib.codestruct as plugin  # noqa: E402


class Workbench:
    def winfo_exists(self) -> bool:
        return True

    def after(self, delay: int, callback: object) -> None:
        pass


plugin._is_shutting_down = False
plugin._nav_session_token = "cap_new"  # noqa: S105
plugin._nav_poll_generation = 2
plugin._nav_poll_active = True
plugin._nav_poll_in_flight = True
plugin._nav_queue = queue.Queue()
plugin._nav_queue.put(("STOP", 1))  # old generation's late HTTP 403
plugin._poll_navigate(Workbench(), "http://127.0.0.1:8000", "cap_new", 2)
print("New session active after old STOP:", plugin._nav_poll_active)
assert plugin._nav_poll_active, "Old STOP disabled the new session"
