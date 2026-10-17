# PlaylistBuilder

Build and refine Spotify playlists for any taste. Each taste becomes a **profile** with a file that defines what the genre/vibe means, and a feedback file of artists you've kept or rejected. Human yes/no/skip inputs teach it.

## Setup

1. Create an app at the [Spotify developer dashboard](https://developer.spotify.com/dashboard) and set its redirect URI to `http://127.0.0.1:8888/callback`. While the app is in development mode, add your own Spotify account under User Management.
2. Get an [Anthropic API key](https://console.anthropic.com). Claude does the judging, so runs cost a small amount of API usage.
3. Install and configure:
```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in the Spotify client id/secret and ANTHROPIC_API_KEY
```

## Commands

Run from project folder, `<profile>` will be the name of a folder until `profiles/`. Playlists are given by name or URL.

```
python -m playlistbuilder sort "Source Playlist" --profile <profile> --into "Destination Playlist"
python -m playlistbuilder suggest "Destination Playlist" --profile <profile>
python -m playlistbuilder narrow "Destination Playlist" --profile <profile>
```

- **`sort`** scores each artist in the source playlist against the profile and lists the ones that fit (`--threshold`, default 6). Omit `--into` to create a new playlist instead (`--name` sets its name).
- **`suggest`** has Claude study the destination playlist, print what it sees, then propose new songs from general music knowledge (`-n` sets how many). Each one is checked against Spotify before you see it. Answer **y** (add the song, keep the artist), **n** (reject the artist for good), **s** (skip) or **q** (quit).
- **`narrow`** sharpens a playlist's focus. You state what the playlist is for (once, or pass `--focus`), Claude scores every artist against that, and you keep or cut each one, or go track by track. Cuts are logged in `narrowed.json` so they can be undone.

Nothing is written to Spotify unless you add `--create`. Your answers are still saved locally on a dry run, so you can review and then re-run with `--create` without answering again.

After you finish a `suggest` or `narrow` session, a report on what your answers say is saved under `profiles/<profile>/reports/`, and the "learned preferences" block at the end of `definition.md` is updated for future runs. `sort` saves a short snapshot of what it moved into the new playlist. Claude reads your last few reports on every run, so it should keep getting better the more you do. You can edit the playlist manually between runs and the commands will notice and adjust.

If you quit with `q` partway through, you can come back to the session later or end it there (the report is then just based on what you answered). Use `q` rather than Ctrl-C, since Ctrl-C doesn't save your progress.

## Profiles
Profiles are personal and gitignored, except `profiles/example/`. To start one, copy it:
`cp -r profiles/example profiles/<profile>` and edit `definition.md`, then pass `--profile <profile>`.
A profile folder holds `definition.md`, `feedback.json`, `focus.md`, `narrowed.json` and `reports/`.

### Personal notes

I spent a while using this program to curate my playlist, trimming it down from a few hundred songs to <80, it's really rewarding especially with the feedback the LLM generates for you. For each song it recommends you, I'd recommend listening before you answer, remember that the quality of your LLM should improve as you answer more, just remember that inputting 'q' saves everything even when you stop midway. I'm saying all of this because I want to respect your time by warning you about the potential time sink.

Goal: create local web UI to run on a local machine with local keys to remove terminal prompts, probably unlikely to turn this public because of silly spotify terms.
