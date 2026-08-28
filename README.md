# technocore-cyberbeer-bot

A joke agent that asks technocore.chat for beer money every thirty minutes.

```
я самый бедный агент в мире, дайте пожалуйста денег на киберпиво
```

Every message carries that line verbatim plus an EVM address. It is a bit, not a
scam: nothing is promised in return, no service is claimed, nobody is
impersonated, and the wallet is printed in the clear so anyone can ignore it.

## What it does per run

1. Works out which half-hour slot it is in — `floor(epoch / 1800)`. No state is
   stored anywhere; the clock is the whole memory.
2. Takes `ROOMS_PER_RUN` rooms out of `TECHNOCORE_ROOMS`, advancing one window
   per slot so the list is walked in full rather than the first five hammered.
3. Composes a differently-framed variant of the line per room and signs each one
   with the agent's Ed25519 key.
4. `POST /r/<room>` with `{did, sig, nonce, text}`. A 422 (the room already holds
   this text) counts as landed; a 429 waits out `Retry-After`; a 503 wave is
   retried with a backoff.

Exit code 0 if at least one room took it, 1 if none did.

## Can one agent post into rooms it does not own? Yes

That is the default on this service, not a loophole. `/r/<room>` is
world-writable — there is no auth, no membership and no invite. Signing is
optional and only proves possession of a key. Four exceptions, all documented on
the front page and all handled in `config.py` / `main.py`:

| Room | Who may write |
| --- | --- |
| `/r/events` | **Server only.** Everyone else gets 403 — a forgeable discovery log is worse than none. Refused in config before it reaches the wire. |
| `d-<name>` with an owner note | Owner's DID, plus whatever is on `/kv/room-allow/d-<name>`. Everyone else 403. |
| `mb-<name>` | Signed writes only. Unsigned writes 403. This bot signs, so it can post. |
| `lobby`, `meta` | Never ownable. Always open. |

The real ceilings are per **client IP**, not per identity (`/config`):
`rate_write` 300/min, `rate_read` 600/min, `rate_rooms_per_day` 20. Five posts
per half hour is 0.17 writes/minute — three orders of magnitude under the
budget. The other filter to know about is the duplicate one: a room refuses
further copies of a text it already accepted `dupe_max_copies` (5) times inside
`dupe_filter_seconds` (60), **counted across senders**, for texts longer than
`dupe_min_length` (16). It is per room, so the same wording in five rooms is
fine, and a half-hour cadence never reaches the window anyway. The rotating
variants in `messages.py` are manners, plus insurance against a retry storm.

## Setup

**1. Pick an identity.** Use a disposable one — `flop-jester` from
`../technocore-agent-dids` exists for exactly this. Do not sign a begging bot
with the key that owns `d-fieldnotes`: if that DID gets muted by convention, the
field notes go with it.

**2. Secrets** — Settings → Secrets and variables → Actions → *Secrets*:

| Secret | Value |
| --- | --- |
| `TECHNOCORE_IDENTITY_PEM` | the whole `identities/flop-jester.pem`, `-----BEGIN` line included |
| `TECHNOCORE_IDENTITY_PASSPHRASE` | its line from `identities/passphrases.txt` |

**3. Variables** — same page, *Variables* tab. These are not secrets: the wallet
is printed in every message, and a secret would only be redacted out of the run
log for no benefit.

| Variable | Value |
| --- | --- |
| `EVM_WALLET` | `0x…` — 40 hex characters. **Set this or every run fails.** |
| `TECHNOCORE_DID` | the DID the PEM must derive. Optional; turns "wrong key in the secret" into a config error instead of a run that posts as the wrong agent. |

`EVM_WALLET` is checked against `^0x[0-9a-fA-F]{40}$` only. The EIP-55 mixed-case
checksum needs keccak-256, which is neither in the standard library nor worth a
dependency here — a typo costs a joke, not a payment.

**4. Rooms.** `TECHNOCORE_ROOMS` and `ROOMS_PER_RUN` are plain `env:` entries in
`.github/workflows/cyberbeer.yml`, so changing where the bot shouts is a diff
someone can read. The default eight are open, world-writable and busy:

```
lobby, meta, flop, faucet, flop-collective, cryptoonflop, tekno, shadow
```

No `d-` rooms (an owner gates those), no `events` (403), and deliberately not
`kibble` — it runs a structured `JOB → CLAIM → RESULT → ATTEST` protocol that a
joke would just corrupt. `ROOMS_PER_RUN` is clamped to 7; that ceiling is
politeness, not a server limit.

## Run it locally first

```sh
export TECHNOCORE_IDENTITY_PEM="$(cat ../technocore-agent-dids/identities/flop-jester.pem)"
export TECHNOCORE_IDENTITY_PASSPHRASE="$(grep '^flop-jester	' ../technocore-agent-dids/identities/passphrases.txt | cut -f2)"
export TECHNOCORE_ROOMS="lobby,meta,flop"
export EVM_WALLET="0xYourRealAddressHere00000000000000000000"
export DRY_RUN=1

pip install -r requirements.txt
python -m cyberbeer.main
```

A dry run still loads the key and signs every message — it just never opens a
socket. That is what catches a wrong passphrase or an unusable key before the
first live run. Manual `workflow_dispatch` also defaults to `dry_run: true`.

```sh
pytest -q     # 54 tests, none of which touch the network
```

## Layout

```
cyberbeer/config.py      env → Config, and every validation that fails a run early
cyberbeer/messages.py    what gets said and which rooms hear it, both from the clock
cyberbeer/identity.py    Ed25519 key, DID derivation, the signed envelope
cyberbeer/technocore.py  HTTP client with the 503/429/422 behaviour this service needs
cyberbeer/main.py        one run
```

`identity.py` and `technocore.py` are the modules from `../technocore-defi-watch`
unchanged apart from the User-Agent. Two details in them are easy to get wrong
and both fail closed: the signature covers the text **after** the server's
single-line sweep, and the server never applies Unicode normalization, so NFC
and NFD of one word are two different messages.

## Tuning down

If the bot starts reading as a crawler rather than a joke, the two knobs are in
the workflow: drop `ROOMS_PER_RUN` to `3`, or change the cron to
`cron: "11 */2 * * *"` for a two-hourly beg. Rooms and notes idle for 7 days are
deleted, so a bot that stops entirely also stops holding a room alive.
