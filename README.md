# PlaylistBuilder

Build and refine Spotify playlists for any taste. Each taste is a **profile** under `profiles/<name>/`
with a `definition.md` (what the genre/vibe means) and a `feedback.json` (artists you've kept or rejected).
Claude does the judging; your yes/no answers teach it.

## Setup
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in Spotify client id/secret and ANTHROPIC_API_KEY
```
Spotify app redirect URI must be `http://127.0.0.1:8888/callback`.

## Commands
```
python -m playlistbuilder sort "Source Playlist" --profile artrock --into "Dest"   # dry run; add --create to write
python -m playlistbuilder suggest "Dest" --profile artrock --create                # new songs, learns from y/n
python -m playlistbuilder narrow "Dest" --profile artrock --create                 # cut off-focus songs
```
Playlists can be given by name or URL. Nothing is written to Spotify without `--create`.
After `suggest` and `narrow`, a report is saved under `profiles/<name>/reports/` and the
"learned preferences" block at the end of `definition.md` is updated.
