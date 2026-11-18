"""Timer.lua: the C_Timer backport the 3.3.5 client needs.

C_Timer arrived in patch 6.0. On WotLK the addon schedules everything — the
companion buffer's 0.25 s flush, its 2 s idle pulse, the chat-log flush, the
welcome popup — through its own timer built on a frame's OnUpdate. The memory
reader depends on that cadence, so it is measured here frame by frame rather
than assumed.
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("lupa", reason="lupa provides the Lua 5.1 runtime the addon needs")

from tests.lua_harness import AddonHarness, load_companion_buffer  # noqa: E402


@pytest.fixture
def timer():
    harness = AddonHarness()
    harness.load("Timer.lua")
    harness.lua.execute("_fired = {}")
    return harness


def fired(harness, name: str) -> int:
    value = harness.lua.globals()._fired[name]
    return int(value) if value is not None else 0


def counter(harness, name: str):
    return harness.lua.eval(f"function() _fired['{name}'] = (_fired['{name}'] or 0) + 1 end")


def driver_shown(harness) -> bool:
    frames = list(harness.lua.globals()._harness_frames.values())
    drivers = [f for f in frames if f._scripts.OnUpdate is not None]
    assert len(drivers) == 1, "Timer.lua should drive everything from one frame"
    return bool(drivers[0]._shown)


# ── the API the rest of the addon was written against ───────────────────────


def test_a_ticker_fires_at_its_interval_not_once_per_frame(timer):
    timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "t"))

    timer.run_for(10.0, fps=60)

    assert fired(timer, "t") in (39, 40), "a 0.25 s ticker should fire four times a second"


@pytest.mark.parametrize("fps", [20, 60, 144])
def test_the_cadence_does_not_depend_on_the_frame_rate(timer, fps):
    timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "t"))

    timer.run_for(5.0, fps=fps)

    assert 19 <= fired(timer, "t") <= 20


def test_the_first_tick_comes_one_interval_after_creation(timer):
    timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "t"))

    timer.run_for(0.2, fps=60)
    assert fired(timer, "t") == 0

    timer.run_for(0.1, fps=60)
    assert fired(timer, "t") == 1


def test_after_fires_exactly_once(timer):
    timer.addon_table.C_Timer.After(3, counter(timer, "a"))

    timer.run_for(2.9, fps=30)
    assert fired(timer, "a") == 0

    timer.run_for(5.0, fps=30)
    assert fired(timer, "a") == 1


def test_a_cancelled_ticker_stops(timer):
    ticker = timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "t"))
    timer.run_for(1.0)
    before = fired(timer, "t")

    ticker.Cancel(ticker)
    timer.run_for(2.0)

    assert fired(timer, "t") == before


def test_a_long_frame_fires_a_ticker_once_instead_of_bursting(timer):
    """A loading screen is one enormous frame. Catching up would rebuild the
    companion buffer a dozen times in a row for nothing."""
    timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "t"))

    timer.advance(5.0)
    timer.pump(5.0)

    assert fired(timer, "t") == 1


def test_the_driver_frame_is_hidden_when_there_is_nothing_to_run(timer):
    """OnUpdate costs a call every frame; with no timers it should not run."""
    assert driver_shown(timer) is False

    ticker = timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "t"))
    assert driver_shown(timer) is True

    ticker.Cancel(ticker)
    timer.pump(0.016)
    assert driver_shown(timer) is False


def test_an_error_in_one_callback_is_reported_and_the_rest_keep_running(timer):
    timer.addon_table.C_Timer.NewTicker(0.25, timer.lua.eval("function() error('boom') end"))
    timer.addon_table.C_Timer.NewTicker(0.25, counter(timer, "ok"))

    # A little past a second: frame times are floats, and the fourth tick can
    # land a rounding error after t = 1.0.
    timer.run_for(1.1)

    assert fired(timer, "ok") == 4
    assert timer.errors and "boom" in timer.errors[0]
    assert len(timer.errors) == 4, "a failing ticker must keep its cadence, not fire every frame"


def test_a_timer_created_inside_a_callback_is_not_advanced_by_the_same_frame(timer):
    spawn = timer.lua.eval(
        "function() addonTable_C_Timer.After(0.25, function() _fired.child = 1 end) end"
    )
    timer.lua.globals().addonTable_C_Timer = timer.addon_table.C_Timer
    timer.addon_table.C_Timer.After(0.25, spawn)

    timer.pump(0.3)
    assert fired(timer, "child") == 0

    timer.pump(0.3)
    assert fired(timer, "child") == 1


# ── the companion buffer's cadence, end to end ──────────────────────────────

PULSE = re.compile(r"^0\|META\|FLUSH\|(\d+)$", re.MULTILINE)


def pulse_of(harness) -> int:
    found = PULSE.search(harness.db.wctbuf or "")
    return int(found.group(1)) if found else 0


def test_a_message_reaches_the_buffer_within_a_quarter_second():
    h = load_companion_buffer()
    h.addon_table.StartBufferFlush()
    h.run_for(1.0)

    h.addon_table.BufferAddEntry("hello", "RAW", "SAY", "Thrall")
    h.run_for(0.25)

    assert "hello" in h.buffer_text()


def test_an_idle_buffer_still_pulses_about_every_two_seconds():
    """The heartbeat is what lets the reader tell a live buffer from a freed
    copy of it. Run on real frames rather than `fire_tickers`, so the 0.25 s
    tick and the 2 s heartbeat interact the way they do in the client."""
    h = load_companion_buffer()
    h.addon_table.StartBufferFlush()
    h.addon_table.BufferAddEntry("hello", "RAW", "SAY", "Thrall")
    h.run_for(0.5)
    start = pulse_of(h)

    h.run_for(20.0, fps=60)

    assert 9 <= pulse_of(h) - start <= 10


def test_stopping_the_flush_stops_the_pulse():
    h = load_companion_buffer()
    h.addon_table.StartBufferFlush()
    h.run_for(3.0)
    h.addon_table.StopBufferFlush()
    stopped_at = pulse_of(h)

    h.run_for(5.0)

    assert pulse_of(h) == stopped_at
