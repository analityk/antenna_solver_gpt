"""File-stream capacity for the native MSVC solver in this worker process."""

import ctypes
import sys
from xml.etree import ElementTree


def _load_ucrt():
    # The supported MSVC openEMS package links the dynamic CRT. Use UCRT,
    # not the separate legacy msvcrt.dll stream table. This call must happen
    # in the worker that imports/runs openEMS, not just its parent CLI.
    crt = ctypes.CDLL("ucrtbase.dll", use_errno=True)
    for name, arguments, result in (
            ("_getmaxstdio", [], ctypes.c_int),
            ("_setmaxstdio", [ctypes.c_int], ctypes.c_int),
            ("fopen", [ctypes.c_char_p, ctypes.c_char_p], ctypes.c_void_p),
            ("fclose", [ctypes.c_void_p], ctypes.c_int)):
        function = getattr(crt, name)
        function.argtypes = arguments
        function.restype = result
    return crt


def configure_stdio(crt, probe_count):
    # Reserve capacity for standard streams, native field files, logs and
    # temporary postprocessing files. Never lower a pre-existing higher limit.
    required = probe_count + 128
    if required > 8192:
        raise RuntimeError(f"Sondy wymagają {required} strumieni z rezerwą; limit UCRT wynosi 8192.")
    before = int(crt._getmaxstdio())
    target = max(512, 1 << (required - 1).bit_length())
    if before < required and int(crt._setmaxstdio(target)) < required:
        raise RuntimeError(f"Nie można zwiększyć limitu strumieni UCRT z {before} do {target}.")
    after = int(crt._getmaxstdio())
    if after < required:
        raise RuntimeError(f"UCRT udostępnia {after} strumieni; wymagane co najmniej {required}.")
    # Exercise the SAME C stream API as native code. Python open() would only
    # check its lower-level descriptors, not this 512-stream table.
    opened = []
    try:
        for _ in range(probe_count):
            handle = crt.fopen(b"NUL", b"w")
            if not handle:
                raise RuntimeError(f"Kontrola UCRT: można otworzyć tylko {len(opened)} z "
                                   f"{probe_count} dodatkowych strumieni. FDTD nie uruchomiono.")
            opened.append(handle)
    finally:
        for handle in opened:
            crt.fclose(handle)
    return {"runtime": "ucrtbase.dll", "probe_streams": probe_count,
            "reserve_streams": 128, "limit_before": before, "limit_after": after,
            "simultaneous_probe_stream_check": "passed"}


def prepare_native_io(model_xml):
    if sys.platform != "win32":
        return {"runtime": "not_windows", "simultaneous_probe_stream_check": "not_applicable"}
    properties = list(ElementTree.parse(model_xml).iter("ProbeBox"))
    # One process/file per probe primitive in this adapter. Refuse ambiguous
    # custom XML instead of claiming its capacity has been checked.
    if any(p.find("Primitives") is None or len(p.find("Primitives")) != 1 for p in properties):
        raise RuntimeError("Kontrola strumieni wymaga jednej geometrii na sondę.")
    names = [p.get("Name") for p in properties]
    if any(not n for n in names) or len(names) != len(set(names)):
        raise RuntimeError("Nazwy sond muszą być niepuste i unikalne.")
    try:
        result = configure_stdio(_load_ucrt(), len(properties))
    except (OSError, AttributeError) as exc:
        raise RuntimeError("Nie można przygotować UCRT dla natywnego openEMS: " + str(exc)) from exc
    print(f"Kontrola plików sond: {result['probe_streams']}; limit UCRT "
          f"{result['limit_before']} -> {result['limit_after']}; otwarcie strumieni OK.", flush=True)
    return result
