"""narrow: sharpen a playlist's focus by cutting songs that fit the genre but not the purpose."""
import collections
import json

import anthropic

from . import learn
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


def ask(prompt, choices):
    ans = ""
    while ans not in choices:
        ans = input(prompt).strip().lower()
    return ans


def run(sp, profile, playlist, focus, create):
    pid = get_playlist_id(sp, playlist)
    tracks = fetch_tracks(sp, pid)

    if focus:
        profile.set_focus(focus)
    if not profile.focus:
        profile.set_focus(input("What is this playlist for? (one or two sentences) "))
    print(f"Focus: {profile.focus}\n")

    state = profile.narrowed()
    groups = collections.defaultdict(list)
    for t in tracks:
        groups[t["artists"][0]].append(t)
    todo = {a: ts for a, ts in groups.items() if a not in state["kept_artists"]}
    if not todo:
        print("Every artist here has already been reviewed.")
        return

    fits = score_fit(anthropic.Anthropic(), todo, profile)
    order = sorted(todo, key=lambda a: fits.get(a, {}).get("fit", 0))

    events, cut, cut_artists = [], [], []
    for a in order:
        f = fits.get(a, {})
        ts = todo[a]
        ans = ask(f"{a} ({len(ts)} tracks) fit {f.get('fit', '?')}/10: {f.get('reason', '')}"
                  "  [k=keep all/c=cut all/t=track by track/s=skip/q=quit] ", ("k", "c", "t", "s", "q"))
        if ans == "q":
            break
        if ans == "s":
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

    print(f"\n{len(cut)} tracks marked for removal.")
    if create:
        state["cut_artists"] += cut_artists
        state["cut_tracks"] += [{"uri": t["uri"], "artist": t["artists"][0], "name": t["name"]} for t in cut]
    profile.save_narrowed(state)
    if cut and create:
        uris = list(dict.fromkeys(t["uri"] for t in cut))
        for i in range(0, len(uris), 100):
            sp.playlist_remove_all_occurrences_of_items(pid, uris[i:i + 100])
        print(f"Removed from the playlist (logged in profiles/{profile.name}/narrowed.json so it can be undone).")
    elif cut:
        print("Re-run with --create to actually remove them from Spotify.")

    if events:
        learn.report_and_update(anthropic.Anthropic(), profile, "narrow",
                                [f"PLAYLIST FOCUS: {profile.focus}"] + events)
