"""narrow: sharpen a playlist's focus by cutting songs that fit the genre but not the purpose."""
import collections
import json

import anthropic

from . import learn
from .prompts import ask, ask_quit_choice
from .spotify import fetch_tracks, get_playlist_id

MODEL = "claude-sonnet-5-5"


def score_fit(client, groups, profile):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=profile.definition + profile.calibration(),
        messages=[{"role": "user", "content": (
            "Score each artist 0-10 for how well they serve this playlist's specific purpose "
            "(10 = squarely on-focus, 0 = off-focus even if good music). Judge sound and "
            "songwriting approach, not fame.\n"
            'Reply with only a JSON object mapping each artist name exactly as given to '
            '{"fit": int, "reason": "<10 words max>"}.\n\n'
            + json.dumps({a: len(ts) for a, ts in groups.items()})
        )}],
    )
    text = next(b.text for b in msg.content if b.type == "text")
    return json.JSONDecoder().raw_decode(text[text.index("{"):])[0]


def run(sp, profile, playlist, focus, create):
    pid = get_playlist_id(sp, playlist)
    tracks = fetch_tracks(sp, pid)

    if focus:
        profile.set_focus(focus)
    if not profile.focus:
        profile.set_focus(input("What is this playlist for? (one or two sentences) "))
    print(f"Focus: {profile.focus}\n")

    state = profile.narrowed()
    if state["pending_cut"] and state.get("pending_playlist") not in (None, pid):
        print("Discarding pending cuts that belong to a different playlist.")
        state["pending_cut"], state["pending_artists"] = [], []
    groups = collections.defaultdict(list)
    for t in tracks:
        groups[t["artists"][0]].append(t)
    todo = {a: ts for a, ts in groups.items()
            if a not in state["kept_artists"] and a not in state["pending_artists"]}
    if state["pending_cut"]:
        print(f"{len(state['pending_cut'])} cuts are pending from an earlier dry run.")
    elif not todo:
        print("Every artist here has already been reviewed.")
        return

    events, cut, cut_artists, finished = [], [], [], True
    sess = profile.load_session("narrow")
    if sess and sess["playlist"] == pid:
        if ask(f"Unfinished session with {len(sess['events'])} answers so far. "
               "Resume it? [y=resume/n=drop it] ", ("y", "n")) == "y":
            events = sess["events"]
        else:
            profile.clear_session("narrow")
    order, fits = [], {}
    if todo:
        fits = score_fit(anthropic.Anthropic(), todo, profile)
        order = sorted(todo, key=lambda a: fits.get(a, {}).get("fit", 0))
    for a in order:
        f = fits.get(a, {})
        ts = todo[a]
        ans = ask(f"{a} ({len(ts)} tracks) fit {f.get('fit', '?')}/10: {f.get('reason', '')}"
                  "  [k=keep all/c=cut all/t=track by track/s=skip/q=quit] ", ("k", "c", "t", "s", "q"))
        if ans == "q":
            finished = ask_quit_choice() == "e"
            if not finished:
                profile.save_session("narrow", {"playlist": pid, "events": events})
            break
        if ans == "s":
            events.append(f"SKIPPED (undecided): {a} ({len(ts)} tracks, model fit {f.get('fit')})")
            continue
        if ans == "k":
            state["kept_artists"].append(a)
            events.append(f"KEPT in focus: {a} ({len(ts)} tracks, model fit {f.get('fit')})")
        elif ans == "c":
            cut += ts
            cut_artists.append(a)
            events.append(f"CUT from playlist: {a} ({len(ts)} tracks, model fit {f.get('fit')})")
        else:
            kept = []
            for t in ts:
                if ask(f"    {t['name']}  [k/c] ", ("k", "c")) == "c":
                    cut.append(t)
                else:
                    kept.append(t)
            state["kept_artists"].append(a)
            events.append(f"TRACK BY TRACK {a}: kept {[t['name'] for t in kept]}, cut "
                          f"{[t['name'] for t in ts if t not in kept]}")

    new = [{"uri": t["uri"], "artist": t["artists"][0], "name": t["name"]} for t in cut]
    state["pending_cut"] = list({c["uri"]: c for c in state["pending_cut"] + new}.values())
    state["pending_artists"] = list(dict.fromkeys(state["pending_artists"] + cut_artists))
    state["pending_playlist"] = pid
    print(f"\n{len(state['pending_cut'])} tracks marked for removal.")
    to_cut = list(state["pending_cut"])
    if to_cut and create:
        uris = list(dict.fromkeys(c["uri"] for c in to_cut))
        for i in range(0, len(uris), 100):
            sp.playlist_remove_all_occurrences_of_items(pid, uris[i:i + 100])
        logged = {c["uri"] for c in state["cut_tracks"]}
        state["cut_tracks"] += [c for c in to_cut if c["uri"] not in logged]
        state["cut_artists"] = list(dict.fromkeys(state["cut_artists"] + state["pending_artists"]))
        state["pending_cut"], state["pending_artists"] = [], []
        profile.save_narrowed(state)
        print(f"Removed from the playlist (logged in profiles/{profile.name}/narrowed.json so it can be undone).")
    else:
        profile.save_narrowed(state)
        if to_cut:
            print("Saved. Re-run with --create to remove them from Spotify (no need to answer again).")

    if not finished:
        print("Session saved. Run the same command again to pick up where you left off.")
    else:
        profile.clear_session("narrow")
        if events:
            learn.report_and_update(anthropic.Anthropic(), profile, "narrow",
                                    [f"PLAYLIST FOCUS: {profile.focus}"] + events)
