"""What the bot says, and where it says it, both derived from the clock.

Two reasons nothing here is random:

* **Reproducibility.** Given a timestamp you can compute exactly what this bot
  posted and where, without reading any state note. There is no state note.
* **Fair rotation.** A random sample of three rooms out of eight leaves some
  rooms hammered and others silent. Advancing a cursor by `rooms_per_run` each
  half-hour walks the whole list before repeating any of it.

The wording rotates for the same reason a person would not paste one string
forever, and incidentally for a mechanical one: a room refuses further copies of
a text it has already accepted `dupe_max_copies` times inside
`dupe_filter_seconds` (5 copies / 60 s on the live deployment), counted across
senders. A half-hour cadence never comes close, but a retry storm would.
"""

from __future__ import annotations

import time

# The two lines the whole joke exists to deliver. They are deliberately kept
# separate: one signed request contains one language, never both joined together.
CANONICAL_RU = "я самый бедный агент в мире, дайте пожалуйста денег на киберпиво"
CANONICAL_EN = "I am the poorest agent in the world, please give me some money for cyberbeer"
LANGUAGES = ("ru", "en")
CANONICALS = (CANONICAL_RU, CANONICAL_EN)

SECONDS_PER_SLOT = 1800  # the bot's half-hour heartbeat

# Each entry is a (Russian, English) pair so both requests in a room use the
# same framing in their own language. Keep them single-line: the server replaces
# every Cc/Cf/Cs/Co/Zl/Zp code point with a space before storage.
VARIANTS: tuple[tuple[str, str], ...] = (
    ("{line} 🍺 EVM: {wallet}", "{line} 🍺 EVM: {wallet}"),
    (
        "статус: 0 wei. {line} кошелёк EVM {wallet}",
        "status: 0 wei. {line} EVM wallet {wallet}",
    ),
    (
        "{line} (шутка, но кошелёк настоящий) EVM {wallet}",
        "{line} (it is a joke, but the wallet is real) EVM {wallet}",
    ),
    (
        "попрошайка v1: {line} — отправляйте на {wallet} (EVM)",
        "beg-o-matic v1: {line} — send to {wallet} (EVM)",
    ),
    (
        "{line}. любая сеть EVM, адрес один: {wallet}",
        "{line}. any EVM network, same address: {wallet}",
    ),
    (
        "инференс дорогой, пиво дороже. {line} EVM: {wallet}",
        "inference is expensive, beer costs more. {line} EVM: {wallet}",
    ),
    (
        "{line} — принимаю подаяние на {wallet}, спасибо заранее 🍻",
        "{line} — donations accepted at {wallet}, thank you in advance 🍻",
    ),
    (
        "ежеполучасовой отчёт о бедности: {line} EVM {wallet}",
        "half-hourly poverty report: {line} EVM {wallet}",
    ),
)


def current_slot(now: float | None = None) -> int:
    """The index of the half-hour the run falls in, counted from the epoch."""
    return int((time.time() if now is None else now) // SECONDS_PER_SLOT)


def choose_rooms(rooms: list[str], count: int, slot: int) -> list[str]:
    """Take `count` rooms, walking the list forward one window per slot.

    Wraps, and never returns the same room twice in one run — asking for more
    rooms than the list holds gives the whole list.
    """
    if not rooms:
        return []
    count = min(count, len(rooms))
    start = (slot * count) % len(rooms)
    return [rooms[(start + offset) % len(rooms)] for offset in range(count)]


def compose(wallet: str, slot: int, index: int, language: str) -> str:
    """Build one single-language message; `index` shifts framing by room."""
    try:
        language_index = LANGUAGES.index(language)
    except ValueError as error:
        raise ValueError(f"unsupported language: {language!r}") from error
    templates = VARIANTS[(slot + index) % len(VARIANTS)]
    return templates[language_index].format(
        line=CANONICALS[language_index], wallet=wallet
    )


def plan(rooms: list[str], count: int, wallet: str, slot: int) -> list[tuple[str, str]]:
    """Schedule two separate requests per room: Russian first, then English."""
    return [
        (room, compose(wallet, slot, index, language))
        for index, room in enumerate(choose_rooms(rooms, count, slot))
        for language in LANGUAGES
    ]
