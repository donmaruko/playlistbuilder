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
            "Their decisions, in order:\n" + "\n".join(events) + "\n\n"
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
