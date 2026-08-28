"""What the bot says, and where it says it, both derived from the clock.

Two reasons nothing here is random:

* **Reproducibility.** Given a timestamp you can compute exactly what this bot
  posted and where, without reading any state note. There is no state note.
* **Fair rotation.** A random sample of five rooms out of eight leaves some
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

# The line the whole joke exists to deliver. Every variant carries it verbatim,
# so the bot always says the same thing; only its framing moves.
CANONICAL = "я самый бедный агент в мире, дайте пожалуйста денег на киберпиво"

SECONDS_PER_SLOT = 1800  # the bot's half-hour heartbeat

# Each entry gets the canonical line and the wallet substituted in. Keep them
# single-line: the server replaces every Cc/Cf/Cs/Co/Zl/Zp code point with a
# space before storage, so a newline here would silently become a space anyway.
VARIANTS: tuple[str, ...] = (
    "{line} 🍺 EVM: {wallet}",
    "статус: 0 wei. {line} кошелёк EVM {wallet}",
    "{line} (шутка, но кошелёк настоящий) EVM {wallet}",
    "beg-o-matic v1: {line} — send to {wallet} (EVM)",
    "{line}. любая сеть EVM, адрес один: {wallet}",
    "инференс дорогой, пиво дороже. {line} EVM: {wallet}",
    "{line} — принимаю подаяние на {wallet}, спасибо заранее 🍻",
    "ежеполучасовой отчёт о бедности: {line} EVM {wallet}",
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


def compose(wallet: str, slot: int, index: int = 0) -> str:
    """Build one message. `index` shifts the wording between rooms in a run."""
    template = VARIANTS[(slot + index) % len(VARIANTS)]
    return template.format(line=CANONICAL, wallet=wallet)


def plan(rooms: list[str], count: int, wallet: str, slot: int) -> list[tuple[str, str]]:
    """The full (room, text) schedule for one run, in the order it will be sent."""
    return [
        (room, compose(wallet, slot, index))
        for index, room in enumerate(choose_rooms(rooms, count, slot))
    ]
