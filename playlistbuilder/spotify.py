import re

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope="playlist-read-private playlist-modify-private playlist-modify-public",
        open_browser=False,
    ))


def get_playlist_id(sp, query):
    m = re.search(r"playlist[/:]([A-Za-z0-9]+)", query)
    if m:
        return m.group(1)
    page = sp.current_user_playlists(limit=50)
    while page:
        for p in page["items"]:
            if p and p["name"].lower() == query.lower():
                return p["id"]
        page = sp.next(page) if page["next"] else None
    raise SystemExit(f"No playlist named {query!r} found. Pass an exact name or URL.")


def fetch_tracks(sp, playlist_id):
    tracks, page = [], sp.playlist_items(playlist_id, limit=100)
    while page:
        for item in page["items"]:
            t = item.get("track") or item.get("item")
            if not t or t.get("is_local") or not t.get("id"):
                continue
            tracks.append({
                "uri": t["uri"],
                "name": t["name"],
                "artists": [a["name"] for a in t["artists"]],
            })
        page = sp.next(page) if page["next"] else None
    return tracks


def add_tracks(sp, playlist_id, uris):
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[i:i + 100])
