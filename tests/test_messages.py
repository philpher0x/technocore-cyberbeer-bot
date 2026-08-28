"""The two things that decide behaviour: what gets said, and where."""

from __future__ import annotations

import pytest

from cyberbeer.identity import MAX_MESSAGE_CHARS, normalize_text
from cyberbeer.messages import (
    CANONICAL,
    SECONDS_PER_SLOT,
    VARIANTS,
    choose_rooms,
    compose,
    current_slot,
    plan,
)

WALLET = "0x1234567890abcdef1234567890abcdef12345678"
ROOMS = ["lobby", "meta", "flop", "faucet", "flop-collective", "cryptoonflop", "tekno", "shadow"]


@pytest.mark.parametrize("slot", range(len(VARIANTS) * 2))
def test_every_variant_carries_the_line_and_the_wallet(slot):
    text = compose(WALLET, slot)
    assert CANONICAL in text
    assert WALLET in text


@pytest.mark.parametrize("slot", range(len(VARIANTS) * 2))
def test_every_variant_survives_the_servers_single_line_sweep(slot):
    """A message that changes under normalization would be signed as one thing
    and stored as another. Compose must already produce the stored bytes."""
    text = compose(WALLET, slot)
    assert normalize_text(text) == text
    assert len(text) <= MAX_MESSAGE_CHARS


def test_wording_moves_between_rooms_in_one_run():
    texts = [text for _, text in plan(ROOMS, 5, WALLET, slot=0)]
    assert len(set(texts)) == 5


def test_a_run_never_repeats_a_room():
    for slot in range(20):
        chosen = choose_rooms(ROOMS, 5, slot)
        assert len(chosen) == 5
        assert len(set(chosen)) == 5


def test_rotation_covers_every_room_before_repeating_the_cycle():
    """Five of eight per run must reach all eight, not orbit the first five."""
    seen = set()
    for slot in range(8):
        seen.update(choose_rooms(ROOMS, 5, slot))
    assert seen == set(ROOMS)


def test_asking_for_more_rooms_than_exist_gives_all_of_them():
    assert sorted(choose_rooms(["lobby", "meta"], 7, slot=3)) == ["lobby", "meta"]


def test_empty_room_list_plans_nothing():
    assert plan([], 5, WALLET, slot=1) == []


def test_slot_advances_once_per_half_hour():
    # Aligned to a slot boundary, so "one second before the next slot" really is.
    base = float((1_700_000_000 // SECONDS_PER_SLOT) * SECONDS_PER_SLOT)
    assert current_slot(base) == current_slot(base + SECONDS_PER_SLOT - 1)
    assert current_slot(base + SECONDS_PER_SLOT) == current_slot(base) + 1
