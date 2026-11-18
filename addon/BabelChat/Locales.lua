-- Locales.lua — UI strings for BabelChat: English (enUS) and Hungarian (huHU)
--
-- The UI language is NOT GetLocale(). This build targets an English 3.3.5
-- client played by someone who reads Hungarian, so the language comes from the
-- addon's own setting — BabelChatDB.dict.targetLocale, the same one the gloss
-- uses — and defaults to Hungarian.
--
-- That setting lives in the saved variables, which do not exist yet while this
-- file runs. So `L` resolves each key when it is read rather than at load:
-- huHU first (or whatever the setting says), then enUS for anything a
-- translation is missing. Code that captures a string at load time therefore
-- gets the default language; everything built at PLAYER_LOGIN or later — the
-- options panel, the slash commands — gets the player's choice.

local addonName, addonTable = ...

local DEFAULT_LOCALE = "huHU"
local strings = { enUS = {}, huHU = {} }
addonTable.LocaleStrings = strings

-- ==========================================
-- ENGLISH (enUS) — every key lives here
-- ==========================================
local E = strings.enUS
E["UI_TITLE"] = "BabelChat Configuration"
E["UI_ENABLE_TEXT"] = " Enable Dictionary Translation"
E["UI_COLOR_BTN"] = "Choose Color"
E["UI_LANG_LABEL"] = "Translate to:"
E["UI_TEST_BTN"] = "Test Translation"
E["TT_TEST_BTN"] = "Run a translation test in the chat window."
E["CHAT_LOADED"] = "Addon loaded."
E["SLASH_ON"] = "Translations: |cff00ff00ENABLED|r"
E["SLASH_OFF"] = "Translations: |cffff0000DISABLED|r"
E["SLASH_TEST_ORIGINAL"] = "Original: "
E["SLASH_TEST_RESULT"] = "Result: "
E["SLASH_TEST_ERROR"] = "Translations disabled."
E["TEST_NO_MATCH"] = "No dictionary matches found."
E["TEST_SUPPRESSED"] = "The companion app is running, so the gloss stays out of chat and the overlay answers instead. Tick \"show the gloss even when the app is running\" in /babel config if you want both."
E["HELP_HEADER"] = "--- BabelChat Help ---"
E["HELP_CONFIG_MSG"] = "Opens options panel."
E["HELP_ONOFF_MSG"] = "Enable or disable translations."
E["HELP_TEST_MSG"] = "Perform a translation test."
E["HELP_COMPANION_MSG"] = "Show companion app buffer status."
E["HELP_LOG_MSG"] = "Toggle chat logging to a file"

-- Categories
E["CAT_HEADER"] = "Categories to translate:"
E["CAT_MAZZ"] = "Dungeons & Raids"
E["CAT_SOCIAL"] = "Social & Slang"
E["CAT_CLASSES"] = "Classes"
E["CAT_ROLES"] = "Roles"
E["CAT_STATS"] = "Character stats"
E["CAT_PROF"] = "Professions"
E["CAT_COMBAT"] = "Combat"
E["CAT_TRADE"] = "Trade"
E["CAT_GROUPS"] = "Groups"
E["CAT_GUILD"] = "Guild"
E["CAT_STATUS"] = "Status / States"
E["CAT_SLANG"] = "Slang & Shortcuts"
E["CAT_ENDGAME"] = "Endgame"
E["GEN_HEADER"] = "General"
E["UI_ALWAYS_GLOSS"] = " Show the gloss even when the app is running"
E["TT_ALWAYS_GLOSS"] = "Off by default: the companion overlay already shows a full translation of the same message, so the in-chat gloss stays quiet while the app is set up."

-- Channels
E["CH_SAY"] = "Say"
E["CH_PARTY"] = "Party"
E["CH_RAID"] = "Raid"
E["CH_BATTLEGROUND"] = "Battleground"
E["CH_GUILD"] = "Guild"
E["CH_WHISPER"] = "Whisper"
E["CH_CHANNEL"] = "Global Channels"
E["CH_EMOTE"] = "Emote"
E["CH_HEADER"] = "Channels to translate:"

-- Tooltips
E["TT_ENABLE"] = "Enable or disable all translations globally."
E["TT_COLOR"] = "Choose the color for the translated text in chat."
E["TT_LANG"] = "The language the gloss is written in. It is also the language of this panel and of the /babel commands (after a /reload)."
E["TT_CAT_MAZZ"] = "Translate dungeon and raid terminology."
E["TT_CAT_SOCIAL"] = "Translate common internet slang and social expressions."
E["TT_CAT_CLASSES"] = "Translate class names and specializations."
E["TT_CAT_ROLES"] = "Translate dungeon roles (Tank, Healer, DPS)."
E["TT_CAT_STATS"] = "Translate item and character statistics."
E["TT_CAT_PROF"] = "Translate profession names."
E["TT_CAT_COMBAT"] = "Translate combat-related terms."
E["TT_CAT_TRADE"] = "Translate trading and economy terms."
E["TT_CAT_GROUPS"] = "Translate group-finding terminology."
E["TT_CAT_GUILD"] = "Translate guild-related terms."
E["TT_CAT_STATUS"] = "Translate statuses and states (AFK, OOM, etc)."
E["TT_CAT_SLANG"] = "Gaming slang, chat shortcuts and raid callouts."
E["TT_CAT_ENDGAME"] = "Endgame and guild recruitment shorthand."
E["GLOSS_MORE"] = "and %d more"

E["TT_CH_SAY"] = "Translate messages from /say and /yell."
E["TT_CH_PARTY"] = "Translate messages from Party chat."
E["TT_CH_RAID"] = "Translate messages from Raid and Raid Warning."
E["TT_CH_BATTLEGROUND"] = "Translate messages from Battleground chat."
E["TT_CH_GUILD"] = "Translate messages from Guild and Officer chat."
E["TT_CH_WHISPER"] = "Translate incoming and outgoing Whispers."
E["TT_CH_CHANNEL"] = "Translate messages from global channels (Trade, General, etc)."
E["TT_CH_EMOTE"] = "Translate emotes."

-- About
E["ABOUT_HEADER"] = "About"
E["ABOUT_AUTHORS"] = "Andrey Yumashev — addon and companion app. AhegaoZKun — Linux support."
E["ABOUT_DICT_CREDIT"] = "Glossary based on WoW Translator by Pirson (MIT)."
E["ABOUT_LICENSE"] = "Released under the MIT License."
E["TT_ABOUT_LINK"] = "Click the box and press Ctrl+C to copy. An addon cannot open a browser for you."

-- Companion
E["COMP_HEADER"] = "Companion App"
E["COMP_ENABLE"] = " Enable Companion Buffer"
E["TT_COMP_ENABLE"] = "Write chat messages to memory buffer for the companion overlay app."

-- Minimap
E["QT_MINIMAP_TT"] = "|cffd597ffBabelChat|r\n|cffffffffClick:|r Open Settings"
E["KOSZI_LABEL"] = "Köszi"
E["KOSZI_TT"] = "|cffd597ffKöszi|r\n|cffffffffClick:|r say a random haiku\n|cffffffffDrag:|r move\n/koszi hide: hide the button"
E["KOSZI_HIDDEN"] = "Köszi button hidden. /koszi show brings it back."

-- First run welcome
E["WELCOME_1"] = "Welcome to |cffd597ffBabelChat|r!"
E["WELCOME_2"] = "BabelChat explains gaming terms right in your chat, in Hungarian or English. No setup, no account, no key — it is already working."
E["WELCOME_3"] = "Type |cffffff00/babel config|r to open settings and pick your language."
E["WELCOME_4"] = "Want full sentence translation too? Get the |cff40ff40free|r companion app:"
E["WELCOME_5"] = "|cffffff00https://github.com/Yumash/BabelChat|r"
E["WELCOME_6"] = "The app is free and needs no account: it translates on your own computer with OPUS-MT, and nothing leaves your machine. Enable in: Interface > AddOns > BabelChat > Companion App."
E["WELCOME_OK"] = "OK"
E["WELCOME_SETTINGS"] = "Settings"

-- Slash command replies
E["CMD_NO_PANEL"] = "Settings panel not available. Use Interface > AddOns."
E["CMD_BUFFER"] = "Companion buffer:"
E["CMD_MESSAGES"] = "Messages"
E["CMD_SEQ"] = "Seq"
E["CMD_FLUSH"] = "Flush"
E["CMD_ON"] = "ON"
E["CMD_OFF"] = "OFF"
E["CMD_LOG_ON"] = "Chat logging enabled."
E["CMD_LOG_OFF"] = "Chat logging disabled."

-- ==========================================
-- HUNGARIAN (huHU)
-- ==========================================
local H = strings.huHU
H["UI_TITLE"] = "BabelChat beállítások"
H["UI_ENABLE_TEXT"] = " Szótári fordítás bekapcsolása"
H["UI_COLOR_BTN"] = "Szín választása"
H["UI_LANG_LABEL"] = "Fordítás nyelve:"
H["UI_TEST_BTN"] = "Fordítás tesztelése"
H["TT_TEST_BTN"] = "Fordítási teszt futtatása a csevegőablakban."
H["CHAT_LOADED"] = "Kiegészítő betöltve."
H["SLASH_ON"] = "Fordítás: |cff00ff00BEKAPCSOLVA|r"
H["SLASH_OFF"] = "Fordítás: |cffff0000KIKAPCSOLVA|r"
H["SLASH_TEST_ORIGINAL"] = "Eredeti: "
H["SLASH_TEST_RESULT"] = "Eredmény: "
H["SLASH_TEST_ERROR"] = "A fordítás ki van kapcsolva."
H["TEST_NO_MATCH"] = "Nincs találat a szótárban."
H["TEST_SUPPRESSED"] = "A kísérőalkalmazás fut, ezért a magyarázat nem jelenik meg a csevegésben — helyette az átfedés válaszol. Ha mindkettőt szeretnéd, kapcsold be a „Magyarázat akkor is, ha fut az alkalmazás” opciót a /babel config alatt."
H["HELP_HEADER"] = "--- BabelChat súgó ---"
H["HELP_CONFIG_MSG"] = "Megnyitja a beállításokat."
H["HELP_ONOFF_MSG"] = "Fordítás be- vagy kikapcsolása."
H["HELP_TEST_MSG"] = "Fordítási teszt futtatása."
H["HELP_COMPANION_MSG"] = "A kísérőalkalmazás pufferének állapota."
H["HELP_LOG_MSG"] = "Csevegésnapló fájlba írásának be- vagy kikapcsolása"

H["CAT_HEADER"] = "Fordítandó kategóriák:"
H["CAT_MAZZ"] = "Kazamaták és raidek"
H["CAT_SOCIAL"] = "Közösség és szleng"
H["CAT_CLASSES"] = "Kasztok"
H["CAT_ROLES"] = "Szerepek"
H["CAT_STATS"] = "Karakterértékek"
H["CAT_PROF"] = "Szakmák"
H["CAT_COMBAT"] = "Harc"
H["CAT_TRADE"] = "Kereskedelem"
H["CAT_GROUPS"] = "Csoportok"
H["CAT_GUILD"] = "Céh"
H["CAT_STATUS"] = "Állapotok"
H["CAT_SLANG"] = "Szleng és rövidítések"
H["CAT_ENDGAME"] = "Végjáték"
H["GEN_HEADER"] = "Általános"
H["UI_ALWAYS_GLOSS"] = " Magyarázat akkor is, ha fut az alkalmazás"
H["TT_ALWAYS_GLOSS"] = "Alapból kikapcsolva: a kísérőalkalmazás átfedése már teljes fordítást mutat ugyanarról az üzenetről, ezért a csevegésbeli magyarázat hallgat, amíg az alkalmazás be van állítva."

H["CH_SAY"] = "Mondás"
H["CH_PARTY"] = "Csoport"
H["CH_RAID"] = "Raid"
H["CH_BATTLEGROUND"] = "Csatatér"
H["CH_GUILD"] = "Céh"
H["CH_WHISPER"] = "Suttogás"
H["CH_CHANNEL"] = "Nyilvános csatornák"
H["CH_EMOTE"] = "Emote"
H["CH_HEADER"] = "Fordítandó csatornák:"

H["TT_ENABLE"] = "Az összes fordítás be- vagy kikapcsolása."
H["TT_COLOR"] = "A csevegésben megjelenő fordítás színe."
H["TT_LANG"] = "A magyarázat nyelve. Ez a nyelve ennek a panelnek és a /babel parancsoknak is (egy /reload után)."
H["TT_CAT_MAZZ"] = "Kazamaták és raidek kifejezéseinek fordítása."
H["TT_CAT_SOCIAL"] = "Internetes szleng és köszönések, társasági kifejezések fordítása."
H["TT_CAT_CLASSES"] = "Kasztnevek és specializációk fordítása."
H["TT_CAT_ROLES"] = "Csoportszerepek fordítása (tank, gyógyító, DPS)."
H["TT_CAT_STATS"] = "Tárgy- és karakterértékek fordítása."
H["TT_CAT_PROF"] = "Szakmanevek fordítása."
H["TT_CAT_COMBAT"] = "Harccal kapcsolatos kifejezések fordítása."
H["TT_CAT_TRADE"] = "Kereskedelmi és gazdasági kifejezések fordítása."
H["TT_CAT_GROUPS"] = "Csoportkeresési kifejezések fordítása."
H["TT_CAT_GUILD"] = "Céhes kifejezések fordítása."
H["TT_CAT_STATUS"] = "Állapotok és helyzetek fordítása (AFK, OOM stb.)."
H["TT_CAT_SLANG"] = "Játékos szleng, csevegőrövidítések és raidhívások fordítása."
H["TT_CAT_ENDGAME"] = "Végjátékos és céhtoborzási rövidítések fordítása."
H["GLOSS_MORE"] = "és még %d"

H["TT_CH_SAY"] = "A /say és /yell üzenetek fordítása."
H["TT_CH_PARTY"] = "A csoportcsevegés fordítása."
H["TT_CH_RAID"] = "A raid- és raidfigyelmeztető üzenetek fordítása."
H["TT_CH_BATTLEGROUND"] = "A csatatéri csevegés fordítása."
H["TT_CH_GUILD"] = "A céhes és tiszti csevegés fordítása."
H["TT_CH_WHISPER"] = "A bejövő és kimenő suttogások fordítása."
H["TT_CH_CHANNEL"] = "A nyilvános csatornák (Trade, General stb.) fordítása."
H["TT_CH_EMOTE"] = "Az emote-ok fordítása."

H["ABOUT_HEADER"] = "Névjegy"
H["ABOUT_AUTHORS"] = "Andrey Yumashev — kiegészítő és kísérőalkalmazás. AhegaoZKun — Linux-támogatás."
H["ABOUT_DICT_CREDIT"] = "A szótár Pirson WoW Translator kiegészítőjén alapul (MIT)."
H["ABOUT_LICENSE"] = "MIT licenc alatt kiadva."
H["TT_ABOUT_LINK"] = "Kattints a mezőbe, és nyomd meg a Ctrl+C-t a másoláshoz. Egy kiegészítő nem tud böngészőt nyitni."

H["COMP_HEADER"] = "Kísérőalkalmazás"
H["COMP_ENABLE"] = " Kísérőpuffer bekapcsolása"
H["TT_COMP_ENABLE"] = "A csevegés üzeneteinek írása a memóriapufferbe a kísérőalkalmazás átfedéséhez."

H["QT_MINIMAP_TT"] = "|cffd597ffBabelChat|r\n|cffffffffKattintás:|r Beállítások megnyitása"
H["KOSZI_LABEL"] = "Köszi"
H["KOSZI_TT"] = "|cffd597ffKöszi|r\n|cffffffffKattintás:|r véletlen haiku /say-ben\n|cffffffffHúzás:|r mozgatás\n/koszi hide: gomb elrejtése"
H["KOSZI_HIDDEN"] = "A Köszi gomb elrejtve. A /koszi show visszahozza."

H["WELCOME_1"] = "Üdv a |cffd597ffBabelChat|r kiegészítőben!"
H["WELCOME_2"] = "A BabelChat a csevegésben, helyben elmagyarázza a játékos kifejezéseket, magyarul vagy angolul. Nincs beállítás, nincs fiók, nincs kulcs — már működik."
H["WELCOME_3"] = "Írd be: |cffffff00/babel config|r — itt nyílnak a beállítások, és itt választhatsz nyelvet."
H["WELCOME_4"] = "Teljes mondatokat is fordítanál? Töltsd le az |cff40ff40ingyenes|r kísérőalkalmazást:"
H["WELCOME_5"] = "|cffffff00https://github.com/Yumash/BabelChat|r"
H["WELCOME_6"] = "Az alkalmazás ingyenes, és nem kell hozzá fiók: a saját gépeden fordít az OPUS-MT modellel, a szöveg nem hagyja el a gépet. Bekapcsolás: Interface > AddOns > BabelChat > Kísérőalkalmazás."
H["WELCOME_OK"] = "OK"
H["WELCOME_SETTINGS"] = "Beállítások"

H["CMD_NO_PANEL"] = "A beállítópanel nem érhető el. Használd az Interface > AddOns menüt."
H["CMD_BUFFER"] = "Kísérőpuffer:"
H["CMD_MESSAGES"] = "Üzenetek"
H["CMD_SEQ"] = "Sorszám"
H["CMD_FLUSH"] = "Ürítés"
H["CMD_ON"] = "BE"
H["CMD_OFF"] = "KI"
H["CMD_LOG_ON"] = "Csevegésnapló bekapcsolva."
H["CMD_LOG_OFF"] = "Csevegésnapló kikapcsolva."

-- ==========================================
-- LOOKUP
-- ==========================================
local function ActiveLocale()
    local db = BabelChatDB
    local chosen = type(db) == "table" and type(db.dict) == "table" and db.dict.targetLocale
    if chosen and strings[chosen] then return chosen end
    return DEFAULT_LOCALE
end
addonTable.ActiveUILocale = ActiveLocale

local L = setmetatable({}, {
    __index = function(_, key)
        local value = strings[ActiveLocale()][key]
        if value == nil then value = strings.enUS[key] end
        return value
    end,
})

addonTable.L = L
