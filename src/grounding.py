"""Numeric grounding check: every number an agent writes must exist in the data it was given.

Extracts percentages and dollar amounts from agent text and looks for a matching value
(within rounding tolerance) in the toolbox output. Ungrounded numbers are flagged in the UI.
"""
import re

NUM = re.compile(r"(?P<dollar>\$\s?)?(?P<num>-?\d[\d,]*\.?\d*)\s?(?P<pct>%)?(?P<k>k\b)?", re.I)


def _collect(obj, out):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, out)
    elif isinstance(obj, str):
        for m in NUM.finditer(obj):
            try:
                out.add(float(m.group("num").replace(",", "")))
            except ValueError:
                pass


def _texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)


def check(agent_output, *sources):
    known = set()
    for s in sources:
        _collect(s, known)
    candidates = known | {k * 100 for k in known} | {abs(k) for k in known} | {abs(k) * 100 for k in known}
    flagged, total = [], 0
    for text in _texts(agent_output):
        for m in NUM.finditer(text):
            raw = m.group("num").replace(",", "")
            if not (m.group("pct") or m.group("dollar")):
                continue  # only check percentages and dollar figures
            try:
                v = abs(float(raw)) * (1000 if m.group("k") else 1)
            except ValueError:
                continue
            total += 1
            tol = 0.6 if m.group("pct") else max(1.0, v * 0.01)
            if not any(abs(v - c) <= tol for c in candidates):
                flagged.append(m.group(0).strip())
    # "unmatched" counts every occurrence (same basis as "summary"); "ungrounded" lists the distinct values
    return {"checked": total, "unmatched": len(flagged), "ungrounded": sorted(set(flagged)),
            "summary": f"{total - len(flagged)}/{total} figures traced to data" if total else "no figures cited"}
