# Session State — credentials scrub + GitHub push (2026-10-13)

## Goal
Remove credentials from the repo, replace with placeholders, scrub local history, push clean state to GitHub.

## Done
- `config.py` replaced with placeholders (`your-email@gmail.com`, `your-app-password`, `change-this-to-a-random-string`); `config.example.py` deleted (config.py itself is the template now).
- Real credentials backed up locally to `config.local.py` (gitignored, never pushed). Workflow: copy over `config.py` to run; `git restore config.py` before committing.
- `.gitignore` updated: removed `config.py` ignore; added `config.local.py`, `*.exe`, `*.zip`.
- Untracked `__pycache__/*.pyc` (compiled config leaked secrets), `build/`, `dist/`, `.exe`, `.zip` artifacts from git.
- Removed literal key `super-secret-key-123` from `TEACHING_NOTES.md` (2 refs).
- Local history scrubbed (orphan rewrite + reflog expire + gc): old commits contained app passwords `ufsvdpunejmeonid` and `xhxuyisjzxheesqz` in `config.py` and compiled `.pyc`. Verified zero secret matches post-gc.
- Pushed clean commit `5281a1b` to `https://github.com/Micatob/keylogger` (`master`), on top of existing remote history (no force push — remote history was already clean, placeholders only). Preserved remote-only `requirements.txt` (pynput, pywin32, requests).
- Remote `origin` configured (was missing on Desktop clone). Old stale `origin/*` refs to Hermesfury/keylogger-github purged; that repo currently points to the same clean commit as Micatob/keylogger.

## Key facts
- GitHub: `Micatob/keylogger`, branch `master`. Desktop repo: `C:\Users\Hermes\Desktop\keylogger`. Old clone: `C:\Users\Hermes\Documents\GitHub\keylogger` (remote still Hermesfury/keylogger-github).
- Three Gmail app passwords existed in history; two (`ufsv...`, `xhxu...`) are burned. Current one (`euethyhhczwkjper`) never committed — only in `config.local.py`.

## Pending / on return
- User must revoke old app passwords at https://myaccount.google.com/apppasswords and put the fresh one in `config.local.py`.
- Optional: point Documents clone's remote at Micatob/keylogger, or delete/privatize Hermesfury/keylogger-github.
