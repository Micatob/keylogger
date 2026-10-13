# Session State — keylogger course prep (2026-10-07)

## Goal
Prepare teaching material for a course module on how the keylogger in this repo works, how it could evolve, and how it reaches machines — framed for defense/detection.

## Done
- Explored full repo (`pykelogger.py`, `kky.py`, `keyhook.py`, `keylogger.cpp`, `antidetect.py`, `evasion.py`, `obfuscation.py`, `storage.py`, `crypto_utils.py`, `c2/`, `plugins/`, `config.py`, `pykelogger.spec`, `log_utils.py`).
- Verified all base64-obfuscated constants by decoding (SMTP/IMAP hosts, Run key, `WindowsUpdateClient`, `pythonw.exe "{}"`, `[CMD]`, log banners, VM indicators).
- Wrote `TEACHING_NOTES.md` (~3.5h lecture: architecture, 3 capture techniques, exfil, anti-analysis, persistence, obfuscation limits, crypto review, C2-as-RAT, AMSI/ETW, packaging, purple-team roadmap, initial access, detection handout, 16-item weakness register, 9 exercises).

## Key findings (verified)
- `evasion.py`, `keyhook.py`, `storage.py`, `c2/`, `plugins/` are orphaned — never imported by `pykelogger.py`.
- `antidetect.py` VM checks partly dead: driver paths say `druvers` not `drivers` (`:83-92`); registry keys corrupted (`Services^vmtools`, `Scci`) (`:63-74`).
- Persistence broken in PyInstaller one-file build (`pykelogger.py:44` vs `pykelogger.spec:32`); `PERSISTENCE=False` by default.
- Thread race on `logged_data` drops keystrokes (`pykelogger.py:71` vs `:151`).
- C++ exfil broken: STARTTLS on implicit-TLS 465 + malformed AUTH PLAIN (`keylogger.cpp:263-266,294-334`); polling misses taps (`:459-469`).
- Crypto: static salt, embedded key shipped in exe, silent base64 downgrade, XOR fallback.

## User decisions
- Leave all source code as-is; do NOT fix bugs for now.
- User challenged "no bugs / clean" claim — answered with evidence it has bugs and is AV-loud.
- Delivery/initial-access covered at threat-model + ATT&CK level only; lure crafting out of scope.

## Pending / on return
- User said they will be back later. No open code changes. Next step is theirs (e.g., review `TEACHING_NOTES.md`, adjust depth/audience, plan labs).
