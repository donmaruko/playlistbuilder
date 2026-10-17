"""After a session: tell the human what their answers say, and teach future runs."""
SEP = "=====LEARNED====="
MODEL = "claude-sonnet-5-5"


def report_and_update(client, profile, kind, events):
    """events: list of short strings like 'ACCEPTED: Kate Bush - Hounds Of Love (why)'."""
    if not events:
        return
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=profile.definition + profile.calibration(),
        messages=[{"role": "user", "content": (
            f"A listener just finished a '{kind}' session for this playlist profile. "
            "Their decisions, in order (SKIPPED means undecided: treat it as uncertainty, not "
            "rejection, and mention what the skips suggest):\n" + "\n".join(events) + "\n\n"
            f"Write two parts separated by a line containing only {SEP}\n"
            "PART 1: a report addressed to the listener as 'you', under 200 words, plain prose. "
            "Say what their answers reveal about the taste of this playlist, and call out any "
            "surprises or contradictions. End with exactly two lines: 'More of: ...' and 'Less of: ...'.\n"
            "PART 2: the updated 'Learned preferences' for future AI runs. Merge the existing "
            "learned preferences (inside the markers in the profile above, if present) with these "
            "new signals. At most 8 bullets, each a general principle about sound, structure or "
            "mood rather than a list of artists. Drop old bullets these decisions contradict. "
            "Output the bullets only."
        )}],
    )
    text = next(b.text for b in msg.content if b.type == "text")
    report, _, learned = text.partition(SEP)
    path = profile.save_report(kind, report)
    if learned.strip():
        profile.set_learned(learned)
    print(f"\n=== What your answers say ===\n{report.strip()}\n")
    print(f"(saved to {path}; definition.md's learned preferences updated)")


def recap(client, profile, kind, summary):
    """A snapshot report with no human decisions: what a freshly built playlist consists of."""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=profile.definition + profile.calibration(),
        messages=[{"role": "user", "content": (
            f"A '{kind}' run just built or filled a playlist. Artists and track counts, with why "
            "each fit:\n" + summary + "\n\nIn under 150 words, plain prose addressed to the "
            "listener as 'you', describe the genres present and the common thread of these songs. "
            "Treat it as an opening snapshot: later suggest and narrow sessions will change it."
        )}],
    )
    text = next(b.text for b in msg.content if b.type == "text")
    path = profile.save_report(kind, text)
    print(f"\n=== Playlist snapshot ===\n{text.strip()}\n\n(saved to {path})")
