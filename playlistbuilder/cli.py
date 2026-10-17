import argparse

from . import narrow, sort, suggest
from .profile import Profile
from .spotify import client


def main():
    ap = argparse.ArgumentParser(prog="playlistbuilder")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("sort", help="pull songs that fit a profile out of a source playlist")
    s.add_argument("source", help="source playlist name or URL")
    s.add_argument("--profile", required=True, help="profile name (folder under profiles/)")
    s.add_argument("--into", help="existing playlist to add to (name or URL); omit to create a new one")
    s.add_argument("--name", help="name for a new playlist (default: profile name)")
    s.add_argument("--threshold", type=int, default=6, help="min score to include (default 6)")
    s.add_argument("--create", action="store_true", help="actually write to Spotify")

    g = sub.add_parser("suggest", help="suggest new songs for a playlist and learn from your answers")
    g.add_argument("playlist", help="playlist to grow (name or URL)")
    g.add_argument("--profile", required=True, help="profile name (folder under profiles/)")
    g.add_argument("-n", type=int, default=25, help="how many suggestions to ask for")
    g.add_argument("--create", action="store_true", help="add accepted songs to the playlist")

    n = sub.add_parser("narrow", help="sharpen a playlist's focus by cutting off-focus songs")
    n.add_argument("playlist", help="playlist to narrow (name or URL)")
    n.add_argument("--profile", required=True, help="profile name (folder under profiles/)")
    n.add_argument("--focus", help="what the playlist is for (saved; asked once if omitted)")
    n.add_argument("--create", action="store_true", help="actually remove cut songs from the playlist")

    args = ap.parse_args()
    profile = Profile.load(args.profile)
    sp = client()
    if args.cmd == "sort":
        sort.run(sp, profile, args.source, args.into, args.name or profile.name, args.threshold, args.create)
    elif args.cmd == "narrow":
        narrow.run(sp, profile, args.playlist, args.focus, args.create)
    else:
        suggest.run(sp, profile, args.playlist, args.n, args.create)
