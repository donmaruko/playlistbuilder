"""Remember what each playlist looked like after our last run, so edits made by hand are noticed."""
import collections
import json

CAP = 60


def _label(t):
    return f"{t['artists'][0]} - {t['name']}"


def summary(tracks):
    counts = collections.Counter(t["artists"][0] for t in tracks)
    return json.dumps(counts.most_common())


def load(profile, pid):
    f = profile.dir / "snapshots.json"
    return json.loads(f.read_text()).get(pid) if f.exists() else None


def save(profile, pid, tracks):
    f = profile.dir / "snapshots.json"
    data = json.loads(f.read_text()) if f.exists() else {}
    data[pid] = {t["uri"]: _label(t) for t in tracks}
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def changes(prev, tracks):
    """(added, removed) labels edited outside our runs, or None when there is no baseline yet."""
    if prev is None:
        return None
    cur = {t["uri"]: _label(t) for t in tracks}
    return ([v for u, v in cur.items() if u not in prev],
            [v for u, v in prev.items() if u not in cur])


def _clip(items):
    extra = f" (+{len(items) - CAP} more)" if len(items) > CAP else ""
    return "; ".join(items[:CAP]) + extra


def describe(ch):
    """Prompt text about hand edits."""
    if ch is None:
        return ""
    added, removed = ch
    if not added and not removed:
        return "The listener has not edited the playlist by hand since the last run.\n"
    out = "The listener edited the playlist by hand since the last run. These are strong, deliberate signals.\n"
    if added:
        out += f"Added by hand ({len(added)}): {_clip(added)}\n"
    if removed:
        out += f"Removed by hand ({len(removed)}): {_clip(removed)}\n"
    return out + ("Treat removals as the listener deciding those songs don't belong, even if the artist "
                  "is in the confirmed list, and additions as taste they have confirmed.\n")


def events(ch):
    """Session-event lines so the report accounts for hand edits."""
    if not ch or not (ch[0] or ch[1]):
        return []
    added, removed = ch
    out = []
    if added:
        out.append(f"MANUAL EDIT, added by hand: {_clip(added)}")
    if removed:
        out.append(f"MANUAL EDIT, removed by hand: {_clip(removed)}")
    return out
