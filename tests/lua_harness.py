"""Run the WoW addon's Lua under a real Lua 5.1 interpreter.

WoW 3.3.5 runs Lua 5.1, and `lupa.lua51` embeds exactly that, so addon logic
can be exercised for real instead of being eyeballed or re-implemented in
Python. What the harness supplies is the surrounding game: the handful of WoW
globals the addon touches, plus a manual clock and a manual frame pump so tests
drive time rather than wait for it.

Fidelity, stated plainly so nobody over-trusts a green test:

* Only the globals listed in `_install_wow_globals` exist. Anything else the
  addon reaches for surfaces as a nil-index error, which is the intended
  outcome: the harness should fail loudly rather than paper over a new
  dependency on game state. Files that need more than that — the options
  panel's templates, `InterfaceOptions_AddCategory` — stub it themselves, per
  test file.
* `CreateFrame` here is a minimal 3.3.5-shaped frame: SetScript/GetScript,
  Show/Hide/IsShown, and nothing else. It exists so `Timer.lua` — the addon's
  own C_Timer backport, built on a frame's OnUpdate — runs for real. Test files
  that replace `CreateFrame` with a richer stub load `Timer.lua` against theirs.
* Time is the harness's: `GetTime()` returns `now`, and `pump()` delivers
  OnUpdate to every shown frame with the elapsed time you pass. `run_for()`
  does both at a frame rate, which is how the timer cadence is measured.
  `fire_tickers()` keeps its old meaning — every live timer fires once, the
  clock does not move — by pumping one enormous frame, since a timer that fell
  behind fires once and never bursts.
* `LoggingChat` is always false.
* The process C locale is pinned to "C" at import (see below). Without it
  `string.lower` and `%w`/`%s` behave differently from WoW for every byte above
  127, which silently changes what a Cyrillic test proves.
"""

from __future__ import annotations

import locale
from pathlib import Path

from lupa import lua51

# Lua's string.lower and its %w/%s classes call the C library's tolower and
# isalpha, which read the process locale. Something in the test environment —
# PyQt6, or lupa itself — sets LC_CTYPE from Windows, and under a non-C locale
# the results are wrong in ways that matter here: two distinct letters can
# lower-case to the same bytes, and a UTF-8 trail byte can match %s so the
# tokeniser splits a word mid-character. WoW runs under the C locale. Pin it,
# or every non-ASCII assertion in the suite is measuring this machine rather
# than the game.
locale.setlocale(locale.LC_CTYPE, "C")

ADDON_DIR = Path(__file__).resolve().parent.parent / "addon" / "BabelChat"

# Something that is not a string: what the buffer and the chat filter must
# refuse without raising. A table, because it cannot be concatenated by
# accident the way a number can.
_NON_STRING_FACTORY = """
return function()
    return setmetatable({}, {
        __concat = function(a, b) return "<table>" end,
        __tostring = function() return "<table>" end,
    })
end
"""

# A frame with just enough of the 3.3.5 Frame API for Timer.lua. Every frame is
# remembered so `pump` can deliver OnUpdate the way the client does: to shown
# frames only.
_FRAME_STUB = """
_harness_frames = {}
CreateFrame = function(kind, name, parent)
    local frame = { _scripts = {}, _shown = true, _kind = kind }
    function frame:SetScript(handler, fn) self._scripts[handler] = fn end
    function frame:GetScript(handler) return self._scripts[handler] end
    function frame:Show() self._shown = true end
    function frame:Hide() self._shown = false end
    function frame:IsShown() return self._shown end
    table.insert(_harness_frames, frame)
    if name then _G[name] = frame end
    return frame
end
_harness_pump = function(elapsed)
    for _, frame in ipairs(_harness_frames) do
        local onUpdate = frame._scripts.OnUpdate
        if frame._shown and onUpdate then onUpdate(frame, elapsed) end
    end
end
"""


class AddonHarness:
    """A Lua 5.1 runtime preloaded with WoW stubs and the addon's files."""

    def __init__(self) -> None:
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.now = 0.0
        self.errors: list[str] = []
        self._install_wow_globals()
        self._make_non_string = self.lua.execute(_NON_STRING_FACTORY)
        self.addon_table = self.lua.eval("{}")
        self.lua.globals().BabelChatDB = self.lua.eval("{}")

    # ── game stubs ───────────────────────────────────────────────────────

    def _install_wow_globals(self) -> None:
        g = self.lua.globals()

        g.GetTime = lambda: self.now
        g.UnitName = lambda _unit: "Tester"
        g.GetRealmName = lambda: "Test Realm"
        g.LoggingChat = lambda *_a: False
        g.geterrorhandler = lambda: (lambda err: self.errors.append(str(err)))

        # WoW exposes these as globals; Lua 5.1 only has table.insert/remove.
        self.lua.execute("tinsert = table.insert; tremove = table.remove")
        self.lua.execute(_FRAME_STUB)

    # ── driving the world ────────────────────────────────────────────────

    def advance(self, seconds: float) -> None:
        """Move the clock. Does not run any frame — call `pump` for that."""
        self.now += seconds

    def pump(self, elapsed: float) -> None:
        """Deliver one OnUpdate to every shown frame, without moving the clock."""
        self.lua.globals()._harness_pump(elapsed)

    def run_for(self, seconds: float, fps: int = 60) -> None:
        """Play `seconds` of game time at `fps`: clock and OnUpdate together."""
        step = 1.0 / fps
        for _ in range(round(seconds * fps)):
            self.now += step
            self.pump(step)

    def fire_tickers(self) -> None:
        """Run every live timer once, without moving the clock.

        One frame long enough to make every timer overdue. A late ticker fires
        once and re-arms, so nothing fires twice.
        """
        self.pump(1e9)

    def secret(self):
        """A value that is not a string. Kept under its old name: the tests
        that use it were written for retail's secret chat values, and on 3.3.5
        what they still pin is that a non-string is refused without raising."""
        return self._make_non_string()

    def non_string(self):
        return self._make_non_string()

    # ── loading addon files ──────────────────────────────────────────────

    def load(self, *filenames: str) -> None:
        """Load addon files in order, passing the usual (name, addonTable) varargs."""
        for name in filenames:
            source = (ADDON_DIR / name).read_text(encoding="utf-8")
            chunk = self.lua.execute("return function(src, chunkname) return assert(loadstring(src, chunkname)) end")(
                source, "@" + name
            )
            chunk("BabelChat", self.addon_table)

    # ── convenience accessors ────────────────────────────────────────────

    @property
    def db(self):
        return self.lua.globals().BabelChatDB

    def enable_companion(self) -> None:
        self.lua.execute("BabelChatDB.companion = { enabled = true, flushInterval = 5 }")

    def buffer_text(self) -> str:
        raw = self.db.wctbuf
        return raw if raw is not None else ""

    def buffer_frame(self) -> str:
        """The buffer up to and including the end marker, without the padding.

        Every real reader stops at the marker; the buffer is padded past it to a
        fixed length so that rebuilding it does not move it in memory.
        """
        text = self.buffer_text()
        marker = "__WCT_END__"
        cut = text.find(marker)
        return text if cut == -1 else text[: cut + len(marker)]

    def buffer_entries(self) -> list[str]:
        """Buffer payload lines: everything between the header and the end marker."""
        text = self.buffer_frame()
        if not text:
            return []
        lines = text.split("\n")
        # First line is the __WCT_BUF_NNNN__ header, last is __WCT_END__.
        body = lines[1:-1]
        return [ln for ln in body if ln and not ln.startswith("0|META|")]


def load_companion_buffer() -> AddonHarness:
    """Harness with Timer.lua and CompanionBuffer.lua loaded, companion on."""
    harness = AddonHarness()
    harness.load("Timer.lua", "CompanionBuffer.lua")
    harness.enable_companion()
    harness.addon_table.PreallocateCompanionKeys()
    return harness
