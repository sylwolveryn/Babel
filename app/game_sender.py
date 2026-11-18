"""Hand a message to the addon, which says it in game.

The addon keeps a small array of numbers, the mailbox (addon/BabelChat/
Outbox.lua documents its layout). This module finds that array in the game's
memory and writes the message into it; the addon notices within a tenth of a
second, sends it with SendChatMessage, and writes back the message number as
confirmation (negated when it could not send, with the reason in game chat).

Writing into the game is limited to that array: before every write the two
marker numbers are read back, so a mailbox that has gone away (a /reload, a
logout) is searched for again rather than written into.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import struct
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Must match Outbox.lua.
MARKER_A = 7340033 * 1048573
MARKER_B = 5003 * 1000003 * 97
SLOTS = 100
BYTES_PER_SLOT = 6
MAX_BYTES = SLOTS * BYTES_PER_SLOT

# Lua 5.1 on the 32-bit client: a TValue is an 8-byte value and a 4-byte type
# tag, padded to 16 bytes; LUA_TNUMBER is 3.
TVALUE_SIZE = 16
LUA_TNUMBER = 3

SLOT_HEARTBEAT = 3
SLOT_ACK = 4
SLOT_SEQ = 5
SLOT_LENGTH = 6
SLOT_PAYLOAD = 7

ACK_TIMEOUT_S = 2.0

# (id sent to the addon, label in the dropdown)
CHANNELS: tuple[tuple[str, str], ...] = (
    ("SAY", "Mondás (/s)"),
    ("YELL", "Kiáltás (/y)"),
    ("WHISPER", "Suttogás (/w)"),
    ("REPLY", "Válasz (/r)"),
    ("PARTY", "Csoport (/p)"),
    ("RAID", "Raid (/ra)"),
    ("RAID_WARNING", "Raid figyelmeztetés (/rw)"),
    ("BATTLEGROUND", "Csatatér (/bg)"),
    ("GUILD", "Céh (/g)"),
    ("OFFICER", "Tiszti (/o)"),
    ("CHANNEL:1", "General (/1)"),
    ("CHANNEL:2", "Trade (/2)"),
    ("CHANNEL:3", "LocalDefense (/3)"),
    ("CHANNEL:4", "LookingForGroup (/4)"),
    ("CHANNEL:World", "World"),
)
DEFAULT_CHANNEL = "SAY"


class SendError(Exception):
    """Why a message could not be handed over; the text is shown to the user."""


def encode(channel: str, target: str, text: str) -> tuple[int, list[int]]:
    """The message as the addon reads it: its byte length and the slot values."""
    data = f"{channel}\t{target}\t{text}".encode()
    if len(data) > MAX_BYTES:
        raise SendError("Az üzenet túl hosszú.")
    values = []
    for start in range(0, len(data), BYTES_PER_SLOT):
        chunk = data[start : start + BYTES_PER_SLOT]
        values.append(int.from_bytes(chunk, "little"))
    return len(data), values


def _number(value: int | float) -> bytes:
    return struct.pack("<d", float(value))


_PATTERN = _number(MARKER_A) + struct.pack("<i", LUA_TNUMBER)


# ── Windows process access ──────────────────────────────────────────────────

PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_READWRITE = 0x04
MAX_ADDRESS = 0xFFFF_FFFF  # the 3.3.5a client is a 32-bit process
CHUNK = 4 * 1024 * 1024


class _MemoryInfo(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("PartitionId", wt.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


class _Process:
    def __init__(self, pid: int) -> None:
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32.OpenProcess.restype = wt.HANDLE
        self._k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        self._k32.VirtualQueryEx.restype = ctypes.c_size_t
        self._k32.ReadProcessMemory.argtypes = [
            wt.HANDLE,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._k32.WriteProcessMemory.argtypes = self._k32.ReadProcessMemory.argtypes
        access = PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_QUERY_INFORMATION
        self.handle = self._k32.OpenProcess(access, False, pid)
        if not self.handle:
            raise SendError("Nem lehet hozzáférni a WoW-hoz.")

    def close(self) -> None:
        if self.handle:
            self._k32.CloseHandle(self.handle)
            self.handle = None

    def regions(self):
        info = _MemoryInfo()
        address = 0
        while address < MAX_ADDRESS:
            if not self._k32.VirtualQueryEx(self.handle, address, ctypes.byref(info), ctypes.sizeof(info)):
                break
            base = info.BaseAddress or 0
            size = info.RegionSize
            if info.State == MEM_COMMIT and info.Type == MEM_PRIVATE and info.Protect == PAGE_READWRITE:
                yield base, size
            address = base + size

    def read(self, address: int, size: int) -> bytes | None:
        buffer = ctypes.create_string_buffer(size)
        done = ctypes.c_size_t()
        if not self._k32.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(done)):
            return None
        return buffer.raw[: done.value]

    def write(self, address: int, data: bytes) -> bool:
        done = ctypes.c_size_t()
        ok = self._k32.WriteProcessMemory(self.handle, address, data, len(data), ctypes.byref(done))
        return bool(ok) and done.value == len(data)


# ── The mailbox ─────────────────────────────────────────────────────────────


@dataclass
class _Mailbox:
    pid: int
    address: int

    def slot(self, index: int) -> int:
        return self.address + (index - 1) * TVALUE_SIZE


class GameSender:
    """Sends translated text into the game through the addon's mailbox.

    Thread-safe; `send` blocks (a search of the game's memory the first time,
    then a fraction of a second for the addon's confirmation), so call it off
    the UI thread.
    """

    def __init__(self, find_pid=None) -> None:
        if find_pid is None:
            from app.memory_scan_windows import _find_wow_pid as find_pid
        self._find_pid = find_pid
        self._mailbox: _Mailbox | None = None
        self._lock = threading.Lock()

    def send(self, channel: str, target: str, text: str) -> None:
        """Raises SendError, with a message for the user, if it did not go out."""
        length, values = encode(channel, target, text)
        with self._lock:
            pid = self._find_pid()
            if pid is None:
                raise SendError("A WoW nem fut.")
            process = _Process(pid)
            try:
                mailbox = self._mailbox if self._mailbox and self._mailbox.pid == pid else None
                if mailbox is None or not self._intact(process, mailbox):
                    mailbox = self._mailbox = self._locate(process, pid)
                self._deliver(process, mailbox, length, values)
            finally:
                process.close()

    @staticmethod
    def _read_number(process: _Process, address: int) -> float | None:
        raw = process.read(address, 12)
        if raw is None or len(raw) < 12 or struct.unpack_from("<i", raw, 8)[0] != LUA_TNUMBER:
            return None
        return struct.unpack_from("<d", raw)[0]

    def _intact(self, process: _Process, mailbox: _Mailbox) -> bool:
        return (
            self._read_number(process, mailbox.slot(1)) == MARKER_A
            and self._read_number(process, mailbox.slot(2)) == MARKER_B
        )

    def _locate(self, process: _Process, pid: int) -> _Mailbox:
        started = time.monotonic()
        candidates = []
        for base, size in process.regions():
            offset = 0
            while offset < size:
                length = min(CHUNK, size - offset)
                data = process.read(base + offset, length)
                if data:
                    hit = data.find(_PATTERN)
                    while hit != -1:
                        mailbox = _Mailbox(pid, base + offset + hit)
                        if self._intact(process, mailbox):
                            candidates.append(mailbox)
                        hit = data.find(_PATTERN, hit + 1)
                offset += length
        logger.info("Mailbox search: %d candidate(s) in %.1fs", len(candidates), time.monotonic() - started)
        if not candidates:
            raise SendError("Az addon nem válaszol — fut a játék, és be van kapcsolva a BabelChat addon?")

        # A /reload leaves the old mailbox behind; only the live one's
        # heartbeat moves.
        first = [self._read_number(process, c.slot(SLOT_HEARTBEAT)) for c in candidates]
        time.sleep(0.35)
        for candidate, before in zip(candidates, first, strict=True):
            if self._read_number(process, candidate.slot(SLOT_HEARTBEAT)) != before:
                return candidate
        raise SendError("Az addon nem fut (a játék szünetel, vagy töltőképernyőn vagy).")

    def _deliver(self, process: _Process, mailbox: _Mailbox, length: int, values: list[int]) -> None:
        current = self._read_number(process, mailbox.slot(SLOT_SEQ))
        seq = int(current or 0) + 1
        ok = True
        for i, value in enumerate(values):
            ok &= process.write(mailbox.slot(SLOT_PAYLOAD + i), _number(value))
        ok &= process.write(mailbox.slot(SLOT_LENGTH), _number(length))
        # The message number last: it is what the addon waits for.
        ok &= process.write(mailbox.slot(SLOT_SEQ), _number(seq))
        if not ok:
            self._mailbox = None
            raise SendError("Nem sikerült írni a játékba.")

        deadline = time.monotonic() + ACK_TIMEOUT_S
        while time.monotonic() < deadline:
            ack = self._read_number(process, mailbox.slot(SLOT_ACK))
            if ack == seq:
                return
            if ack == -seq:
                raise SendError("A játék nem tudta elküldeni — az okát kiírta a játék chatjébe.")
            time.sleep(0.05)
        # Most likely a mailbox left behind by a /reload: search again next time.
        self._mailbox = None
        raise SendError("Az addon nem erősítette meg a küldést.")
