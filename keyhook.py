import ctypes
import ctypes.wintypes
import threading
import time
from log_utils import log

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

_HOOK_HANDLE = None
_hook_thread = None
_callbacks = []

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(KBDLLHOOKSTRUCT))

def _get_key_name(vk):
    SPECIAL = {
        0x08: "[BKSP]", 0x09: "[TAB]", 0x0D: "[ENTER]",
        0x10: "[SHIFT]", 0x11: "[CTRL]", 0x12: "[ALT]",
        0x14: "[CAPS]", 0x1B: "[ESC]", 0x20: "[SPACE]",
        0x2E: "[DEL]", 0x25: "[LEFT]", 0x27: "[RIGHT]",
        0x26: "[UP]", 0x28: "[DOWN]", 0x2D: "[INS]",
        0x24: "[HOME]", 0x23: "[END]", 0x21: "[PGUP]",
        0x22: "[PGDN]", 0x2C: "[PRTSC]", 0x91: "[SCRLK]",
        0x13: "[PAUSE]", 0x90: "[NUMLK]",
        0x70: "[F1]", 0x71: "[F2]", 0x72: "[F3]", 0x73: "[F4]",
        0x74: "[F5]", 0x75: "[F6]", 0x76: "[F7]", 0x77: "[F8]",
        0x78: "[F9]", 0x79: "[F10]", 0x7A: "[F11]", 0x7B: "[F12]",
        0x5B: "[WIN]", 0x5C: "[WIN]", 0x5D: "[MENU]",
    }
    if vk in SPECIAL:
        return SPECIAL[vk]
    state = ctypes.wintypes.BYTE(0)
    keyboard_state = (ctypes.wintypes.BYTE * 256)()
    user32.GetKeyboardState(keyboard_state)
    buf = ctypes.create_unicode_buffer(8)
    ret = user32.ToUnicode(vk, 0, keyboard_state, buf, 8, 0)
    if ret > 0:
        return buf.value
    return f"[0x{vk:02X}]"

def _hook_callback(nCode, wParam, lParam):
    if nCode < 0:
        return user32.CallNextHookEx(None, nCode, wParam, lParam)
    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        key_name = _get_key_name(kb.vkCode)
        for cb in _callbacks:
            try:
                cb(key_name, kb.vkCode)
            except Exception:
                pass
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

_proc = LowLevelKeyboardProc(_hook_callback)

def _message_pump():
    msg = ctypes.wintypes.MSG()
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret <= 0:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

def start():
    global _HOOK_HANDLE, _hook_thread
    _HOOK_HANDLE = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL,
        _proc,
        kernel32.GetModuleHandleW(None),
        0
    )
    if not _HOOK_HANDLE:
        log("error", f"SetWindowsHookEx failed: {ctypes.GetLastError()}")
        return False
    _hook_thread = threading.Thread(target=_message_pump, daemon=True)
    _hook_thread.start()
    log("info", "WH_KEYBOARD_LL hook installed")
    return True

def stop():
    global _HOOK_HANDLE
    if _HOOK_HANDLE:
        user32.UnhookWindowsHookEx(_HOOK_HANDLE)
        _HOOK_HANDLE = None
        log("info", "Keyboard hook removed")
    return True

def register_callback(cb):
    _callbacks.append(cb)

def unregister_callback(cb):
    if cb in _callbacks:
        _callbacks.remove(cb)
