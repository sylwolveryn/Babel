"""The things a player invokes by hand, run for real.

Splitting Core.lua moved the slash commands, the self test and the welcome frame
into Commands.lua and left `local L = addonTable.L` behind. Nothing failed to
parse, nothing failed to load, and the suite stayed green — but `/babel test`
and the Test button in the options panel both raised "attempt to index global
'L'" the moment a player pressed them.

A syntax check cannot see that, and neither can a static scan of an extraction
diff. Calling the entry points can.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("lupa", reason="lupa provides the Lua 5.1 runtime the addon needs")

from tests.lua_harness import AddonHarness  # noqa: E402

ADDON_DIR = Path(__file__).resolve().parent.parent / "addon" / "BabelChat"


def toc_lua_files() -> list[str]:
    """The addon's own files, in the order the TOC loads them."""
    listed = [
        line.strip().replace("\\", "/")
        for line in (ADDON_DIR / "BabelChat.toc").read_text(encoding="utf-8").splitlines()
        if line.strip().endswith(".lua")
    ]
    return [name for name in listed if not name.startswith("Libs/")]


@pytest.fixture
def addon():
    """Every first-party file loaded in TOC order, with the game stubbed."""
    harness = AddonHarness()
    lua = harness.lua
    lua.execute(
        """
        _printed = {}
        DEFAULT_CHAT_FRAME = { AddMessage = function(_, msg) table.insert(_printed, msg) end }
        SlashCmdList = {}
        strtrim = function(s) return (s:gsub("^%s*(.-)%s*$", "%1")) end
        UIParent = nil
        -- The 3.3.5 options API: register a panel, open the window on it.
        _opened = {}
        _added = {}
        InterfaceOptions_AddCategory = function(panel) table.insert(_added, panel) end
        InterfaceOptionsFrame_OpenToCategory = function(panel) table.insert(_opened, panel) end
        GetAddOnMetadata = function() return "3.4.0" end
        -- A stand-in that answers to both shapes a frame is used in: `f:Method()`
        -- and `f.SubFrame:Method()`. Returning a plain function for every miss
        -- models the first and breaks on the second, which is how TitleBg —
        -- a field, not a method — brought this fixture down.
        local anything
        anything = setmetatable({}, {
            __index = function() return anything end,
            __call = function() return anything end,
            __newindex = function() end,
        })
        _all_frames = {}
        CreateFrame = function(_, name)
            local frame = setmetatable({
                name = name,
                GetName = function(self) return self.name end,
                -- Kept so a test can fire the handlers the addon installs.
                SetScript = function(self, handler, fn) rawset(self, "_" .. handler, fn) end,
            }, {
                __index = function() return anything end,
            })
            if name then
                _G[name] = frame
                _G[name .. "Text"] = anything
            end
            table.insert(_all_frames, frame)
            return frame
        end
        setmetatable(_G, { __index = function(_, key)
            if type(key) == "string" and key:match("^UIDropDownMenu_") then
                return function() return {} end
            end
            return nil
        end })
        """
    )
    for name in toc_lua_files():
        harness.load(name)
    harness.addon_table.InitialiseSavedVariables()
    harness.addon_table.RebuildMasterDict()
    return harness


def printed(harness) -> list[str]:
    return [str(v) for v in harness.lua.globals()._printed.values()]


def run_slash(harness, argument: str) -> None:
    harness.lua.globals().SlashCmdList["BABELCHAT"](argument)


# ── the entry points a player can reach ──────────────────────────────────────


def test_the_self_test_reports_a_translation(addon):
    """`/babel test` and the Test button in the options panel both call this.
    It raised on a missing locale table after Core.lua was split."""
    addon.addon_table.RunTest()

    lines = printed(addon)
    assert lines, "the self test printed nothing"
    assert any("LFM" in line for line in lines), f"the sample message is missing: {lines}"


@pytest.mark.parametrize(
    "argument",
    ["", "help", "test", "on", "off", "companion", "buf", "log on", "log off", "config", "nonsense"],
)
def test_every_slash_command_runs_without_raising(addon, argument):
    """Each of these reaches for the locale table, the saved variables or both.
    A missing upvalue shows up here and nowhere else."""
    run_slash(addon, argument)

    assert printed(addon), f"/babel {argument} printed nothing"


def test_the_config_panel_test_button_is_wired_to_the_self_test(addon):
    """The button and the slash command must reach the same code — the panel
    lives in a different file from the function it calls."""
    assert addon.addon_table.RunTest is not None
    addon.addon_table.CreateConfigUI()

    addon.addon_table.RunTest()

    assert any("LFM" in line for line in printed(addon))


def test_the_welcome_frame_can_be_shown(addon):
    """It moved in the same split and is reached from the load handler, which
    means a player only finds out it is broken on a fresh install."""
    addon.addon_table.ShowWelcomeFrame()


def test_turning_the_glossary_off_and_on_is_reported_to_the_player(addon):
    run_slash(addon, "off")
    assert addon.lua.globals().BabelChatDB.dict.enabled is False

    run_slash(addon, "on")
    assert addon.lua.globals().BabelChatDB.dict.enabled is True


# ── the self test has to name the real reason ────────────────────────────────


def test_the_self_test_shows_the_gloss_even_while_the_companion_is_running(addon):
    """It reported "no dictionary matches found" when the dictionary matched
    four terms and the addon was simply staying quiet because the companion app
    was running. The one moment a player is looking for an answer is the worst
    moment to name the wrong cause."""
    addon.lua.execute("BabelChatDB.companion.enabled = true")
    addon.lua.execute("_printed = {}")

    addon.addon_table.RunTest()

    lines = printed(addon)
    assert any("LFM = " in line for line in lines), f"the gloss was not shown: {lines}"
    assert not any("TEST_NO_MATCH" in line for line in lines)


def test_the_self_test_says_why_the_gloss_will_not_appear_in_chat(addon):
    """Showing it without explaining would be its own confusion: the player
    would go looking for it in chat and not find it."""
    addon.lua.execute("BabelChatDB.companion.enabled = true")
    addon.lua.execute("_printed = {}")

    addon.addon_table.RunTest()

    explained = addon.lua.globals().BabelChatDB and addon.addon_table.ShouldSuppressGloss()
    assert explained, "the fixture no longer suppresses, so this test proves nothing"
    assert len(printed(addon)) == 3, "expected the original, the result and the reason"


def test_the_self_test_stays_quiet_about_suppression_when_there_is_none(addon):
    # The companion is on by default; with it off nothing is suppressed.
    addon.lua.execute("BabelChatDB.companion.enabled = false")
    addon.lua.execute("_printed = {}")

    addon.addon_table.RunTest()

    assert len(printed(addon)) == 2, "nothing to explain when the companion is off"


def test_a_disabled_glossary_is_reported_as_disabled_not_as_no_match(addon):
    addon.lua.execute("BabelChatDB.dict.enabled = false")
    addon.lua.execute("_printed = {}")

    addon.addon_table.RunTest()

    assert len(printed(addon)) == 2


def test_ordinary_chat_still_stays_quiet_while_the_companion_runs(addon):
    """Forcing the gloss is for the test command only. If it leaked into the
    chat filter, both the addon and the overlay would answer every message."""
    addon.lua.execute("BabelChatDB.companion.enabled = true")

    _text, changed = addon.addon_table.TranslateChat("LFM ICC HC 25m Need Tank and Healer")

    assert bool(changed) is False


# ── the "and N more" counter ─────────────────────────────────────────────────


def test_the_overflow_counter_is_separated_and_reads_as_words(addon):
    """Written as " +4" it ran onto the end of the last translation and read as
    part of it: "HC = Хероик +4" looks like a term, not like a count of what did
    not fit. The first person to see it asked what the +4 was."""
    addon.lua.execute("_printed = {}")

    text, changed = addon.addon_table.TranslateChat("LFM ICC HC 25m Need Tank and Healer", True)

    assert bool(changed) is True
    shown = text.count(" = ")  # three pairs; the counter names the rest
    assert shown == 3, text
    assert re.search(r" · és még \d+\|r$", text), text
    assert not re.search(r"\+\d", text), text


def test_the_counter_is_absent_when_everything_fitted(addon):
    text, changed = addon.addon_table.TranslateChat("ty", True)

    assert bool(changed) is True
    assert "és még" not in text


def test_the_gloss_survives_a_missing_locale_table(addon):
    """DictEngine is loaded on its own in other tests, and reading the locale
    table at load time would take the whole gloss down for a word."""
    saved = addon.addon_table.L
    addon.addon_table.L = None
    try:
        text, changed = addon.addon_table.TranslateChat("LFM ICC HC 25m Need Tank and Healer", True)
        assert bool(changed) is True
        assert "LFM = " in text
        assert re.search(r"\+\d", text), "the fallback counter should still appear"
    finally:
        addon.addon_table.L = saved


# ── the first thing a new player reads ───────────────────────────────────────


def locale_table(locale: str):
    """Locales.lua as a player who chose `locale` in the panel sees it.

    The UI language is the addon's own setting (dict.targetLocale), not the
    client's GetLocale() — this build is for an English client read in
    Hungarian."""
    harness = AddonHarness()
    harness.lua.execute(f'BabelChatDB = {{ dict = {{ targetLocale = "{locale}" }} }}')
    harness.load("Locales.lua")
    return harness.addon_table.L


@pytest.mark.parametrize("locale", ["enUS", "huHU"])
def test_the_welcome_popup_names_the_translator_the_app_actually_uses(locale):
    """The companion app translates locally with OPUS-MT and nothing else.
    Naming a provider the app no longer has sends the player looking for a
    setting that does not exist."""
    text = str(locale_table(locale)["WELCOME_6"])

    assert "OPUS-MT" in text, text
    for removed in ("MyMemory", "GigaChat", "DeepL", "Microsoft"):
        assert removed not in text, f"{locale}: still advertises {removed}"


@pytest.mark.parametrize("locale", ["enUS", "huHU"])
def test_the_welcome_popup_states_no_term_count(locale):
    """It said "380+" against 383, and the number moves whenever a term is
    added. A count in a popup earns nothing and goes stale by itself."""
    table = locale_table(locale)

    def without_markup(text: str) -> str:
        # |cffd597ff is a colour code, not a number the reader sees.
        return re.sub(r"[|]c[0-9a-fA-F]{8}|[|]r", "", text)

    counted = [
        key
        for key in ("WELCOME_1", "WELCOME_2", "WELCOME_3", "WELCOME_4", "WELCOME_6")
        if re.search(r"\d{3}\+?", without_markup(str(table[key])))
    ]

    assert counted == [], f"{locale}: these state a term count: {counted}"


def test_the_ui_defaults_to_hungarian_on_an_english_client():
    """GetLocale() says enUS; the player reads Hungarian. With nothing saved,
    the addon must speak Hungarian."""
    harness = AddonHarness()
    harness.lua.globals().GetLocale = lambda: "enUS"
    harness.lua.execute("BabelChatDB = nil")
    harness.load("Locales.lua")

    assert str(harness.addon_table.L["GEN_HEADER"]) == "Általános"


def test_a_key_missing_from_hungarian_falls_back_to_english():
    harness = AddonHarness()
    harness.load("Locales.lua")
    harness.addon_table.LocaleStrings.huHU["GEN_HEADER"] = None

    assert str(harness.addon_table.L["GEN_HEADER"]) == "General"


def test_both_languages_define_the_same_keys():
    """A key only English has silently shows English in a Hungarian panel."""
    harness = AddonHarness()
    harness.load("Locales.lua")
    tables = harness.addon_table.LocaleStrings
    english = set(tables.enUS.keys())
    hungarian = set(tables.huHU.keys())

    assert english - hungarian == set(), f"no Hungarian for: {sorted(english - hungarian)}"
    assert hungarian - english == set(), f"Hungarian-only keys: {sorted(hungarian - english)}"


def test_only_english_and_hungarian_are_shipped():
    harness = AddonHarness()
    harness.load("Locales.lua")

    assert sorted(harness.addon_table.LocaleStrings.keys()) == ["enUS", "huHU"]


def test_the_config_command_opens_the_panel_twice(addon):
    """3.3.5's InterfaceOptionsFrame_OpenToCategory only opens the window on
    the first call when it was closed; the second selects the panel. Calling
    it once is the classic "it opened the Game tab instead" bug."""
    addon.addon_table.CreateConfigUI()

    run_slash(addon, "config")

    opened = list(addon.lua.globals()._opened.values())
    assert len(opened) == 2
    # `name` is what the options window lists the panel as.
    assert [panel.name for panel in opened] == ["BabelChat", "BabelChat"]
    assert addon.addon_table.configPanel.name == "BabelChat"


def test_the_poll_fallback_command_is_gone(addon):
    """ScrollingMessageFrame:GetMessageInfo does not exist on 3.3.5, so there
    is nothing for /babel poll to fall back to. It now just shows the help."""
    assert addon.addon_table.StartPollTimer is None

    addon.lua.execute("_printed = {}")
    run_slash(addon, "poll on")

    assert any("/babel config" in line for line in printed(addon))


@pytest.mark.parametrize("argument", ["", "companion", "log on", "config"])
def test_the_slash_commands_answer_in_the_players_language(addon, argument):
    """Half the /babel output was English literals while the other half went
    through the table, so a non-English player got a half-translated help
    screen. The fixture saves nothing, so the addon is on its default: huHU."""

    addon.lua.execute("_printed = {}")
    run_slash(addon, argument)

    def readable(line: str) -> str:
        return re.sub(r"[|]c[0-9a-fA-F]{8}|[|]r|/babel[\w |]*", "", line)

    english = [
        line
        for line in printed(addon)
        if re.search(r"\b(?:enabled|disabled|Messages|Companion buffer|fallback|Toggle|available)\b", readable(line))
    ]

    assert english == [], f"/babel {argument} answers in English: {english}"


# ── the login handler, end to end ────────────────────────────────────────────


def test_the_login_handler_wires_everything_up(addon):
    """PLAYER_LOGIN is where every 3.3.5 replacement meets: the options panel,
    the minimap button, the chat filters, the companion keys and the timer
    that shows the welcome popup. Run it once, the way the client does."""
    lua = addon.lua
    lua.execute(
        """
        Minimap = CreateFrame("Frame", "Minimap")
        GameTooltip = CreateFrame("GameTooltip", "GameTooltip")
        _filters = {}
        ChatFrame_AddMessageEventFilter = function(event, fn) _filters[event] = fn end
        print = function(msg) table.insert(_printed, msg) end
        BabelChatDB = { companion = { enabled = true } }
        """
    )
    # rawget: a stub frame answers every missing key with a stand-in.
    with_handler = lua.eval(
        "function(key) local out = {} for _, f in ipairs(_all_frames) do"
        " if rawget(f, key) then table.insert(out, f) end end return out end"
    )
    login = list(with_handler("_OnEvent").values())
    assert len(login) == 1, "Core.lua should install exactly one event handler"

    login[0]._OnEvent(login[0], "PLAYER_LOGIN")

    db = lua.globals().BabelChatDB
    filters = lua.globals()._filters
    assert db.wctAnchor == 8675309123457
    assert db.dict.targetLocale == "huHU"
    assert filters.CHAT_MSG_BATTLEGROUND is not None
    assert filters.CHAT_MSG_BATTLEGROUND_LEADER is not None
    assert filters.CHAT_MSG_BN_WHISPER is not None
    assert filters.CHAT_MSG_INSTANCE_CHAT is None
    assert len(list(lua.globals()._added.values())) == 1, "the panel was not registered"
    assert addon.addon_table.minimapButton is not None

    # A battleground line reaches the companion under the token the app maps,
    # and the timers — the flush and the 3 s welcome popup — run off the one
    # OnUpdate driver.
    filters.CHAT_MSG_BATTLEGROUND(None, "CHAT_MSG_BATTLEGROUND", "inc mid", "Bob")
    # Server announcements reach the companion too, and are never rewritten
    # in the player's own chat window (the filter returns nothing).
    assert filters.CHAT_MSG_SYSTEM(None, "CHAT_MSG_SYSTEM", "[SERVER] Restart in 5 minutes") is None
    drivers = list(with_handler("_OnUpdate").values())
    assert len(drivers) == 1, "Timer.lua should drive every timer from one frame"
    addon.now += 5
    drivers[0]._OnUpdate(drivers[0], 5.0)

    assert "|RAW|BATTLEGROUND|Bob|inc mid" in str(db.wctbuf)
    assert "|RAW|SYSTEM||[SERVER] Restart in 5 minutes" in str(db.wctbuf)
    assert lua.globals().BabelChatWelcomeFrame is not None, "the first-run popup never appeared"


# ── the Köszi button ─────────────────────────────────────────────────────────


def _login(addon):
    lua = addon.lua
    lua.execute(
        """
        Minimap = CreateFrame("Frame", "Minimap")
        GameTooltip = CreateFrame("GameTooltip", "GameTooltip")
        ChatFrame_AddMessageEventFilter = function() end
        print = function(msg) table.insert(_printed, msg) end
        BabelChatDB = { companion = { enabled = true } }
        _said = {}
        SendChatMessage = function(text, kind) table.insert(_said, { text = text, kind = kind }) end
        """
    )
    find = lua.eval(
        "function(key) local out = {} for _, f in ipairs(_all_frames) do"
        " if rawget(f, key) then table.insert(out, f) end end return out end"
    )
    login = list(find("_OnEvent").values())[0]
    login._OnEvent(login, "PLAYER_LOGIN")
    return lua


def test_the_koszi_button_says_a_haiku_from_the_list_in_say(addon):
    lua = _login(addon)
    HAIKUS = list(addon.addon_table.HAIKUS.values())
    button = addon.addon_table.kosziButton
    assert button is not None, "the Köszi button was not created at login"

    button._OnClick(button)

    said = list(lua.globals()._said.values())
    assert len(said) == 1
    assert said[0].kind == "SAY"
    assert said[0].text in HAIKUS


def test_koszi_slash_command_says_and_toggles_the_button(addon):
    lua = _login(addon)
    slash = lua.globals().SlashCmdList.BABELCHATKOSZI

    slash("")
    assert len(list(lua.globals()._said.values())) == 1

    slash("hide")
    assert lua.globals().BabelChatDB.minimap.koszi.hide is True
    slash("show")
    assert lua.globals().BabelChatDB.minimap.koszi.hide is False
    # Toggling never adds a top-level key: that would rehash the table the
    # companion app reads through.
    assert lua.globals().BabelChatDB.koszi is None


def test_the_addon_carries_23_three_line_haikus(addon):
    haikus = list(addon.addon_table.HAIKUS.values())
    assert len(haikus) == 23
    assert len(set(haikus)) == 23
    # One chat line each: three lines joined by " / ", short enough for /say.
    for haiku in haikus:
        assert len(haiku.split(" / ")) == 3, haiku
        assert len(haiku) < 255


def test_the_companion_buffer_is_on_by_default_and_turned_on_once_for_old_saves(addon):
    """Off, the addon writes nothing for the app: the overlay stays empty and
    only the keyword gloss shows in chat — what the first 3.3.5a test saw."""
    lua = addon.lua
    lua.execute("BabelChatDB = nil")
    assert addon.addon_table.InitialiseSavedVariables().companion.enabled is True

    lua.execute("BabelChatDB = { companion = { enabled = false } }")
    assert addon.addon_table.InitialiseSavedVariables().companion.enabled is True

    # After that one migration, switching it off sticks.
    lua.execute("BabelChatDB.companion.enabled = false")
    assert addon.addon_table.InitialiseSavedVariables().companion.enabled is False
