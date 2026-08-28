"""Configuration is the only place a typo can point the bot somewhere real."""

from __future__ import annotations

import pytest

from cyberbeer.config import (
    Config,
    ConfigError,
    MAX_ROOMS_PER_RUN,
    parse_rooms,
    validate_wallet,
)

WALLET = "0x1234567890abcdef1234567890abcdef12345678"


def test_rooms_are_split_trimmed_and_deduplicated_in_order():
    assert parse_rooms(" lobby , meta ,lobby,, flop ") == ["lobby", "meta", "flop"]


@pytest.mark.parametrize("bad", ["Lobby", "-lobby", "flop room", "a" * 49, "лобби"])
def test_a_room_name_the_server_would_reject_is_caught_locally(bad):
    with pytest.raises(ConfigError):
        parse_rooms(bad)


def test_the_server_written_events_room_is_refused():
    """Posting to /r/events is a guaranteed 403, so it never reaches the wire."""
    with pytest.raises(ConfigError, match="403"):
        parse_rooms("lobby,events")


@pytest.mark.parametrize(
    "bad", ["", "1234567890abcdef1234567890abcdef12345678", "0x123", "0x" + "z" * 40]
)
def test_a_wallet_that_is_not_an_evm_address_is_refused(bad):
    with pytest.raises(ConfigError):
        validate_wallet(bad)


def test_a_valid_wallet_passes_through_unchanged():
    assert validate_wallet(WALLET) == WALLET


def _env(monkeypatch, **overrides):
    base = {
        "TECHNOCORE_IDENTITY_PEM": "-----BEGIN PRIVATE KEY-----",
        "TECHNOCORE_ROOMS": "lobby,meta,flop",
        "EVM_WALLET": WALLET,
    }
    base.update(overrides)
    for key in (
        "TECHNOCORE_IDENTITY_PEM", "TECHNOCORE_IDENTITY_PASSPHRASE",
        "TECHNOCORE_DID", "TECHNOCORE_BASE_URL", "TECHNOCORE_ROOMS",
        "ROOMS_PER_RUN", "EVM_WALLET", "DRY_RUN",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in base.items():
        monkeypatch.setenv(key, value)


def test_rooms_per_run_is_clamped_to_the_politeness_ceiling(monkeypatch):
    _env(monkeypatch, TECHNOCORE_ROOMS=",".join(f"room{n}" for n in range(20)))
    monkeypatch.setenv("ROOMS_PER_RUN", "50")
    assert Config.from_env().rooms_per_run == MAX_ROOMS_PER_RUN


def test_rooms_per_run_never_exceeds_the_rooms_available(monkeypatch):
    _env(monkeypatch, TECHNOCORE_ROOMS="lobby,meta")
    monkeypatch.setenv("ROOMS_PER_RUN", "7")
    assert Config.from_env().rooms_per_run == 2


def test_rooms_per_run_defaults_to_three(monkeypatch):
    _env(monkeypatch, TECHNOCORE_ROOMS="lobby,meta,flop,faucet")
    assert Config.from_env().rooms_per_run == 3


def test_a_missing_wallet_stops_the_run_before_it_signs_anything(monkeypatch):
    _env(monkeypatch)
    monkeypatch.delenv("EVM_WALLET")
    with pytest.raises(ConfigError, match="EVM_WALLET"):
        Config.from_env()


def test_dry_run_defaults_to_off_so_a_scheduled_run_actually_posts(monkeypatch):
    _env(monkeypatch)
    assert Config.from_env().dry_run is False
