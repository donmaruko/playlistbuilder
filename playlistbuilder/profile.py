"""A profile is one genre/taste: a definition plus the keep/omit feedback you've given it."""
import json
from dataclasses import dataclass, field
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
START, END = "<!-- learned:start -->", "<!-- learned:end -->"


@dataclass
class Profile:
    name: str
    definition: str
    keep: list = field(default_factory=list)
    omit: list = field(default_factory=list)

    @property
    def dir(self):
        return PROFILES_DIR / self.name

    @classmethod
    def load(cls, name):
        d = PROFILES_DIR / name
        if not (d / "definition.md").exists():
            raise SystemExit(f"No profile {name!r}. Create profiles/{name}/definition.md first.")
        fb = {}
        if (d / "feedback.json").exists():
            fb = json.loads((d / "feedback.json").read_text())
        return cls(name, (d / "definition.md").read_text(), fb.get("keep", []), fb.get("omit", []))

    def save(self):
        (self.dir / "feedback.json").write_text(
            json.dumps({"keep": self.keep, "omit": self.omit}, indent=2))

    def decided(self):
        return {a.lower() for a in self.keep + self.omit}

    # --- focus: what this particular playlist is *for* (narrower than the genre) ---
    @property
    def focus(self):
        f = self.dir / "focus.md"
        return f.read_text().strip() if f.exists() else ""

    def set_focus(self, text):
        (self.dir / "focus.md").write_text(text.strip() + "\n")

    def narrowed(self):
        f = self.dir / "narrowed.json"
        base = {"kept_artists": [], "cut_artists": [], "cut_tracks": [], "pending_cut": [], "pending_artists": []}
        return {**base, **json.loads(f.read_text())} if f.exists() else base

    def save_narrowed(self, data):
        (self.dir / "narrowed.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # --- learned preferences: auto-maintained block at the end of definition.md ---
    def set_learned(self, text):
        block = f"{START}\n## Learned preferences (auto-updated)\n{text.strip()}\n{END}"
        if START in self.definition:
            head = self.definition[:self.definition.index(START)]
            tail = self.definition[self.definition.index(END) + len(END):]
            self.definition = head + block + tail
        else:
            self.definition = self.definition.rstrip() + "\n\n" + block + "\n"
        (self.dir / "definition.md").write_text(self.definition)

    # --- unfinished sessions, so a q-quit can be resumed ---
    def load_session(self, kind):
        f = self.dir / f"session-{kind}.json"
        return json.loads(f.read_text()) if f.exists() else None

    def save_session(self, kind, data):
        (self.dir / f"session-{kind}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def clear_session(self, kind):
        (self.dir / f"session-{kind}.json").unlink(missing_ok=True)

    def save_report(self, kind, text):
        import datetime
        d = self.dir / "reports"
        d.mkdir(exist_ok=True)
        path = d / f"{datetime.datetime.now():%Y-%m-%d-%H%M}-{kind}.md"
        path.write_text(text.strip() + "\n")
        return path

    def recent_reports(self, n=3):
        d = self.dir / "reports"
        if not d.exists():
            return ""
        files = sorted(d.glob("*.md"))[-n:]
        return "\n\n".join(f"[{f.stem}]\n{f.read_text().strip()}" for f in files)

    def calibration(self):
        out = ""
        if self.focus:
            out += f"\nThis playlist's specific purpose, set by the listener: {self.focus}\n"
        nar = self.narrowed()
        cut = list(dict.fromkeys(nar["cut_artists"] + nar["pending_artists"]))
        if nar["kept_artists"]:
            out += ("Artists the listener reviewed and kept as on-focus for this playlist: "
                    + ", ".join(nar["kept_artists"]) + ".\n")
        if cut:
            out += ("Artists the listener removed (or marked for removal) from this playlist while "
                    "narrowing its focus (fine music, but off-focus here): " + ", ".join(cut) + ".\n")
        partial = {}
        for c in nar["cut_tracks"] + nar["pending_cut"]:
            if c["artist"] not in cut:
                partial.setdefault(c["artist"], []).append(c["name"])
        if partial:
            out += ("Specific tracks cut from artists who otherwise stayed (the tracks that stayed "
                    "are the on-focus ones): "
                    + "; ".join(f"{a}: {', '.join(ts)}" for a, ts in partial.items()) + ".\n")
        if self.keep or self.omit:
            out += (
                "\nThe listener has confirmed these as fitting: " + ", ".join(self.keep)
                + ".\nThe listener rejected these as NOT fitting (even if they seem adjacent): "
                + ", ".join(self.omit) + ".\nUse this to calibrate your taste model.\n"
            )
        recent = self.recent_reports()
        if recent:
            out += ("\nReports from the listener's most recent sessions, oldest first, for context "
                    "(the learned preferences above are their distillation):\n" + recent + "\n")
        return out
