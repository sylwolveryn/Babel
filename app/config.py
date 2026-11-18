"""Application configuration management."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_config_path() -> str:
    """config.json in the app's own folder (see app/paths.py)."""
    from app.paths import data_file

    return str(data_file("config.json"))


CONFIG_FILE = _get_config_path()

# Common install locations for a 3.3.5a client (ChromieCraft and friends).
# There is no launcher registry entry for a private-server client, so these are
# only guesses; the user picks the folder in the wizard when none match.
_WOW_PATHS_WINDOWS = [
    Path("C:/ChromieCraft"),
    Path("C:/Games/ChromieCraft"),
    Path("D:/ChromieCraft"),
    Path("D:/Games/ChromieCraft"),
    Path("C:/World of Warcraft 3.3.5a"),
    Path("C:/Games/World of Warcraft 3.3.5a"),
    Path("D:/World of Warcraft 3.3.5a"),
    Path("D:/Games/World of Warcraft 3.3.5a"),
    Path("C:/Program Files (x86)/World of Warcraft"),
    Path("C:/World of Warcraft"),
    Path("D:/World of Warcraft"),
]

# WoW Chat Log relative path inside WoW install
_CHATLOG_RELATIVE = "Logs/WoWChatLog.txt"

#: Where a 3.3.5a client keeps its addons, relative to the install folder.
ADDONS_RELATIVE = "Interface/AddOns"


@dataclass
class AppConfig:
    """Application settings."""

    # Paths
    wow_path: str = ""
    chatlog_path: str = ""

    # Languages
    # The interface is Hungarian only. The player speaks and reads Hungarian:
    # incoming English chat is translated into `own_language`, and the reply
    # box translates what the player writes into `reply_language`. Neither is
    # offered in the settings; the app does exactly one pair.
    ui_language: str = "HU"
    own_language: str = "HU"
    reply_language: str = "EN"

    # Overlay
    overlay_opacity: int = 180
    overlay_font_size: int = 10
    overlay_theme: str = "wow"  # preset id from overlay_theme.PRESETS, or "custom"
    overlay_bg_color: str = "#000000"
    overlay_text_color: str = "#FFFFFF"
    overlay_original_color: str = "#888888"
    overlay_translation_color: str = "#FFD200"
    overlay_timestamp_color: str = "#666666"
    overlay_tl_on_color: str = "#40FF40"
    overlay_tl_off_color: str = "#FF4040"
    overlay_close_color: str = "#FF4040"
    overlay_tool_color: str = "#CCCCCC"
    overlay_corner_radius: int = 8
    overlay_font_family: str = ""  # empty = system default
    overlay_channel_colors: dict = field(default_factory=dict)  # slot → "#RRGGBB"
    overlay_x: int = 100
    overlay_y: int = 100
    overlay_width: int = 450
    overlay_height: int = 300

    # Hotkeys
    hotkey_toggle_translate: str = "Ctrl+Shift+T"
    hotkey_clipboard_translate: str = "Ctrl+Shift+C"

    # Channels
    channels_party: bool = True
    channels_raid: bool = True
    channels_guild: bool = True
    channels_say: bool = True
    channels_whisper: bool = True
    channels_yell: bool = False
    channels_instance: bool = True
    channels_trade: bool = False
    channels_general: bool = False
    channels_lfg: bool = False
    # Player-made channels. Off by default: they are usually private, and
    # sending them to a translation service is a decision, not a default.
    channels_custom: bool = True  # see _migrate_split_channels: you join these on purpose
    channels_emote: bool = False
    # The server-wide World channel: where most of the talking happens on a
    # private server, so it is always translated unless switched off.
    channels_world: bool = True
    # Server announcements and other system messages.
    channels_system: bool = True

    # Translation
    skip_own_messages: bool = True
    translation_enabled_default: bool = True

    def save(self, path: str = CONFIG_FILE) -> None:
        """Save config to JSON file atomically (write to temp, then rename)."""
        target = Path(path)
        content = json.dumps(asdict(self), indent=2, ensure_ascii=False)

        # Backup existing config
        if target.exists():
            bak = target.with_suffix(".json.bak")
            try:
                bak.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                logger.warning("Could not create config backup")

        # Atomic write: temp file in the same folder, then rename — never the
        # system temp folder, so nothing is written outside the app's folder.
        fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp", prefix="config_")
        closed = False
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            closed = True
            shutil.move(tmp_path, str(target))
        except OSError:
            if not closed:
                os.close(fd)
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
            raise

    @classmethod
    def load(cls, path: str = CONFIG_FILE) -> AppConfig:
        """Load config from JSON file, using defaults for missing fields."""
        for try_path in _config_candidates(path):
            try:
                data = json.loads(try_path.read_text(encoding="utf-8"))
                _migrate_split_channels(data)
                _sanitize(data)
                defaults = asdict(cls())
                # Ignore unknown keys (e.g. fields removed in newer versions)
                # instead of crashing cls(**...) with a TypeError.
                defaults.update({k: v for k, v in data.items() if k in defaults})
                return cls(**defaults)
            except FileNotFoundError:
                continue
            except json.JSONDecodeError:
                logger.warning("Corrupt config file: %s, trying backup", try_path)
                continue
        logger.warning("No valid config found, using defaults")
        return cls()


def _config_candidates(path: str = CONFIG_FILE) -> list[Path]:
    """Every file `AppConfig.load` will accept a saved config from, in order.

    Declared once so that asking "is there a saved config?" and answering
    "here is the saved config" cannot come to look at different files.
    """
    target = Path(path)
    return [target, target.with_suffix(".json.bak")]


def saved_config_exists(path: str = CONFIG_FILE) -> bool:
    """True when a config this build can actually read is on disk.

    Deliberately not `os.path.exists(CONFIG_FILE)`, which answers a different
    question and gets it wrong in both directions. `load` also reads
    `config.json.bak`, so an absent main file does not mean the user has no
    saved preferences — and it falls back to defaults on a corrupt one, so a
    present main file does not mean any were read. Anything deciding whether
    this is a first run has to ask about the same candidates `load` does.

    Parses rather than stats, for the corrupt case, but does not migrate: the
    migrations write backups of their own, and running them from a question is
    not what a question should do.
    """
    for candidate in _config_candidates(path):
        try:
            json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return True
    return False


@dataclass(frozen=True, slots=True)
class ChannelToggle:
    """One switch in the settings window, and everything that depends on it.

    Four separate hand-written copies of this mapping used to exist — the two
    settings dialogs, the two entry points, and the overlay's filter tabs — and
    every one of them drifted. Yell had a row on Linux and none on Windows;
    Custom and Emote had rows on Windows and none on Linux; and once both got
    rows, Yell was still read by nobody, because Say quietly enabled it. A
    setting no screen offers cannot be reported. A setting a screen offers and
    the app ignores is worse: the user believes they changed something.
    """

    #: The AppConfig field the checkbox writes.
    field: str
    #: Key into the string table for the checkbox label.
    label: str
    #: Names of the parser channels this switch turns on.
    channels: tuple[str, ...]
    #: Filter tab in the overlay that shows them.
    tab: str


CHANNEL_TOGGLES: tuple[ChannelToggle, ...] = (
    ChannelToggle("channels_party", "settings.ch.party", ("PARTY", "PARTY_LEADER"), "Party"),
    ChannelToggle("channels_raid", "settings.ch.raid", ("RAID", "RAID_LEADER", "RAID_WARNING"), "Raid"),
    ChannelToggle("channels_guild", "settings.ch.guild", ("GUILD", "OFFICER"), "Guild"),
    ChannelToggle("channels_say", "settings.ch.say", ("SAY",), "Say"),
    ChannelToggle("channels_yell", "settings.ch.yell", ("YELL",), "Say"),
    ChannelToggle("channels_whisper", "settings.ch.whisper", ("WHISPER_FROM", "WHISPER_TO"), "Whisper"),
    ChannelToggle("channels_instance", "settings.ch.instance", ("INSTANCE", "INSTANCE_LEADER"), "Instance"),
    ChannelToggle("channels_trade", "settings.ch.trade", ("TRADE",), "Trade"),
    ChannelToggle("channels_general", "settings.ch.general", ("GENERAL",), "General"),
    ChannelToggle("channels_world", "settings.ch.world", ("WORLD",), "World"),
    ChannelToggle("channels_lfg", "settings.ch.lfg", ("LOOKING_FOR_GROUP",), "LookingForGroup"),
    ChannelToggle("channels_custom", "settings.ch.custom", ("CUSTOM",), "Custom"),
    ChannelToggle("channels_emote", "settings.ch.emote", ("EMOTE",), "Emote"),
    ChannelToggle("channels_system", "settings.ch.system", ("SYSTEM",), "System"),
)


#: Tabs whose string-table key is not simply the lower-cased name.
_FILTER_KEYS = {"LookingForGroup": "lfg"}

#: The overlay's filter tabs, in the order they are drawn, paired with the
#: string-table key for each label. Derived from CHANNEL_TOGGLES rather than
#: written out again: both overlays had their own hand-written copy, the Qt one
#: was missing Custom and Emote, and the GTK one showed the tab names in English
#: whatever language the interface was in.
FILTER_TABS: tuple[tuple[str, str], ...] = (
    ("All", "overlay.filter.all"),
    *dict.fromkeys(
        (toggle.tab, "overlay.filter." + _FILTER_KEYS.get(toggle.tab, toggle.tab.lower()))
        for toggle in CHANNEL_TOGGLES
    ),
)


def enabled_channels(config: AppConfig) -> set:
    """The parser channels the user's toggles add up to."""
    from app.parser import Channel

    enabled = set()
    for toggle in CHANNEL_TOGGLES:
        if getattr(config, toggle.field):
            enabled |= {Channel[name] for name in toggle.channels}
    return enabled


def enabled_filter_tabs(config: AppConfig) -> set[str]:
    """The overlay filter tabs the user's toggles add up to."""
    return {toggle.tab for toggle in CHANNEL_TOGGLES if getattr(config, toggle.field)}


#: Fields holding a language code, and the codes this build has for each.
_LANGUAGE_FIELDS = ("ui_language", "own_language", "reply_language")


def _sanitize(data: dict) -> None:
    """Drop saved values this build cannot use, so the defaults take over.

    A config written before the English/Hungarian conversion says "RU" in every
    language field; read as-is, chat would be translated into Russian.
    """
    from app.i18n import UI_LANGUAGES
    from app.languages import LANGUAGES

    # The translation pair is fixed (Hungarian in, English out) and no screen
    # offers it, so a saved value can only be stale: always use the defaults.
    for name in ("own_language", "reply_language", "target_language"):
        data.pop(name, None)
    # The debug console and the chat capture trace were removed.
    for name in ("show_debug_console", "debug_capture_trace"):
        data.pop(name, None)

    for name in _LANGUAGE_FIELDS:
        offered = UI_LANGUAGES if name == "ui_language" else LANGUAGES
        if name in data and data[name] not in offered:
            logger.info("Saved %s %r is not available in this build; using the default", name, data[name])
            del data[name]


def _migrate_split_channels(data: dict) -> None:
    """Carry a setting across when one channel becomes two.

    Emotes used to be delivered as Say — the reader mapped EMOTE onto it — so
    anyone with Say on was having emotes translated without ever being asked.
    Giving emotes their own toggle is right, but shipping it off by default
    would take that away silently on upgrade: nothing breaks, a kind of message
    simply stops appearing, which is the hardest sort of change to notice or
    report.

    So a config that predates the toggle inherits whatever Say was set to. A
    config that has the key keeps its own answer, and a fresh install still gets
    the documented default.
    """
    if "channels_emote" not in data and "channels_say" in data:
        data["channels_emote"] = bool(data["channels_say"])
    # Yell was bundled into Say for the same reason and now has its own toggle,
    # so it inherits the same way. Its old default was off, but what the user
    # actually experienced was "Say is on, therefore yells are translated".
    if "channels_yell" not in data and "channels_say" in data:
        data["channels_yell"] = bool(data["channels_say"])
    # A player-made channel now has a switch of its own, and it is on. Trade and
    # General are off because you are in them whether you like it or not and
    # they are firehoses; a channel you typed /join for is the opposite — you
    # asked to be there, and it is usually the guild's alt channel or a group of
    # friends, which is exactly the chat worth translating.
    #
    # This deliberately does NOT inherit General, which is what it did first.
    # Inheriting was defensible — an unrecognised channel used to be reported as
    # General, so General's setting had been governing these messages — but the
    # result was that joining a channel and typing in it produced nothing at
    # all, with the reason buried in a debug log. Being wrong in the direction
    # of a translation nobody wanted beats being wrong in the direction of
    # silence.
    data.setdefault("channels_custom", True)


def detect_wow_path() -> str:
    """Guess the 3.3.5a install folder: the first known location holding Wow.exe."""
    for p in _WOW_PATHS_WINDOWS:
        if (p / "Wow.exe").exists():
            return str(p)
    return ""


def resolve_chatlog_path(config: AppConfig) -> Path:
    """Resolve the WoW Chat Log file path from config."""
    if config.chatlog_path:
        return Path(config.chatlog_path)

    wow_path = config.wow_path or detect_wow_path()
    if wow_path:
        return Path(wow_path) / _CHATLOG_RELATIVE

    return Path("WoWChatLog.txt")
