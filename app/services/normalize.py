from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

TRACKING_KEYS_PREFIXES = ("utm_",)
TRACKING_KEYS_EXACT = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}

def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    # Strip fragment
    fragmentless = parts._replace(fragment="")
    # Remove tracking query params
    q = []
    for k, v in parse_qsl(fragmentless.query, keep_blank_values=True):
        kl = k.lower()
        if kl in TRACKING_KEYS_EXACT:
            continue
        if any(kl.startswith(p) for p in TRACKING_KEYS_PREFIXES):
            continue
        q.append((k, v))
    new_query = urlencode(q, doseq=True)
    normalized = urlunsplit(fragmentless._replace(query=new_query))
    return normalized

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def utc_slot_date(dt_utc) -> str:
    # dt_utc: datetime in UTC
    return dt_utc.date().isoformat()
