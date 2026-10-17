# PlaylistBuilder

Build and refine Spotify playlists for any taste. Each taste becomes a **profile** with a file that defines what the genre/vibe means, and a feedback file of artists you've kept or rejected. Human yes/no/skip inputs teach it.

## Setup
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in Spotify client id/secret and ANTHROPIC_API_KEY
```
Spotify app redirect URI must be `http://127.0.0.1:8888/callback`.

## Commands
```
python -m playlistbuilder sort "Source Playlist" --profile <profile> --into "Destination Playlist"   # dry run; add --create to write
python -m playlistbuilder suggest "Destination Playlist" --profile <profile> --create                # new songs, learns from y/n
python -m playlistbuilder narrow "Destination Playlist" --profile <profile> --create                 # cut off-focus songs
```
`<profile>` is the name of a folder under `profiles/` (see Profiles below).
Playlists can be given by name or URL. Nothing is written to Spotify without `--create`.
After `suggest` and `narrow`, a report is saved under `profiles/<profile>/reports/` and the
"learned preferences" block at the end of `definition.md` is updated.

## Profiles
Profiles are personal and gitignored, except `profiles/example/`. To start one, copy it:
`cp -r profiles/example profiles/<profile>` and edit `definition.md`, then pass `--profile <profile>`.
A profile folder holds `definition.md`, `feedback.json`, `focus.md`, `narrowed.json` and `reports/`.

### Personal notes

I spent a while using this program to curate my playlist, trimming it down from a few hundred songs to <80, it's really rewarding especially with the feedback the LLM generates for you. For each song it recommends you, I'd recommend listening before you answer, remember that the quality of your LLM should improve as you answer more, just remember that inputting 'q' saves everything even when you stop midway. I'm saying all of this because I want to respect your time by warning you about the potential time sink.
