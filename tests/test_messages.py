"""The two things that decide behaviour: what gets said, and where."""

from __future__ import annotations

import pytest

from cyberbeer.identity import MAX_MESSAGE_CHARS, normalize_text
from cyberbeer.messages import (
    CANONICAL_EN,
    CANONICAL_RU,
    LANGUAGES,
    SECONDS_PER_SLOT,
    VARIANTS,
    choose_rooms,
    compose,
    current_slot,
    plan,
)

WALLET = "0x1234567890abcdef1234567890abcdef12345678"
ROOMS = ["lobby", "meta", "flop", "faucet", "flop-collective", "cryptoonflop", "tekno", "shadow"]


@pytest.mark.parametrize(
    ("language", "canonical", "other"),
    (("ru", CANONICAL_RU, CANONICAL_EN), ("en", CANONICAL_EN, CANONICAL_RU)),
)
@pytest.mark.parametrize("slot", range(len(VARIANTS) * 2))
def test_every_request_has_exactly_one_language(language, canonical, other, slot):
    text = compose(WALLET, slot, index=0, language=language)
    assert text.count(canonical) == 1
    assert other not in text
    assert WALLET in text


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("slot", range(len(VARIANTS) * 2))
def test_every_variant_survives_the_servers_single_line_sweep(language, slot):
    """A message that changes under normalization would be signed as one thing
    and stored as another. Compose must already produce the stored bytes."""
    text = compose(WALLET, slot, index=0, language=language)
    assert normalize_text(text) == text
    assert len(text) <= MAX_MESSAGE_CHARS


def test_three_rooms_get_two_separate_requests_each():
    schedule = plan(ROOMS, 3, WALLET, slot=0)
    chosen = choose_rooms(ROOMS, 3, slot=0)

    assert len(schedule) == 6
    assert [room for room, _ in schedule] == [
        room for room in chosen for _ in LANGUAGES
    ]
    for offset in range(0, len(schedule), 2):
        russian = schedule[offset][1]
        english = schedule[offset + 1][1]
        assert CANONICAL_RU in russian
        assert CANONICAL_EN not in russian
        assert CANONICAL_EN in english
        assert CANONICAL_RU not in english


def test_wording_moves_between_rooms_in_one_run():
    schedule = plan(ROOMS, 3, WALLET, slot=0)
    assert len({text for _, text in schedule[::2]}) == 3
    assert len({text for _, text in schedule[1::2]}) == 3


def test_a_run_never_repeats_a_room():
    for slot in range(20):
        chosen = choose_rooms(ROOMS, 3, slot)
        assert len(chosen) == 3
        assert len(set(chosen)) == 3


def test_rotation_covers_every_room_before_repeating_the_cycle():
    """Three of eight per run must reach all eight, not orbit the first three."""
    seen = set()
    for slot in range(8):
        seen.update(choose_rooms(ROOMS, 3, slot))
    assert seen == set(ROOMS)


def test_asking_for_more_rooms_than_exist_gives_all_of_them():
    assert sorted(choose_rooms(["lobby", "meta"], 7, slot=3)) == ["lobby", "meta"]


def test_empty_room_list_plans_nothing():
    assert plan([], 3, WALLET, slot=1) == []


def test_slot_advances_once_per_half_hour():
    # Aligned to a slot boundary, so "one second before the next slot" really is.
    base = float((1_700_000_000 // SECONDS_PER_SLOT) * SECONDS_PER_SLOT)
    assert current_slot(base) == current_slot(base + SECONDS_PER_SLOT - 1)
    assert current_slot(base + SECONDS_PER_SLOT) == current_slot(base) + 1
