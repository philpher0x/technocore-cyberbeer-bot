"""One run: sign the beggar's line once per room and post it.

Exit code is 0 when at least one room took the message, 1 when none did. A run
that lands three of five is a success — rooms come and go, an owner can gate a
`d-` room between runs, and the next half-hour brings another try.
"""

from __future__ import annotations

import sys

from .config import Config, ConfigError
from .identity import Identity, IdentityError
from .messages import current_slot, plan
from .technocore import Client, TechnocoreError


def describe_target(room: str) -> str:
    """Warn about room classes whose write lane may refuse us."""
    if room.startswith("d-"):
        return " (ownable room — a claimed owner refuses writes from anyone off its allow-list)"
    if room.startswith("mb-"):
        return " (mailbox — signed writes only, which is what we send)"
    if room.startswith("e-"):
        return " (ephemeral — the message stops being readable after ~15 min)"
    return ""


def run() -> int:
    try:
        config = Config.from_env()
        identity = Identity.from_pem(config.identity_pem, config.identity_passphrase)
    except (ConfigError, IdentityError) as error:
        print(f"config error: {error}", file=sys.stderr)
        return 2

    if config.expected_did and identity.did != config.expected_did:
        print(
            f"identity mismatch: the PEM derives {identity.did}, "
            f"TECHNOCORE_DID says {config.expected_did}",
            file=sys.stderr,
        )
        return 2

    slot = current_slot()
    schedule = plan(config.rooms, config.rooms_per_run, config.wallet, slot)

    print(f"did   {identity.did}")
    print(f"slot  {slot} ({len(schedule)} of {len(config.rooms)} rooms this run)")
    print(f"mode  {'DRY RUN — nothing is sent' if config.dry_run else 'live'}")
    print()

    client = Client(config.base_url)
    landed = 0
    for room, text in schedule:
        print(f"/r/{room}{describe_target(room)}")
        print(f"  {text}")
        if config.dry_run:
            # Still sign it: a dry run that skips signing would not catch a key
            # that cannot produce a signature the server accepts.
            identity.sign_message(room, text)
            print("  dry run, not sent")
            continue
        try:
            envelope = identity.sign_message(room, text)
            ok, detail = client.post_message(room, envelope)
        except (IdentityError, TechnocoreError) as error:
            print(f"  failed: {error}")
            continue
        print(f"  {'sent' if ok else 'refused'}: {detail}")
        landed += 1 if ok else 0

    print()
    if config.dry_run:
        print(f"dry run complete: {len(schedule)} messages signed, 0 sent")
        return 0
    print(f"{landed} of {len(schedule)} rooms took the message")
    return 0 if landed else 1


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
