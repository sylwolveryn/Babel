"""Setting keys, their migration, and the layout arithmetic behind the panel.

The category toggles were named after the Spanish addon this dictionary came
from — `showMazz`, `showClases`, `showComercio` — which nobody reading their own
SavedVariables could decode. Renaming them is only safe if the saved values move
with them: otherwise every category a player had switched off comes back on,
silently, on the next login.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("lupa", reason="lupa provides the Lua 5.1 runtime the addon needs")

from tests.lua_harness import AddonHarness  # noqa: E402

ADDON_DIR = Path(__file__).resolve().parent.parent / "addon" / "BabelChat"

# Renamed in this change; the values must follow.
RENAMED = {
    "showMazz": "showDungeons",
    "showClases": "showClasses",
    "showCombate": "showCombat",
    "showComercio": "showTrade",
    "showGrupos": "showGroups",
    "showHermandad": "showGuild",
    "showEstado": "showStatus",
    "showProfesiones": "showProfessions",
}


@pytest.fixture
def core():
    """Core.lua loaded far enough to expose the migration helper.

    Core.lua registers an event frame at the bottom; the harness's stubs cover
    what it touches at load time, and the handler never fires here.
    """
    harness = AddonHarness()
    lua = harness.lua
    # A frame that accepts any method call and returns another such frame, which
    # is enough for Core.lua to finish loading without a game underneath it.
    lua.execute(
        "CreateFrame = function()  return setmetatable({}, {__index = function() return function() end end})end"
    )
    lua.execute("SlashCmdList = {}; strtrim = function(s) return (s:gsub('^%s*(.-)%s*$', '%1')) end")
    harness.addon_table.L = lua.eval("setmetatable({}, {__index = function(_, k) return k end})")
    harness.load("Core.lua")
    return harness


# ── the migration ────────────────────────────────────────────────────────────


def test_a_disabled_category_stays_disabled_through_the_rename(core):
    settings = core.lua.eval("{ showMazz = false, showClases = false, showSocial = true }")

    moved = core.addon_table.MigrateSettingKeys(settings)

    assert moved == 2
    assert settings["showDungeons"] is False
    assert settings["showClasses"] is False
    assert settings["showSocial"] is True


def test_the_old_keys_are_removed(core):
    settings = core.lua.eval("{ showMazz = false }")

    core.addon_table.MigrateSettingKeys(settings)

    assert settings["showMazz"] is None


def test_running_the_migration_twice_changes_nothing(core):
    settings = core.lua.eval("{ showComercio = false, showGrupos = true }")

    first = core.addon_table.MigrateSettingKeys(settings)
    second = core.addon_table.MigrateSettingKeys(settings)

    assert (first, second) == (2, 0)
    assert settings["showTrade"] is False
    assert settings["showGroups"] is True


def test_a_config_already_on_the_new_keys_is_untouched(core):
    settings = core.lua.eval("{ showDungeons = false, showClasses = true }")

    moved = core.addon_table.MigrateSettingKeys(settings)

    assert moved == 0
    assert settings["showDungeons"] is False
    assert settings["showClasses"] is True


def test_when_both_names_are_present_the_new_one_wins(core):
    """It is what the player last chose in a version that used it."""
    settings = core.lua.eval("{ showMazz = true, showDungeons = false }")

    core.addon_table.MigrateSettingKeys(settings)

    assert settings["showDungeons"] is False
    assert settings["showMazz"] is None


def test_a_missing_settings_table_is_survivable(core):
    assert core.addon_table.MigrateSettingKeys(None) == 0
    assert core.addon_table.MigrateSettingKeys("not a table") == 0


def test_every_renamed_key_is_covered(core):
    renames = dict(core.addon_table.SETTING_RENAMES)
    assert renames == RENAMED


# ── the panel, built ─────────────────────────────────────────────────────────


def source(*names: str) -> str:
    return chr(10).join((ADDON_DIR / name).read_text(encoding="utf-8") for name in names)


RECORDING_FRAME = """
    _frames = {}
    _registered = nil
    _scroll_child = nil

    local function NewFrame(kind, name, parent, template)
        local frame = {
            -- `false` rather than nil: a nil field falls through to the
            -- __index below and comes back as a function, which reads as
            -- "present" on the Python side and made this fixture lie once.
            kind = kind, name = name or false, parent = parent, template = template or false,
            points = {}, height = 0, width = 0, text = false, shown = true,
        }
        function frame:GetName() return self.name end
        function frame:SetPoint(anchor, a, b, c, d)
            -- Both shapes the panel uses: (anchor, x, y) and
            -- (anchor, relativeTo, relativePoint, x, y).
            if type(a) == "table" then
                -- Anchored to another frame: its x/y are in that frame's space,
                -- not the panel's, so they are recorded but not comparable.
                table.insert(self.points, { anchor = anchor, relative = a, x = c, y = d, absolute = false })
            else
                table.insert(self.points, { anchor = anchor, x = a, y = b, absolute = true })
            end
        end
        function frame:SetSize(w, h) self.width, self.height = w, h end
        function frame:SetHeight(h) self.height = h end
        function frame:SetWidth(w) self.width = w end
        function frame:SetText(value) self.text = value end
        function frame:SetScrollChild(child) _scroll_child = child end
        function frame:CreateTexture()
            local texture = NewFrame("Texture")
            table.insert(_frames, texture)
            return texture
        end
        function frame:CreateFontString()
            local fontString = NewFrame("FontString")
            table.insert(_frames, fontString)
            return fontString
        end
        return setmetatable(frame, {
            __index = function(_, key)
                if key == "GetName" then return nil end
                return function() end
            end,
        })
    end

    CreateFrame = function(kind, name, parent, template)
        local frame = NewFrame(kind, name, parent, template)
        table.insert(_frames, frame)
        if name then
            _G[name] = frame
            -- InterfaceOptionsCheckButtonTemplate creates a "<name>Text" label.
            _G[name .. "Text"] = NewFrame("FontString", name .. "Text")
        end
        return frame
    end

    UIParent = CreateFrame("Frame", "UIParent")
    GetAddOnMetadata = function() return "3.4.1" end
    -- The dropdown API is a dozen loose globals and none of them matter to
    -- what these tests measure. Narrowly scoped so any OTHER missing global
    -- still surfaces as the nil-index error the harness intends.
    setmetatable(_G, { __index = function(_, key)
        if type(key) == "string" and key:match("^UIDropDownMenu_") then
            return function() return {} end
        end
        return nil
    end })
    ColorPickerFrame = CreateFrame("Frame", "ColorPickerFrame")
    -- The 3.3.5 options API. Retail's Settings.* must not be reached for:
    -- it is deliberately absent here, so a call to it is a nil-index error.
    InterfaceOptions_AddCategory = function(panel) _registered = panel end
"""


@pytest.fixture
def panel(core):
    """Config.lua run for real, with a CreateFrame that records what it built.

    These properties used to be checked by matching the source text, which meant
    renaming a local variable reddened a test without breaking the addon, and
    shipping the bug the test named passed as long as some line still looked
    right. Building the panel measures the panel.
    """
    lua = core.lua
    lua.execute(RECORDING_FRAME)
    # The addon's own defaults, not a hand-written stand-in: a panel that reads
    # a field ApplyDefaults never writes is exactly the failure worth catching.
    lua.execute("BabelChatDB = {}")
    core.addon_table.InitialiseSavedVariables()
    core.load("Config.lua")
    core.addon_table.CreateConfigUI()
    return core


def _load_dictionary_data(harness):
    """The engine plus the tables it indexes.

    A toggle can only be shown to switch something if the thing it switches is
    loaded; without the Data files every category looks equally dead and the
    test passes on nothing.
    """
    for path in sorted((ADDON_DIR / "Data").glob("*.lua")):
        harness.load(f"Data/{path.name}")
    harness.load("DictEngine.lua")


def built_frames(harness):
    return list(harness.lua.globals()._frames.values())


def checkbox_keys(harness) -> set[str]:
    """The category toggles the panel actually created, by their setting key."""
    prefix = "WCT_CB_"
    return {
        frame.name[len(prefix):]
        for frame in built_frames(harness)
        if frame.name and str(frame.name).startswith(prefix)
    }


def test_the_panel_creates_a_checkbox_for_every_category_the_engine_reads(panel):
    """The engine consults a fixed map of setting keys. One the panel never
    shows is a category the user cannot switch on, permanently off or
    permanently on depending on the default."""
    _load_dictionary_data(panel)
    engine_keys = set(re.findall(r'\{ key = "(\w+)"', source("DictEngine.lua")))

    shown = checkbox_keys(panel)

    assert engine_keys - shown == set(), f"the engine reads a toggle nobody can see: {engine_keys - shown}"


def test_every_checkbox_the_panel_shows_has_a_default(panel):
    """A toggle with no default starts as nil, which reads as off — so a
    category the user never touched is silently disabled."""
    panel.lua.execute("BabelChatDB.dict.settings = {}")
    panel.addon_table.InitialiseSavedVariables()
    defaults = panel.lua.globals().BabelChatDB.dict.settings

    missing = [key for key in checkbox_keys(panel) if defaults[key] is None]

    assert missing == [], f"no default for: {missing}"


def test_the_scrolling_canvas_is_registered_and_is_not_the_scroll_child(panel):
    """Registering the scroll child instead of the canvas gives the options
    window a frame that scrolls inside itself and clips at the wrong edge."""
    registered = panel.lua.globals()._registered
    child = panel.lua.globals()._scroll_child

    assert registered is not None, "nothing was registered with the options window"
    assert child is not None, "the scroll frame was never given its content"
    assert registered.name != child.name
    # InterfaceOptions_AddCategory lists a panel under its `name` field.
    assert registered.name == "BabelChat"


def test_the_panel_offers_no_zone_or_item_set_toggles(panel):
    """Those came from LibBabble, which this build does not ship. A checkbox
    for them would switch nothing."""
    shown = checkbox_keys(panel)

    assert {"showZones", "showSets"} & shown == set()


def test_battleground_chat_has_its_own_channel_toggle(panel):
    """3.3.5 has no instance chat; battleground chat is its own pair of events,
    and the toggle that covers them is labelled for it."""
    g = panel.lua.globals()
    names = {str(frame.name) for frame in built_frames(panel) if frame.name}
    # A checkbox's label is its "<name>Text" child, created by the template.
    labels = {str(g[name + "Text"].text) for name in names if name.startswith("WCT_CH_CB_")}

    assert "CH_BATTLEGROUND" in labels, "no Battleground channel toggle"
    assert not any("INSTANCE" in name for name in names)


def test_the_language_dropdown_offers_only_english_and_hungarian():
    text = source("Config.lua")
    offered = set(re.findall(r'\{ value = "(\w+)", name = "[^"]+" \}', text))

    assert offered == {"enUS", "huHU"}


def test_no_section_heading_overlaps_the_row_beneath_it(panel):
    """Two sections used a 5px gap and two used 25px; the difference was not
    intentional, and 5px under a 14px heading put the checkbox inside the text.

    Only headings are checked. The category grid runs on a deliberate 25px
    pitch, which is tighter than the template's 26px hit area and correct: that
    was never the complaint, and asserting on it would fail the addon for
    looking the way it is meant to look.
    """
    headings = [
        (frame, point)
        for frame in built_frames(panel)
        if frame.kind == "FontString" and not frame.name and frame.text
        for point in frame.points.values()
        if point.absolute and point.y is not None and point.x is not None
    ]
    rows = sorted(
        (
            (point.y, point.x, frame)
            for frame in built_frames(panel)
            for point in frame.points.values()
            if point.absolute and point.y is not None and point.x is not None
        ),
        key=lambda row: -row[0],
    )

    too_close = []
    for heading, point in headings:
        below = [y for y, x, frame in rows if y < point.y and frame is not heading]
        if not below:
            continue
        gap = point.y - max(below)
        if gap < HEADING_HEIGHT:
            too_close.append((heading.text, gap))

    assert too_close == [], f"a {HEADING_HEIGHT}px heading with less than that beneath it: {too_close}"


# ── the keys the rest of the addon uses ──────────────────────────────────────
# ── the keys the rest of the addon uses ──────────────────────────────────────


def test_every_toggle_the_panel_shows_actually_switches_a_category(panel):
    """The Spanish-derived key names were renamed across three files. A leftover
    would read a key nothing writes, and the category would appear enabled in
    the panel while translating nothing — silent, and impossible for a user to
    report as anything but "it does not work".

    This used to be a regex over the source of those three files, which cut the
    text to 7% of itself before searching and never looked at Config.lua at all.
    Switching each toggle and watching the dictionary respond measures the thing
    the names were only a proxy for.
    """
    _load_dictionary_data(panel)
    settings = panel.lua.globals().BabelChatDB.dict.settings

    dead = []
    for key in sorted(checkbox_keys(panel)):
        for other in checkbox_keys(panel):
            settings[other] = False
        panel.addon_table.RebuildMasterDict()
        without = panel.addon_table.MasterDictSize()

        settings[key] = True
        panel.addon_table.RebuildMasterDict()
        with_it = panel.addon_table.MasterDictSize()

        if with_it <= without:
            dead.append(key)

    assert dead == [], f"these toggles switch nothing: {dead}"


def test_the_old_spanish_key_names_are_gone_from_the_panel(panel):
    """The rename table is the one place they are still allowed to appear."""
    shown = checkbox_keys(panel)
    survivors = sorted(shown & set(RENAMED))

    assert survivors == [], f"the panel still shows: {survivors}"


# ── layout arithmetic ────────────────────────────────────────────────────────
#
# The panel IS built here now, so these are the two heights the recorded frames
# are measured against: a heading's text and a checkbox's hit area. The bug was
# a five-pixel gap under a fourteen-pixel heading, with a twenty-six-pixel
# control beneath it.

HEADING_HEIGHT = 14
CHECKBOX_HEIGHT = 26


def config_constant(name: str) -> int:
    match = re.search(rf"^local {name} = (\d+)$", source("Config.lua"), re.M)
    assert match, f"{name} is not a plain constant any more"
    return int(match.group(1))


def test_every_section_uses_the_shared_gap():
    """Two sections used 5 and two used 25; the difference was not intentional."""
    text = source("Config.lua")
    literal_gaps = re.findall(r"yOffset = yOffset - (\d+)\n(\s+)for i, info in ipairs", text)
    assert literal_gaps == [], f"a section still hardcodes its gap: {literal_gaps}"




# ── which language the gloss speaks ──────────────────────────────────────────


def locale_harness(client_locale: str, saved: str | None = None):
    """Core.lua initialised as it would be on a client with this locale."""
    harness = AddonHarness()
    lua = harness.lua
    lua.execute(
        "CreateFrame = function()  return setmetatable({}, {__index = function() return function() end end})end"
    )
    lua.execute("SlashCmdList = {}; strtrim = function(s) return (s:gsub('^%s*(.-)%s*$', '%1')) end")
    lua.globals().GetLocale = lambda: client_locale
    harness.addon_table.L = lua.eval("setmetatable({}, {__index = function(_, k) return k end})")
    harness.load("Core.lua")
    if saved is not None:
        lua.globals().BabelChatDB = lua.eval(f'{{ dict = {{ targetLocale = "{saved}" }} }}')
    harness.addon_table.InitialiseSavedVariables()
    return harness


@pytest.mark.parametrize("client", ["enUS", "enGB", "huHU", "deDE"])
def test_a_fresh_install_glosses_in_hungarian_whatever_the_client(client):
    """This build is for an English 3.3.5 client read by a Hungarian player.
    The client's locale is exactly the wrong signal, so it is not consulted."""
    h = locale_harness(client)

    assert h.lua.globals().BabelChatDB.dict.targetLocale == "huHU"


@pytest.mark.parametrize("saved", ["enUS", "huHU"])
def test_a_supported_language_the_player_chose_is_never_overwritten(saved):
    h = locale_harness("enUS", saved=saved)

    assert h.lua.globals().BabelChatDB.dict.targetLocale == saved


@pytest.mark.parametrize("saved", ["ruRU", "esES", "deDE", "zhCN"])
def test_a_saved_language_the_dictionary_no_longer_carries_becomes_hungarian(saved):
    """A config from the retail build may name any of fourteen languages. Only
    two exist now; anything else would gloss every term in English fallback
    while the panel showed a language nobody can pick."""
    h = locale_harness("enUS", saved=saved)

    assert h.lua.globals().BabelChatDB.dict.targetLocale == "huHU"


def test_settings_for_removed_features_are_cleared():
    """Zone and item-set toggles, the poll fallback and instance chat no longer
    exist. Left in place they would be read by nothing and confuse anyone
    reading their own SavedVariables."""
    harness = AddonHarness()
    lua = harness.lua
    lua.execute(
        "CreateFrame = function()  return setmetatable({}, {__index = function() return function() end end})end"
    )
    lua.execute("SlashCmdList = {}")
    harness.addon_table.L = lua.eval("setmetatable({}, {__index = function(_, k) return k end})")
    harness.load("Core.lua")
    lua.globals().BabelChatDB = lua.eval(
        "{ dict = { settings = { showZones = false, showSets = true,"
        " channels = { CHAT_MSG_INSTANCE_CHAT = false } } },"
        " companion = { pollFallback = true } }"
    )

    harness.addon_table.InitialiseSavedVariables()
    db = lua.globals().BabelChatDB

    assert db.dict.settings.showZones is None
    assert db.dict.settings.showSets is None
    assert db.companion.pollFallback is None
    assert db.dict.settings.channels.CHAT_MSG_INSTANCE_CHAT is None
    assert db.dict.settings.channels.CHAT_MSG_BATTLEGROUND is True
    assert db.dict.settings.channels.CHAT_MSG_BATTLEGROUND_LEADER is True


def test_the_rename_runs_before_the_defaults_are_filled_in():
    """The one ordering the initialiser was extracted from the event handler to
    make testable — and then wasn't tested, so swapping the two lines left the
    whole suite green.

    It is load-bearing: defaults first would see the new key missing, default it
    to `true`, and hand every upgrading player back the categories they had
    switched off.
    """
    harness = AddonHarness()
    lua = harness.lua
    lua.execute(
        "CreateFrame = function()  return setmetatable({}, {__index = function() return function() end end})end"
    )
    lua.execute("SlashCmdList = {}; strtrim = function(s) return (s:gsub('^%s*(.-)%s*$', '%1')) end")
    harness.addon_table.L = lua.eval("setmetatable({}, {__index = function(_, k) return k end})")
    harness.load("Core.lua")
    lua.globals().BabelChatDB = lua.eval(
        '{ dict = { settings = { showMazz = false, showComercio = false, showSocial = true } } }'
    )

    harness.addon_table.InitialiseSavedVariables()
    settings = lua.globals().BabelChatDB.dict.settings

    assert settings.showDungeons is False, "a category the player switched off came back on"
    assert settings.showTrade is False
    assert settings.showSocial is True
    assert settings.showMazz is None, "the old key should be gone, not kept alongside"


# ── labels have to fit the column they sit in ────────────────────────────────

#: The category grid is three columns 190px apart (Config.lua), a checkbox eats
#: about 26px of that, and the label is drawn in GameFontHighlightSmall. What is
#: left holds roughly 26 characters. This is a budget, not a measurement — the
#: harness has no font metrics — but it is calibrated against the label that
#: actually overflowed: "Эндгейм: М+, вылазки, экипировка (22)" at 37, which ran
#: straight through the checkbox in the next column.
CATEGORY_LABEL_BUDGET = 26


def locale_table(locale: str):
    """The UI strings a player who chose `locale` sees. The UI language is the
    addon's own setting, not GetLocale()."""
    harness = AddonHarness()
    harness.lua.execute(f'BabelChatDB = {{ dict = {{ targetLocale = "{locale}" }} }}')
    harness.load("Locales.lua")
    return harness.addon_table.L


#: Every category label key the panel uses (Config.lua).
CATEGORY_KEYS = (
    "CAT_MAZZ", "CAT_SOCIAL", "CAT_CLASSES", "CAT_ROLES", "CAT_STATS", "CAT_PROF", "CAT_COMBAT",
    "CAT_TRADE", "CAT_GROUPS", "CAT_GUILD", "CAT_STATUS", "CAT_SLANG", "CAT_ENDGAME",
)


def category_labels(locale: str) -> dict[str, str]:
    """Every category label as the options panel will render it, with its count."""
    table = locale_table(locale)
    labels = {key: table[key] for key in CATEGORY_KEYS}
    missing = [key for key, value in labels.items() if value is None]
    assert missing == [], f"{locale}: the panel asks for labels that do not exist: {missing}"
    return {key: str(value) for key, value in labels.items()}


def test_the_label_keys_checked_here_are_the_ones_the_panel_uses():
    used = set(re.findall(r'text = L\["(CAT_\w+)"\]', source("Config.lua")))

    assert used == set(CATEGORY_KEYS)


@pytest.mark.parametrize("locale", ["enUS", "huHU"])
def test_no_category_label_runs_into_the_next_column(locale):
    """The Endgame label read "Эндгейм: М+, вылазки, экипировка (22)" and
    overlapped the checkbox beside it. A label is a name; what the category
    covers belongs in the tooltip, which already existed and was duplicating it.
    """
    # Four more characters for the " (NN)" the panel appends.
    too_long = {
        key: (text, len(text) + 5)
        for key, text in category_labels(locale).items()
        if len(text) + 5 > CATEGORY_LABEL_BUDGET
    }

    assert too_long == {}, f"{locale}: these will overlap the next column: {too_long}"


@pytest.mark.parametrize("locale", ["enUS", "huHU"])
def test_every_category_has_a_tooltip_that_says_more_than_its_label(locale):
    """Shortening the labels is only safe if the explanation is somewhere. It is
    the tooltip's whole job, and a tooltip that merely repeats the label is not
    doing it."""
    table = locale_table(locale)

    lazy = []
    for key in category_labels(locale):
        tooltip = table["TT_" + key]
        if tooltip is None or len(str(tooltip)) <= len(str(table[key])):
            lazy.append(key)

    assert lazy == [], f"{locale}: no useful tooltip for {lazy}"


# ── the About section ────────────────────────────────────────────────────────


def link_boxes(harness) -> dict[str, str]:
    """The addresses the panel offers, by the EditBox that holds each."""
    return {
        frame.name: str(frame.text)
        for frame in built_frames(harness)
        if frame.name and str(frame.name).startswith("WCT_Link")
    }


def test_the_panel_offers_the_project_page(panel):
    """A player who wants to report something or check for an update has
    nowhere to look otherwise — a WoW addon cannot open a browser, so the
    address has to be in front of them to copy."""
    addresses = set(link_boxes(panel).values())

    assert any("github.com/Yumash/BabelChat" in url for url in addresses), addresses


def test_the_panel_points_at_no_retail_storefront(panel):
    """CurseForge and Wago list the retail build. A 3.3.5 player sent there
    downloads an addon their client cannot load."""
    addresses = " ".join(link_boxes(panel).values())

    assert "curseforge" not in addresses.lower()
    assert "wago" not in addresses.lower()


def test_every_box_holds_something_that_can_be_pasted_as_it_stands(panel):
    """A truncated or relative address is worse than none: it looks copyable and
    goes nowhere. Web addresses must be complete URLs; a wallet address is not a
    URL but must still be whole and free of stray whitespace, because it is
    pasted into a payment form where a typo loses the money."""
    bad = {}
    for name, value in link_boxes(panel).items():
        if value != value.strip() or " " in value:
            bad[name] = f"whitespace in {value!r}"
        elif "." in value.split("/")[0] and not value.startswith("https://"):
            bad[name] = f"looks like a URL but is not https: {value!r}"
        elif not value.startswith("https://") and len(value) < 26:
            bad[name] = f"too short to be a wallet address: {value!r}"

    assert bad == {}, f"not usable as it stands: {bad}"


def test_the_panel_carries_no_payment_details(panel):
    """The donation link and wallet addresses were dropped from this build. A
    payment address in a fork's panel is one nobody here can vouch for."""
    values = " ".join(link_boxes(panel).values())
    panel_source = source("Config.lua")

    assert "cloudtips" not in values and "cloudtips" not in panel_source
    assert all(value.startswith("https://") for value in link_boxes(panel).values()), "a non-URL (wallet?) box"


@pytest.mark.parametrize("locale", ["enUS", "huHU"])
def test_the_about_section_credits_both_the_authors_and_the_glossary(locale):
    """The glossary is Pirson's under MIT. Crediting it only in a file nobody
    opens is not crediting it."""
    table = locale_table(locale)

    authors = str(table["ABOUT_AUTHORS"])
    credit = str(table["ABOUT_DICT_CREDIT"])

    assert "AhegaoZKun" in authors, authors
    assert "Pirson" in credit, credit
    assert "MIT" in credit, credit
    assert "MIT" in str(table["ABOUT_LICENSE"])
