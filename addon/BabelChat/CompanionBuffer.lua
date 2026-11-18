-- CompanionBuffer.lua — Memory buffer for companion app (ReadProcessMemory)
-- Ring buffer written to SavedVariable, read by BabelChat.exe via pymem.

local ADDON_NAME, addonTable = ...

-- The addon's own backport of the retail timer API (Timer.lua). The 3.3.5
-- client has no C_Timer, and this deliberately is not the global name.
local C_Timer = addonTable.C_Timer

-- ── Constants ────────────────────────────────────────────────
local MSG_LIMIT = 50           -- ring buffer size
local FLUSH_INTERVAL = 0.25   -- match companion poll rate (was 1.5s)
-- Rebuild at least this often even with nothing new to say. Every rebuild
-- allocates a NEW Lua string and frees the old one, and the freed bytes stay
-- readable for a while — so the companion can be looking at a copy that will
-- never change again. It cannot tell that from a quiet chat, because until now
-- the only thing in the buffer that moved was the message counter. A pulse that
-- ticks regardless is what makes a dead copy recognisable at a glance.
local HEARTBEAT_INTERVAL = 2.0

-- ── State ────────────────────────────────────────────────────
local wctBuf = {}              -- accumulator table
local wctSeq = 0               -- monotonic sequence counter
local wctFlush = 0             -- monotonic rebuild counter — the buffer's pulse
local lastRebuild = 0          -- GetTime() of the last rebuild
local bufDirty = false
local flushTicker = nil
local logFlushTicker = nil

-- ── Dedup ───────────────────────────────────────────────
-- ChatFilter fires once per ChatFrame displaying the event.
-- 3 chat windows showing SAY = 3 calls. Dedup by (author+text).
local DEDUP_SIZE = 10
local DEDUP_TTL = 2.0  -- seconds
local dedupRing = {}   -- { key = "author\0text", time = GetTime() }
local dedupIdx = 0

-- ── Argument check ──────────────────────────────────────────
-- Only real strings go into the buffer. A number would be written as digits,
-- and a nil or a table would raise inside the chat filter, which takes chat
-- handling down for every line that follows. Checked at the door, before the
-- value is compared in IsDuplicate or stored anywhere.
local string_gsub = string.gsub

local function IsUsable(value)
    return type(value) == "string"
end

-- ── Field sanitising ────────────────────────────────────────
-- The buffer is newline-delimited, pipe-separated, and framed by the literal
-- __WCT_BUF_NNNN__ / __WCT_END__ markers the companion scans for. Any of those
-- appearing inside a field breaks the record — and one of them is reachable by
-- anyone: a player can type "__WCT_END__" into Trade chat, and the companion
-- would then treat the buffer as ending there, silently dropping every entry
-- after it.
--
-- Replacing rather than escaping is deliberate. A newline and a tab carry no
-- meaning in a chat message, and a channel name cannot contain a pipe, so there
-- is nothing on the other side worth reconstructing. Escaping would buy exact
-- fidelity for characters nobody can see, at the price of an escape alphabet, a
-- protocol version negotiation, and an ambiguity against buffers written by
-- older addon versions.
-- Two constraints on the stand-in, both learned the hard way.
--
-- It must contain no underscore: gsub resumes scanning AFTER each match and
-- never revisits the seam it just wrote, so a replacement ending in "_" lets
-- the marker re-form from its own output — "__WCT__WCT_END__" became
-- "_ WCT_" + "_WCT_END__", a literal end marker again.
--
-- And it must not begin with "[WCT]", which is on the companion's list of
-- addon-chatter prefixes to ignore: a mangled message starting with it was
-- silently dropped on arrival instead of being shown mangled.
local _MARKER_STAND_IN = "(WCT)"

local function SanitizeText(value)
    local out = string_gsub(value, "[\n\r\t]", " ")
    out = string_gsub(out, "__WCT_", _MARKER_STAND_IN)
    return out
end

-- Structural fields additionally lose the pipe. Message text keeps its pipes:
-- WoW hyperlinks and colour codes are built from them and the reader splits
-- with a field limit, so trailing pipes in the text are already safe.
local function SanitizeField(value)
    return (string_gsub(SanitizeText(value), "|", "/"))
end

local function IsDuplicate(author, text)
    local now = GetTime()
    local key = author .. "\0" .. text
    -- Check existing entries
    for i = 1, #dedupRing do
        if dedupRing[i].key == key and (now - dedupRing[i].time) < DEDUP_TTL then
            return true
        end
    end
    -- Add new entry (ring buffer)
    dedupIdx = (dedupIdx % DEDUP_SIZE) + 1
    dedupRing[dedupIdx] = { key = key, time = now }
    return false
end

-- ── Pre-allocate SavedVariable keys ──────────────────────────
-- The companion app caches the hash Node pointer for "wctbuf".
-- If the table resizes (new keys added), the Node array relocates
-- and the companion loses the pointer. So all keys must exist from start.
function addonTable.PreallocateCompanionKeys()
    local db = BabelChatDB
    if db.wctbuf == nil then db.wctbuf = "" end
    if db.wctSeq == nil then db.wctSeq = 0 end
    if db.wctFlush == nil then db.wctFlush = 0 end
    -- A number that never changes, so the companion can find it however long
    -- the search takes, and know where this table's storage lives. Everything
    -- else here moves or ticks: the buffer string is reallocated on every
    -- rebuild, and a search for a value that changes while you search finds
    -- nothing. This one is the fixed point the rest is measured from.
    db.wctAnchor = 8675309123457
    if db._r1 == nil then db._r1 = 0 end
    if db._r2 == nil then db._r2 = 0 end
    if db._r3 == nil then db._r3 = 0 end
    -- Restore seq counter so it survives /reload (reader tracks by seq)
    wctSeq = db.wctSeq or 0
    -- Carried across a reload for the same reason as the sequence: the reader
    -- compares pulses between copies, and a pulse that restarted at zero would
    -- make the live buffer look older than the corpse of the previous session.
    wctFlush = db.wctFlush or 0
end

-- ── Buffer rebuild ───────────────────────────────────────────
-- Concatenate ring buffer into a single string with markers.
-- Seq number embedded in header for fast staleness check:
--   __WCT_BUF_0042__\nline1\nline2\n__WCT_END__
-- Non-string values are rejected at insert time (see IsUsable), so every
-- entry here is a plain string and the buffer can be joined in one pass.

-- The 3.3.5 client has no GetNormalizedRealmName. The normalised form is the
-- realm name with its spaces and hyphens removed, which is what the retail
-- function returned and what the companion was written against.
local function NormalizedRealmName()
    local realm = GetRealmName and GetRealmName() or ""
    return (string_gsub(realm, "[%s%-]", ""))
end

local function RebuildBuffer()
    local seqHeader = string.format("__WCT_BUF_%04d__", wctSeq % 10000)
    -- Include player name so companion can identify own messages
    local playerName = UnitName("player")
    local realmName = NormalizedRealmName()
    local fullName = playerName and (playerName .. "-" .. realmName) or ""
    -- One table.concat instead of rebuilding a growing string 50 times. The old
    -- loop re-concatenated the whole buffer per entry and probed the result each
    -- time — quadratic work and ~190 KB of garbage per flush, four times a
    -- second, forever.
    -- Computed here, committed after the concat succeeds. Advancing the
    -- counter first and then failing would leave the number in memory ahead of
    -- the number on disk, so a /reload would restore the smaller one and the
    -- pulse would step BACKWARDS — which the reader takes as a sign that the
    -- buffer it is holding has died.
    local pulse = wctFlush + 1
    -- First record, before anything that can vary in length, so a truncated
    -- read still carries it.
    local parts = {
        seqHeader,
        "0|META|FLUSH|" .. pulse,
        -- Retail hides chat from addons inside a live mythic keystone and the
        -- companion reports that from this record. 3.3.5 never does, so it is
        -- always 0 — kept so the layout the companion parses does not move.
        "0|META|LOCKED|0",
        "0|META|PLAYER|" .. fullName,
    }
    for idx = 1, #wctBuf do
        parts[#parts + 1] = wctBuf[idx]
    end
    parts[#parts + 1] = "__WCT_END__"
    BabelChatDB.wctbuf = table.concat(parts, "\n")
    wctFlush = pulse
    BabelChatDB.wctSeq = wctSeq
    BabelChatDB.wctFlush = wctFlush
    lastRebuild = GetTime()
    bufDirty = false
end

-- ── Public API ───────────────────────────────────────────────

-- Add a chat entry to the ring buffer.
-- kind: "RAW" (untouched) or "DICT" (the addon glossed this line in chat)
-- event: short event name (e.g. "SAY", "GUILD", "WHISPER")
-- author: sender name (e.g. "Thrall-Sargeras")
--
-- Both kinds carry the same fields. The gloss text itself is deliberately NOT
-- transmitted: the companion discards it on arrival (pipeline._on_new_line
-- logs "Dict message ignored, using DeepL") because a full sentence
-- translation is strictly better than a list of term pairs. Sending it cost a
-- duplicate copy of every glossed message in a 50-entry ring buffer, and — via
-- the newline DictEngine embeds in its display string — was splitting the
-- record in half, so the field never survived the trip anyway. `kind` is kept
-- because it tells the companion the line was already glossed in chat.
function addonTable.BufferAddEntry(text, kind, event, author)
    local db = BabelChatDB
    if not db or not db.companion or not db.companion.enabled then return end

    -- Check every caller-supplied value BEFORE it is tested, compared or stored.
    -- `kind` is not checked: it is one of our own string literals, never a chat
    -- event argument.
    if not IsUsable(text) then
        return
    end

    -- A missing author and a non-string author get the same treatment: neither
    -- can be written to the buffer.
    local safeAuthor = "Unknown"
    if IsUsable(author) then safeAuthor = SanitizeField(author) end
    local safeEvent = "SAY"
    if IsUsable(event) then safeEvent = SanitizeField(event) end
    local safeText = SanitizeText(text)

    -- Dedup: skip if same (author, text) seen within TTL
    if IsDuplicate(safeAuthor, safeText) then return end

    wctSeq = wctSeq + 1
    -- Record: SEQ|KIND|EVENT|author|text
    local safeKind = "RAW"
    if kind == "DICT" then safeKind = "DICT" end
    local entry = wctSeq .. "|" .. safeKind .. "|" .. safeEvent .. "|" .. safeAuthor .. "|" .. safeText
    tinsert(wctBuf, entry)
    while #wctBuf > MSG_LIMIT do
        tremove(wctBuf, 1)
    end
    bufDirty = true
end

-- Start the periodic buffer flush ticker.
function addonTable.StartBufferFlush()
    if flushTicker then return end

    -- Initialize buffer with markers so companion can find it immediately
    if not BabelChatDB.wctbuf or BabelChatDB.wctbuf == "" then
        BabelChatDB.wctbuf = "__WCT_BUF_0000__\n__WCT_END__"
    end

    flushTicker = C_Timer.NewTicker(FLUSH_INTERVAL, function()
        -- Idle chat still rebuilds, just rarely. One concat of a couple of
        -- kilobytes every two seconds is nothing next to a companion that goes
        -- deaf for minutes at a time.
        if bufDirty or (GetTime() - lastRebuild) >= HEARTBEAT_INTERVAL then
            -- table.concat fails on the whole table, not on one entry, and this
            -- ticker runs four times a second forever. Without the guard a
            -- single unexpected entry would mean a Lua error every 0.25s until
            -- the player reloads — and bufDirty would never clear, so no
            -- message would reach the companion again either.
            local ok = pcall(RebuildBuffer)
            if not ok then
                -- Drop the batch rather than retry it: whatever is in there
                -- cannot be serialised, and keeping it poisons every flush.
                wctBuf = {}
                bufDirty = false
                -- And back off. `lastRebuild` is set at the END of a rebuild,
                -- so a failed one leaves it stale and the heartbeat condition
                -- true — which turns a repeating failure into four attempts a
                -- second instead of one every two, for as long as the cause
                -- lasts. That is the exact spin this guard was written to stop.
                lastRebuild = GetTime()
            end
        end
    end)
end

function addonTable.StopBufferFlush()
    if flushTicker then
        flushTicker:Cancel()
        flushTicker = nil
    end
end

-- Chat log flush (toggle LoggingChat off/on to force WoW file buffer write)
function addonTable.StartLogFlush(interval)
    if logFlushTicker then return end
    interval = interval or 5
    logFlushTicker = C_Timer.NewTicker(interval, function()
        if LoggingChat() then
            LoggingChat(false)
            LoggingChat(true)
        end
    end)
end

function addonTable.StopLogFlush()
    if logFlushTicker then
        logFlushTicker:Cancel()
        logFlushTicker = nil
    end
end

-- Status info for slash commands
function addonTable.GetBufferStatus()
    return #wctBuf, wctSeq, MSG_LIMIT, (flushTicker ~= nil)
end
