"""The TOC and what ships beside it, checked against what is on disk and what
the 3.3.5 client can actually run.

This build targets World of Warcraft 3.3.5a (WotLK, build 12340). Two failure
modes motivated the original file and still apply: a file listed in the TOC but
missing from disk is invisible until a user installs the package, and a file
on disk but not in the TOC is dead code that looks live.

The port added a third: the retail build embedded LibStub-versioned libraries
(LibDBIcon minor 56, CallbackHandler minor 8) that call APIs 3.3.5 does not
have. LibStub hands the newest minor to EVERY addon that asks, so shipping them
would have broken other addons' minimap buttons and callbacks as well as ours.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("lupa", reason="lupa provides the Lua 5.1 runtime the addon needs")

from lupa import lua51  # noqa: E402

ADDON_DIR = Path(__file__).resolve().parent.parent / "addon" / "BabelChat"
TOC = ADDON_DIR / "BabelChat.toc"

#: The interface number of the 3.3.5a client.
WOTLK_INTERFACE = "30300"


def toc_files() -> list[str]:
    """File entries from the TOC, in load order (directives and comments dropped)."""
    entries = []
    for line in TOC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def addon_source() -> str:
    """Every first-party Lua file, Data excluded."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(ADDON_DIR.glob("*.lua")))


# ── the TOC matches the tree ─────────────────────────────────────────────────


def test_every_file_listed_in_the_toc_exists():
    missing = [e for e in toc_files() if not (ADDON_DIR / e.replace("\\", "/")).is_file()]
    assert missing == [], f"TOC lists files that are not on disk: {missing}"


def test_no_embedded_library_is_shipped():
    """Nothing under Libs/, and nothing in the TOC that loads from there."""
    assert not (ADDON_DIR / "Libs").exists(), "a Libs directory is back"
    assert [e for e in toc_files() if e.startswith("Libs")] == []


def test_libbabble_is_gone_from_the_addon():
    """The zone and item-set categories came from LibBabble, which is retail
    data for a retail client. Nothing may still reach for it."""
    source = code_only(addon_source())

    assert "LibBabble" not in source
    assert "InitLibBabble" not in source
    assert "showZones" not in source.replace("settings.showZones = nil", "")
    assert "showSets" not in source.replace("settings.showSets = nil", "")


def test_the_toc_opens_with_a_directive():
    """A TOC whose first line is a plain '#' comment silently drops every
    directive after it."""
    first = TOC.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("## "), first


def test_the_interface_version_is_wotlk():
    """3.3.5 reads exactly one number. Anything else marks the addon
    "out of date" on the character screen, and a retail-style comma list is
    not understood at all."""
    first = TOC.read_text(encoding="utf-8").splitlines()[0]

    assert first == f"## Interface: {WOTLK_INTERFACE}", first


@pytest.mark.parametrize(
    "directive",
    ["Category", "Category-ruRU", "Notes-ruRU", "Notes-esES", "Notes-esMX", "X-Curse-Project-ID", "X-Wago-ID",
     "OptionalDeps"],
)
def test_no_retail_only_or_dropped_directive_remains(directive):
    """3.3.5 has no addon categories; the store IDs belong to the retail
    release; the libraries OptionalDeps named are no longer shipped."""
    assert toc_directive(directive) is None, f"## {directive} is still in the TOC"


def test_the_timer_backport_loads_before_anything_that_schedules():
    order = [e.replace("\\", "/") for e in toc_files()]

    assert order[0] == "Timer.lua", order[:3]


def test_the_options_panel_loads_before_the_minimap_button_and_core():
    """Core opens the panel from the minimap button at PLAYER_LOGIN; both have
    to be defined by then. Load order makes that true without relying on the
    event."""
    order = [e.replace("\\", "/") for e in toc_files()]

    assert order.index("Config.lua") < order.index("MinimapButton.lua") < order.index("Core.lua")


# ── nothing retail-only is called ────────────────────────────────────────────

#: APIs and templates the 3.3.5 client does not have, with what replaced them.
RETAIL_ONLY = {
    r"\bSettings\.": "InterfaceOptions_AddCategory / InterfaceOptionsFrame_OpenToCategory",
    r"\bC_AddOns\b": "GetAddOnMetadata",
    r"\bC_ChatInfo\b": "nothing (unused)",
    r":SetColorTexture\(": "Texture:SetTexture(r, g, b, a)",
    r":SetResizeBounds\(": "SetMinResize / SetMaxResize",
    r"BackdropTemplate": "plain CreateFrame; SetBackdrop is native on 3.3.5",
    r"SetupColorPickerAndShow": "ColorPickerFrame.func / cancelFunc / previousValues",
    r"BasicFrameTemplate": "a frame with a dialog backdrop",
    r"MinimalSliderWithStepper": "OptionsSliderTemplate",
    r"\bMixin\(|CreateFromMixins": "plain tables",
    r"GetNormalizedRealmName": "GetRealmName with spaces and hyphens removed",
    r"\bissecretvalue\b|\bcanaccessvalue\b": "nothing: 3.3.5 has no secret values",
    r"GetMessageInfo": "nothing: the poll fallback was removed",
    r"INSTANCE_CHAT": "CHAT_MSG_BATTLEGROUND / CHAT_MSG_BATTLEGROUND_LEADER",
    r"securecallfunction": "pcall",
    r":SetSize\(": "SetWidth + SetHeight",
}


def code_only(text: str) -> str:
    """Lua source with comments removed, so a comment that names the retail API
    it replaced does not count as calling it."""
    text = re.sub(r"--\[(=*)\[.*?\]\1\]", "", text, flags=re.S)
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


@pytest.mark.parametrize("name", sorted(p.name for p in ADDON_DIR.glob("*.lua")))
@pytest.mark.parametrize("pattern", sorted(RETAIL_ONLY))
def test_no_retail_only_api_is_called(name, pattern):
    code = code_only((ADDON_DIR / name).read_text(encoding="utf-8"))
    code = code.replace("CHAT_MSG_INSTANCE_CHAT_LEADER = nil", "").replace("CHAT_MSG_INSTANCE_CHAT = nil", "")

    found = re.findall(pattern, code)

    assert found == [], f"{name} calls {found[0]!r}; on 3.3.5 use {RETAIL_ONLY[pattern]}"


@pytest.mark.parametrize("name", sorted(p.name for p in ADDON_DIR.glob("*.lua")))
def test_the_global_c_timer_is_never_used(name):
    """3.3.5 has no C_Timer. The addon's own is addonTable.C_Timer, and a file
    that uses the name must have taken it from there — otherwise it is reading
    a global that is nil on the client, or another addon's shim."""
    code = code_only((ADDON_DIR / name).read_text(encoding="utf-8"))
    if "C_Timer" not in code or name == "Timer.lua":
        return

    assert "local C_Timer = addonTable.C_Timer" in code, f"{name} uses a global C_Timer"


# ── documentation that claims a number ───────────────────────────────────────


ROOT = Path(__file__).resolve().parent.parent

#: Every file that describes the project to somebody who did not write it.
DOCS = (
    "README.md",
    # The file inside the zip: the first thing a stranger reads.
    "addon/BabelChat/README.md",
)


def shipped_term_count() -> int:
    return sum(
        len(re.findall(r'^\s*\["?[^\]]+"?\]\s*=\s*\{', path.read_text(encoding="utf-8"), re.M))
        for path in (ROOT / "addon" / "BabelChat" / "Data").glob("*.lua")
    )


@pytest.mark.parametrize("name", DOCS)
def test_no_document_states_a_term_count_that_is_not_the_term_count(name):
    """The README said 314 while the data files held 383. A number in a document
    is a claim, and a stale one is the kind a contributor trusts and repeats.

    Every document is checked, not just the two READMEs: the count appeared in
    three files and only one of them was ever corrected by hand.
    """
    counted = r"(\d{3})[  ](?:gaming terms|terms|игровых терминов|игровых термина|термина|терминов)"
    claimed = set()
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        # The credits state how many terms Pirson's addon contributed. That is a
        # fact about a different addon and does not move when ours does.
        if "Pirson" in line or "WoW Translator" in line:
            continue
        claimed.update(int(n) for n in re.findall(counted, line))

    assert claimed <= {shipped_term_count()}, (
        f"{name} claims {sorted(claimed)}, the data files hold {shipped_term_count()}"
    )


def test_at_least_one_document_still_states_the_term_count():
    """The check above passes vacuously on a document that states no number.
    Somewhere the count has to be advertised, or the test guards nothing."""
    counted = r"(\d{3})[  ](?:gaming terms|terms|игровых терминов|игровых термина|термина|терминов)"
    stating = [name for name in DOCS if re.search(counted, (ROOT / name).read_text(encoding="utf-8"))]

    assert stating, "no document states the term count any more — this test now guards nothing"


def shipped_category_count() -> int:
    """One data file per glossary category."""
    return len(list((ROOT / "addon" / "BabelChat" / "Data").glob("*.lua")))


@pytest.mark.parametrize("name", DOCS)
def test_no_document_states_a_category_count_that_is_not_the_category_count(name):
    """It said 12 in one file and 13 in another while the data held 13 and the
    options panel showed 15 toggles — the two extra being zones and item sets,
    which are not data files."""
    text = (ROOT / name).read_text(encoding="utf-8")
    counted = r"(\d{1,2})[  ](?:categories|категори[а-я]+)"

    claimed = {int(n) for n in re.findall(counted, text)}

    assert claimed <= {shipped_category_count()}, (
        f"{name} claims {sorted(claimed)} categories, there are {shipped_category_count()} data files"
    )


@pytest.mark.parametrize("name", DOCS)
def test_no_document_still_sells_the_gloss_format_that_was_removed(name):
    """The gloss used to be a second line beginning with an arrow. That format
    was the project owner's headline complaint and the reason the engine was
    rewritten; a store page still advertising it sells the version people
    complained about."""
    text = (ROOT / name).read_text(encoding="utf-8")
    removed = [
        line.strip()
        for line in text.splitlines()
        if re.search(r"annotation (?:below|under)|аннотаци[а-я]+ под|подсказк[а-я]+ под сообщением", line)
    ]

    assert removed == [], f"{name} still describes the removed gloss format: {removed}"


@pytest.mark.parametrize("name", DOCS)
def test_no_document_tells_the_user_to_run_as_administrator(name):
    """The build stopped asking for elevation: ReadProcessMemory against a
    process owned by the same user never needed it, and standing elevation turns
    an ordinary library-planting bug into a full compromise.

    Documentation that still tells people to elevate is worse than stale — it
    talks them into granting a privilege the app does not use.
    """
    text = (ROOT / name).read_text(encoding="utf-8")

    # The first version matched two exact phrases and fired on none of the seven
    # lines that were telling people to elevate, in three languages across four
    # files — one of which was not even in DOCS. Match the instruction rather
    # than the word: a document is allowed to say "administrator rights are not
    # needed", and has to be able to.
    instructs = re.compile(
        r"(?:run|ejecuta|ejecutar|right-click|запусти|запуск|убедись)"
        # Not [^.] — the gap is usually "`BabelChat.exe` **", and excluding the
        # dot in the filename is why the Russian and Spanish steps went unseen.
        # A dot does not match a newline, so this stays on one line.
        r".{0,60}?"
        r"(?:as (?:an )?administrator|como administrador"
        r"|от (?:имени )?администратора)",
        re.IGNORECASE,
    )
    # Two exceptions, and both have to be allowed or the documentation cannot
    # say the true thing. A line about WoW itself being elevated is correct
    # advice — a normal-privilege process cannot read an elevated one. And a
    # line that quotes the old instruction in order to retract it is the most
    # useful sentence in the file for anyone who followed it before.
    permitted = re.compile(
        r"(?:wow|сам игр|the same way|так же"  # about the game, not the app
        r"|out of date|устарел|don't|не надо|dropped the request"  # a retraction
        r"|if you have a shortcut|остался ярлык|tells the user)",  # or a reference to this rule
        re.IGNORECASE,
    )

    telling = [line.strip() for line in text.splitlines() if instructs.search(line) and not permitted.search(line)]

    assert telling == [], f"{name} still tells the user to elevate: {telling}"


@pytest.mark.parametrize("name", DOCS)
def test_no_document_describes_credentials_as_one_flat_field_per_provider(name):
    """`deepl_api_key` at the top level of config.json is the shape from before
    providers declared themselves. It is still migrated on load, so naming it as
    the current shape sends a hand-editing user to a field the app rewrites."""
    text = (ROOT / name).read_text(encoding="utf-8")
    stale = re.findall(r'"(deepl_api_key|microsoft_api_key|microsoft_region)"\s*:', text)

    assert stale == [], f"{name} documents the pre-registry config shape: {stale}"


# ── directives the addon does not work without ───────────────────────────────


def toc_directive(name: str) -> str | None:
    for line in TOC.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith(f"## {name}:"):
            return line.split(":", 1)[1].strip()
    return None


def test_the_saved_variable_the_companion_reads_is_declared():
    """The single line the whole companion protocol rests on. Without it WoW
    never persists BabelChatDB, so BabelChatDB.wctbuf never exists, the memory
    reader finds nothing, and the app looks broken with no error anywhere.

    Nothing covered it: renaming it left the entire suite green.
    """
    assert toc_directive("SavedVariables") == "BabelChatDB"


def test_every_lua_file_the_addon_ships_is_loaded_by_the_toc():
    """A file present on disk and absent from the TOC is dead code that looks
    live. Dropping DictEngine.lua from the load order left the suite green."""
    listed = {
        line.strip().replace("\\", "/")
        for line in TOC.read_text(encoding="utf-8-sig").splitlines()
        if line.strip().endswith(".lua")
    }
    root = TOC.parent
    on_disk = {
        str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*.lua") if "Libs" not in path.parts
    }

    unloaded = sorted(on_disk - listed)

    assert unloaded == [], f"shipped but never loaded: {unloaded}"


def test_the_engine_loads_after_the_data_it_indexes():
    """RebuildMasterDict reads addonTable.*Dict at load time, so a data file
    listed after DictEngine.lua contributes nothing and its category is silently
    empty."""
    order = [
        line.strip().replace("\\", "/")
        for line in TOC.read_text(encoding="utf-8-sig").splitlines()
        if line.strip().endswith(".lua")
    ]
    engine = order.index("DictEngine.lua")
    late_data = [name for name in order[engine:] if name.startswith("Data/")]

    assert late_data == [], f"loaded after the engine that indexes them: {late_data}"


def test_the_addon_and_the_app_report_the_same_version():
    """The addon is installed by hand, so `## Version` is the only way a user or
    a bug report can say which one is running — and the readers carry a compat
    branch keyed on a version number, which is only meaningful if the two agree.
    """
    from app.branding import VERSION

    assert toc_directive("Version") == VERSION


@pytest.mark.parametrize("name", sorted(p.name for p in (TOC.parent).glob("*.lua")))
def test_every_addon_file_parses_as_lua(name):
    """A syntax error in a file WoW loads is silent to everyone but the player,
    who sees the addon simply not work. Splitting a file is exactly when one
    gets introduced."""
    source = (TOC.parent / name).read_text(encoding="utf-8")
    runtime = lua51.LuaRuntime()

    # loadstring returns (nil, message) on a parse error, and lupa hands that
    # back as a tuple — which is not None, so checking the result as a whole
    # passes on a file that does not compile. Ask Lua whether it compiled.
    ok, error = runtime.execute(
        """
        return function(source, name)
            local chunk, err = loadstring(source, name)
            return chunk ~= nil, err
        end
        """
    )(source, name)

    assert ok, f"{name} does not parse: {error}"
