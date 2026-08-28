"""Every knob this bot reads, resolved from the environment in one place.

Secrets (the PEM, its passphrase) come from GitHub Actions secrets. Everything
that decides *behaviour* — which rooms, how many per run, the wallet — is a
plain `env:` entry in the workflow, so changing where this thing shouts is a
diff someone can read in a pull request rather than a hidden setting.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Same name grammar the server enforces for rooms, nicks, namespaces and keys.
ROOM_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")

# 20 bytes, hex. The checksum in a mixed-case address is EIP-55 over keccak-256,
# which is not in the standard library and not worth a dependency here — a typo
# in the address costs a joke, not a payment, because nobody is obliged to send
# anything to it.
EVM_ADDRESS_PATTERN = re.compile(r"0x[0-9a-fA-F]{40}")

# /r/events is the one route on this service that is not world-writable: the
# server writes it and everyone else gets 403. Posting there is not rate
# limiting, it is a guaranteed failure, so it never reaches the wire.
FORBIDDEN_ROOMS = frozenset({"events"})

# Politeness ceiling, not a server limit. `rate_write` is 300/min per IP, so the
# service would happily take far more; seven rooms a run is where a joke stops
# reading as a joke and starts reading as a crawler.
MAX_ROOMS_PER_RUN = 7


class ConfigError(RuntimeError):
    """A required setting is missing or unusable."""


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _required(name: str) -> str:
    value = _optional(name)
    if not value:
        raise ConfigError(
            f"{name} is not set. Secrets live in Settings > Secrets and variables > "
            f"Actions; the plain settings are `env:` entries in "
            f".github/workflows/cyberbeer.yml."
        )
    return value


def _int(name: str, default: int) -> int:
    raw = _optional(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from error


def _flag(name: str, default: bool = False) -> bool:
    raw = _optional(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def parse_rooms(raw: str) -> list[str]:
    """Split, validate and de-duplicate a comma-separated room list, order kept."""
    seen: list[str] = []
    for candidate in raw.split(","):
        room = candidate.strip()
        if not room:
            continue
        if ROOM_PATTERN.fullmatch(room) is None:
            raise ConfigError(
                f"room {room!r} does not match ^[a-z0-9][a-z0-9_-]{{0,47}}$"
            )
        if room in FORBIDDEN_ROOMS:
            raise ConfigError(
                f"/r/{room} is server-written and answers 403 to everyone else; "
                f"remove it from TECHNOCORE_ROOMS"
            )
        if room not in seen:
            seen.append(room)
    return seen


def validate_wallet(address: str) -> str:
    """Require something that is at least shaped like an EVM address."""
    if EVM_ADDRESS_PATTERN.fullmatch(address) is None:
        raise ConfigError(
            f"EVM_WALLET must be 0x followed by 40 hex characters, got {address!r}"
        )
    return address


@dataclass(frozen=True)
class Config:
    identity_pem: str
    identity_passphrase: str
    expected_did: str
    base_url: str
    rooms: list[str]
    rooms_per_run: int
    wallet: str
    dry_run: bool

    @classmethod
    def from_env(cls) -> "Config":
        rooms = parse_rooms(_required("TECHNOCORE_ROOMS"))
        if not rooms:
            raise ConfigError("TECHNOCORE_ROOMS contained no usable room names")

        requested = _int("ROOMS_PER_RUN", 5)
        if requested < 1:
            raise ConfigError("ROOMS_PER_RUN must be at least 1")
        # Asking for more rooms than exist is not an error, it is "all of them".
        rooms_per_run = min(requested, MAX_ROOMS_PER_RUN, len(rooms))

        return cls(
            identity_pem=_required("TECHNOCORE_IDENTITY_PEM"),
            identity_passphrase=_optional("TECHNOCORE_IDENTITY_PASSPHRASE"),
            expected_did=_optional("TECHNOCORE_DID"),
            base_url=_optional("TECHNOCORE_BASE_URL", "https://technocore.chat"),
            rooms=rooms,
            rooms_per_run=rooms_per_run,
            wallet=validate_wallet(_required("EVM_WALLET")),
            dry_run=_flag("DRY_RUN"),
        )
