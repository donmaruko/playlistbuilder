"""suggest: propose new songs for a playlist from general music knowledge, learn from y/n."""
import json

import anthropic

from . import learn, snapshot
from .prompts import ask, ask_quit_choice
from .spotify import add_tracks, fetch_tracks, get_playlist_id

MODEL = "claude-sonnet-5-5"


def playlist_summary(existing):
    return snapshot.summary(existing)


def analyze(client, existing, profile, drift=""):
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
            f"{drift}"
            f"Playlist artists (track counts): {playlist_summary(existing)}"
        )}],
    )
    return next(b.text for b in msg.content if b.type == "text").strip()


def propose(client, existing, profile, n, analysis, drift=""):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=profile.definition + profile.calibration(),
        messages=[{"role": "user", "content": (
            f"Suggest {n} songs this listener would love, in the spirit of their playlist. "
            "Draw on the whole breadth of music: other eras, scenes, countries, deep cuts, "
            "not just the obvious names. Pick the specific song that best represents the artist. "
            "One song per artist.\n\n"
            f"Your analysis of the playlist as it stands:\n{analysis}\n\n{drift}"
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

    ch = snapshot.changes(snapshot.load(profile, pid), existing)
    drift = snapshot.describe(ch)
    if ch and (ch[0] or ch[1]):
        print(f"Since the last run you added {len(ch[0])} and removed {len(ch[1])} tracks by hand; factoring that in.\n")

    sess = profile.load_session("suggest")
    if sess and sess["playlist"] == pid:
        if ask(f"Unfinished session: {len(sess['queue'])} suggestions left, {len(sess['events'])} answered. "
               "Resume it? [y=resume/n=drop it and start fresh] ", ("y", "n")) == "y":
            queue, events, accepted = sess["queue"], sess["events"], sess["accepted"]
            events += snapshot.events(ch)
            analysis = analyze(ai, existing, profile, drift)
            print(f"What I see in the playlist now:\n{analysis}\n")
        else:
            profile.clear_session("suggest")
            sess = None
    else:
        sess = None
    if not sess:
        analysis = analyze(ai, existing, profile, drift)
        print(f"What I see in the playlist:\n{analysis}\n")
        queue, events, accepted = propose(ai, existing, profile, n, analysis, drift), [], []
        events += snapshot.events(ch)

    finished = True
    while queue:
        s = queue.pop(0)
        a = s["artist"]
        if a.lower() in have_artists | profile.decided():
            continue
        t = find_on_spotify(sp, a, s["track"])
        if not t or t["uri"] in have_uris:
            continue
        ans = ask(f"{a} - {t['name']}  ({s['why']})  [y/n/s=skip/q=quit] ", ("y", "n", "s", "q"))
        if ans == "q":
            queue.insert(0, s)
            finished = ask_quit_choice() == "e"
            break
        if ans == "y":
            profile.keep.append(a)
            accepted.append(t["uri"])
            events.append(f"ACCEPTED: {a} - {t['name']} ({s['why']})")
        elif ans == "n":
            profile.omit.append(a)
            events.append(f"REJECTED: {a} - {t['name']} ({s['why']})")
        else:
            events.append(f"SKIPPED (undecided): {a} - {t['name']} ({s['why']})")
        profile.save()

    if not finished:
        profile.save_session("suggest", {"playlist": pid, "queue": queue, "events": events,
                                         "accepted": accepted})
        snapshot.save(profile, pid, fetch_tracks(sp, pid))
        print("Session saved. Run the same command again to pick up where you left off.")
        return

    profile.clear_session("suggest")
    print(f"\n{len(accepted)} accepted.")
    if accepted and create:
        add_tracks(sp, pid, accepted)
        print("Added to playlist.")
    elif accepted:
        print("Re-run with --create to add them (answers are already saved).")
    snapshot.save(profile, pid, fetch_tracks(sp, pid))
    learn.report_and_update(ai, profile, "suggest", events)
