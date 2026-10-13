"""Finance pack source parsers (spec §4.2 thing 1): synthetic email, chat, vendor portal, ERP log.

Each parser turns one raw record into plain dicts. Identifiers are hashed here, on ingest (spec
§1 R6): an email address goes in, `hid` comes out, and the address is dropped. Message and chat
text is kept only as `text`, for the Reader; no name or address is copied into an output field.

The salt comes from the environment when it is set (core/graph/hashing.py). When it is not, the
fixed SYNTHETIC_SALT below is used. That is safe only because every identifier in this pack is an
invented `.example` address; it protects nothing real, and it is not a secret.

Time: records carry ISO dates in UTC; outputs carry whole epoch seconds.
"""

from datetime import UTC, datetime

from core.graph.hashing import MissingSaltError, identifier_hash, load_salt

SYNTHETIC_SALT = b"northbridge-synthetic-case-not-a-secret"

PLACE_INBOX = {"ref": "northbridge:inbox:ap", "kind": "list"}
PLACE_PORTAL = {"ref": "northbridge:portal:vendors", "kind": "portal"}
PLACE_ERP = {"ref": "northbridge:erp:log", "kind": "tracker"}


def chat_place(channel: str) -> dict:
    return {"ref": f"northbridge:chat:{channel}", "kind": "chat"}


def default_salt() -> bytes:
    """The environment salt if one is configured, else the synthetic one (see module comment)."""
    try:
        return load_salt()
    except MissingSaltError:
        return SYNTHETIC_SALT


def to_epoch(date_utc: str) -> int:
    return int(datetime.fromisoformat(date_utc.replace("Z", "+00:00")).astimezone(UTC).timestamp())


def hid(address: str, salt: bytes) -> str:
    """Hash of a lower-cased address. Same input and salt always give the same hid."""
    return identifier_hash(address.strip().lower(), salt=salt)


def _common(rec: dict, source: str) -> dict:
    return {
        "ref": f"northbridge:{source}:{rec['id']}",
        "source": source,
        "at": to_epoch(rec["date"]),
        "synthetic": rec["synthetic"],
        "planted": rec["planted"],
        "campaign_id": rec["campaign_id"],
        "vendor": rec.get("vendor"),
    }


def parse_email(rec: dict, salt: bytes) -> dict:
    """An email is an Action by its sender. Everyone on it can see the inbox thread."""
    out = _common(rec, "email")
    out.update(
        kind="email",
        hid=hid(rec["sender"], salt),
        seen_by=sorted({hid(a, salt) for a in [*rec["to"], *rec["cc"]]}),
        place=PLACE_INBOX,
        text=rec["subject"] + "\n" + rec["body"],
    )
    return out


def parse_chat(rec: dict, salt: bytes) -> dict:
    out = _common(rec, "chat")
    out.update(
        kind="chat",
        hid=hid(rec["user"], salt),
        seen_by=[],
        place=chat_place(rec["channel"]),
        text=rec["text"],
    )
    return out


def parse_portal(rec: dict, salt: bytes) -> dict:
    out = _common(rec, "portal")
    out.update(
        kind="portal_event",
        hid=hid(rec["user"], salt),
        seen_by=[],
        place=PLACE_PORTAL,
        event=rec["event"],
    )
    return out


def parse_erp(rec: dict, salt: bytes) -> dict:
    """An ERP entry is one of: grant, bank_change, policy, leave. Returns {'entry': ..., ...}."""
    entry = rec["entry"]
    base = _common(rec, "erp")
    base.update(entry=entry, place=PLACE_ERP)
    if entry == "grant":
        base.update(
            hid=hid(rec["actor"], salt),
            by_hid=hid(rec["by"], salt),
            privilege=rec["privilege"],
        )
    elif entry == "bank_change":
        base.update(
            kind="bank_change",
            hid=hid(rec["actor"], salt),
            channel=rec["channel"],
            callback=bool(rec["callback_logged"]),
            approvers=int(rec["approvers_required"]),
            approved_by=sorted(hid(a, salt) for a in rec["approved_by"]),
        )
    elif entry == "policy":
        base.update(
            privilege=rec["privilege"],
            approvers_required=int(rec["approvers_required"]),
            holders=sorted(hid(a, salt) for a in rec["holders"]),
        )
    elif entry == "leave":
        base.update(hid=hid(rec["actor"], salt), until=to_epoch(rec["until"]))
    else:
        raise ValueError(f"unknown ERP entry {entry!r}")
    return base


PARSERS = {
    "email": parse_email,
    "chat": parse_chat,
    "portal": parse_portal,
    "erp": parse_erp,
}


def parse_records(records: list[dict], salt: bytes | None = None) -> list[dict]:
    """Parse every raw record. Order follows the input. An unknown source is an error."""
    salt = salt if salt is not None else default_salt()
    out = []
    for rec in records:
        parser = PARSERS.get(rec["source"])
        if parser is None:
            raise ValueError(f"unknown finance source {rec['source']!r}")
        out.append(parser(rec, salt))
    return out
