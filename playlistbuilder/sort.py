"""sort: scan a source playlist and pull out the songs that fit a profile."""
import json

import anthropic

from . import learn, snapshot
from .spotify import add_tracks, fetch_tracks, get_playlist_id

MODEL = "claude-haiku-5-5"
BATCH = 40


def classify_artists(client, artists, profile):
    """Return {artist: {"score": 0-10, "reason": str}}."""
    out = {}
    for i in range(0, len(artists), BATCH):
        chunk = artists[i:i + BATCH]
        msg = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=profile.definition + profile.calibration(),
            messages=[{"role": "user", "content": (
                "Score each artist 0-10 for how well their body of work fits the taste "
                "described above (10 = squarely in it, 0 = not at all). Judge the artist's "
                "general output; if you don't recognize an artist, score 0.\n"
                "Reply with only a JSON object mapping each artist name exactly as given to "
                '{"score": int, "reason": "<8 words max>"}.\n\n'
                + json.dumps(chunk)
            )}],
        )
        text = next(b.text for b in msg.content if b.type == "text")
        out.update(json.JSONDecoder().raw_decode(text[text.index("{"):])[0])
    return out


def run(sp, profile, source, dest, name, threshold, create):
    tracks = fetch_tracks(sp, get_playlist_id(sp, source))
    print(f"{len(tracks)} tracks read.")

    artists = sorted({a for t in tracks for a in t["artists"]} - set(profile.keep) - set(profile.omit))
    scores = classify_artists(anthropic.Anthropic(), artists, profile)
    for a in profile.keep:
        scores[a] = {"score": 10, "reason": "confirmed by you"}
    for a in profile.omit:
        scores[a] = {"score": 0, "reason": "rejected by you"}

    picked, per_artist = [], {}
    for t in tracks:
        best = max(t["artists"], key=lambda a: scores.get(a, {}).get("score", 0))
        if scores.get(best, {}).get("score", 0) >= threshold:
            picked.append(t)
            per_artist[best] = per_artist.get(best, 0) + 1

    for a, n in sorted(per_artist.items(), key=lambda kv: -scores[kv[0]]["score"]):
        tag = "" if a in profile.keep else "  <- unreviewed"
        print(f"[{scores[a]['score']:>2}] {a} ({n}){tag}  {scores[a].get('reason', '')}")
    print(f"\n{len(picked)} of {len(tracks)} tracks from {len(per_artist)} artists match (threshold {threshold}).")

    if not create:
        print("Dry run. Re-run with --create to write to Spotify.")
        return

    if dest:
        pl_id = get_playlist_id(sp, dest)
        already = {t["uri"] for t in fetch_tracks(sp, pl_id)}
    else:
        pl_id = sp.current_user_playlist_create(name, public=False, description="Built by PlaylistBuilder")["id"]
        already = set()
    uris = [u for u in dict.fromkeys(t["uri"] for t in picked) if u not in already]
    print(f"{len(picked) - len(uris)} already in the playlist, skipped.")
    add_tracks(sp, pl_id, uris)
    print(f"Added {len(uris)} new tracks: https://open.spotify.com/playlist/{pl_id}")
    snapshot.save(profile, pl_id, fetch_tracks(sp, pl_id))
    if uris:
        summary = "\n".join(f"{a} ({n}): {scores[a].get('reason', '')}" for a, n in per_artist.items())
        learn.recap(anthropic.Anthropic(), profile, "sort", summary)
