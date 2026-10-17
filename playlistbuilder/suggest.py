"""suggest: propose new songs for a playlist from general music knowledge, learn from y/n."""
import collections
import json

import anthropic

from . import learn
from .spotify import add_tracks, fetch_tracks, get_playlist_id

MODEL = "claude-sonnet-5-5"


def playlist_summary(existing):
    counts = collections.Counter(t["artists"][0] for t in existing)
    return json.dumps(counts.most_common())


def analyze(client, existing, profile):
    """Step 1: study the playlist as it stands, so suggestions respond to its current shape."""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=profile.definition + profile.calibration(),
        messages=[{"role": "user", "content": (
            "Study this playlist as it stands right now. In under 120 words, plain prose, say: "
            "which genres and scenes are present (and roughly how heavily), the common thread "
            "running through them, and what is over- or under-represented. Then one sentence on "
            "what that implies for new recommendations.\n\n"
            f"Playlist artists (track counts): {playlist_summary(existing)}"
        )}],
    )
    return next(b.text for b in msg.content if b.type == "text").strip()


def propose(client, existing, profile, n, analysis):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=profile.definition + profile.calibration(),
        messages=[{"role": "user", "content": (
            f"Suggest {n} songs this listener would love, in the spirit of their playlist. "
            "Draw on the whole breadth of music: other eras, scenes, countries, deep cuts, "
            "not just the obvious names. Pick the specific song that best represents the artist. "
            "One song per artist.\n\n"
            f"Your analysis of the playlist as it stands:\n{analysis}\n\n"
            f"Playlist artists (track counts): {playlist_summary(existing)}\n"
            f"Confirmed fits (taste anchors): {json.dumps(profile.keep)}\n"
            f"Rejected, never suggest these artists: {json.dumps(profile.omit)}\n"
            "Never suggest anyone already in the playlist.\n\n"
            'Reply with only a JSON array of {"artist": str, "track": str, "why": "<12 words max>"}.'
        )}],
    )
    text = next(b.text for b in msg.content if b.type == "text")
    return json.JSONDecoder().raw_decode(text[text.index("["):])[0]


def find_on_spotify(sp, artist, track):
    res = sp.search(q=f'track:"{track}" artist:"{artist}"', type="track", limit=5)
    for t in res["tracks"]["items"]:
        if any(a["name"].lower() == artist.lower() for a in t["artists"]):
            return t
    return None


def run(sp, profile, playlist, n, create):
    pid = get_playlist_id(sp, playlist)
    existing = fetch_tracks(sp, pid)
    have_uris = {t["uri"] for t in existing}
    have_artists = {a.lower() for t in existing for a in t["artists"]}

    ai = anthropic.Anthropic()
    analysis = analyze(ai, existing, profile)
    print(f"What I see in the playlist:\n{analysis}\n")

    accepted, events = [], []
    for s in propose(ai, existing, profile, n, analysis):
        a = s["artist"]
        if a.lower() in have_artists | profile.decided():
            continue
        t = find_on_spotify(sp, a, s["track"])
        if not t or t["uri"] in have_uris:
            continue
        ans = ""
        while ans not in ("y", "n", "s", "q"):
            ans = input(f"{a} - {t['name']}  ({s['why']})  [y/n/s=skip/q=quit] ").strip().lower()
        if ans == "q":
            break
        if ans == "y":
            profile.keep.append(a)
            accepted.append(t["uri"])
            events.append(f"ACCEPTED: {a} - {t['name']} ({s['why']})")
        elif ans == "n":
            profile.omit.append(a)
            events.append(f"REJECTED: {a} - {t['name']} ({s['why']})")
        profile.save()

    print(f"\n{len(accepted)} accepted.")
    if accepted and create:
        add_tracks(sp, pid, accepted)
        print("Added to playlist.")
    elif accepted:
        print("Re-run with --create to add them (answers are already saved).")

    learn.report_and_update(ai, profile, "suggest", events)
