-- Outbox.lua — say what the companion app translated
--
-- The app has no way to call into the game, so the addon keeps a small table
-- of numbers (the "mailbox") that the app finds in the game's memory and
-- writes into. The addon checks it ten times a second, and when the app has
-- left a new message, sends it with SendChatMessage and confirms it.
--
-- The mailbox is a plain array of numbers, never saved and never resized, so
-- the app writing into it moves nothing:
--
--   [1] [2]   two marker numbers the app searches for (made at run time, so
--             the pair appears nowhere else — not even in this file's code)
--   [3]       heartbeat: counts up while the addon runs, so the app can tell
--             the live mailbox from a stale one left by a /reload
--   [4]       the last message number the addon handled, negative if it
--             could not send it (written by the addon)
--   [5]       message number (written by the app, last)
--   [6]       message length in bytes (written by the app)
--   [7..]     the message, six bytes to a number, little-endian (by the app)
--
-- A message is "CHANNEL\tTARGET\tTEXT" in UTF-8. CHANNEL is one of the
-- SendChatMessage chat types, "REPLY" (whisper whoever whispered last),
-- "CHANNEL:<number>" or "CHANNEL:<name>" (a numbered channel such as World).

local ADDON_NAME, addonTable = ...
local C_Timer = addonTable.C_Timer

local SLOTS = 100 -- 600 bytes: a long reply after translation, plus a name and tabs
local SIZE = 6 + SLOTS
local BYTES_PER_SLOT = 6

local mailbox = {}
for i = 1, SIZE do
    mailbox[i] = 0
end
-- Multiplied at run time, so neither marker is a constant anywhere in the
-- addon's code. A plain `7340033 * 1048573` would not do: Lua 5.1 folds
-- constant arithmetic when it compiles, which would put the marker in the
-- function's constant table — and the pair next to each other.
local function Product(a, b)
    return a * b
end
mailbox[1] = Product(7340033, 1048573)
mailbox[2] = Product(Product(5003, 1000003), 97)
addonTable.outboxMailbox = mailbox

local lastSeen = 0
local MAX_CHAT_BYTES = 255

local function Decode()
    local length = mailbox[6]
    if type(length) ~= "number" or length < 1 or length > SLOTS * BYTES_PER_SLOT then
        return nil
    end
    local bytes = {}
    for i = 1, math.ceil(length / BYTES_PER_SLOT) do
        local value = mailbox[6 + i] or 0
        for _ = 1, BYTES_PER_SLOT do
            local byte = value % 256
            bytes[#bytes + 1] = byte
            value = (value - byte) / 256
        end
    end
    local chars = {}
    for i = 1, length do
        chars[i] = string.char(bytes[i])
    end
    return table.concat(chars)
end

-- Split into chat-sized pieces at spaces, never inside a UTF-8 character.
local function Pieces(text)
    local pieces = {}
    while #text > MAX_CHAT_BYTES do
        local cut = MAX_CHAT_BYTES
        local space = text:sub(1, MAX_CHAT_BYTES):match(".*() ")
        if space and space > 1 then
            cut = space - 1
        else
            -- No space: back off any UTF-8 continuation bytes.
            while cut > 1 and text:byte(cut + 1) and text:byte(cut + 1) >= 128 and text:byte(cut + 1) < 192 do
                cut = cut - 1
            end
        end
        pieces[#pieces + 1] = text:sub(1, cut)
        text = text:sub(cut + 1):gsub("^ +", "")
    end
    if #text > 0 then
        pieces[#pieces + 1] = text
    end
    return pieces
end

local function Fail(message)
    DEFAULT_CHAT_FRAME:AddMessage("|cffff6060BabelChat:|r " .. message)
    return false
end

local function Send(channel, target, text)
    local chatType, where = channel, nil
    if channel == "WHISPER" then
        if target == "" then
            return Fail("nincs megadva, kinek suttogjak.")
        end
        where = target
    elseif channel == "REPLY" then
        local last = ChatEdit_GetLastTellTarget and ChatEdit_GetLastTellTarget()
        if not last or last == "" then
            return Fail("még senki nem suttogott neked, nincs kinek válaszolni.")
        end
        chatType, where = "WHISPER", last
    elseif channel:sub(1, 8) == "CHANNEL:" then
        local id = channel:sub(9)
        local number = tonumber(id)
        if not number then
            number = GetChannelName(id)
        end
        if not number or number == 0 then
            return Fail("nem vagy bent a(z) " .. id .. " csatornán.")
        end
        chatType, where = "CHANNEL", number
    end
    for _, piece in ipairs(Pieces(text)) do
        SendChatMessage(piece, chatType, nil, where)
    end
    return true
end

local function Check()
    local seq = mailbox[5]
    if type(seq) ~= "number" or seq == lastSeen then
        return
    end
    lastSeen = seq
    local sent = false
    local message = Decode()
    if message then
        local channel, target, text = message:match("^([^\t]*)\t([^\t]*)\t(.*)$")
        if channel and text ~= "" then
            sent = Send(channel, target, text)
        end
    end
    -- The message number back as confirmation; negative when it did not go out.
    mailbox[4] = sent and seq or -seq
end

local beat = 0
C_Timer.NewTicker(0.1, function()
    beat = beat + 1
    mailbox[3] = beat
    Check()
end)

-- A /reload or logout leaves this table behind as garbage; wiping the
-- markers keeps the app from writing into it. Core.lua's event handler calls
-- this on PLAYER_LOGOUT (the addon keeps to one event frame).
function addonTable.CloseOutbox()
    mailbox[1], mailbox[2] = 0, 0
end
