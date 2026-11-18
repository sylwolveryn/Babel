"""Memory reader entry point.

The frame markers come from `addon_protocol`: they are part of the addon's
wire format, not of the reader.
"""

from app.addon_protocol import MARKER_END, MARKER_START  # noqa: F401  (re-export)
from app.memory_reader_windows import (  # noqa: F401  (re-export)
    POLL_INTERVAL,
    WOW_PROCESS_NAMES,
    MemoryChatWatcher,
    WoWAddonBufReader,
)
