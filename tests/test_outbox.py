"""Sending replies into the game: app/game_sender.py writes, Outbox.lua says it.

The addon half runs under real Lua 5.1, fed with exactly the numbers the app
would write, so the encoding both sides share is tested end to end. The app
half runs against a fake process whose memory is a bytearray laid out the way
the 32-bit client lays out a Lua array.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app import game_sender as gs

pytest.importorskip("lupa", reason="lupa provides the Lua 5.1 runtime the addon needs")

from tests.lua_harness import AddonHarness  # noqa: E402


@pytest.fixture
def addon():
    harness = AddonHarness()
    harness.sent = []
    harness.chat = []
    g = harness.lua.globals()
    g.SendChatMessage = lambda text, kind, _lang=None, where=None: harness.sent.append((text, kind, where))
    g.GetChannelName = lambda name: 6 if name == "World" else 0
    g.ChatEdit_GetLastTellTarget = lambda: "Thrall"
    harness.lua.execute(
        "DEFAULT_CHAT_FRAME = {AddMessage = function(self, m) _chat_lines = (_chat_lines or 0) + 1 end}"
    )
    harness.load("Timer.lua", "Outbox.lua")
    return harness


def deliver(addon, channel: str, target: str, text: str) -> int:
    """Do what the app does: payload, length, then the message number."""
    mailbox = addon.addon_table.outboxMailbox
    length, values = gs.encode(channel, target, text)
    for i, value in enumerate(values):
        mailbox[gs.SLOT_PAYLOAD + i] = value
    mailbox[gs.SLOT_LENGTH] = length
    seq = int(mailbox[gs.SLOT_SEQ]) + 1
    mailbox[gs.SLOT_SEQ] = seq
    addon.run_for(0.2)
    return seq


def test_markers_are_the_numbers_the_app_searches_for(addon):
    mailbox = addon.addon_table.outboxMailbox
    assert mailbox[1] == gs.MARKER_A
    assert mailbox[2] == gs.MARKER_B


def test_the_marker_is_not_a_constant_in_the_addon_code():
    source = (Path(__file__).resolve().parent.parent / "addon" / "BabelChat" / "Outbox.lua").read_text(encoding="utf-8")
    assert str(gs.MARKER_A) not in source and str(gs.MARKER_B) not in source


def test_heartbeat_moves(addon):
    mailbox = addon.addon_table.outboxMailbox
    before = mailbox[gs.SLOT_HEARTBEAT]
    addon.run_for(0.3)
    assert mailbox[gs.SLOT_HEARTBEAT] > before


@pytest.mark.parametrize(
    ("channel", "target", "expected"),
    [
        ("SAY", "", ("SAY", None)),
        ("YELL", "", ("YELL", None)),
        ("WHISPER", "Jaina", ("WHISPER", "Jaina")),
        ("REPLY", "", ("WHISPER", "Thrall")),
        ("RAID_WARNING", "", ("RAID_WARNING", None)),
        ("GUILD", "", ("GUILD", None)),
        ("CHANNEL:2", "", ("CHANNEL", 2)),
        ("CHANNEL:World", "", ("CHANNEL", 6)),
    ],
)
def test_each_channel_is_sent_where_it_should(addon, channel, target, expected):
    seq = deliver(addon, channel, target, "Hello, árvíztűrő tükörfúrógép!")
    assert addon.sent == [("Hello, árvíztűrő tükörfúrógép!", *expected)]
    assert addon.addon_table.outboxMailbox[gs.SLOT_ACK] == seq


def test_a_message_is_sent_once(addon):
    deliver(addon, "SAY", "", "once")
    addon.run_for(1.0)
    assert len(addon.sent) == 1


@pytest.mark.parametrize(("channel", "target"), [("WHISPER", ""), ("CHANNEL:Nowhere", "")])
def test_what_cannot_be_sent_is_reported_back_negative(addon, channel, target):
    seq = deliver(addon, channel, target, "hello")
    assert addon.sent == []
    assert addon.addon_table.outboxMailbox[gs.SLOT_ACK] == -seq


def test_long_text_is_split_at_spaces_into_chat_sized_pieces(addon):
    text = " ".join(["szó"] * 70)  # 349 bytes
    deliver(addon, "SAY", "", text)
    assert len(addon.sent) == 2
    assert all(len(piece.encode()) <= 255 for piece, *_ in addon.sent)
    assert " ".join(piece for piece, *_ in addon.sent) == text


def test_a_closed_mailbox_cannot_be_found(addon):
    addon.addon_table.CloseOutbox()
    assert addon.addon_table.outboxMailbox[1] == 0


def test_too_long_is_refused_before_anything_is_written():
    with pytest.raises(gs.SendError):
        gs.encode("SAY", "", "x" * (gs.MAX_BYTES + 1))


# ── the app half, against fake game memory ──────────────────────────────────


class FakeProcess:
    """Game memory as a bytearray, with a mailbox at `base` the fake addon serves."""

    def __init__(self, base: int = 0x1000, live: bool = True, fail_channel: str | None = None):
        self.base = base
        self.memory = bytearray(base + gs.TVALUE_SIZE * (gs.SLOTS + 10))
        self.live = live
        self.fail_channel = fail_channel
        self.sent: list[str] = []
        for i in range(1, gs.SLOTS + 7):
            self._set(i, 0)
        self._set(1, gs.MARKER_A)
        self._set(2, gs.MARKER_B)

    def _offset(self, index: int) -> int:
        return self.base + (index - 1) * gs.TVALUE_SIZE

    def _set(self, index: int, value: float) -> None:
        struct.pack_into("<di", self.memory, self._offset(index), float(value), gs.LUA_TNUMBER)

    def _get(self, index: int) -> float:
        return struct.unpack_from("<d", self.memory, self._offset(index))[0]

    def regions(self):
        yield 0, len(self.memory)

    def read(self, address: int, size: int) -> bytes:
        if self.live:
            self._set(gs.SLOT_HEARTBEAT, self._get(gs.SLOT_HEARTBEAT) + 1)
            self._serve()
        return bytes(self.memory[address : address + size])

    def write(self, address: int, data: bytes) -> bool:
        self.memory[address : address + len(data)] = data
        return True

    def _serve(self) -> None:
        seq = self._get(gs.SLOT_SEQ)
        if seq and abs(self._get(gs.SLOT_ACK)) != seq:
            length = int(self._get(gs.SLOT_LENGTH))
            data = b"".join(
                int(self._get(gs.SLOT_PAYLOAD + i)).to_bytes(gs.BYTES_PER_SLOT, "little")
                for i in range(-(-length // gs.BYTES_PER_SLOT))
            )[:length]
            channel, _target, text = data.decode().split("\t", 2)
            ok = channel != self.fail_channel
            if ok:
                self.sent.append(text)
            self._set(gs.SLOT_ACK, seq if ok else -seq)

    def close(self) -> None:
        pass


@pytest.fixture
def sender(monkeypatch):
    def make(process):
        monkeypatch.setattr(gs, "_Process", lambda pid: process)
        monkeypatch.setattr(gs.time, "sleep", lambda _s: None)
        return gs.GameSender(find_pid=lambda: 1234)

    return make


def test_sender_finds_the_mailbox_and_the_addon_confirms(sender):
    process = FakeProcess()
    sender(process).send("SAY", "", "Szia, mindenki!")
    assert process.sent == ["Szia, mindenki!"]


def test_sender_sends_a_second_message_with_the_next_number(sender):
    process = FakeProcess()
    s = sender(process)
    s.send("SAY", "", "egy")
    s.send("SAY", "", "kettő")
    assert process.sent == ["egy", "kettő"]


def test_sender_reports_a_message_the_game_refused(sender):
    process = FakeProcess(fail_channel="WHISPER")
    with pytest.raises(gs.SendError, match="játék chatjébe"):
        sender(process).send("WHISPER", "", "hello")


def test_sender_ignores_a_mailbox_whose_heartbeat_stopped(sender):
    with pytest.raises(gs.SendError, match="nem fut"):
        sender(FakeProcess(live=False)).send("SAY", "", "hello")


def test_sender_without_wow(monkeypatch):
    with pytest.raises(gs.SendError, match="nem fut"):
        gs.GameSender(find_pid=lambda: None).send("SAY", "", "hello")
