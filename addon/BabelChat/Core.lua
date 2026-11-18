-- Core.lua — BabelChat v2.2.2
-- Thin init: wires DictEngine + CompanionBuffer + ChatFilter + slash commands.
-- Dictionary translation inline in chat + memory buffer for companion overlay.

local ADDON_NAME, addonTable = ...
local L = addonTable.L
-- The addon's own C_Timer backport (Timer.lua); the 3.3.5 client has none.
local C_Timer = addonTable.C_Timer

local PREFIX = "|cffffff00[|r|cffd597ffBabelChat|r|cffffff00]|r "

local function Print(msg)
    print(PREFIX .. msg)
end

-- ==========================================
-- DEFAULT DATABASE
-- ==========================================
local DEFAULTS = {
    -- Dictionary settings (from Pirson's WoWTranslator)
    dict = {
        enabled = true,
        -- The gloss language, and the language of the addon's own UI. Not
        -- taken from GetLocale(): the client is English, the reader is not.
        -- See NormaliseTargetLocale.
        targetLocale = "huHU",
        -- When to print the in-chat gloss: "auto" keeps out of the way
        -- when the companion app is set up, because the overlay already
        -- shows a full translation of the same line.
        mode = "auto",
        -- Grey, not the old bright green: this is now a short aside at the
        -- end of the line rather than a translation on its own row, and it
        -- should sit behind the message rather than compete with it. An
        -- existing choice is left alone — it is the player's setting.
        chatColor = "808080",
        settings = {
            showDungeons = true,
            showSocial = true,
            showClasses = true,
            showCombat = true,
            showTrade = true,
            showStats = true,
            showGroups = true,
            showGuild = true,
            showProfessions = true,
            showRoles = true,
            showStatus = true,
            showSlang = true,
            showEndgame = true,
            skipSameLanguage = true,
            channels = {}
        }
    },
    -- Companion app settings (disabled by default — addon works standalone)
    companion = {
        -- On: this build exists to feed the companion app. Off, the addon
        -- writes nothing for it to read, the overlay stays empty, and only the
        -- keyword gloss appears in chat.
        enabled = true,
        autoLog = false,
        verbose = false,
        flushInterval = 5,
    },
    -- First run flag
    firstRun = true,
    -- Minimap icon
    minimap = {},
}

-- ==========================================
-- SETTING KEY MIGRATION
-- ==========================================
-- The category toggles were named after the Spanish source this dictionary came
-- from — showMazz (mazmorras), showClases, showComercio — which meant nobody
-- reading their own SavedVariables could tell what they controlled.
--
-- Renaming them without moving the values would silently re-enable every
-- category a player had switched off: the old key stops being read, the new one
-- is absent, and ApplyDefaults fills it with `true`.
addonTable.SETTING_RENAMES = {
    showMazz        = "showDungeons",
    showClases      = "showClasses",
    showCombate     = "showCombat",
    showComercio    = "showTrade",
    showGrupos      = "showGroups",
    showHermandad   = "showGuild",
    showEstado      = "showStatus",
    showProfesiones = "showProfessions",
}

-- Returns how many values it moved, which makes the migration testable and
-- makes "it ran and found nothing" distinguishable from "it did not run".
function addonTable.MigrateSettingKeys(settings)
    if type(settings) ~= "table" then return 0 end
    local moved = 0
    for old, new in pairs(addonTable.SETTING_RENAMES) do
        if settings[old] ~= nil then
            -- A value already under the new name wins: it is what the player
            -- last chose in a version that used it. Running this twice is
            -- therefore a no-op, which matters because it runs on every load.
            if settings[new] == nil then
                settings[new] = settings[old]
                moved = moved + 1
            end
            settings[old] = nil
        end
    end
    return moved
end

-- Deep merge defaults into db (non-destructive)
local function ApplyDefaults(db, defaults)
    for k, v in pairs(defaults) do
        if type(v) == "table" then
            if db[k] == nil then db[k] = {} end
            if type(db[k]) == "table" then
                ApplyDefaults(db[k], v)
            end
        elseif db[k] == nil then
            db[k] = v
        end
    end
end

-- The languages the dictionary carries, and so the only gloss targets.
addonTable.SUPPORTED_LOCALES = { enUS = true, huHU = true }
addonTable.DEFAULT_LOCALE = "huHU"

-- Which language the gloss (and the addon's UI) is written in.
--
-- Deliberately not GetLocale(): this build is for an English 3.3.5 client
-- played by someone who reads Hungarian, so the client's language is exactly
-- the wrong answer. A saved choice of English or Hungarian is kept; anything
-- else — an older config that saved ruRU or esES, or no choice at all — means
-- the default.
local function NormaliseTargetLocale()
    local db = BabelChatDB
    if not addonTable.SUPPORTED_LOCALES[db.dict.targetLocale] then
        db.dict.targetLocale = addonTable.DEFAULT_LOCALE
    end
end

-- A chat argument that is safe to treat as text. A number would pass a length
-- probe (Lua 5.1 coerces) and then raise in gsub, which would take the chat
-- filter down for the rest of the session — so ask about the type.
local function IsUsableString(value)
    return type(value) == "string"
end

-- ==========================================
-- CHAT EVENT FILTER (dual-path)
-- ==========================================
-- Every event here exists on the 3.3.5 client. There is no INSTANCE_CHAT
-- (that arrived in 5.1); battleground chat is CHAT_MSG_BATTLEGROUND[_LEADER].
-- CHAT_MSG_BN_WHISPER exists from 3.3.5 but never fires on a private server,
-- and a filter on an event that never fires costs nothing.
local CHAT_EVENTS = {
    "CHAT_MSG_SAY", "CHAT_MSG_YELL",
    "CHAT_MSG_WHISPER", "CHAT_MSG_WHISPER_INFORM",
    "CHAT_MSG_BN_WHISPER",
    "CHAT_MSG_PARTY", "CHAT_MSG_PARTY_LEADER",
    "CHAT_MSG_RAID", "CHAT_MSG_RAID_LEADER", "CHAT_MSG_RAID_WARNING",
    "CHAT_MSG_BATTLEGROUND", "CHAT_MSG_BATTLEGROUND_LEADER",
    "CHAT_MSG_GUILD", "CHAT_MSG_OFFICER",
    "CHAT_MSG_CHANNEL", "CHAT_MSG_EMOTE",
}
addonTable.CHAT_EVENTS = CHAT_EVENTS

-- The 3.3.5 filter contract (ChatFrame_MessageEventHandler): called as
-- filter(chatFrame, event, arg1 .. arg11). Returning true hides the line;
-- returning false followed by replacement arguments rewrites it; returning
-- nothing leaves it alone.
local function ChatFilter(self, event, text, author, ...)
    local db = BabelChatDB
    if not db then return end

    -- Strip CHAT_MSG_ prefix for compact event name
    local shortEvent = event:gsub("^CHAT_MSG_", "")

    -- For public channels, send the channel's TYPE id alongside its name.
    --
    -- CHAT_MSG_CHANNEL on 3.3.5 is (text, author, lang, channelString,
    -- author2, flags, zoneChannelID, channelIndex, channelBaseName, unused,
    -- lineID). `...` starts at arg3, so channelString is select(2, ...) and
    -- zoneChannelID is select(5, ...).
    --
    -- The name alone was the bug: the companion matched it against English
    -- words, so on a Russian client "Торговля" matched nothing and every public
    -- channel — Trade included — was filed as General. zoneChannelID is the
    -- same number on every locale, and it is 0 for a player-made channel, which
    -- is exactly the distinction that was missing.
    --
    -- Encoded as "CHANNEL:<id>:<name>". An older addon sends "CHANNEL:<name>",
    -- which the companion still understands.
    if event == "CHAT_MSG_CHANNEL" then
        local channelString = select(2, ...)
        local zoneChannelID = select(5, ...)
        -- Checked before the gsub below: anything but a string would raise
        -- there, and that would take the chat filter down for the session.
        if IsUsableString(channelString) then
            -- Strip a leading "N. " channel-number prefix if present.
            local name = channelString:gsub("^%d+%.%s*", "")
            if name ~= "" then
                -- Zero means "a player made this channel" and the companion
                -- treats it as such, so it must never stand in for "we could
                -- not read the id". When the id is unreadable, send the older
                -- two-part form and let the companion fall back to the name.
                local channelType
                if IsUsableString(zoneChannelID) or type(zoneChannelID) == "number" then
                    channelType = tonumber(zoneChannelID)
                end
                if channelType then
                    shortEvent = "CHANNEL:" .. channelType .. ":" .. name
                else
                    shortEvent = "CHANNEL:" .. name
                end
            end
        end
    end

    -- Dictionary translation (if enabled and channel not filtered)
    local translated, wasChanged
    local dictChannelEnabled = not db.dict.settings.channels or db.dict.settings.channels[event] ~= false
    if db.dict.enabled and dictChannelEnabled then
        -- pcall: an error escaping a chat filter breaks it for every later line
        local ok, t, c = pcall(addonTable.TranslateChat, text)
        if ok then
            translated, wasChanged = t, c
        end
    end

    -- Buffer for companion app — ALL channels, regardless of dict filter.
    -- Wrapped in pcall for the same reason TranslateChat is: this runs inside a
    -- chat event filter, and an error escaping here does not just lose one
    -- message — it breaks the filter for every chat line that follows, for the
    -- whole encounter. BufferAddEntry probes its own arguments, so this is the
    -- second layer, not the first.
    if wasChanged then
        pcall(addonTable.BufferAddEntry, text, "DICT", shortEvent, author)
    else
        pcall(addonTable.BufferAddEntry, text, "RAW", shortEvent, author)
    end

    -- Return modified text for inline chat display
    if wasChanged then
        return false, translated, author, ...
    end
end

-- System messages: server announcements, restart warnings and the like. Kept
-- apart from ChatFilter on purpose: they only go to the companion app, and the
-- dictionary never rewrites them in the player's own chat window.
local function SystemFilter(self, event, text)
    if BabelChatDB then
        pcall(addonTable.BufferAddEntry, text, "RAW", "SYSTEM", "")
    end
end
addonTable.SystemFilter = SystemFilter

-- ==========================================
-- INITIALIZATION
-- ==========================================
local initFrame = CreateFrame("Frame")
initFrame:RegisterEvent("PLAYER_LOGIN")
-- Also fires on /reload: the reply mailbox (Outbox.lua) is closed then.
initFrame:RegisterEvent("PLAYER_LOGOUT")

-- Everything that has to happen to BabelChatDB before anything reads it, in
-- the one order that is correct: adopt the old addon's table if that is all
-- the player has, rename the Spanish-derived keys, and only then fill in
-- defaults. The other order sees the new keys missing, defaults them to
-- `true`, and hands every player back the categories they had switched off.
--
-- Exported rather than left inline in the event handler so it can run without
-- a game underneath it: that ordering is the part most worth a test, and it
-- was unreachable while it lived inside OnEvent.
function addonTable.InitialiseSavedVariables()
    -- Migrate from old ChatTranslatorHelper if present
    if ChatTranslatorHelperDB and not BabelChatDB then
        BabelChatDB = ChatTranslatorHelperDB
        Print("|cFF40FF40Migrated settings from ChatTranslatorHelper.|r")
    end

    -- Initialize database
    if not BabelChatDB then
        BabelChatDB = {}
    end
    -- Rename the Spanish-derived setting keys BEFORE defaults are filled in.
    -- The other order would see the new keys missing, default them to `true`,
    -- and hand every player back the categories they had switched off.
    if BabelChatDB.dict and BabelChatDB.dict.settings then
        addonTable.MigrateSettingKeys(BabelChatDB.dict.settings)
    end
    ApplyDefaults(BabelChatDB, DEFAULTS)

    -- Settings for things this build no longer has: the zone and item-set
    -- categories (LibBabble), the GetMessageInfo poll fallback, and the
    -- retail-only instance chat. Only nested keys are cleared — a top-level
    -- key of BabelChatDB must never be removed or added here, because the
    -- companion holds a slot in that table (see PreallocateCompanionKeys).
    local db = BabelChatDB
    db.dict.settings.showZones = nil
    db.dict.settings.showSets = nil
    db.companion.pollFallback = nil
    db.dict.settings.channels.CHAT_MSG_INSTANCE_CHAT = nil
    db.dict.settings.channels.CHAT_MSG_INSTANCE_CHAT_LEADER = nil

    -- Earlier builds shipped the companion switch off, and a saved `false`
    -- outlives a changed default. Turn it on once; after that the player's own
    -- choice stands. The marker is nested, like everything else added here.
    if not db.companion.onByDefault then
        db.companion.enabled = true
        db.companion.onByDefault = true
    end

    -- Initialize default channel states
    for _, e in ipairs(CHAT_EVENTS) do
        if db.dict.settings.channels[e] == nil then
            db.dict.settings.channels[e] = true
        end
    end

    NormaliseTargetLocale()
    return db
end

-- Exported so a test can call it: the token it builds for a public channel
-- is what the companion classifies on, and getting it wrong files a real
-- Trade channel as a private one.
addonTable.ChatFilter = ChatFilter

initFrame:SetScript("OnEvent", function(self, event)
    if event == "PLAYER_LOGOUT" then
        if addonTable.CloseOutbox then
            addonTable.CloseOutbox()
        end
        return
    end
    local db = addonTable.InitialiseSavedVariables()

    -- Pre-allocate companion keys (pointer stability)
    addonTable.PreallocateCompanionKeys()

    -- Build master dictionary
    addonTable.RebuildMasterDict()

    -- Register chat event filter for all channels
    for _, e in ipairs(CHAT_EVENTS) do
        ChatFrame_AddMessageEventFilter(e, ChatFilter)
    end
    ChatFrame_AddMessageEventFilter("CHAT_MSG_SYSTEM", SystemFilter)

    -- Start companion buffer flush
    if db.companion.enabled then
        addonTable.StartBufferFlush()
    end

    -- Start chat log flush if auto-logging enabled
    if db.companion.autoLog then
        if not LoggingChat() then LoggingChat(true) end
        addonTable.StartLogFlush(db.companion.flushInterval)
    end

    -- Create config UI
    addonTable.CreateConfigUI()

    -- Minimap button (MinimapButton.lua), plus an LDB launcher when some other
    -- addon has already loaded LibDataBroker.
    addonTable.CreateMinimapButton()

    -- The "Köszi" button (KosziButton.lua): says a random haiku in /say.
    addonTable.CreateKosziButton()

    -- First run: show welcome popup
    if db.firstRun then
        db.firstRun = false
        C_Timer.After(3, function()
            addonTable.ShowWelcomeFrame()
        end)
    else
        Print(L["CHAT_LOADED"])
    end
end)
