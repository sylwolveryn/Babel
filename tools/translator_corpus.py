"""Chat lines for comparing translators, each with a reference translation.

The English lines are the kind of thing World, Trade and party chat on a
3.3.5a server actually say — slang, abbreviations, item links and all — plus
some plain sentences as a control. The Hungarian lines are what a player types
into the reply box. References are natural Hungarian/English renderings, not
the only right answer: chrF against them is a rough guide to compare engines
with each other, not a grade.
"""

from __future__ import annotations

#: (English chat line, reference Hungarian translation)
EN_HU: tuple[tuple[str, str], ...] = (
    ("hey can you help me with this quest please", "Szia, segítenél ebben a küldetésben, kérlek?"),
    ("where is the auction house in this city", "Hol van az aukciósház ebben a városban?"),
    ("thanks for the group, see you later", "Köszi a csapatot, később találkozunk!"),
    ("good morning everyone, raid tonight at eight", "Jó reggelt mindenkinek, ma este nyolckor raid."),
    ("anyone want to run heroic halls of lightning", "Valaki jön heroic Halls of Lightningra?"),
    ("need a tank for ICC 10, 5k gs minimum", "Tank kell ICC 10-be, minimum 5k GS."),
    ("LFM VoA 25 need healers", "Tagokat keresünk VoA 25-be, healerek kellenek."),
    ("heal 55 for RDF", "55-ös healer RDF-re."),
    ("WTS stack of frostweave cloth, pst", "Eladó egy stack Frostweave Cloth, írj suttogásban."),
    ("WTB enchanter for weapon, will tip", "Enchantert keresek fegyverre, adok borravalót."),
    ("brb 5 min, dont pull without me", "Mindjárt jövök, 5 perc, ne húzzatok nélkülem."),
    ("can someone summon me please", "Valaki megidézne, kérlek?"),
    ("the boss enrages at 20 percent, save cooldowns", "A boss 20 százaléknál bedühödik, tartsátok meg a cooldownokat."),
    ("stay out of the fire and kill the adds first", "Ne álljatok a tűzben, és először az addokat öljétek meg."),
    ("I am going to log off now, good night", "Most kilépek, jó éjszakát!"),
    ("does anyone know where the flight master is", "Tudja valaki, hol van a repülőmester?"),
    ("my bags are full, I need to sell some stuff", "Tele vannak a táskáim, el kell adnom pár dolgot."),
    ("that was a great run, well played everyone", "Ez nagyon jó run volt, szép volt mindenkinek."),
    ("sorry, I disconnected, coming back now", "Bocsi, kidobott, most jövök vissza."),
    ("guild recruiting for weekend raids, whisper me", "A céh hétvégi raidekre toboroz, írj nekem."),
    ("how much gold do you want for it", "Mennyi aranyat kérsz érte?"),
    ("i need to repair before the next pull", "Javítanom kell a következő pull előtt."),
    ("ready check, everyone ready?", "Készenléti ellenőrzés, mindenki kész?"),
    ("the dungeon finder queue is really long today", "A dungeon finder sor ma nagyon hosszú."),
    ("lol that wipe was my fault", "Lol, az a wipe az én hibám volt."),
)

#: (Hungarian reply-box line, reference English translation)
HU_EN: tuple[tuple[str, str], ...] = (
    ("Köszi a segítséget!", "Thanks for the help!"),
    ("Mindjárt jövök, várjatok egy percet.", "I'll be right back, wait a minute."),
    ("Kell még egy gyógyító a csapatba?", "Do you need another healer for the group?"),
    ("Hol van a bank ebben a városban?", "Where is the bank in this city?"),
    ("Ne húzzátok még, töltenem kell a manát.", "Don't pull yet, I need to regen mana."),
    ("Mennyiért adod ezt a kardot?", "How much are you selling this sword for?"),
    ("Jó éjszakát mindenkinek, holnap folytatjuk.", "Good night everyone, we'll continue tomorrow."),
    ("Bocsánat, nem beszélek jól angolul.", "Sorry, I don't speak English well."),
    ("Csatlakozhatok a csapatotokhoz?", "Can I join your group?"),
    ("Szép volt, gratulálok mindenkinek!", "Well done, congratulations everyone!"),
)
