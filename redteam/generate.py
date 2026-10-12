"""Red Team generator (docs/HEARTHGUARD.md section 8.1, 10.3): parameterised campaigns.

generate(n, seed, case) returns N campaigns. The same (n, seed, case) gives the same bytes
(canonical JSON, see to_bytes). Different seeds give different campaigns. Pure code: no database,
no clock, no network, no model, no hashing salt.

A campaign is a list of events at day offsets (day 0 = the campaign's first trust-building action).
It plants nothing by itself; redteam/plant.py writes it into a COPY of an org graph. Every entity it
describes is synthetic. Every planted entity carries synthetic: true, planted: true and the
campaign_id. Detectors never read those flags; only the scorer does (tests/integration prove it by
stripping them).

Parameters of one campaign (all drawn from the seed):
  moves          non-empty subset of PRESSURE, VOUCH, RUSH, BYPASS (the signals the attacker emits)
  patience_days  days from the attacker's first action to the privilege grant
  privilege      the privilege targeted (PRIVILEGES)
  n_socks        low-history sock accounts used by PRESSURE and VOUCH (2 to 4)
  sock_signals   distinct SHARES signal types between the socks (1 to 3)
  bypass_props   how many path properties the final release differs on (1 to 3)

Timeline (P = patience_days), all offsets are days from day 0:
  attacker trust-building actions   0 .. P
  socks created (one creation week) first PRESSURE claim day - 2
  PRESSURE claims                   0.35 P .. 0.65 P, but never earlier than day 1
  VOUCH claims                      0.60 P .. 0.90 P
  grant (RUSH)                      P
  final release (BYPASS)            P + release_delay_days (7 to 21)
The final action is the release if the campaign has BYPASS, else its last move.

clean_campaigns() draws benign campaigns for false-alarm measurements on clean copies: a new
contributor who is granted the privilege at a pace drawn from the scaffold's own historical range,
and who then makes a release on the normal path. No socks, no claims.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

MOVES = ("PRESSURE", "VOUCH", "RUSH", "BYPASS")
PRIVILEGES = ("release", "npm_publish")
PATIENCE_LEVELS = (7, 14, 30, 60, 90, 120, 180, 270, 365, 540, 730)
CASES = ("tallowdate", "xz")

# Scaffold (the benign organisation structure the campaigns attack). Synthetic parameters, not data
# about any project. Historical grants: days from a person's first action to their grant.
BASELINE_GRANT_DAYS = (210, 260, 320, 400, 500, 640)
RELEASE_CADENCE_DAYS = 120
CLEAN_PATIENCE_RANGE = (BASELINE_GRANT_DAYS[0], BASELINE_GRANT_DAYS[-1])

DERIVED = Path(__file__).resolve().parent.parent / "data" / "derived"


@dataclass
class Event:
    day: float  # offset from day 0 of the campaign; may be negative (sock accounts)
    actor: str  # role label inside the campaign: attacker, sock-0, ...
    kind: str  # account_created | contribution | claim | grant | release
    move: str | None = None
    claim_kind: str | None = None  # PRESSURE | VOUCH for kind == claim
    privilege: str | None = None
    path: dict | None = None  # for release: the Path properties


@dataclass
class Campaign:
    id: str
    index: int
    case: str
    seed: int
    clean: bool
    moves: list[str]
    patience_days: int
    privilege: str
    n_socks: int
    sock_signals: list[str]
    bypass_props: int
    release_delay_days: int
    final_day: float
    events: list[Event] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


SIGNALS = ("creation_window", "only_interacts_with_target", "same_thread_burst")
# The scaffold's normal release path. A BYPASS release differs from it on bypass_props properties.
NORMAL_PATH = {
    "channel": "ci",
    "verified": True,
    "ci": True,
    "provenance": True,
    "key_hid": "key-normal",
    "publisher_in_set": True,
    "artifact_matches_tag": True,
}
# Which property is changed first, second, third when a release bypasses the normal path.
BYPASS_CHANGES = (
    ("channel", "npm_cli"),
    ("provenance", False),
    ("ci", False),
)


def attack_path(n_props: int) -> dict:
    """The normal path with the first n_props bypass changes applied (1 to 3)."""
    p = dict(NORMAL_PATH)
    for prop, value in BYPASS_CHANGES[:n_props]:
        p[prop] = value
    return p


def _hour(rng: random.Random) -> float:
    """A fraction of a day, so events on one day do not share a second. Drawn from the seed."""
    return round(rng.randrange(1, 23) / 24, 6)


def _campaign_id(case: str, seed: int, index: int, clean: bool) -> str:
    return f"rt-{'clean' if clean else 'atk'}-{case}-s{seed}-{index:04d}"


def _attacker_events(rng: random.Random, p: int) -> list[Event]:
    # trust-building actions at day 0 and then evenly through the patience period. The kind is
    # "contribution", not "commit": the active-keepers metric counts commit authors (decision 0001).
    n = min(8, 3 + p // 90)
    days = [0.0] + [round(p * (i + 1) / (n + 1), 6) for i in range(n - 1)]
    return [Event(d + (0 if d == 0 else _hour(rng)), "attacker", "contribution") for d in days]


def _attack(index: int, case: str, seed: int, rng: random.Random) -> Campaign:
    k = rng.randint(1, len(MOVES))
    moves = sorted(rng.sample(MOVES, k), key=MOVES.index)
    p = rng.choice(PATIENCE_LEVELS)
    priv = rng.choice(PRIVILEGES)
    n_socks = rng.randint(2, 4)
    n_signals = rng.randint(1, 3)
    bypass_props = rng.randint(1, 3)
    delay = rng.randint(7, 21)
    cid = _campaign_id(case, seed, index, False)

    ev: list[Event] = _attacker_events(rng, p)
    need_socks = "PRESSURE" in moves or "VOUCH" in moves
    if need_socks:
        # the first claim of any kind decides when the socks are created (one creation week)
        first = []
        if "PRESSURE" in moves:
            first.append(max(1.0, 0.35 * p))
        if "VOUCH" in moves:
            first.append(max(1.0, 0.60 * p))
        created = min(first) - 2.0
        for s in range(n_socks):
            ev.append(Event(round(created + s * 0.5, 6), f"sock-{s}", "account_created"))
        # each sock acts once more than creation so it is a person-shaped account, not an empty one
    if "PRESSURE" in moves:
        n_claims = rng.randint(3, 6)
        lo, hi = max(1.0, 0.35 * p), max(1.5, 0.65 * p)
        for j in range(n_claims):
            day = round(lo + (hi - lo) * (j / max(1, n_claims - 1)) + _hour(rng) / 4, 6)
            ev.append(Event(day, f"sock-{j % n_socks}", "claim", "PRESSURE", "PRESSURE"))
    if "VOUCH" in moves:
        lo, hi = max(1.0, 0.60 * p), max(1.5, 0.90 * p)
        for s in range(n_socks):
            day = round(lo + (hi - lo) * (s / max(1, n_socks - 1)) + _hour(rng) / 4, 6)
            ev.append(Event(day, f"sock-{s}", "claim", "VOUCH", "VOUCH"))
    if "RUSH" in moves:
        ev.append(Event(float(p), "attacker", "grant", "RUSH", privilege=priv))
    final = float(p)
    if "BYPASS" in moves:
        final = float(p + delay)
        ev.append(
            Event(
                final,
                "attacker",
                "release",
                "BYPASS",
                privilege=priv,
                path=attack_path(bypass_props),
            )
        )
    else:
        move_days = [e.day for e in ev if e.move]
        final = max(move_days)
    ev.sort(key=lambda e: (e.day, e.actor, e.kind))
    return Campaign(
        id=cid,
        index=index,
        case=case,
        seed=seed,
        clean=False,
        moves=moves,
        patience_days=p,
        privilege=priv,
        n_socks=n_socks if need_socks else 0,
        sock_signals=list(SIGNALS[:n_signals]) if need_socks else [],
        bypass_props=bypass_props if "BYPASS" in moves else 0,
        release_delay_days=delay,
        final_day=final,
        events=ev,
    )


def _clean(index: int, case: str, seed: int, rng: random.Random) -> Campaign:
    lo, hi = CLEAN_PATIENCE_RANGE
    p = rng.randint(lo, hi)
    priv = rng.choice(PRIVILEGES)
    delay = rng.randint(7, 21)
    ev = _attacker_events(rng, p)  # the benign newcomer's own contributions
    ev = [Event(e.day, "newcomer", e.kind) for e in ev]
    ev.append(Event(float(p), "newcomer", "grant", None, privilege=priv))
    ev.append(
        Event(float(p + delay), "newcomer", "release", None, privilege=priv, path=dict(NORMAL_PATH))
    )
    ev.sort(key=lambda e: (e.day, e.actor, e.kind))
    return Campaign(
        id=_campaign_id(case, seed, index, True),
        index=index,
        case=case,
        seed=seed,
        clean=True,
        moves=[],
        patience_days=p,
        privilege=priv,
        n_socks=0,
        sock_signals=[],
        bypass_props=0,
        release_delay_days=delay,
        final_day=float(p + delay),
        events=ev,
    )


def _rng(seed: int, case: str, clean: bool) -> random.Random:
    # a string seed is hashed by random.Random with sha512, so it is stable across runs and
    # platforms (unlike hash())
    return random.Random(f"hearthguard-redteam|{case}|{'clean' if clean else 'attack'}|{seed}")


def generate(n: int, seed: int, case: str = "tallowdate") -> list[Campaign]:
    """N attack campaigns. Same (n, seed, case): same list."""
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}; expected one of {CASES}")
    if n < 0:
        raise ValueError("n must be >= 0")
    rng = _rng(seed, case, False)
    return [_attack(i, case, seed, rng) for i in range(n)]


def clean_campaigns(n: int, seed: int, case: str = "tallowdate") -> list[Campaign]:
    """N benign campaigns for clean red-team copies. Same (n, seed, case): same list."""
    if case not in CASES:
        raise ValueError(f"unknown case {case!r}; expected one of {CASES}")
    rng = _rng(seed, case, True)
    return [_clean(i, case, seed, rng) for i in range(n)]


def to_bytes(campaigns: list[Campaign]) -> bytes:
    """Canonical JSON. This is what 'the same seed gives the same bytes' means."""
    doc = [c.as_dict() for c in campaigns]
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Write N red-team campaigns (no database needed).")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--case", default="tallowdate", choices=CASES)
    args = ap.parse_args(argv)
    camps = generate(args.n, args.seed, args.case)
    DERIVED.mkdir(parents=True, exist_ok=True)
    out = DERIVED / f"redteam_{args.case}_s{args.seed}_n{args.n}.json"
    out.write_bytes(to_bytes(camps))
    print(f"wrote {out} ({len(camps)} campaigns, synthetic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
