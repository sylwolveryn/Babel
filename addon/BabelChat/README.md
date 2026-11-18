# BabelChat

Chat in a language you don't read, translated where you're already looking.

This build is for the **World of Warcraft 3.3.5a (WotLK, build 12340)** client.

## On its own

Install it and play. Nothing to configure, no account, no key.

Gaming terms get their meaning appended in grey on the same line:

```
lfm icc 25 need heal    lfm = Tagokat keresünk · icc = Icecrown Citadel · heal = Gyógyító
```

**367 terms**, glossed in Hungarian by default or in English if you pick it in
`/babel config`. The addon's own panel and messages follow the same choice, not
the client's language.

## With the companion app

For whole sentences rather than terms, run the free companion app from
<https://github.com/Yumash/BabelChat>. It reads this addon's chat buffer out of
the game's memory and shows translations in an overlay above WoW — reading
only, no injection, no automation. The addon on its own needs none of it.

While the app is running the addon stays quiet, so the same message is not
answered twice in different words. Turn on "show the gloss even when the app is
running" in `/babel config` if you want both.

## Commands

| Command | What it does |
|---|---|
| `/babel` | help |
| `/babel config` | settings panel (Interface > AddOns > BabelChat) |
| `/babel on` / `off` | glossary on or off |
| `/babel test` | try it on a sample message |
| `/babel companion` | companion buffer status |
| `/babel log on` / `off` | chat logging to a file |

## Credits

The glossary began as [WoW Translator](https://www.curseforge.com/wow/addons/wow-translator)
by **Pirson** (MIT). BabelChat added slang, rewrote the matching engine, and
built the companion app.

- **Pirson** — glossary data and the in-game translation idea
- **Andrey Yumashev** — addon, companion app, translation engine
- **AhegaoZKun** — Linux/Wayland support

MIT License. Full description and privacy notes:
<https://github.com/Yumash/BabelChat>
