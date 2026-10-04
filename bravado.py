#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Parham (Leon) Faraji. Source signature: Leon-Executes.
"""Bravado — a local, single-file Windows equalizer controller.

Sections: 01 model / 02 DSP / 03 persistence / 04 Windows audio /
05 APO transactions / 06 local API / 07 embedded panel / 08 tests & entry point.
Source requires Python 3.12, NumPy and pywebview. System processing uses installed Equalizer APO.
No audio loopback, automatic gain recovery, cloud service, or remote assets.
"""
from __future__ import annotations

import argparse
import configparser
import copy
import ctypes as ct
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import urllib.request
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import numpy as np
except ImportError:
    raise SystemExit('Bravado needs NumPy. Run: python -m pip install "numpy>=1.26,<3"')

if os.name == "nt" and getattr(sys, "frozen", False):
    # Keep bundled DLLs available to Python without exporting PyInstaller's
    # altered DLL search path to WebView2, PowerShell or APO tools.
    _runtime_dlls = os.add_dll_directory(sys._MEIPASS)
    ct.windll.kernel32.SetDllDirectoryW(None)

# ============================================================================
# 01 — Validated model. Factory presets and validated settings.
# ============================================================================
VERSION = "0.8.6"
SIGNATURE = "Bravado Signature Preset"
DOUBLE_DB = 20 * math.log10(2)
ADMIN_TIMEOUT = 60
FREQUENCIES = [10, 30, 50, 90, 160, 300, 500, 1000, 1600, 3000, 5000, 9000, 16000, 20000]
GAINS = [8.9, 9.1, 4, 8.2, 7.1, 6, 2.2, 5.1, 5.8, -3.3, 3.3, 6, -3.8, -5.1]
QUALITIES = [2.5, 3.75, 2.5, 3, 2, 1.41, 1.41, 2, 2, 1, 1.5, 2, 1, 1]
# Leon-Executes / voicing desk.
# Original, assertive alternatives built around Signature's tonal scale.
# Explicit filter gains and Q; no automatic level adjustment. See PRESETS.md.
VOICES = {
    "Nordrassil": (1.4,
        (2.8, 4.5, 2.8, 6, 5.7, 4, 0, 4.8, 4.6, -4.3, 2.8, 6, -4, -5),
        (1.2, 1.3, 2.5, 1.8, 1.6, 1.3, 1.8, 1.2, 1.6, 1.3, 1.5, 1.7, 1.2, 1.2)),
    "Marble Alibi": (0,
        (0, 7, 1, 7.4, 4.8, 2.2, -2.8, 5.8, 6.5, -5.5, 4, 5.8, -4, -5),
        (.71, 2.8, 2.5, 2.4, 2.3, 1.7, 2.1, 1.8, 2.2, 1.8, 2, 2, 1.5, 1.5)),
    "Red Herring": (0,
        (6, 10, 0, 9, 4.8, 1.3, -4, 3.2, 4, -4.8, 1, 6.8, -4.5, -5.5),
        (1.05, 2.8, 2.5, 3.2, 2.2, 1.8, 1.9, 1.8, 2, 1.6, 2, 2.6, 1.5, 1.5)),
    "Pocket Physics": (0,
        (4, 7, 0, 8, 8, 4, -4, 3.5, 3.7, -4.5, 1.6, 8, -4.5, -5.5),
        (1.6, 2.2, 2.5, 2.3, 2.3, 1.8, 2.1, 2, 2, 1.6, 2, 3, 1.5, 1.5)),
}
# Reuse the otherwise neutral first band for distinct sub-bass support.
SUB_BASS_CENTRES = {"Red Herring": 20, "Pocket Physics": 24, "Nordrassil": 24}
PRESET_ORDER = (SIGNATURE, "Pocket Physics", "Flat", "Nordrassil", "Marble Alibi", "Red Herring")
PRESET_NOTES = {
    SIGNATURE: "The original Bravado curve. Full-bodied and vivid.",
    "Flat": "Uncoloured reference. EQ and effects at unity.",
    "Nordrassil": "Expansive body, deep foundation and sustained strength.",
    "Marble Alibi": "Forward voices, firm bass and open articulation.",
    "Red Herring": "Deepest weight, hard bass contrast and a recessed lower midrange.",
    "Pocket Physics": "Deep bass under dense kick-drum body and crisp treble bite.",
}
RATES = (44100, 48000, 88200, 96000, 176400, 192000)
CHANNELS = {"all": "All speakers", "L": "Left", "R": "Right", "C": "Center",
            "LFE": "Subwoofer", "RL": "Left rear", "RR": "Right rear",
            "SL": "Left side", "SR": "Right side"}
KINDS = ("PK", "LS", "HS", "HP", "LP", "NO")
APP_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
MARKER = "# BRAVADO MANAGED v1"
MAX_JSON = 256 * 1024


def number(value, lo, hi, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}")
    return value


def flag(value, label):
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be true or false")
    return value


def bank(flat=False):
    return {"bands": [{"freq": f, "gain": 0 if flat else g, "q": q,
                       "kind": "PK", "enabled": True}
                      for f, g, q in zip(FREQUENCIES, GAINS, QUALITIES)],
            "trim": 0, "delay": 0, "mute": False}


def defaults():
    return {"schema": 1, "name": SIGNATURE, "preamp": 0.0,
            "processing": "native", "output": 0, "rumble": False, "bypass": False,
            "double_track": False,
            "room": False, "room_amount": 20, "separation": 0,
            "bass_track": False, "bass_delay": 0,
            "device": "all", "banks": {"all": bank()}}


def factory_presets():
    """Fresh models keep factory settings independent of preview edits."""
    presets = {SIGNATURE: defaults(),
               "Flat": {**defaults(), "name": "Flat", "banks": {"all": bank(True)}}}
    for name, (preamp, gains, qualities) in VOICES.items():
        model = defaults()
        model.update(name=name, preamp=preamp)
        for band_, gain, quality in zip(model["banks"]["all"]["bands"], gains, qualities):
            band_.update(gain=gain, q=quality)
        if name in SUB_BASS_CENTRES:
            model["banks"]["all"]["bands"][0]["freq"] = SUB_BASS_CENTRES[name]
        if name == "Nordrassil":
            model["banks"]["all"]["bands"][12]["enabled"] = False
        presets[name] = model
    return {name: presets[name] for name in PRESET_ORDER}


def machine_key():
    """Local identity only; never expose the underlying Windows identifier."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                        0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        identity = winreg.QueryValueEx(key, "MachineGuid")[0]
    return hashlib.sha256(str(identity).encode()).hexdigest()


def validate(raw):
    if not isinstance(raw, dict) or raw.get("schema") != 1:
        raise ValueError("Expected a Bravado schema 1 preset")
    name = raw.get("name", "Untitled")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
        raise ValueError("Preset name must contain 1–80 printable characters")
    device = raw.get("device", "all")
    if device != "all" and not re.fullmatch(r"\{[0-9A-Fa-f-]{36}\}", str(device)):
        raise ValueError("Select all devices or a playback endpoint GUID")
    result = {"schema": 1, "name": name.strip(), "device": device,
              "preamp": number(raw.get("preamp"), -60, 30, "Preamp"),
              "processing": "native",  # Legacy guarded presets migrate without hidden attenuation.
              "output": number(raw.get("output"), -60, 0, "Output attenuation"),
              "rumble": flag(raw.get("rumble", False), "Rumble protection"),
              "double_track": flag(raw.get("double_track", False), "Aligned double"),
              "room": flag(raw.get("room", False), "Stereo Room"),
              "room_amount": number(raw.get("room_amount", 20), 0, 40, "Room amount"),
              "separation": number(raw.get("separation", 0), -100, 100, "Separation"),
              "bass_track": flag(raw.get("bass_track", False), "Bass double"),
              "bass_delay": number(raw.get("bass_delay", 0), 0, 10, "Bass sync delay"),
              "bypass": flag(raw.get("bypass", False), "Bypass"), "banks": {}}
    banks = raw.get("banks")
    if not isinstance(banks, dict) or "all" not in banks or set(banks) - set(CHANNELS):
        raise ValueError("Invalid speaker banks")
    for key, b in banks.items():
        if not isinstance(b, dict) or not isinstance(b.get("bands"), list) or not 1 <= len(b["bands"]) <= 32:
            raise ValueError("Each bank needs 1–32 bands")
        bands = []
        for item in b["bands"]:
            kind = item.get("kind", "PK")
            if kind not in KINDS:
                raise ValueError("Unsupported filter type")
            bands.append({"freq": number(item.get("freq"), 10, 20000, "Frequency"),
                          "gain": number(item.get("gain"), -30, 30, "Band gain"),
                          "q": number(item.get("q"), 0.25, 12, "Q"), "kind": kind,
                          "enabled": flag(item.get("enabled", True), "Band enabled")})
        result["banks"][key] = {"bands": bands, "trim": number(b.get("trim", 0), -60, 0, "Speaker trim"),
                                "delay": number(b.get("delay", 0), 0, 200, "Delay"),
                                "mute": flag(b.get("mute", False), "Speaker mute")}
    if raw.get("processing", "native") not in ("native", "guarded"):
        raise ValueError("Unknown processing mode")
    stages = raw.get("preamp_stages")
    if stages is not None:
        if not isinstance(stages, list) or not 1 <= len(stages) <= 32:
            raise ValueError("Invalid preamp stages")
        clean = []
        for stage in stages:
            pos = stage.get("before")
            if type(pos) is not int or not 0 <= pos <= len(result["banks"]["all"]["bands"]):
                raise ValueError("Invalid preamp stage position")
            clean.append({"before": pos, "db": number(stage.get("db"), -60, 30, "Stage preamp")})
        if [x["before"] for x in clean] != sorted(x["before"] for x in clean):
            raise ValueError("Preamp stages must be ordered")
        if not math.isclose(sum(x["db"] for x in clean), result["preamp"], abs_tol=1e-9):
            raise ValueError("Preamp stages do not equal the displayed total")
        result["preamp_stages"] = clean
    return result


# ============================================================================
# 02 — DSP: native APO filters and explicit room / bass-copy effects.
# Leon-Executes / signal workshop.
# ============================================================================
def coefficients(b, rate):
    """RBJ/W3C cookbook, double precision. Shelf Q uses alpha = sin(w)/(2Q)."""
    w = 2 * math.pi * b["freq"] / rate
    c, s = math.cos(w), math.sin(w)
    alpha, A = s / (2 * b["q"]), 10 ** (b["gain"] / 40)
    kind = b["kind"]
    a = [1 + alpha, -2*c, 1-alpha]
    if kind == "PK":
        v, a = [1+alpha*A, -2*c, 1-alpha*A], [1+alpha/A, -2*c, 1-alpha/A]
    elif kind == "HP":
        v = [(1+c)/2, -(1+c), (1+c)/2]
    elif kind == "LP":
        v = [(1-c)/2, 1-c, (1-c)/2]
    elif kind == "NO":
        v = [1, -2*c, 1]
    else:
        t = 2*math.sqrt(A)*alpha
        if kind == "LS":
            v = [A*((A+1)-(A-1)*c+t), 2*A*((A-1)-(A+1)*c), A*((A+1)-(A-1)*c-t)]
            a = [(A+1)+(A-1)*c+t, -2*((A-1)+(A+1)*c), (A+1)+(A-1)*c-t]
        else:
            v = [A*((A+1)+(A-1)*c+t), -2*A*((A-1)+(A+1)*c), A*((A+1)+(A-1)*c-t)]
            a = [(A+1)-(A-1)*c+t, 2*((A-1)-(A+1)*c), (A+1)-(A-1)*c-t]
    v, a = np.asarray(v)/a[0], np.asarray(a)/a[0]
    if np.max(np.abs(np.roots(a))) >= 1:
        raise ValueError("Unstable filter rejected")
    return v, a


def response(bands, frequencies, rate):
    z = np.exp(-2j*np.pi*np.asarray(frequencies)/rate)
    h = np.ones_like(z)
    for b in bands:
        if b["enabled"]:
            v, a = coefficients(b, rate)
            h *= (v[0]+v[1]*z+v[2]*z*z)/(1+a[1]*z+a[2]*z*z)
    return h


def effective_bands(model, key):
    if model["bypass"]:
        return []
    result = list(model["banks"][key]["bands"])
    if key == "all" and model["rumble"]:
        result.append({"freq": 25, "gain": 0, "q": 2**-0.5, "kind": "HP", "enabled": True})
    return result


def impulse(bands, rate):
    """Frequency sampling of a causal IIR. Reject insufficiently decayed tails.

    The finite result, not the ideal IIR, is the actual playback filter. Its L1
    norm bounds *any* bounded input sequence, including pathological transients.
    Tail error is controlled separately for fidelity; safety does not rely on it.
    """
    if not any(b["enabled"] and (b["gain"] != 0 or b["kind"] in ("HP", "LP", "NO")) for b in bands):
        return np.array([1.0])
    n = 1 << math.ceil(math.log2(rate*4))
    while n <= 2**22:
        target = response(bands, np.fft.rfftfreq(n, 1/rate), rate)
        h = np.fft.irfft(target, n)
        norm = float(np.sum(np.abs(h)))
        if not math.isfinite(norm) or norm > 1e8:
            raise ValueError("Filter exceeds numerical design limits")
        if np.sum(np.abs(h[n//2:])) < 1e-8 * max(1, norm):
            tail = np.cumsum(np.abs(h[:n//2])[::-1])[::-1]
            hits = np.flatnonzero(tail < 1e-8 * max(1, norm))
            end = max(32, int(hits[0]) if len(hits) else n//2)
            return h[:end].copy()
        n *= 2
    raise ValueError("This extreme curve rings too long. Reduce low-frequency gain or Q.")


def wav_float(samples, rate):
    raw = samples.astype("<f4").tobytes()
    channels = samples.shape[1] if samples.ndim == 2 else 1
    # IEEE float WAVE with fact chunk, supported by APO's libsndfile.
    fmt = struct.pack("<HHIIHH", 3, channels, rate, rate*4*channels, 4*channels, 32)
    body = b"WAVEfmt " + struct.pack("<I", 16) + fmt
    body += b"fact" + struct.pack("<II", 4, len(samples))
    body += b"data" + struct.pack("<I", len(raw)) + raw
    return b"RIFF" + struct.pack("<I", len(body)) + body


def room_impulse(rate, amount):
    """Short static stereo room: immediate dry sound, early reflections, dark tail.

    Fixed per-channel L1 <= 1 preserves bounded input peaks. No feedback,
    modulation, auto makeup, crossfeed, or random changes between applies.
    """
    wet = amount / 100
    result = np.zeros((int(rate * .42) + 1, 2), dtype=float)
    for channel in range(2):
        rng = np.random.default_rng(8701 + channel)
        start = int(rate * .028)
        n = len(result) - start
        noise = rng.standard_normal(n)
        # A short smoothing kernel darkens the late reflections.
        width = max(3, int(rate / 4000))
        noise = np.convolve(noise, np.ones(width)/width, mode="full")[:n]
        noise *= np.exp(-np.arange(n)/rate/.060)
        noise[-int(rate*.025):] *= np.linspace(1, 0, int(rate*.025))
        tail = np.zeros(len(result))
        tail[start:] = noise / max(np.abs(noise).sum(), 1e-15) * .35
        times = np.array([.009, .014, .021, .029, .038, .047, .059, .073])
        times += channel * np.array([.002, -.001, .003, -.002, .001, .004, -.003, .002])
        weights = np.exp(-times/.033)
        weights *= .65 / weights.sum()
        for seconds, weight in zip(times, weights):
            tail[int(round(seconds*rate))] += weight
        tail /= np.abs(tail).sum()
        result[:, channel] = wet * tail
        result[0, channel] = 1 - wet
    result = result.astype("<f4")
    for channel in range(2):
        bound = float(np.abs(result[:, channel].astype(float)).sum())
        if bound > 1:
            result[:, channel] = (result[:, channel].astype(float) / (bound * (1+1e-7))).astype("<f4")
    if not np.isfinite(result).all() or np.max(np.abs(result.astype(float)).sum(axis=0)) > 1:
        raise ValueError("Stereo Room failed its fixed peak bound")
    return result


def append_room(files, lines, model):
    if not model["room"] or model["room_amount"] == 0 or model["bypass"]:
        return
    lines += ["# Stereo Room: fixed peak-preserving mix; front L/R only.",
              "# Other sample rates remain dry; no change to EQ or level."]
    for rate in RATES:
        name = f"room-{rate}.wav"
        files[name] = wav_float(room_impulse(rate, model["room_amount"]), rate)
        lines += [f"If: sampleRate == {rate}", "  Channel: L R",
                  f"  Convolution: {name}", "EndIf:"]
    lines.append("Channel: all")


def bass_filter():
    return {"freq": 120, "gain": 0, "q": 2**-.5, "kind": "LP", "enabled": True}


def bass_impulse(model, rate):
    # Original sample remains at t=0. Only the low-pass copy is delayed.
    low = impulse([bass_filter()], rate)
    offset = int(round(model["bass_delay"] * rate / 1000))
    h = np.zeros(len(low) + offset)
    h[offset:] = low
    h[0] += 1
    return h.astype("<f4")


def bass_response(model, f, rate):
    if not model["bass_track"] or model["bypass"]:
        return np.ones_like(np.asarray(f), dtype=complex)
    offset = int(round(model["bass_delay"] * rate / 1000))
    return 1 + response([bass_filter()], f, rate) * np.exp(-2j*np.pi*np.asarray(f)*offset/rate)


def append_bass(files, lines, model):
    if not model["bass_track"] or model["bypass"]:
        return
    lines.append("# Bass double: original plus 120 Hz low-pass copy; only copy delayed.")
    for rate in RATES:
        name = f"bass-{rate}.wav"
        files[name] = wav_float(bass_impulse(model, rate), rate)
        lines += [f"If: sampleRate == {rate}", "  Channel: all", f"  Convolution: {name}", "EndIf:"]
    lines.append("Channel: all")


def separation_filters(amount):
    """Positive control: center presence and frequency-selective stereo width.

    M/S encode/decode uses 1/2 and 1, respectively, so zero is unity.
    These are ordinary native IIR filters, not source reconstruction.
    """
    t = max(0, amount) / 100
    def band(kind, freq, gain, q):
        return dict(kind=kind, freq=freq, gain=gain*t, q=q, enabled=True)
    return ([band("PK", 2500, 1.5, .8)],
            [band("LS", 180, -12, math.sqrt(.5)), band("HS", 700, 4, math.sqrt(.5))])


def separation_response(model, f, rate):
    amount = 0 if model["bypass"] else model["separation"]
    if amount <= 0:
        return np.ones_like(f, dtype=complex), np.full_like(f, 1+amount/100, dtype=complex)
    mid, side = separation_filters(amount)
    return response(mid, f, rate), response(side, f, rate)


def append_separation(lines, model):
    amount = model["separation"]
    if not amount or model["bypass"] or model["banks"]["all"]["mute"]:
        return
    lines += ["# Separation: final front L/R mid/side processing; no added delay or normalization.",
              "If: inputChannelCount >= 2", "  Channel: L R"]
    if amount < 0:
        # Convex mixing reaches exact mono without doubling the signal.
        own, cross = 1+amount/200, -amount/200
        lines.append(f"  Copy: L={own:.12g}*L+{cross:.12g}*R R={cross:.12g}*L+{own:.12g}*R")
    else:
        # Each Copy line is atomic: both assignments read the previous buffers.
        lines.append("  Copy: L=0.5*L+0.5*R R=0.5*L+-0.5*R")
        for channel, bands in zip(("L", "R"), separation_filters(amount)):
            lines.append(f"  Channel: {channel}")
            for b in bands:
                kind = {"LS": "LSC", "HS": "HSC"}.get(b["kind"], b["kind"])
                lines.append(f'  Filter: ON {kind} Fc {b["freq"]:.12g} Hz Gain {b["gain"]:.12g} dB Q {b["q"]:.12g}')
        lines += ["  Channel: L R", "  Copy: L=L+R R=L+-1*R"]
    # Final mixing must never revive a bank the user explicitly muted.
    for channel in ("L", "R"):
        if model["banks"].get(channel, {}).get("mute"):
            lines.append(f"  Copy: {channel}=0.0")
    lines += ["EndIf:", "Channel: all"]


def boost_headroom(model):
    """Advisory combined response estimate; never a gain or apply restriction.

    Include the all-channel path (also used by unconfigured channels), each
    speaker cascade, DC/Nyquist, and filter centers at every supported rate.
    This estimates steady-state gain, not transient peaks or speaker power.
    """
    worst = -300.0
    if model["banks"]["all"]["mute"]:
        return worst
    separation_bound = 0.0
    for rate in RATES:
        centers = [b["freq"] for bank in model["banks"].values() for b in bank["bands"]]
        f = np.unique(np.r_[0, np.geomspace(1, rate/2, 8192), centers])
        mid, side = separation_response(model, f, rate)
        # Stereo matrix row-sum bound accounts for phase as well as magnitude.
        # Adding its maximum to the worst bank is conservative for unequal banks.
        row_sum = (abs(mid+side) + abs(mid-side))/2
        separation_bound = max(separation_bound, float(20*np.log10(row_sum.max())))
        common = 20*np.log10(np.maximum(abs(response(effective_bands(model, "all"), f, rate)), 1e-15))
        common += model["preamp"] + model["output"] + model["banks"]["all"]["trim"] + (DOUBLE_DB if model["double_track"] else 0)
        common += 20*np.log10(np.maximum(abs(bass_response(model, f, rate)), 1e-15))
        worst = max(worst, float(common.max()))
        for key, b in model["banks"].items():
            if key == "all" or b["mute"]:
                continue
            extra = 20*np.log10(np.maximum(abs(response(effective_bands(model, key), f, rate)), 1e-15)) + b["trim"]
            worst = max(worst, float((common + extra).max()))
    return worst + separation_bound


def boost_notice(model):
    peak = boost_headroom(model)
    label = "Conservative gain estimate" if model["separation"] and not model["bypass"] else "Modeled full-scale peak"
    return (f"{label} {peak:+.1f} dBFS; clipping possible. " if peak > 0 else
            f"{label} {peak:+.1f} dBFS. ") + "Estimated response, not a live measurement."


def native_bundle(model):
    """Native APO IIRs, with imported preamps at their original chain positions."""
    files = {}
    lines = [MARKER, "# Native APO filters; no hidden attenuation or gain recovery.",
             f'Device: {model["device"]}']
    for key in CHANNELS:
        if key not in model["banks"]:
            continue
        b = model["banks"][key]
        lines.append(f"Channel: {key}")
        stages = model.get("preamp_stages", [{"before": 0, "db": model["preamp"]}]) if key == "all" else []
        bands = effective_bands(model, key)
        if model["bypass"]:
            stages = [{"before": 0, "db": model["preamp"]}] if key == "all" else []
        for i in range(len(bands)+1):
            for stage in stages:
                if stage["before"] == i:
                    lines.append(f'Preamp: {stage["db"]:.12g} dB')
            if i == len(bands):
                break
            band = bands[i]
            kind = {"LS": "LSC", "HS": "HSC", "HP": "HPQ", "LP": "LPQ"}.get(band["kind"], band["kind"])
            gain = f' Gain {band["gain"]:.12g} dB' if band["kind"] in ("PK", "LS", "HS") else ""
            lines.append(f'Filter {i+1}: {"ON" if band["enabled"] else "OFF"} {kind} Fc {band["freq"]:.12g} Hz{gain} Q {band["q"]:.12g}')
        trim = b["trim"] + (model["output"] if key == "all" else 0)
        if trim:
            lines.append(f"Preamp: {trim:.12g} dB")
        if key == "all" and model["double_track"]:
            # x[n] + x[n] = 2*x[n]. Apply once, without another playback stream.
            lines += ["# Aligned double: sample-identical sum; no added delay.", f"Preamp: {DOUBLE_DB:.12g} dB"]
        if key == "all":
            append_bass(files, lines, model)
        if b["delay"]:
            lines.append(f'Delay: {b["delay"]:.12g} ms')
        if b["mute"]:
            lines.append("Preamp: -200 dB")
    lines.append("Channel: all")
    report = {"48000": {key: native_stats(model, key) for key in model["banks"]}}
    if model["double_track"] or ((model["bass_track"] or model["separation"]) and not model["bypass"]):
        report["48000"]["all"]["boost_notice"] = boost_notice(model)
    files.update({"preset.json": json_bytes(model), "report.json": json_bytes(report)})
    append_room(files, lines, model)
    append_separation(lines, model)
    files["filters.txt"] = ("\n".join(lines)+"\n").encode()
    return files, report


def native_stats(model, key):
    applied = model["banks"][key]["trim"] + (model["preamp"]+model["output"]+(DOUBLE_DB if model["double_track"] else 0) if key == "all" else 0)
    f = np.geomspace(10, 23999, 8192)
    shape = response(effective_bands(model, key), f, 48000)
    if key == "all":
        shape *= bass_response(model, f, 48000)
    peak = float(np.max(20*np.log10(np.maximum(abs(shape), 1e-15))))+applied
    return {"mode": "native", "applied_db": applied, "estimated_peak_gain_db": peak,
            "rate": 48000, "requested_db": applied, "scope": "Selected bank before Room and Separation"}


def compile_bundle(raw, hold=None):
    # hold is retained only for callers from earlier versions. No ceiling,
    # normalization or previous gain state influences native compilation.
    return native_bundle(validate(raw))


def preview(raw, key, hold=None):
    model = validate(raw)
    if key not in model["banks"]:
        raise ValueError("Unknown speaker bank")
    f = np.geomspace(10, 20000, 400)
    stats = native_stats(model, key)
    if model["double_track"] or ((model["bass_track"] or model["separation"]) and not model["bypass"]):
        stats["double_note"] = boost_notice(model)
    curve = response(effective_bands(model, key), f, 48000)
    if key == "all":
        curve *= bass_response(model, f, 48000)
    ideal = 20*np.log10(np.maximum(np.abs(curve), 1e-12))
    return {"frequency": f.tolist(), "curve": ideal.tolist(),
            "protected": (np.full_like(ideal, -150) if model["banks"][key]["mute"] else ideal+stats["applied_db"]).tolist(), "stats": stats}


# ============================================================================
# 03 — Local atomic storage and deliberately restrictive preset import.
# ============================================================================
def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".bravado-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(obj):
    return json.dumps(obj, indent=2, allow_nan=False).encode("utf-8")


def import_preset(text):
    if len(text.encode("utf-8")) > MAX_JSON:
        raise ValueError("Preset exceeds 256 KiB")
    if text.lstrip().startswith("{"):
        return validate(json.loads(text))
    p = defaults()
    p["name"] = "Imported curve"
    p["banks"] = {"all": bank(True)}
    warnings = []
    if text.lstrip().startswith("["):
        ini = configparser.ConfigParser(interpolation=None, strict=True)
        ini.read_string(text)
        if "Frequencies" not in ini or "Gains" not in ini:
            raise ValueError("Legacy preset import needs Frequencies and Gains sections")
        rows = []
        for i in range(1, 33):
            if f"Frequency{i}" not in ini["Frequencies"]:
                break
            filter_code = ini.get("Filters", f"Filter{i}", fallback="0")
            if filter_code not in ("0", ""):
                raise ValueError("Legacy preset import supports peak filters only; export APO text for other types")
            rows.append({"freq": ini.getfloat("Frequencies", f"Frequency{i}"),
                         "gain": ini.getfloat("Gains", f"Gain{i}", fallback=0),
                         "q": ini.getfloat("Qualities", f"Quality{i}", fallback=1.41),
                         "kind": "PK", "enabled": True})
        p["preamp"] = ini.getfloat("General", "PreAmp", fallback=0)
        p["banks"]["all"]["bands"] = rows
        warnings.append("Imported the all-speaker peak-filter bank only; external effects, other banks and automation are not imported.")
    else:
        rows, pres = [], []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.fullmatch(r"Preamp:\s*([-+\d.eE]+)\s*dB", line, re.I)
            if m:
                pres.append({"before": len(rows), "db": float(m[1])}); continue
            m = re.fullmatch(r"Filter(?:\s+\d+)?:\s*(ON|OFF)\s+(PK|PEQ|LSC|HSC|HPQ|LPQ|NO)\s+Fc\s+([-+\d.eE]+)\s*Hz(?:\s+Gain\s+([-+\d.eE]+)\s*dB)?(?:\s+Q\s+([-+\d.eE]+))?", line, re.I)
            if m:
                on, kind, freq, gain, q = m.groups()
                rows.append({"enabled": on.upper() == "ON", "kind": {"PEQ": "PK", "LSC": "LS", "HSC": "HS", "HPQ": "HP", "LPQ": "LP"}.get(kind.upper(), kind.upper()),
                             "freq": float(freq), "gain": float(gain or 0), "q": float(q or 0.70710678)})
                continue
            if line.lower() in ("channel: all", "device: all"):
                continue
            raise ValueError(f"Unsupported command (nothing imported): {line[:90]}")
        if not rows:
            raise ValueError("No supported filters found")
        p["preamp"] = sum(x["db"] for x in pres)
        if pres:
            p["preamp_stages"] = pres
        p["banks"]["all"]["bands"] = rows
    warnings.append("Imported EQ and gain settings. Review the curve before applying.")
    return validate(p), warnings


# ============================================================================
# 04 — Native Windows endpoint discovery, read-only meter, mute-only emergency.
#      No third-party COM wrapper; no Windows volume setter exists in this app.
# ============================================================================
class GUID(ct.Structure):
    _fields_ = [("bytes", ct.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__((ct.c_ubyte * 16).from_buffer_copy(uuid.UUID(value).bytes_le))


def com_call(ptr, slot, restype, argtypes, *args):
    table = ct.cast(ptr, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    fn = ct.WINFUNCTYPE(restype, ct.c_void_p, *argtypes)(table[slot])
    result = fn(ptr, *args)
    if restype == ct.c_long and result < 0:
        raise OSError(f"Windows audio HRESULT 0x{result & 0xffffffff:08x}")
    return result


def release(ptr):
    if ptr:
        com_call(ptr, 2, ct.c_ulong, [])


class WindowsAudio:
    def __enter__(self):
        if os.name != "nt":
            raise OSError("Windows audio is available on Windows only")
        self.ole = ct.OleDLL("ole32")
        self.ole.CoInitializeEx(None, 0)
        self.enum = ct.c_void_p()
        self.ole.CoCreateInstance(ct.byref(GUID("bcde0395-e52f-467c-8e3d-c4579291692e")), None, 23,
                                  ct.byref(GUID("a95664d2-9614-4f35-a746-de8db63617e6")), ct.byref(self.enum))
        return self

    def __exit__(self, *args):
        release(self.enum)
        self.ole.CoUninitialize()

    def devices(self):
        collection = ct.c_void_p()
        com_call(self.enum, 3, ct.c_long, [ct.c_int, ct.c_ulong, ct.POINTER(ct.c_void_p)], 0, 1, ct.byref(collection))
        result = []
        try:
            count = ct.c_uint()
            com_call(collection, 3, ct.c_long, [ct.POINTER(ct.c_uint)], ct.byref(count))
            for i in range(count.value):
                dev = ct.c_void_p()
                com_call(collection, 4, ct.c_long, [ct.c_uint, ct.POINTER(ct.c_void_p)], i, ct.byref(dev))
                try:
                    ident = ct.c_void_p()
                    com_call(dev, 5, ct.c_long, [ct.POINTER(ct.c_void_p)], ct.byref(ident))
                    name = ct.wstring_at(ident)
                    self.ole.CoTaskMemFree(ident)
                    guid = re.search(r"\{[0-9a-fA-F-]{36}\}$", name).group(0)
                    friendly = guid
                    try:
                        import winreg
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\MMDevices\\Audio\\Render\\"+guid+"\\Properties") as k:
                            friendly = winreg.QueryValueEx(k, "{a45c254e-df1c-4efd-8020-67d146a850e0},2")[0]
                            try:
                                friendly += " (" + winreg.QueryValueEx(k, "{b3f8fa53-0004-438e-9003-51a46e139bfc},6")[0] + ")"
                            except OSError:
                                pass
                    except OSError:
                        pass
                    result.append({"id": name, "guid": guid, "name": str(friendly)})
                finally:
                    release(dev)
        finally:
            release(collection)
        return result

    def activate(self, iid, device_id=None):
        dev = ct.c_void_p()
        if device_id:
            com_call(self.enum, 5, ct.c_long, [ct.c_wchar_p, ct.POINTER(ct.c_void_p)], device_id, ct.byref(dev))
        else:
            com_call(self.enum, 4, ct.c_long, [ct.c_int, ct.c_int, ct.POINTER(ct.c_void_p)], 0, 1, ct.byref(dev))
        try:
            obj = ct.c_void_p()
            com_call(dev, 3, ct.c_long, [ct.POINTER(GUID), ct.c_ulong, ct.c_void_p, ct.POINTER(ct.c_void_p)],
                     ct.byref(GUID(iid)), 23, None, ct.byref(obj))
            return obj
        finally:
            release(dev)

    def meter(self):
        obj = self.activate("c02216f6-8c67-4b5b-9d00-d008e73e0064")
        try:
            value = ct.c_float()
            com_call(obj, 3, ct.c_long, [ct.POINTER(ct.c_float)], ct.byref(value))
            return min(1, max(0, value.value))
        finally:
            release(obj)

    def mute_all(self):
        results, errors = [], []
        for dev in self.devices():
            obj = None
            try:
                obj = self.activate("5cdf2c82-841e-4546-9722-0cf74078229a", dev["id"])
                com_call(obj, 14, ct.c_long, [ct.c_int, ct.c_void_p], 1, None)
                results.append(dev["name"])
            except Exception as e:
                errors.append(f'{dev["name"]}: {e}')
            finally:
                release(obj)
        return results, errors


def emergency_windows_mute():
    try:
        with WindowsAudio() as audio:
            names, errors = audio.mute_all()
        return {"ok": bool(names) and not errors, "devices": names,
                "error": "; ".join(errors) or ("" if names else "No active playback endpoints")}
    except Exception as e:
        return {"ok": False, "devices": [], "error": str(e)}


def find_apo():
    candidates = []
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\EqualizerAPO") as key:
                candidates.append(Path(winreg.QueryValueEx(key, "ConfigPath")[0]))
        except OSError:
            pass
    candidates.append(Path(os.environ.get("ProgramFiles", "C:/Program Files"))/"EqualizerAPO"/"config")
    return next((p for p in candidates if p.is_dir() and (p.parent/"EqualizerAPO.dll").is_file()), None)


# ============================================================================
# 05 — APO ownership: backup, immutable assets, atomic switch, tamper latch.
# ============================================================================
class Engine:
    def __init__(self, data, apo=None):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True)
        selected_apo = Path(apo) if apo else find_apo()
        self.apo = selected_apo.resolve() if selected_apo else None
        self.lock = threading.RLock()
        self.trip = threading.Event()
        self.authorize_commit = lambda: None
        self.machine = machine_key()
        self.state = {"owned": False, "enabled": False, "muted": False, "fault": "", "report": {}, "files": {}}
        self.storage_error = ""
        try:
            if (self.data/"session.json").exists():
                saved = json.loads((self.data/"session.json").read_text("utf-8"))
                if saved.get("machine") != self.machine:
                    # Presets travel; ownership, recovery paths and device IDs do not.
                    saved = {}
                saved.setdefault("enabled", bool(saved.get("owned")))
                self.state.update(saved)
                # v0.2 treated another controller's takeover as a mute fault.
                # Clear only that obsolete latch; never unmute Windows here.
                if (not self.state["owned"] and self.state.get("fault") ==
                        "The active APO configuration was changed outside Bravado"):
                    self.state.update(muted=False, enabled=False,
                                      fault="Configuration changed outside Bravado. Enable to take control again.")
                if saved.get("machine") == self.machine and self.state.get("apo") != str(self.apo):
                    self.state.update(owned=False, fault="APO path changed; reconnect explicitly")
        except Exception as e:
            self.state.update(owned=False, fault=f"Session unreadable: {e}")
        if self.state["muted"] or self.state["fault"]:
            self.trip.set()

    def save_session(self):
        self.state["apo"] = str(self.apo)
        self.state["machine"] = self.machine
        atomic_write(self.data/"session.json", json_bytes(self.state))

    def root_bytes(self):
        if not self.apo:
            raise ValueError("Equalizer APO was not found. Install/select its config directory first.")
        try:
            return (self.apo/"config.txt").read_bytes()
        except FileNotFoundError:
            return b""

    def current_preset(self):
        if not self.apo:
            raise ValueError("Equalizer APO configuration was not found")
        total = 0
        def read(path, stack=()):
            nonlocal total
            path = path.resolve()
            if not path.is_relative_to(self.apo) or path in stack or len(stack) > 8:
                raise ValueError("Unsupported include path, cycle or depth")
            data = path.read_bytes()
            total += len(data)
            if total > MAX_JSON:
                raise ValueError("Current configuration exceeds 256 KiB")
            text = data.decode("utf-8-sig")
            lines = []
            for line in text.splitlines():
                match = re.fullmatch(r"\s*Include:\s*(.+?)\s*", line, re.I)
                if match:
                    lines.append(read(path.parent/match[1].strip('"'), stack+(path,)))
                else:
                    lines.append(line)
            return "\n".join(lines)
        model, warnings = import_preset(read(self.apo/"config.txt"))
        model["name"] = "Current APO configuration"
        return {"model": model, "warnings": warnings}

    def backup_root(self, data):
        name = "original-" + time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(4) + ".txt"
        atomic_write(self.data/name, data)
        if not self.state.get("backup"):
            self.state["backup"] = name
        self.state["last_takeover_backup"] = name
        # Persist recovery information BEFORE replacing the active configuration.
        self.save_session()

    def commit(self, root, changes):
        """Bounded force-write retries; never bypass permissions or fight forever."""
        for attempt in range(4):
            try:
                self.authorize_commit()
                atomic_write(self.apo/"config.txt", root)
                if self.root_bytes() != root:
                    raise RuntimeError("Configuration was overwritten immediately by another writer")
                self.state.update(changes, owned=True, root_hash=digest(root),
                                  write_attempts=attempt+1, verified_at=time.strftime("%H:%M:%S"))
                self.verify()
                self.save_session()
                return
            except OSError as e:
                if getattr(e, "winerror", None) not in (32, 33) or attempt == 3:
                    raise
            except RuntimeError:
                if attempt == 3:
                    raise
            time.sleep((0.1, 0.25, 0.5)[attempt])

    def enable(self, model):
        was_latched = self.trip.is_set()
        try:
            return self.apply(model, connect=True, force=True)
        except Exception:
            if was_latched:
                self.trip.set()
            raise

    def verify(self, assets=True):
        if not self.state["owned"]:
            return False
        if digest(self.root_bytes()) != self.state.get("root_hash"):
            raise ValueError("The active APO configuration was changed outside Bravado")
        if assets:
            for rel, expected in self.state.get("files", {}).items():
                target = (self.apo/rel).resolve()
                if not target.is_relative_to(self.apo.resolve()):
                    raise ValueError("Invalid managed asset path")
                if digest(target.read_bytes()) != expected:
                    raise ValueError(f"Managed filter changed or disappeared: {rel}")
        return True

    def check(self):
        with self.lock:
            try:
                if self.state["owned"] and digest(self.root_bytes()) != self.state.get("root_hash"):
                    self.state.update(owned=False, enabled=False, fault="Configuration changed outside Bravado. Enable to take control again.")
                    self.save_session()
                    return
                self.verify()
            except Exception as e:
                self.trip.set()
                self.state.update(owned=False, muted=True, fault=str(e))
                self.state["mute_result"] = emergency_windows_mute()
                self.save_session()

    def apply(self, model, connect=False, force=False):
        model = validate(model)
        # Compile and validate before the atomic configuration switch.
        with self.lock:
            if force:
                # An explicit Enable starts a new attempt; a later Panic still cancels it.
                self.trip.clear()
            if self.trip.is_set():
                raise ValueError("Safety latch is set. Acknowledge it first.")
            if not connect and (not self.state["owned"] or not self.state.get("enabled")):
                raise ValueError("Equalizer is disabled. Click Enable first.")
            before = self.root_bytes()
            if self.state["owned"] and not force:
                self.verify()
            files, report = compile_bundle(model)
            if self.trip.is_set():
                raise ValueError("Apply cancelled by emergency mute")
            generation = "bravado-" + uuid.uuid4().hex
            folder = self.apo/generation
            folder.mkdir()
            for name, data in files.items():
                atomic_write(folder/name, data)
            root = (MARKER+"\n# Complete selected processing chain.\nInclude: "+generation+"/filters.txt\n").encode()
            if force:
                before = self.root_bytes()
            if self.root_bytes() != before:
                raise ValueError("APO config changed during compilation. No switch performed.")
            if force or not self.state["owned"]:
                self.backup_root(before)
            if self.trip.is_set():
                raise ValueError("Apply cancelled by emergency mute")
            try:
                self.commit(root, {"enabled": True, "muted": False, "fault": "", "report": report,
                                   "files": {generation+"/"+n: digest(d) for n, d in files.items()},
                                   "model": model})
            except Exception:
                self.trip.set()
                self.state.update(fault="Switch/save failed. Inspect configuration before recovery.")
                raise
            return {"message": "Equalizer enabled. " + report.get("48000", {}).get("all", {}).get("boost_notice", "Endpoint APO setup is required for audible processing."), "report": report}

    def disable(self):
        with self.lock:
            self.trip.clear()
            before = self.root_bytes()
            self.backup_root(before)
            # Off is a genuine unity bypass in either processing mode.
            attenuation = 0.0
            device = validate(self.state.get("model", defaults()))["device"]
            root = (MARKER + "\n# EQ DISABLED: unity output, no filters.\nStage: post-mix\n"
                    f"Device: {device}\nChannel: all\nPreamp: {attenuation:.6f} dB\n").encode()
            try:
                if self.trip.is_set():
                    raise ValueError("Disable cancelled by emergency mute")
                self.commit(root, {"enabled": False, "muted": False, "fault": "", "files": {}})
            except Exception:
                self.trip.set()
                self.state.update(fault="Disable failed. Inspect the active configuration.")
                raise
            return {"message": "Equalizer disabled."}

    def panic(self):
        # Mute is independent of compilation/file locks and never reverses itself.
        self.trip.set()
        result = emergency_windows_mute()
        with self.lock:
            self.state.update(muted=True, mute_result=result)
            if self.state["owned"]:
                try:
                    self.verify(assets=False)
                    # Keep the protected filter assets; add absolute digital silence.
                    root = self.root_bytes() + b"\nDevice: all\nStage: post-mix\nChannel: all\nPreamp: -200 dB\n"
                    atomic_write(self.apo/"config.txt", root)
                    self.state["root_hash"] = digest(root)
                except Exception as e:
                    self.state["fault"] = str(e)
            self.save_session()
        return result

    def acknowledge(self):
        with self.lock:
            # Does not restore audio or change any volume. Apply is still explicit.
            self.state.update(muted=False, fault="")
            self.trip.clear()
            self.save_session()
        return {"message": "Latch acknowledged. Enable or Apply to restore the curve. If Windows is already muted, unmute it manually."}

    def restore(self):
        with self.lock:
            if not self.state["owned"]:
                raise ValueError("Bravado does not own the current configuration; restore the saved backup manually.")
            self.verify(assets=False)
            name = self.state.get("backup", "")
            if not re.fullmatch(r"original-[\w-]+\.txt", name):
                raise ValueError("Original backup is unavailable")
            data = (self.data/name).read_bytes()
            atomic_write(self.apo/"config.txt", data)
            self.state.update(owned=False, enabled=False, muted=False, files={}, fault="")
            self.trip.clear()
            self.save_session()
            return {"message": "Previous audio configuration restored."}

    def status(self):
        return {"apo": str(self.apo or ""), "owned": self.state["owned"],
                "enabled": bool(self.state["owned"] and self.state.get("enabled") and not self.trip.is_set()
                                and not self.state["muted"] and not self.state["fault"]),
                "verified_at": self.state.get("verified_at", ""), "muted": self.state["muted"], "latched": self.trip.is_set(),
                "fault": self.state["fault"], "report": self.state.get("report", {}),
                "storage_error": self.storage_error, "data": str(self.data)}


# ============================================================================
# 06 — Loopback-only API. Ephemeral bearer token, strict origin/host, no CORS.
# ============================================================================
def elevated_action(engine, action, model):
    """Bounded elevation. An expired/cancelled helper cannot commit later."""
    if os.name != "nt":
        raise RuntimeError("Administrator enable is available on Windows only")
    from ctypes import wintypes as wt
    if ct.windll.shell32.IsUserAnAdmin():
        return engine.enable(model) if action == "enable" else engine.disable()

    class ShellInfo(ct.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("fMask", wt.ULONG), ("hwnd", wt.HWND),
                    ("lpVerb", wt.LPCWSTR), ("lpFile", wt.LPCWSTR), ("lpParameters", wt.LPCWSTR),
                    ("lpDirectory", wt.LPCWSTR), ("nShow", ct.c_int), ("hInstApp", wt.HINSTANCE),
                    ("lpIDList", ct.c_void_p), ("lpClass", wt.LPCWSTR), ("hkeyClass", wt.HKEY),
                    ("dwHotKey", wt.DWORD), ("hIcon", wt.HANDLE), ("hProcess", wt.HANDLE)]

    model = validate(model)
    deadline = time.time()+ADMIN_TIMEOUT
    payload = json_bytes({"action": action, "model": model, "apo": str(engine.apo) if engine.apo else None,
                          "expires_at": deadline})
    request = engine.data.resolve()/("elevate-"+secrets.token_hex(12)+".json")
    result_file = request.with_suffix(".result.json")
    atomic_write(request, payload)
    args = [] if getattr(sys, "frozen", False) else [str(Path(__file__).resolve())]
    args += ["--admin-request", str(request), "--request-sha256", digest(payload)]
    info = ShellInfo()
    info.cbSize = ct.sizeof(info); info.fMask = 0x40 | 0x100
    info.lpVerb = "runas"; info.lpFile = sys.executable
    info.lpParameters = subprocess.list2cmdline(args); info.lpDirectory = str(APP_DIR)
    info.nShow = 0
    cancelled = threading.Event()
    finished = threading.Event()
    outcome = {}

    def worker():
        kernel = ct.WinDLL("kernel32", use_last_error=True)
        kernel.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
        kernel.WaitForSingleObject.restype = wt.DWORD
        kernel.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
        kernel.CloseHandle.argtypes = [wt.HANDLE]
        kernel.GetProcessId.argtypes = [wt.HANDLE]
        kernel.GetProcessId.restype = wt.DWORD
        shell = ct.WinDLL("shell32", use_last_error=True)
        shell.ShellExecuteExW.argtypes = [ct.POINTER(ShellInfo)]
        shell.ShellExecuteExW.restype = wt.BOOL
        helper_record = engine.data/"helper-process.json"
        helper_identity = None
        try:
            if not shell.ShellExecuteExW(ct.byref(info)):
                error = ct.get_last_error()
                raise RuntimeError("Administrator request cancelled." if error == 1223 else
                                   f"Windows could not start the administrator helper (error {error}).")
            try:
                with ManagedProcess(kernel.GetProcessId(info.hProcess), terminate=False) as process:
                    helper_identity = process.identity()
                helper_identity["command"] = "--admin-request"
                atomic_write(helper_record, json_bytes(helper_identity))
            except OSError:
                pass  # Lease cancellation still blocks a late commit.
            while kernel.WaitForSingleObject(info.hProcess, 100) == 258:
                if cancelled.is_set() or time.time() >= deadline:
                    # Only the process handle returned by our own launch is stopped.
                    kernel.TerminateProcess(info.hProcess, 1)
                    raise RuntimeError("Administrator operation timed out. Try Enable again.")
            if not result_file.exists():
                raise RuntimeError("Administrator helper exited without a result.")
            outcome.update(json.loads(result_file.read_text("utf-8")))
        except Exception as e:
            outcome.update(ok=False, error=str(e))
        finally:
            if helper_identity and info.hProcess and kernel.WaitForSingleObject(info.hProcess, 0) == 0:
                try:
                    saved = json.loads(helper_record.read_text("utf-8"))
                    if saved.get("pid") == helper_identity["pid"]:
                        helper_record.unlink(missing_ok=True)
                except (OSError, ValueError):
                    pass
            if info.hProcess:
                kernel.CloseHandle(info.hProcess)
            finished.set()

    # ShellExecute itself can wait for UAC, so it must not block the API indefinitely.
    was_latched = engine.trip.is_set()
    engine.lock.acquire()
    engine.trip.clear()
    try:
        threading.Thread(target=worker, daemon=True).start()
        end = time.monotonic()+ADMIN_TIMEOUT
        while not finished.wait(0.1):
            if engine.trip.is_set():
                raise RuntimeError("Administrator operation cancelled by emergency mute")
            if time.monotonic() >= end:
                raise RuntimeError("Administrator approval/operation timed out after 60 seconds. The operation lock was released; try Enable again.")
        if not outcome.get("ok"):
            raise RuntimeError(outcome.get("error", "Administrator operation failed"))
        with engine.lock:
            if (engine.data/"session.json").exists():
                engine.state.update(json.loads((engine.data/"session.json").read_text("utf-8")))
            engine.verify()
        return outcome["result"]
    except Exception:
        if was_latched:
            engine.trip.set()
        raise
    finally:
        cancelled.set()
        try:
            request.unlink(missing_ok=True)
            if finished.is_set():
                result_file.unlink(missing_ok=True)
        finally:
            engine.lock.release()


def check_admin_lease(path, expected_hash, expires_at):
    if time.time() >= number(expires_at, 0, 1e12, "Operation deadline"):
        raise ValueError("Administrator request expired; no configuration switch performed")
    if not path.exists() or not secrets.compare_digest(digest(path.read_bytes()), expected_hash):
        raise ValueError("Administrator request was cancelled; no configuration switch performed")


def run_admin_request(path, expected_hash):
    path = Path(path).resolve()
    if not re.fullmatch(r"elevate-[0-9a-f]{24}\.json", path.name):
        raise ValueError("Invalid administrator request filename")
    raw = path.read_bytes()
    if len(raw) > MAX_JSON or not secrets.compare_digest(digest(raw), expected_hash or ""):
        raise ValueError("Administrator request changed or is invalid")
    data = json.loads(raw)
    try:
        if data["action"] not in ("enable", "disable"):
            raise ValueError("Invalid administrator operation")
        check_admin_lease(path, expected_hash, data.get("expires_at", 0))
        engine = Engine(path.parent, data.get("apo"))
        engine.authorize_commit = lambda: check_admin_lease(path, expected_hash, data.get("expires_at", 0))
        result = engine.enable(validate(data["model"])) if data["action"] == "enable" else engine.disable()
        response = {"ok": True, "result": result}
    except Exception as e:
        response = {"ok": False, "error": str(e)}
    atomic_write(path.with_suffix(".result.json"), json_bytes(response))
    return 0 if response["ok"] else 1


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def serve(engine, port=0, open_browser=False, ready_file=None, on_ready=None, on_server=None):
    token = secrets.token_urlsafe(32)
    mutations = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log the tokenized launch URL.

        def reply(self, status, data, mime="application/json"):
            if not isinstance(data, bytes):
                data = json_bytes(data)
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def permitted(self, api=True):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host:
                self.reply(403, {"error": "Invalid host"}); return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://"+host:
                self.reply(403, {"error": "Invalid origin"}); return False
            if api and not secrets.compare_digest(self.headers.get("X-Bravado-Token", ""), token):
                self.reply(403, {"error": "Open Bravado using its launch shortcut"}); return False
            return True

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if not self.permitted(api=path != "/"):
                return
            try:
                if path == "/":
                    self.reply(200, HTML.encode(), "text/html; charset=utf-8")
                elif path == "/api/state":
                    presets = factory_presets()
                    store = engine.data/"presets.json"
                    if store.exists():
                        try:
                            saved = json.loads(store.read_text("utf-8"))
                            presets.update({k: validate(v) for k, v in saved.items() if k not in presets})
                        except Exception as e:
                            engine.storage_error = f"Saved presets were not loaded: {e}"
                    devices, audio_error = [], ""
                    try:
                        with WindowsAudio() as audio:
                            devices = audio.devices()
                    except Exception as e:
                        audio_error = str(e)
                    self.reply(200, {"version": VERSION, "presets": presets, "devices": devices,
                                     "factory_notes": PRESET_NOTES,
                                     "active_model": self.state_model(), "current_error": "",
                                     "audio_error": audio_error, "status": engine.status()})
                elif path == "/api/current":
                    self.reply(200, engine.current_preset())
                elif path == "/api/status":
                    self.reply(200, engine.status())
                elif path == "/api/meter":
                    try:
                        with WindowsAudio() as audio:
                            value = audio.meter()
                        self.reply(200, {"peak": value})
                    except Exception as e:
                        self.reply(200, {"peak": None, "error": str(e)})
                else:
                    self.reply(404, {"error": "Not found"})
            except Exception as e:
                self.reply(400, {"error": str(e)})

        def state_model(self):
            try:
                return validate(engine.state["model"])
            except (KeyError, ValueError, TypeError):
                return None

        def do_POST(self):
            if not self.permitted():
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > MAX_JSON:
                    raise ValueError("Request size is invalid")
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("JSON required")
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(size))
                path = urllib.parse.urlsplit(self.path).path
                if path == "/api/shutdown":
                    # Shutdown must stay available even when a mutation/UAC is stuck.
                    result = {"message": "Bravado is closing. Your audio settings remain active."}
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                elif path == "/api/panic":
                    result = engine.panic()
                elif path == "/api/preview":
                    result = preview(data["model"], data.get("channel", "all"), engine.state.get("report"))
                elif path == "/api/import":
                    imported = import_preset(data["text"])
                    p, warnings = imported if isinstance(imported, tuple) else (imported, [])
                    result = {"model": p, "warnings": warnings}
                elif path == "/api/export":
                    files, report = compile_bundle(data["model"], engine.state.get("report"))
                    buf = io.BytesIO()
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                        for name, content in files.items():
                            z.writestr(name, content)
                    self.reply(200, buf.getvalue(), "application/zip"); return
                else:
                    if not mutations.acquire(blocking=False):
                        raise ValueError("Another operation is in progress")
                    try:
                        if path in ("/api/enable", "/api/connect"):
                            result = engine.enable(data["model"])
                        elif path == "/api/apply":
                            result = engine.apply(data["model"])
                        elif path == "/api/disable":
                            result = engine.disable()
                        elif path in ("/api/enable-admin", "/api/disable-admin"):
                            result = elevated_action(engine, "enable" if path.endswith("enable-admin") else "disable", data["model"])
                        elif path == "/api/device-setup":
                            if not engine.apo:
                                raise ValueError("Equalizer APO is not installed")
                            selector = engine.apo.parent/"DeviceSelector.exe"
                            if not selector.is_file():
                                raise ValueError("The installed APO Device Selector was not found")
                            os.startfile(str(selector))
                            result = {"message": "Output-device setup opened. Enable Equalizer APO on your playback endpoint there; follow its restart instructions if shown."}
                        elif path == "/api/acknowledge":
                            result = engine.acknowledge()
                        elif path == "/api/restore":
                            result = engine.restore()
                        elif path == "/api/save":
                            model = validate(data["model"])
                            if model["name"] in factory_presets():
                                raise ValueError("Built-in presets are read-only. Save with a new name.")
                            path = engine.data/"presets.json"
                            saved = json.loads(path.read_text("utf-8")) if path.exists() else {}
                            if data.get("delete"):
                                saved.pop(model["name"], None)
                            else:
                                saved[model["name"]] = model
                            atomic_write(path, json_bytes(saved))
                            result = {"message": "Preset library saved"}
                        else:
                            self.reply(404, {"error": "Not found"}); return
                    finally:
                        mutations.release()
                self.reply(200, result)
            except PermissionError as e:
                self.reply(403, {"code": "permission_denied", "error": f"Windows denied file access: {e}. Use Enable as administrator (or Disable as administrator)."})
            except OSError as e:
                self.reply(400, {"code": "io_error", "error": str(e)})
            except Exception as e:
                self.reply(400, {"error": str(e)})

    server = LocalServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/#{token}"
    stop = threading.Event()

    def monitor():
        while not stop.wait(1):
            try:
                engine.check()
            except Exception as e:
                engine.storage_error = str(e)
    threading.Thread(target=monitor, daemon=True).start()
    launch = {"url": url, "pid": os.getpid()}
    if os.name == "nt":
        with ManagedProcess(os.getpid(), terminate=False) as own:
            launch.update(own.identity())
    atomic_write(engine.data/"launch.json", json_bytes(launch))
    if ready_file:
        atomic_write(ready_file, json_bytes(launch))
    if on_ready:
        on_ready()
    print(f"Bravado {VERSION} — local panel at 127.0.0.1:{server.server_port}", flush=True)
    if on_server:
        on_server(server, url)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        # An old controller must never erase a replacement controller's launch file.
        try:
            saved = json.loads((engine.data/"launch.json").read_text("utf-8"))
            if saved.get("pid") == os.getpid():
                (engine.data/"launch.json").unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


# ============================================================================
# 07 — Embedded panel. No JS frameworks, CDN, build pipeline, or asset directory.
# Leon-Executes / behind the glass.
# ============================================================================
HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bravado · Precision equalizer</title>
<style>
:root{color-scheme:dark;--bg:#101316;--panel:#191e23;--line:#303941;--ink:#ecf0ef;--muted:#9da9af;--accent:#b6ee81;--cyan:#7fd5dd;--danger:#ff9589}
*{box-sizing:border-box}html,body{height:100%;overflow:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:12px/1.4 'Segoe UI',sans-serif;display:flex;flex-direction:column}
button,input,select{font:inherit}button,select,input[type=number],input[type=text]{background:#242c32;border:1px solid #3a454e;border-radius:5px;color:var(--ink);padding:5px 8px}button{cursor:pointer;white-space:nowrap}button:hover{background:#354149;border-color:#7c8e98}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}button:disabled{opacity:.4;cursor:wait}button.primary{background:var(--accent);border-color:var(--accent);color:#15220b;font-weight:600}button.danger{border-color:#79524b;color:var(--danger)}button[aria-pressed=true]{background:#303e2b;border-color:#718e5c;color:var(--accent)}button.small{padding:4px 7px;font-size:11px}input[type=checkbox],input[type=range]{accent-color:var(--accent)}input[type=number]{width:65px;font-variant-numeric:tabular-nums}select{max-width:100%}small,.muted{color:var(--muted)}
header{padding:10px 14px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);gap:12px;flex:none}.brand{display:flex;align-items:center;gap:9px}.logo{width:30px;height:30px;border:1px solid var(--accent);border-radius:9px;display:flex;gap:3px;align-items:center;justify-content:center}.logo i{width:2px;background:var(--accent);border-radius:2px}.logo i:nth-child(1){height:10px}.logo i:nth-child(2){height:20px}.logo i:nth-child(3){height:15px}.logo i:nth-child(4){height:7px}h1{font-size:17px;letter-spacing:2.5px;margin:0;font-weight:600}h2{font-size:12px;font-weight:600;margin:0}.tag{display:none;font-size:9px;letter-spacing:1px;text-transform:uppercase}.badge{display:none}.actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.shell{width:100%;padding:10px 12px 8px;flex:1;min-height:0;display:flex;flex-direction:column}.topline{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:9px;flex:none}.title{font-size:16px;font-weight:600}.dirty{color:#c8b792;font-size:10px}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 236px;gap:10px;min-height:0;flex:1}.workspace>*,.lower>*{min-width:0}.maincolumn{display:flex;flex-direction:column;min-height:0;gap:9px;overflow:auto;padding-right:1px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:9px;min-width:0}.maincolumn>.panel{flex:none}.panelhead{padding:8px 10px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:7px}.switchlabel{display:flex;align-items:center;gap:4px;font-size:11px}.preamp{padding:9px 10px;display:flex;align-items:center;gap:9px}.preamp input[type=range]{flex:1;min-width:40px}.preamp small{font-size:10px}.bandwrap{overflow-x:auto;padding:0 8px 6px}.bands{display:flex;min-width:0;gap:3px}.band{flex:1;min-width:41px;text-align:center;padding:5px 1px 2px;border-radius:5px;background:linear-gradient(#20283055,#171c2200)}.band input[type=number]{width:100%;text-align:center;padding:3px 0;border-color:transparent;background:#101519;font-size:10px;appearance:textfield}.band input::-webkit-inner-spin-button{appearance:none}.freq{color:var(--cyan);font-weight:600}.rail{height:100px;margin:6px 0;position:relative;display:flex;justify-content:center;background:repeating-linear-gradient(to top,transparent 0px,transparent 22px,#39424a 23px,transparent 24px);background-size:10px 100%;background-position:center;background-repeat:no-repeat}.rail:after{content:'';position:absolute;top:50%;width:100%;border-top:1px solid #56636a;pointer-events:none}.rail input{writing-mode:vertical-lr;direction:rtl;width:22px;height:100px;margin:0;z-index:1;cursor:ns-resize}.band .gain{color:var(--accent);font-weight:600;margin-bottom:2px}.band select{font-size:10px;width:100%;padding:3px 0;margin-top:3px}.bandlabel{font-size:9px;color:var(--muted);margin:3px 0 1px}.band .enable{height:13px;margin:5px 0 0}.band.disabled{opacity:.45}.scale{min-width:22px;position:relative;color:#82929b;font-size:9px}.scale span{position:absolute;left:0}.scale span:nth-child(1){top:35px}.scale span:nth-child(2){top:78px}.scale span:nth-child(3){top:122px}.tools{padding:0 8px 7px;display:flex;gap:4px;align-items:center;flex-wrap:wrap}.tools .muted{display:none}.tools button.small{font-size:10px;padding:3px 6px}
.bottom{flex:none}.meterpanel{padding:8px 10px}.meter{height:6px;margin-top:6px;background:#0a0e11;border-radius:6px;overflow:hidden}.meter>div{height:100%;width:0;background:linear-gradient(90deg,#79bc77,#c2ed83,#ead473,#ec887a);transition:width .12s}.statrow{display:flex;justify-content:space-between;gap:10px;font-size:10px}.meterpanel>.note{display:none}.lower{display:grid;grid-template-columns:192px minmax(0,1fr);gap:9px;flex:1;min-height:180px}.presetlist{padding:2px;flex:1;min-height:0;overflow:auto}.lower>.panel{min-height:0}.lower>.panel:first-child{display:flex;flex-direction:column;overflow:hidden}.lower .panelhead,.librarytools,.exchange{flex:none}.lower>.panel:first-child:has(.exchange[open]){display:block;overflow:auto}.presetlist button{width:100%;text-align:left;border-color:transparent;background:transparent;border-radius:4px;padding:2px 6px;line-height:12px;font-size:10px;overflow:hidden;text-overflow:ellipsis}.presetlist button.selected{background:#303e2b;border-color:#587348;color:var(--accent)}.lower>.panel:first-child .panelhead{padding:5px 10px}.librarytools{border-top:1px solid var(--line);padding:4px 6px;display:flex;gap:4px;flex-wrap:wrap}.exchange{border-top:1px solid var(--line);padding:4px 6px}.exchange h2{font-size:10px;margin-bottom:5px}.exchange .actions{gap:4px}.exchange button{font-size:10px}.graphbody{padding:5px 9px 8px}canvas{width:100%;height:120px;display:block}.legend{display:flex;gap:10px;font-size:9px;color:var(--muted);flex-wrap:wrap}.legend b{display:inline-block;width:12px;height:2px;vertical-align:middle;margin-right:4px;background:var(--cyan)}.legend .protected{background:var(--accent)}#graphStats{font-size:10px;text-align:right}
.rightcolumn{display:flex;flex-direction:column;gap:9px;min-height:0;overflow:auto}.aside{padding:10px;flex:1}.aside section+section{border-top:1px solid var(--line);margin-top:10px;padding-top:10px}.aside h2{margin-bottom:7px}.aside select{width:100%;margin-bottom:5px;font-size:11px}.field{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:6px;font-size:11px}.field input[type=number]{width:58px;padding:3px 6px}.note{font-size:10px;color:var(--muted);margin:6px 0 0;line-height:1.5}.control-help{font-size:10px;color:var(--muted);margin-top:5px}.control-help summary{cursor:pointer}.control-help[open] summary{color:var(--cyan)}.separation-control{margin:8px 0}.separation-control .field{margin:0}.separation-control output{font-variant-numeric:tabular-nums;color:var(--accent)}.separation-control input{width:100%;margin:5px 0 0;display:block;cursor:ew-resize}.separation-scale{display:flex;justify-content:space-between;font-size:9px;color:var(--muted)}#doubleNote{display:none}.status{padding:9px 10px;font-size:11px;color:var(--muted);flex:none}#statusTitle{color:var(--ink);font-weight:600;display:inline}#statusText{font-size:10px;line-height:1.4;margin-top:3px}.status .actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.status button{font-size:10px;white-space:normal;text-align:left;padding:4px 6px}.status #quitBtn{grid-column:1/-1}.statusgood{color:var(--accent)!important}.footer{display:flex;justify-content:space-between;gap:10px;margin-top:7px;color:#839098;font-size:9px;flex:none}
.message{position:fixed;left:14px;bottom:26px;max-width:min(680px,calc(100vw - 28px));padding:10px 14px;border-radius:7px;border:1px solid #466075;background:#1b2933;white-space:pre-wrap;font-size:12px;box-shadow:0 5px 25px #0007;z-index:10;cursor:pointer}.message.error{border-color:#995c54;background:#322320;color:#ffd0c8}.message:empty,.hidden{display:none!important}dialog{background:var(--panel);border:1px solid #536069;border-radius:10px;color:var(--ink);width:min(580px,90vw);max-height:85vh;overflow:auto;padding:20px}dialog::backdrop{background:#0009}dialog h2{font-size:18px;margin-bottom:12px}dialog p{color:var(--muted);line-height:1.6}dialog .actions{margin-top:16px;justify-content:flex-end}dialog input[type=text]{width:100%}.dangerbox{background:#322623;border:1px solid #7b5146;padding:10px;border-radius:6px;color:#f5bdac!important}kbd{border:1px solid #4a575f;border-radius:4px;padding:1px 4px}*{scrollbar-width:thin;scrollbar-color:#526168 #171c21}
@media(max-width:950px){.workspace{grid-template-columns:minmax(0,1fr) 218px}.band{min-width:36px}.lower{grid-template-columns:174px minmax(0,1fr)}.rail,.rail input{height:100px}.scale span:nth-child(2){top:78px}.scale span:nth-child(3){top:122px}.preamp small{display:none}}
@media(max-width:760px){html,body{overflow:auto;height:auto;min-height:100%}.shell{display:block}.workspace{display:flex;flex-direction:column}.maincolumn,.rightcolumn{overflow:visible}.lower{min-height:0}.bands{min-width:620px}.rightcolumn{margin-top:10px}.topline{align-items:flex-start}.topline .actions{justify-content:flex-end}.title{font-size:14px}.tag{display:none}header{padding:8px 12px}.footer{margin-bottom:6px}}
</style></head><body>
<header><div class="brand"><div class="logo" aria-hidden="true"><i></i><i></i><i></i><i></i></div><div><h1>BRAVADO</h1><div class="tag muted">Precision equalizer / Desktop · 0.8.6</div></div></div><div class="actions"><span class="badge" id="modeBadge">NATIVE APO</span><button id="helpBtn">Help</button><button class="danger" id="panicBtn" title="Mute Windows playback endpoints and latch protection">Mute <small>Esc</small></button></div></header>
<main class="shell"><div id="message" class="message" role="status" aria-live="polite"></div>
<div class="topline"><div><div class="tag muted">PRESET</div><div class="title" id="presetTitle">Bravado Signature Preset</div><span class="dirty" id="dirty">Ready to apply</span></div><div class="actions"><button id="connectBtn" class="primary">Enable</button><button id="disableBtn">Disable</button><button id="applyBtn">Apply changes</button></div></div>
<div class="workspace"><div class="maincolumn"><div class="panel"><div class="panelhead"><h2>Parametric equalizer</h2><div class="actions"><span class="muted" id="bankLabel">All speakers</span><label class="switchlabel"><input type="checkbox" id="bypass">Bypass EQ</label></div></div>
<div class="preamp"><span>Preamp</span><input id="preamp" type="range" min="-60" max="30" step="0.1" value="0" aria-label="Requested preamp"><input id="preampN" type="number" min="-60" max="30" step="0.1" value="0" aria-label="Preamp in dB"><small>dB total <span id="stageNote"></span></small></div>
<div class="bandwrap"><div class="bands" id="bands"></div></div><div class="tools"><button class="small" id="slot1">Set 1</button><button class="small" id="slot2">Set 2</button><button class="small" id="slot3">Set 3</button><button class="small" id="slot4">Set 4</button><button class="small" id="flattenBtn">Flatten</button><button class="small" id="expandBtn">Expand ×1.1</button><button class="small" id="compressBtn">Compress ×0.9</button><button class="small" id="downBtn">−1 dB</button><button class="small" id="upBtn">+1 dB</button><button class="small" id="addBtn">+ Band</button><button class="small" id="removeBtn">− Last band</button><span class="muted" style="margin-left:auto;font-size:11px">Shift-click Set to store · double-click fader to reset</span></div></div>

<div class="bottom"><section class="panel meterpanel"><div class="statrow"><span>Output peak</span><span id="peakLabel">—</span></div><div class="meter"><div id="meterFill"></div></div><p class="note">Read-only endpoint meter. Does not prove APO is installed on the device or measure acoustic loudness.</p></section></div>
<div class="lower"><section class="panel"><div class="panelhead"><h2>Preset library</h2><small>Presets</small></div><div id="presets" class="presetlist"></div><div class="librarytools"><button class="small" id="saveBtn">Save as…</button><button class="small" id="deleteBtn">Delete</button></div><details class="exchange control-help"><summary>Import &amp; export</summary><div class="actions"><button class="small" id="currentBtn">Load current APO</button><button class="small" id="importBtn">Import</button><button class="small" id="jsonBtn">Save JSON</button><button class="small" id="exportBtn">APO bundle</button></div><details class="control-help"><summary>Details</summary><p class="note">Bravado JSON, legacy peak presets, or strict APO/AutoEQ parametric text. Files stay on this computer.</p></details><input type="file" class="hidden" id="fileInput" accept=".json,.peace,.txt"></details></section><section class="panel"><div class="panelhead"><h2>Frequency response</h2><small id="graphStats">Calculating response…</small></div><div class="graphbody"><canvas id="graph" aria-label="Frequency response graph at 48 kHz" role="img"></canvas><div class="legend"><span><b></b>EQ shape</span><span><b class="protected"></b>Output, selected bank</span><span>EQ response · 48 kHz</span></div></div></section></div>
</div><div class="rightcolumn"><aside class="panel aside"><section><h2>Output & speaker</h2><select id="device" aria-label="Playback device"><option value="all">All APO playback devices</option></select><select id="channel" aria-label="Speaker bank"><option value="all">All speakers</option><option value="L">Left</option><option value="R">Right</option><option value="C">Center</option><option value="LFE">Subwoofer</option><option value="RL">Left rear</option><option value="RR">Right rear</option><option value="SL">Left side</option><option value="SR">Right side</option></select><details class="control-help"><summary>Speaker adjustments</summary><div class="field"><label for="trim">Speaker trim · dB</label><input type="number" id="trim" min="-60" max="0" step="0.1"></div><div class="field"><label for="delay">Delay · ms</label><input type="number" id="delay" min="0" max="200" step="0.1"></div><div class="field"><label for="speakerMute">Mute this bank</label><input type="checkbox" id="speakerMute"></div><details class="control-help"><summary>Details</summary><p class="note">Individual speaker banks add correction after the All speakers curve. Processing follows the selected mode.</p></details></details></section>
<section><h2>Space &amp; level</h2><div class="separation-control"><div class="field"><label for="separation">Separation</label><output id="separationValue" for="separation">Original · 0</output></div><input id="separation" type="range" min="-100" max="100" step="1" value="0" aria-label="Separation" aria-describedby="separationNote" title="Double-click to reset to Original"><div class="separation-scale" aria-hidden="true"><span>Mono</span><span>Original</span><span>Wide</span></div><details class="control-help"><summary>Details</summary><p class="note" id="separationNote">Left narrows to mono. Right tightens stereo bass, widens upper frequencies and adds gentle center presence. Front L/R only, after Room and speaker correction; muted banks stay muted. Double-click to reset. Apply to hear edits.</p></details></div><button id="roomBtn" aria-pressed="false" style="width:100%">Stereo Room · Off</button><div class="field"><label for="room_amount">Room amount · %</label><input id="room_amount" type="number" min="0" max="40" step="1" value="20"></div><details class="control-help"><summary>Details</summary><p class="note" id="roomNote">Short stereo ambience with an immediate dry sound. Adjust the amount to blend in reflections.</p></details><div class="field"><label for="double_track">Aligned double · +6.02 dB</label><input type="checkbox" id="double_track"></div><div class="field"><label for="bass_track">Bass double · below 120 Hz</label><input type="checkbox" id="bass_track"></div><div class="field"><label for="bass_delay">Bass sync delay · ms</label><input id="bass_delay" type="number" min="0" max="10" step="0.01" value="0"></div><details class="control-help"><summary>Details</summary><p class="note" id="bassNote">Original sound plus a 120 Hz low-pass copy. Zero added delay by default; small delays change phase and can cancel bass.</p></details><p class="note" id="doubleNote" role="status">Aligned double: +6.02 dB across all frequencies. Bass double: an extra low-pass copy. Apply to hear changes.</p></section><section><h2>Gain controls</h2><div class="field"><label for="output">Output trim · dB</label><input id="output" type="number" min="-60" max="0" step="0.1" value="-6"></div><div class="field"><label for="rumble">25 Hz rumble filter</label><input type="checkbox" id="rumble"></div><details class="control-help"><summary>Details</summary><p class="note"><span id="modeNote">Reduce preamp or output trim if you hear distortion.</span></p></details><button class="small hidden" id="ackBtn" style="margin-top:10px">Acknowledge safety latch</button></section>
</aside><section class="panel status"><div id="statusTitle">Preview mode</div><div id="statusText">Bravado EQ has not been enabled.</div><details class="control-help"><summary>Connection tools</summary><div class="actions" style="margin-top:7px"><button class="small" id="restoreBtn" title="Restore previous APO config…">Restore config…</button><button class="small" id="refreshBtn">Refresh devices</button><button class="small" id="adminEnableBtn" title="Enable as administrator">Admin enable</button><button class="small" id="adminDisableBtn" title="Disable as administrator">Admin disable</button><button class="small" id="deviceSetupBtn" title="Configure output device…">Device setup…</button><button class="small" id="testBtn" title="Quiet 440 Hz test">440 Hz test</button><button class="small" id="quitBtn">Close Bravado</button></div></details></section></div></div><div class="footer"><span>Bravado · 0.8.6</span><span>Ctrl+Enter Apply · Ctrl+S Save preset</span></div>
</main>
<dialog id="confirmDialog"><h2 id="dialogTitle"></h2><div id="dialogBody"></div><div class="actions"><button id="cancelDialog">Cancel</button><button class="primary" id="okDialog">Continue</button></div></dialog>
<dialog id="helpDialog"><h2>Make it your sound</h2><p>Choose a preset, adjust the curve, then select <b>Apply changes</b>. Enable connects Bravado to Equalizer APO; Disable removes Bravado’s effects. Closing Bravado leaves your last applied sound active.</p><p><b>Preamp</b> adjusts the whole curve. Each band changes a frequency region; Q controls its width. Double-click a fader to reset it. Hold Shift while selecting a Set button to store your curve.</p><p><b>Separation</b> narrows to mono on the left; on the right it tightens stereo bass and widens upper frequencies. <b>Stereo Room</b> blends in short reflections. Both affect front left and right channels.</p><p><b>Aligned double</b> adds 6.02 dB across the spectrum. <b>Bass double</b> adds a low-frequency copy below 120 Hz; a delay changes its phase and may reduce bass. Room and bass doubling support standard rates from 44.1 to 192 kHz.</p><p>The graph shows the EQ response before Room and Separation. Output peak measures activity on the Windows default device. Positive gain can clip; lower preamp if you hear distortion.</p><p>Use <b>Connection tools → Device setup</b> if changes are inaudible. Equalizer APO must be installed on the playback device. <b>Esc</b> mutes playback in an emergency; acknowledge the mute before unmuting in Windows.</p><div class="actions"><button id="closeHelp">Done</button></div></dialog>
<dialog id="saveDialog"><h2>Save preset</h2><label for="presetName">Name</label><input id="presetName" type="text" maxlength="80" autocomplete="off"><div class="actions"><button id="cancelSave">Cancel</button><button id="confirmSave" class="primary">Save</button></div></dialog>
<script>
'use strict';
const $=id=>document.getElementById(id), token=location.hash.slice(1)||sessionStorage.getItem('bravadoToken');
if(token){sessionStorage.setItem('bravadoToken',token);history.replaceState(null,'',location.pathname)}
let model=null, library={}, factoryNotes={}, channel='all', initial=null, graphData=null, previewSeq=0, previewTimer=null, busy=false, state=null;
const copy=x=>JSON.parse(JSON.stringify(x)), clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
let noticeTimer;function notify(text,error=false){clearTimeout(noticeTimer);$('message').textContent=text;$('message').classList.toggle('error',error);if(!error)noticeTimer=setTimeout(()=>{$('message').textContent=''},6500)}$('message').onclick=()=>{$('message').textContent=''};
async function api(path,data){const r=await fetch('/api/'+path,{method:data===undefined?'GET':'POST',headers:{'X-Bravado-Token':token||'','Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(data===undefined?10000:90000)});if(!r.ok){let e=await r.json();const err=Error(e.error||r.statusText);err.stale=r.status===403&&e.error==='Open Bravado using its launch shortcut';throw err}return r.headers.get('Content-Type').includes('zip')?r.blob():r.json()}
async function action(fn){if(busy)return;busy=true;for(const id of ['applyBtn','connectBtn','disableBtn','adminEnableBtn','adminDisableBtn','exportBtn','restoreBtn'])$(id).disabled=true;try{await fn()}catch(e){notify(e.message,true)}finally{busy=false;for(const id of ['applyBtn','connectBtn','disableBtn','adminEnableBtn','adminDisableBtn','exportBtn','restoreBtn'])$(id).disabled=false}}
function dirty(){ $('dirty').textContent='Changes not applied';$('presetTitle').textContent=model.name; schedulePreview() }
function bindNumber(id,get,set,min,max){$(id).onchange=()=>{let v=Number($(id).value);if(!Number.isFinite(v)||$(id).value.trim()===''||v<min||v>max){$(id).value=get();notify(`Value must be between ${min} and ${max}.`,true);return}set(v);dirty()}}
function ensureBank(key){if(!model.banks[key]){model.banks[key]=copy(initial.banks.all);model.banks[key].bands.forEach(b=>{b.gain=0;b.q=1.41});model.banks[key].trim=0;model.banks[key].delay=0;model.banks[key].mute=false}}
function renderBands(){const wrap=$('bands');wrap.replaceChildren();let axis=document.createElement('div');axis.className='scale';axis.innerHTML='<span>+30</span><span>0 dB</span><span>−30</span>';wrap.append(axis);model.banks[channel].bands.forEach((band,i)=>{const col=document.createElement('div');col.className='band'+(band.enabled?'':' disabled');
const numeric=(cls,field,min,max,step,label)=>{const n=document.createElement('input');n.type='number';n.className=cls;n.min=min;n.max=max;n.step=step;n.value=band[field];n.setAttribute('aria-label',`Band ${i+1} ${label}`);n.onchange=()=>{let v=Number(n.value);if(n.value===''||!Number.isFinite(v)||v<min||v>max){n.value=band[field];notify(`${label} must be ${min}–${max}`,true);return}band[field]=v;if(field==='gain')slider.value=v;dirty()};return n};
col.append(numeric('freq','freq',10,20000,1,'frequency Hz'));let rail=document.createElement('div');rail.className='rail';let slider=document.createElement('input');slider.type='range';slider.min=-30;slider.max=30;slider.step=.1;slider.value=band.gain;slider.setAttribute('aria-label',`Band ${i+1} gain fader`);slider.oninput=()=>{band.gain=Number(slider.value);gain.value=band.gain.toFixed(1);dirty()};slider.ondblclick=()=>{band.gain=0;slider.value=0;gain.value=0;dirty()};rail.append(slider);col.append(rail);const gain=numeric('gain','gain',-30,30,.1,'gain dB');col.append(gain);let label=document.createElement('div');label.className='bandlabel';label.textContent='Q';col.append(label,numeric('quality','q',.25,12,.01,'quality Q'));let select=document.createElement('select');select.setAttribute('aria-label',`Band ${i+1} filter type`);for(const [value,name] of [['PK','Peak'],['LS','Low shelf'],['HS','High shelf'],['HP','High pass'],['LP','Low pass'],['NO','Notch']])select.add(new Option(name,value));select.value=band.kind;select.onchange=()=>{band.kind=select.value;dirty()};col.append(select);let check=document.createElement('input');check.type='checkbox';check.checked=band.enabled;check.className='enable';check.setAttribute('aria-label',`Enable band ${i+1}`);check.onchange=()=>{band.enabled=check.checked;col.classList.toggle('disabled',!band.enabled);dirty()};col.append(check);wrap.append(col)})}
function render(){if(!model)return;ensureBank(channel);renderMode();$('presetTitle').textContent=model.name;$('preamp').value=$('preampN').value=model.preamp;for(const id of ['output'])$(id).value=model[id];for(const id of ['rumble','bypass','double_track','bass_track'])$(id).checked=!!model[id];renderEffects();$('device').value=model.device;$('channel').value=channel;for(const id of ['trim','delay'])$(id).value=model.banks[channel][id];$('speakerMute').checked=model.banks[channel].mute;$('bankLabel').textContent=$('channel').selectedOptions[0].text;renderBands();renderLibrary();schedulePreview()}
function renderMode(){$('modeBadge').textContent='NATIVE APO';$('modeNote').textContent='Reduce preamp or output trim if you hear distortion.';$('stageNote').textContent=model.preamp_stages?'· stages '+model.preamp_stages.map(s=>s.db+' dB before band '+(s.before+1)).join(' / '):''}
function renderEffects(){renderSeparation();$('bass_delay').value=model.bass_delay??0;$('bass_delay').disabled=!model.bass_track;$('bassNote').textContent=model.bypass&&model.bass_track?'Bass double bypassed with EQ.':'Adds a low-frequency copy below 120 Hz. Delay changes its phase and may reduce bass.';const on=!!model.room;$('roomBtn').setAttribute('aria-pressed',String(on));$('roomBtn').textContent='Stereo Room · '+(on?'On':'Off');$('room_amount').value=model.room_amount??20;$('room_amount').disabled=!on;$('roomNote').textContent=model.bypass&&on?'Room bypassed with EQ. Turn off Bypass and Apply to hear it.':'Short ambience on front L/R · 44.1–192 kHz standard rates. Adjust the amount to blend in reflections.';$('doubleNote').textContent='Aligned double: +6.02 dB across all frequencies. Bass double: an extra low-pass copy. Apply to hear changes.'}
function renderSeparation(){const v=model.separation??0;const label=v===0?'Original · 0':v===-100?'Mono · −100':v<0?'Narrow · '+v:'Wide · +'+v;$('separation').value=v;$('separationValue').textContent=label+(model.bypass?' · bypassed':'');$('separation').setAttribute('aria-valuetext',label+(model.bypass?', bypassed':''))}
$('separation').oninput=()=>{model.separation=Number($('separation').value);renderSeparation();dirty()};
$('separation').ondblclick=()=>{model.separation=0;renderSeparation();dirty()};
$('roomBtn').onclick=()=>{model.room=!model.room;renderEffects();dirty()};
for(const id of ['double_track','bass_track'])$(id).onchange=()=>{model[id]=$(id).checked;renderMode();renderEffects();dirty()};
bindNumber('bass_delay',()=>model.bass_delay??0,v=>model.bass_delay=v,0,10);
bindNumber('room_amount',()=>model.room_amount??20,v=>model.room_amount=v,0,40);
function renderLibrary(){$('presets').replaceChildren();for(const [name,preset] of Object.entries(library)){let b=document.createElement('button');b.textContent=name;b.title=factoryNotes[name]||name;if(model&&name===model.name)b.className='selected';b.onclick=()=>{model=copy(preset);channel='all';render();dirty()};$('presets').append(b)}}
function schedulePreview(){clearTimeout(previewTimer);const seq=++previewSeq;previewTimer=setTimeout(async()=>{try{const data=await api('preview',{model,channel});if(seq!==previewSeq)return;graphData=data;drawGraph();$('doubleNote').textContent=data.stats.double_note||'Aligned double: +6.02 dB across all frequencies. Bass double: an extra low-pass copy. Apply to hear changes.';$('graphStats').textContent=data.stats.mode==='native'?`Gain ${data.stats.applied_db.toFixed(1)} dB · peak ${data.stats.estimated_peak_gain_db.toFixed(1)} dB${data.stats.estimated_peak_gain_db>0?' · clipping possible':''}`:`Fixed gain ${data.stats.applied_db.toFixed(1)} dB · bound ${data.stats.bound_db.toFixed(1)} dBFS`}catch(e){if(seq===previewSeq){$('graphStats').textContent='Invalid design';notify(e.message,true)}}},250)}
function drawGraph(){if(!graphData)return;const c=$('graph'),dpr=devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*dpr;c.height=h*dpr;const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);const l=38,r=w-12,t=13,b=h-28;let low=Math.min(-36,Math.floor(Math.min(...graphData.protected)/12)*12);low=Math.max(low,-96);let high=Math.max(18,Math.ceil(Math.max(...graphData.curve,...graphData.protected)/12)*12);const x=f=>l+Math.log(f/10)/Math.log(2000)*(r-l),y=db=>b-(db-low)/(high-low)*(b-t);ctx.font='10px Segoe UI';ctx.lineWidth=1;for(let db=low;db<=high;db+=12){ctx.strokeStyle=db===0?'#52626b':'#2e373f';ctx.beginPath();ctx.moveTo(l,y(db));ctx.lineTo(r,y(db));ctx.stroke();ctx.fillStyle='#85959f';ctx.fillText(db+'',4,y(db)+3)}for(const f of [10,30,100,300,1000,3000,10000,20000]){ctx.strokeStyle='#2e373f';ctx.beginPath();ctx.moveTo(x(f),t);ctx.lineTo(x(f),b);ctx.stroke();ctx.fillStyle='#85959f';ctx.fillText(f>=1000?(f/1000)+'k':f,x(f)-9,h-8)}ctx.save();ctx.beginPath();ctx.rect(l,t,r-l,b-t);ctx.clip();for(const [key,color] of [['curve','#7fd5dd'],['protected','#b6ee81']]){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=2;graphData.frequency.forEach((f,i)=>{i?ctx.lineTo(x(f),y(graphData[key][i])):ctx.moveTo(x(f),y(graphData[key][i]))});ctx.stroke()}ctx.restore()}
new ResizeObserver(drawGraph).observe($('graph'));
function showState(s){state=s;const bad=s.fault||s.muted;$('statusTitle').textContent=s.muted?'Playback muted':bad?'Needs attention':s.enabled?'Equalizer enabled':s.owned?'Equalizer disabled':'Ready to connect';$('statusTitle').classList.toggle('statusgood',s.enabled&&!bad);$('statusText').textContent=s.fault||(s.owned?'Applied '+s.verified_at:s.apo?'Choose Enable to apply your sound.':'Install Equalizer APO to enable system audio.');$('ackBtn').classList.toggle('hidden',!bad);$('connectBtn').textContent=s.enabled?'Reconnect':'Enable';if(s.storage_error)notify(s.storage_error,true)}

async function load(){const data=await api('state');library=data.presets;factoryNotes=data.factory_notes;initial=copy(library['Bravado Signature Preset']);if(!model)model=copy(data.active_model||initial);const select=$('device');select.replaceChildren(new Option('All APO playback devices','all'));for(const dev of data.devices)select.add(new Option(dev.name,dev.guid));if(model.device!=='all'&&!data.devices.some(d=>d.guid===model.device))select.add(new Option('Saved endpoint (not currently active)',model.device));showState(data.status);render()}
function confirmAction(title,body,fn){$('dialogTitle').textContent=title;$('dialogBody').replaceChildren();const p=document.createElement('p');p.textContent=body;$('dialogBody').append(p);$('confirmDialog').showModal();$('okDialog').onclick=()=>{$('confirmDialog').close();action(fn)}}
$('cancelDialog').onclick=()=>$('confirmDialog').close();$('helpBtn').onclick=()=>$('helpDialog').showModal();$('closeHelp').onclick=()=>$('helpDialog').close();
$('channel').onchange=()=>{channel=$('channel').value;ensureBank(channel);render()};$('device').onchange=()=>{model.device=$('device').value;dirty()};
$('preamp').oninput=()=>{delete model.preamp_stages;model.preamp=Number($('preamp').value);renderMode();$('preampN').value=model.preamp;dirty()};bindNumber('preampN',()=>model.preamp,v=>{delete model.preamp_stages;model.preamp=v;$('preamp').value=v;renderMode()},-60,30);
for(const [id,min,max] of [['output',-60,0]])bindNumber(id,()=>model[id],v=>model[id]=v,min,max);
for(const [id,min,max] of [['trim',-60,0],['delay',0,200]])bindNumber(id,()=>model.banks[channel][id],v=>model.banks[channel][id]=v,min,max);
for(const id of ['rumble','bypass'])$(id).onchange=()=>{model[id]=$(id).checked;renderEffects();dirty()};$('speakerMute').onchange=()=>{model.banks[channel].mute=$('speakerMute').checked;dirty()};
function transform(fn){model.banks[channel].bands.forEach(b=>b.gain=Math.round(clamp(fn(b.gain),-30,30)*10)/10);renderBands();dirty()}
$('flattenBtn').onclick=()=>{model.banks[channel].bands.forEach(b=>{b.gain=0;b.kind='PK'});renderBands();dirty()};$('expandBtn').onclick=()=>transform(v=>v*1.1);$('compressBtn').onclick=()=>transform(v=>v*.9);$('downBtn').onclick=()=>transform(v=>v-1);$('upBtn').onclick=()=>transform(v=>v+1);
$('addBtn').onclick=()=>{const bands=model.banks[channel].bands;if(bands.length===32)return notify('Maximum 32 bands per speaker bank',true);bands.push({freq:1000,gain:0,q:1.41,kind:'PK',enabled:true});renderBands();dirty()};$('removeBtn').onclick=()=>{if(model.banks[channel].bands.length>1){model.banks[channel].bands.pop();if(channel==='all')delete model.preamp_stages;renderMode();renderBands();dirty()}};
async function apply(enable=false,admin=false){const snapshot=copy(model);notify(admin?'Approve the Windows administrator prompt. Applying and verifying configuration…':'Applying changes…');const result=await api(admin?'enable-admin':enable?'enable':'apply',{model:snapshot});notify(result.message);$('dirty').textContent=JSON.stringify(model)===JSON.stringify(snapshot)?'Changes applied':'New changes not applied';showState(await api('status'))}
$('applyBtn').onclick=()=>action(()=>apply());$('connectBtn').onclick=()=>action(()=>apply(true));
$('adminEnableBtn').onclick=()=>action(()=>apply(true,true));
async function disable(admin=false){notify(admin?'Approve the Windows administrator prompt. Disabling EQ…':'Disabling equalizer…');notify((await api(admin?'disable-admin':'disable',{model})).message);showState(await api('status'))}
$('disableBtn').onclick=()=>action(()=>disable());$('adminDisableBtn').onclick=()=>action(()=>disable(true));
$('deviceSetupBtn').onclick=()=>action(async()=>notify((await api('device-setup',{})).message));
$('panicBtn').onclick=async()=>{if(testContext){testContext.close();testContext=null}notify('Emergency mute requested…');try{const r=await api('panic',{});notify(r.ok?'Emergency mute latched. Windows playback endpoints muted.':`Mute could not be confirmed: ${r.error}`,!r.ok);showState(await api('status'))}catch(e){notify('MUTE FAILED: '+e.message+'. Use the physical amplifier or Windows mute now.',true)}};
$('ackBtn').onclick=()=>action(async()=>{notify((await api('acknowledge',{})).message);showState(await api('status'))});
$('restoreBtn').onclick=()=>confirmAction('Restore the previous audio configuration','Restore the audio configuration saved before Bravado was enabled? This replaces your currently applied sound.',async()=>{notify((await api('restore',{})).message);showState(await api('status'))});
$('refreshBtn').onclick=()=>action(load);
$('quitBtn').onclick=()=>confirmAction('Close Bravado','Your last applied audio settings will remain active.',async()=>notify((await api('shutdown',{})).message));
for(let i=1;i<=4;i++){$('slot'+i).title='Load saved set; Shift-click to store current curve';$('slot'+i).onclick=e=>{const name='Set '+i;if(e.shiftKey||!library[name]){action(async()=>{const saved=copy(model);saved.name=name;await api('save',{model:saved});library[name]=saved;renderLibrary();notify(`Current curve stored in ${name}. Click to recall; Shift-click to replace.`)})}else{model=copy(library[name]);channel='all';render();dirty()}}}
let testContext=null;
$('testBtn').onclick=()=>action(async()=>{if(testContext)await testContext.close();testContext=new AudioContext();await testContext.resume();const osc=testContext.createOscillator(),gain=testContext.createGain(),now=testContext.currentTime;osc.frequency.value=440;gain.gain.setValueAtTime(0,now);gain.gain.linearRampToValueAtTime(10**(-42/20),now+.05);gain.gain.setValueAtTime(10**(-42/20),now+.7);gain.gain.linearRampToValueAtTime(0,now+.8);osc.connect(gain).connect(testContext.destination);osc.start(now);osc.stop(now+.85);notify('Playing a short 440 Hz sine at −42 dBFS before system effects. It may be inaudible when Windows is muted.');osc.onended=()=>{testContext?.close();testContext=null}});

function download(blob,name){let url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000)}
$('jsonBtn').onclick=()=>download(new Blob([JSON.stringify(model,null,2)],{type:'application/json'}),'bravado-preset.json');$('exportBtn').onclick=()=>action(async()=>{notify('Building portable APO bundle…');download(await api('export',{model}),'bravado-apo-bundle.zip');notify('Bundle exported with filters.txt, preset and report. Room and bass effects include their WAV assets.')});
$('currentBtn').onclick=()=>action(async()=>{const r=await api('current');model=r.model;channel='all';render();dirty();notify('Current configuration loaded as preview. '+r.warnings.join(' '))});
$('importBtn').onclick=()=>$('fileInput').click();$('fileInput').onchange=()=>action(async()=>{let f=$('fileInput').files[0];if(!f)return;if(f.size>250000)throw Error('Preset exceeds 250 kB');const r=await api('import',{text:await f.text()});model=r.model;channel='all';render();dirty();notify(r.warnings.join('\n')||'Preset imported as preview.');$('fileInput').value='' });
$('saveBtn').onclick=()=>{$('presetName').value=Object.hasOwn(factoryNotes,model.name)?'My preset':model.name;$('saveDialog').showModal();$('presetName').focus();$('presetName').select()};
$('cancelSave').onclick=()=>$('saveDialog').close();$('confirmSave').onclick=()=>{const name=$('presetName').value.trim();if(!name){$('presetName').focus();return}action(async()=>{const saved=copy(model);saved.name=name;await api('save',{model:saved});model=saved;library[name]=copy(saved);$('saveDialog').close();render();notify('Preset saved.')})};$('presetName').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();$('confirmSave').click()}};
$('deleteBtn').onclick=()=>{if(Object.hasOwn(factoryNotes,model.name))return notify('Built-in presets cannot be deleted.');confirmAction('Delete preset',`Delete “${model.name}” from your local library?`,async()=>{await api('save',{model,delete:true});delete library[model.name];renderLibrary();notify('Preset removed from the library.')})};

document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]')){e.preventDefault();$('panicBtn').click()}if(e.ctrlKey&&e.key==='Enter'){e.preventDefault();$('applyBtn').click()}if(e.ctrlKey&&e.key.toLowerCase()==='s'){e.preventDefault();$('saveBtn').click()}});
let polling=false;setInterval(async()=>{if(polling||document.hidden)return;polling=true;try{const [s,m]=await Promise.all([api('status'),api('meter')]);showState(s);$('meterFill').style.width=m.peak===null?'0%':(m.peak*100)+'%';$('peakLabel').textContent=m.peak===null?'Unavailable':m.peak>0?(20*Math.log10(m.peak)).toFixed(1)+' dBFS':'−∞ dBFS'}catch(e){$('statusTitle').textContent=e.stale?'Bravado restarted':'Connection interrupted';$('statusText').textContent=e.stale?'Continue in the new Bravado window.':'Your applied sound remains active. Reopen Bravado to reconnect.';$('peakLabel').textContent='Disconnected'}finally{polling=false}},500);
load().catch(e=>notify(e.message,true));
</script></body></html>'''


# ============================================================================
# 08 — Tests, diagnostics, portable entry point.
# ============================================================================
class ManagedProcess:
    """Hold a process handle so PID reuse cannot redirect a termination."""
    def __init__(self, pid, terminate=True):
        from ctypes import wintypes as wt
        self.k = ct.WinDLL("kernel32", use_last_error=True)
        self.k.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.k.OpenProcess.restype = wt.HANDLE
        self.k.CloseHandle.argtypes = [wt.HANDLE]
        self.k.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ct.POINTER(wt.DWORD)]
        self.k.GetProcessTimes.argtypes = [wt.HANDLE]+[ct.POINTER(wt.FILETIME)]*4
        self.k.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
        self.k.WaitForSingleObject.restype = wt.DWORD
        self.k.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
        self.handle = self.k.OpenProcess(0x1000 | 0x100000 | (1 if terminate else 0), False, pid)
        if not self.handle:
            raise OSError(ct.get_last_error(), f"Cannot access Bravado process {pid}. Run the launcher as administrator if it was elevated.")
        self.pid = pid

    def __enter__(self): return self
    def __exit__(self, *args): self.k.CloseHandle(self.handle)

    def identity(self):
        from ctypes import wintypes as wt
        name = ct.create_unicode_buffer(32768); size = wt.DWORD(len(name))
        if not self.k.QueryFullProcessImageNameW(self.handle, 0, name, ct.byref(size)):
            raise OSError(ct.get_last_error(), "Could not identify controller executable")
        times = [wt.FILETIME() for _ in range(4)]
        if not self.k.GetProcessTimes(self.handle, *(ct.byref(t) for t in times)):
            raise OSError(ct.get_last_error(), "Could not identify controller start time")
        return {"pid": self.pid, "exe": name.value,
                "created": str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)}

    def matches(self, record):
        got = self.identity()
        return (abs(int(got["created"])-int(record.get("created", 0))) < 10
                and os.path.normcase(got["exe"]) == os.path.normcase(record.get("exe", "")))

    def wait(self, ms): return self.k.WaitForSingleObject(self.handle, ms) == 0

    def stop(self):
        if not self.wait(0) and not self.k.TerminateProcess(self.handle, 1):
            raise OSError(ct.get_last_error(), "Could not stop the previous Bravado instance")
        if not self.wait(3000):
            raise RuntimeError("Previous Bravado process did not exit; restart cancelled")


def windows_args(command):
    count = ct.c_int()
    shell = ct.WinDLL("shell32")
    shell.CommandLineToArgvW.argtypes = [ct.c_wchar_p, ct.POINTER(ct.c_int)]
    shell.CommandLineToArgvW.restype = ct.POINTER(ct.c_wchar_p)
    argv = shell.CommandLineToArgvW(command, ct.byref(count))
    if not argv:
        return []
    try:
        return [argv[i] for i in range(count.value)]
    finally:
        kernel = ct.WinDLL("kernel32")
        kernel.LocalFree.argtypes = [ct.c_void_p]
        kernel.LocalFree(argv)


def is_bravado_process(record):
    argv = windows_args(record.get("command", ""))
    if not argv or record.get("pid") == os.getpid():
        return False
    if set(argv[1:]) & {"--self-test", "--diagnose", "--export", "--test-child"}:
        return False
    name = Path(record.get("exe", "")).name.lower()
    if name == "bravado.exe":
        return True
    return (name in ("python.exe", "pythonw.exe", "python3.exe") and len(argv) >= 2
            and Path(argv[1]).name.lower() == "bravado.py"
            and not set(argv[2:]) & {"--self-test", "--diagnose", "--export"})


def discover_controllers():
    # Read-only, narrowly filtered discovery. Never kill Python by image name.
    script = r"""$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$session=(Get-Process -Id $PID).SessionId
$items=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='python3.exe' OR Name='Bravado.exe'" | Where-Object { $_.SessionId -eq $session -and $_.ExecutablePath -and $_.CommandLine } | ForEach-Object {
@{pid=[int]$_.ProcessId;exe=$_.ExecutablePath;command=$_.CommandLine;created=$_.CreationDate.ToFileTimeUtc().ToString()}
})
ConvertTo-Json -InputObject $items -Compress
"""
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, encoding="utf-8", timeout=10, creationflags=0x08000000)
    if result.returncode:
        raise OSError("Windows process discovery was unavailable")
    return [r for r in json.loads(result.stdout or "[]") if is_bravado_process(r)]


def stop_previous(data_dir):
    data_dir = Path(data_dir)
    # Cancel leases before stopping helpers/controllers, including late UAC approval.
    for request in data_dir.glob("elevate-*.json"):
        if re.fullmatch(r"elevate-[0-9a-f]{24}\.json", request.name):
            request.unlink(missing_ok=True)
    launch = {}
    try:
        launch = json.loads((data_dir/"launch.json").read_text("utf-8"))
    except (OSError, ValueError):
        pass
    if launch.get("pid") and not launch.get("created"):
        # Upgrade pre-0.3.1 records only after authenticating the local API and
        # confirming Windows attributes that listening socket to the recorded PID.
        url = launch.get("url", "")
        if re.fullmatch(r"http://127\.0\.0\.1:\d{1,5}/#[A-Za-z0-9_-]{40,60}", url):
            try:
                base, token = url.split("#", 1)
                req = urllib.request.Request(base+"api/status", headers={"X-Bravado-Token": token})
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=2) as response:
                    status = json.load(response)
                if (Path(status.get("data", "")).resolve() == data_dir.resolve()
                        and owns_local_port(launch["pid"], urllib.parse.urlsplit(base).port)):
                    with ManagedProcess(launch["pid"], terminate=False) as process:
                        identity = process.identity()
                        if Path(identity["exe"]).name.lower() in ("python.exe", "pythonw.exe", "python3.exe", "bravado.exe"):
                            launch.update(identity)
            except (OSError, ValueError, KeyError):
                pass
    try:
        candidates = discover_controllers()
    except (OSError, ValueError, subprocess.TimeoutExpired):
        # New launch records carry a creation timestamp + exact executable identity.
        # If discovery is restricted, this avoids making startup depend on WMI.
        candidates = [launch] if launch.get("created") and launch.get("exe") else []
    if launch.get("created") and launch.get("exe") and not any(r.get("pid") == launch.get("pid") for r in candidates):
        candidates.append(launch)
    try:
        helper = json.loads((data_dir/"helper-process.json").read_text("utf-8"))
        if helper.get("created") and helper.get("exe") and not any(r.get("pid") == helper.get("pid") for r in candidates):
            candidates.append(helper)
    except (OSError, ValueError):
        pass
    candidates.sort(key=lambda r: "--admin-request" not in r.get("command", ""))
    seen = set()
    for record in candidates:
        pid = record.get("pid")
        if not isinstance(pid, int) or pid <= 0 or pid == os.getpid() or pid in seen:
            continue
        seen.add(pid)
        try:
            with ManagedProcess(pid) as old:
                if not old.matches(record):
                    continue
                url = launch.get("url", "") if pid == launch.get("pid") else ""
                if re.fullmatch(r"http://127\.0\.0\.1:\d{1,5}/#[A-Za-z0-9_-]{40,60}", url):
                    base, token = url.split("#", 1)
                    try:
                        req = urllib.request.Request(base+"api/shutdown", data=b"{}",
                              headers={"X-Bravado-Token": token, "Content-Type": "application/json"})
                        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=1) as response:
                            response.read(4096)
                    except Exception:
                        pass
                    old.wait(1000)
                old.stop()
        except OSError as e:
            if e.errno == 87:  # Process already exited.
                continue
            raise


def owns_local_port(pid, port):
    """Read Windows' TCP owner table; no WMI or process-name guesses."""
    from ctypes import wintypes as wt
    api = ct.WinDLL("iphlpapi")
    api.GetExtendedTcpTable.argtypes = [ct.c_void_p, ct.POINTER(wt.DWORD), wt.BOOL, wt.ULONG, ct.c_int, wt.ULONG]
    api.GetExtendedTcpTable.restype = wt.DWORD
    size = wt.DWORD()
    api.GetExtendedTcpTable(None, ct.byref(size), False, 2, 5, 0)
    for _ in range(3):
        buffer = ct.create_string_buffer(size.value)
        code = api.GetExtendedTcpTable(buffer, ct.byref(size), False, 2, 5, 0)
        if code == 122:
            continue
        if code:
            raise OSError(code, "Could not verify controller socket ownership")
        raw = buffer.raw
        count = struct.unpack_from("<I", raw)[0]
        for i in range(count):
            state, address, local_port, _, _, owner = struct.unpack_from("<6I", raw, 4+24*i)
            decoded_port = int.from_bytes(struct.pack("<I", local_port)[:2], "big")
            if state == 2 and address == 0x0100007F and decoded_port == port and owner == pid:
                return True
        return False
    raise RuntimeError("TCP ownership changed repeatedly; restart cancelled")


def startup_lock():
    """Serialize replacement launches until the new controller publishes readiness."""
    kernel = ct.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ct.c_void_p, ct.c_int, ct.c_wchar_p]
    kernel.CreateMutexW.restype = ct.c_void_p
    kernel.WaitForSingleObject.argtypes = [ct.c_void_p, ct.c_ulong]
    kernel.WaitForSingleObject.restype = ct.c_ulong
    kernel.ReleaseMutex.argtypes = [ct.c_void_p]
    kernel.CloseHandle.argtypes = [ct.c_void_p]
    handle = kernel.CreateMutexW(None, False, "Local\\Bravado.Startup.v1")
    if not handle:
        raise RuntimeError("Cannot create startup lock")
    if kernel.WaitForSingleObject(handle, 15000) not in (0, 0x80):
        kernel.CloseHandle(handle)
        raise RuntimeError("Another Bravado launch is still starting. Try again shortly.")
    released = False
    def release_startup():
        nonlocal released
        if not released:
            released = True
            kernel.ReleaseMutex(handle)
            kernel.CloseHandle(handle)
    return release_startup


def self_test(stream=None):
    class Tests(unittest.TestCase):
        def test_desktop_size_fits_work_area(self):
            self.assertEqual(desktop_size(1920, 1080), (1120, 800))
            self.assertEqual(desktop_size(1024, 700), (992, 668))
            self.assertEqual(desktop_size(720, 480), (688, 448))

        def test_missing_desktop_runtime_is_actionable(self):
            from unittest.mock import patch
            import winreg
            with patch.object(winreg, "OpenKey", side_effect=FileNotFoundError):
                with self.assertRaisesRegex(RuntimeError, "WebView2 Runtime"):
                    require_desktop_runtime()

        def test_desktop_lifecycle(self):
            from unittest.mock import patch, Mock
            from types import SimpleNamespace
            # Exercise real server lifecycle with a stand-in GUI, without APO writes.
            class Event:
                def __iadd__(self, handler):
                    return self
                def is_set(self):
                    return True
            gui = Mock()
            gui.settings = {}
            gui.create_window.return_value.events = SimpleNamespace(shown=Event(), closed=Event())
            area = SimpleNamespace(Width=1920, Height=1080)
            forms = SimpleNamespace(Screen=SimpleNamespace(FromPoint=lambda _: SimpleNamespace(WorkingArea=area)),
                                    Cursor=SimpleNamespace(Position=None))
            with tempfile.TemporaryDirectory() as d:
                engine = Engine(Path(d)/"data", Path(d)/"apo")
                ready = Path(d)/"launch.json"
                def start(*args, **kwargs):
                    info = json.loads(ready.read_text())
                    url = urllib.parse.urlsplit(info["url"])
                    request = urllib.request.Request(f"http://{url.netloc}/api/state",
                                                     headers={"X-Bravado-Token": url.fragment})
                    with urllib.request.urlopen(request, timeout=2) as reply:
                        self.assertEqual(json.load(reply)["presets"][SIGNATURE]["preamp"], 0)
                gui.start.side_effect = start
                with patch.dict(sys.modules, {"webview": gui, "webview.guilib": SimpleNamespace(initialize=Mock()),
                                              "System.Windows.Forms": forms}):
                    with patch(__name__+".require_desktop_runtime"):
                        desktop(engine, 0, ready)
                self.assertFalse((engine.data/"launch.json").exists())
                self.assertFalse(gui.create_window.call_args.kwargs["resizable"])
                self.assertEqual(gui.start.call_args.kwargs["gui"], "edgechromium")

        def test_missing_apo_keeps_preview_available(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                with patch(__name__+".find_apo", return_value=None):
                    e = Engine(Path(d)/"data")
                    self.assertIsNone(e.apo)
                    self.assertFalse(e.status()["owned"])
                    with self.assertRaisesRegex(ValueError, "Equalizer APO"):
                        e.enable(defaults())
                    self.assertEqual(preview(defaults(), "all")["stats"]["requested_db"], 0)

        def test_factory_presets(self):
            presets = factory_presets()
            self.assertEqual(list(presets), [SIGNATURE, "Pocket Physics", "Flat", "Nordrassil", "Marble Alibi", "Red Herring"])
            self.assertEqual(set(presets), set(PRESET_NOTES))
            self.assertEqual(presets[SIGNATURE]["preamp"], 0)
            flat = presets["Flat"]
            self.assertEqual(flat["preamp"], 0)
            files, report = compile_bundle(flat)
            self.assertAlmostEqual(report["48000"]["all"]["estimated_peak_gain_db"], 0)
            self.assertNotIn(b"Convolution:", files["filters.txt"])
            self.assertNotIn(b"Copy:", files["filters.txt"])
            presets[SIGNATURE]["banks"]["all"]["bands"][0]["gain"] = -30
            self.assertEqual(factory_presets()[SIGNATURE]["banks"]["all"]["bands"][0]["gain"], GAINS[0])

        def test_factory_voice_response(self):
            # Validate the complete tonal contour: overlapping peaks change the result.
            for name in ("Marble Alibi", "Red Herring", "Pocket Physics"):
                model = validate(factory_presets()[name])
                bands = model["banks"]["all"]["bands"]
                self.assertEqual(len(bands), 14)
                self.assertTrue(all(len(v) == 14 for v in VOICES[name][1:]))
                self.assertEqual(model["preamp"], 0)
                for rate in RATES:
                    f = np.geomspace(10, 20000, 8192)
                    h = response(bands, f, rate)
                    db = 20*np.log10(np.maximum(np.abs(h), 1e-15))
                    self.assertTrue(np.isfinite(h).all())
                    for band_ in bands:
                        _, a = coefficients(band_, rate)
                        self.assertLess(float(np.max(np.abs(np.roots(a)))), 1)
                    f = [30, 50, 90, 160, 500, 1200, 3000, 5000, 9000, 16000]
                    db = 20*np.log10(np.abs(response(bands, f, rate)))
                    self.assertGreater(db[0], 5.5)  # Deep weight, not a thin bass bump.
                    self.assertGreater(db[2], 7.5)
                    self.assertGreater(db[3], 5)
                    self.assertGreater(db[2], db[1] + 4)  # 90 Hz dominates 50 Hz.
                    self.assertLess(db[1], 4)
                    self.assertLess(db[4], 0)
                    self.assertGreater(db[5], 2.5)  # Voices retain energy between cuts.
                    self.assertLess(db[6], -1.5)
                    self.assertGreater(db[8], 4)
                    self.assertGreater(db[8], db[7] + .3)
                    self.assertLess(db[9], -2)

        def test_factory_voices_have_distinct_contours(self):
            presets = factory_presets()
            # Compare regions, not isolated sliders. Each voice has its own emphasis.
            for rate in RATES:
                regions = {}
                for name in ("Marble Alibi", "Red Herring", "Pocket Physics"):
                    bands = presets[name]["banks"]["all"]["bands"]
                    regions[name] = [float(np.mean(20*np.log10(np.abs(response(
                        bands, np.geomspace(lo, hi, 64), rate)))))
                        for lo, hi in ((20, 40), (120, 220), (900, 1800), (8500, 9500))]
                marble, red, pocket = (regions[n] for n in ("Marble Alibi", "Red Herring", "Pocket Physics"))
                self.assertGreater(red[0], marble[0] + 1.3)
                self.assertGreater(red[0], pocket[0] + 2)
                self.assertGreater(pocket[1], marble[1] + 2)
                self.assertGreater(pocket[1], red[1] + 2)
                self.assertGreater(marble[2], red[2] + 2.5)
                self.assertGreater(marble[2], pocket[2] + 2.5)
                self.assertGreater(pocket[3], red[3] + .8)
                self.assertGreater(pocket[3], marble[3] + 1)

        def test_sub_bass_support_is_local(self):
            # Compare against the preceding contour; no changes above the first two bands.
            for name in ("Red Herring", "Pocket Physics"):
                model = factory_presets()[name]
                bands = model["banks"]["all"]["bands"]
                previous = copy.deepcopy(bands)
                previous[0].update(freq=10, gain=0, q=.71)
                if name == "Pocket Physics":
                    previous[1].update(gain=5.5, q=3)
                for rate in RATES:
                    f = np.geomspace(18, 40, 128)
                    delta = 20*np.log10(np.abs(response(bands, f, rate) /
                                               response(previous, f, rate)))
                    self.assertGreater(float(delta.min()), 1.5)
                    f = np.geomspace(300, 20000, 512)
                    delta = 20*np.log10(np.abs(response(bands, f, rate) /
                                               response(previous, f, rate)))
                    self.assertLess(float(np.max(np.abs(delta))), .04)
                    f = [50, 90]
                    delta = 20*np.log10(np.abs(response(bands, f, rate) /
                                               response(previous, f, rate)))
                    self.assertLess(delta[0], 1.3)
                    self.assertLess(delta[1], .35)

        def test_nordrassil_reference_curve(self):
            # Reference: approved Nordrassil 2.0 panel, 4 October 2026.
            model = validate(factory_presets()["Nordrassil"])
            self.assertEqual(model["preamp"], 1.4)
            bands = model["banks"]["all"]["bands"]
            self.assertEqual([b["freq"] for b in bands],
                             [24, 30, 50, 90, 160, 300, 500, 1000, 1600, 3000, 5000, 9000, 16000, 20000])
            self.assertEqual([b["gain"] for b in bands],
                             [2.8, 4.5, 2.8, 6, 5.7, 4, 0, 4.8, 4.6, -4.3, 2.8, 6, -4, -5])
            self.assertEqual([b["q"] for b in bands],
                             [1.2, 1.3, 2.5, 1.8, 1.6, 1.3, 1.8, 1.2, 1.6, 1.3, 1.5, 1.7, 1.2, 1.2])
            self.assertEqual([i for i, band_ in enumerate(bands) if not band_["enabled"]], [12])
            files, _ = compile_bundle(model)
            self.assertIn(b"Filter 13: OFF PK Fc 16000 Hz Gain -4 dB Q 1.2", files["filters.txt"])
            restored, _ = import_preset(files["filters.txt"].decode())
            self.assertEqual(restored["banks"]["all"]["bands"], bands)
            for rate in RATES:
                f = np.geomspace(20, 20000, 8192)
                h = response(bands, f, rate)
                self.assertTrue(np.isfinite(h).all())
                # A disabled filter contributes neither gain nor phase.
                np.testing.assert_allclose(h, response(bands[:12]+bands[13:], f, rate), rtol=1e-12, atol=1e-12)
                enabled = copy.deepcopy(bands)
                enabled[12]["enabled"] = True
                difference = 20*np.log10(abs(response(enabled, [16000], rate)[0] /
                                               response(bands, [16000], rate)[0]))
                self.assertAlmostEqual(float(difference), -4, places=8)
                for band_ in bands:
                    _, a = coefficients(band_, rate)
                    self.assertLess(float(np.max(np.abs(np.roots(a)))), 1)

        def test_factory_voice_exports(self):
            for name in VOICES:
                model = factory_presets()[name]
                files, _ = compile_bundle(model)
                text = files["filters.txt"].decode()
                self.assertNotIn("Convolution:", text)
                self.assertNotIn("Copy:", text)
                self.assertTrue(all(b["kind"] == "PK" for b in model["banks"]["all"]["bands"]))
                self.assertIn(f'Preamp: {model["preamp"]:g} dB', text)
                # Export/import must reproduce magnitude AND phase at every rate.
                imported, _ = import_preset(text)
                self.assertEqual(imported["preamp"], model["preamp"])
                for rate in RATES:
                    f = np.geomspace(20, 20000, 1024)
                    np.testing.assert_allclose(
                        response(imported["banks"]["all"]["bands"], f, rate),
                        response(model["banks"]["all"]["bands"], f, rate), rtol=1e-10, atol=1e-10)
                self.assertEqual(model["device"], "all")
                self.assertEqual(model["separation"], 0)
                self.assertFalse(any(model[k] for k in ("room", "rumble", "double_track", "bass_track")))
                model["banks"]["all"]["bands"][0]["gain"] = 30
                self.assertEqual(factory_presets()[name]["banks"]["all"]["bands"][0]["gain"], VOICES[name][1][0])

        def test_machine_sessions_do_not_travel(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                (apo/"config.txt").write_text("Preamp: 0 dB\n")
                with patch(__name__+".machine_key", return_value="first"):
                    e = Engine(root/"data", apo)
                    e.enable(defaults())
                    original = e.root_bytes()
                    atomic_write(e.data/"presets.json", json_bytes({"Personal": {**defaults(), "name": "Personal"}}))
                    self.assertTrue(Engine(root/"data", apo).state["owned"])
                with patch(__name__+".machine_key", return_value="second"):
                    moved = Engine(root/"data", apo)
                    self.assertFalse(moved.state["owned"])
                    self.assertFalse(moved.state["enabled"])
                    self.assertNotIn("model", moved.state)
                    self.assertNotIn("backup", moved.state)
                    self.assertFalse(moved.trip.is_set())
                    self.assertEqual(moved.root_bytes(), original)
                    self.assertTrue((moved.data/"presets.json").exists())

        def test_frozen_maintenance_is_not_a_controller(self):
            record = {"pid": os.getpid()+100000, "exe": r"C:\Bravado\Bravado.exe"}
            for flag in ("--self-test", "--diagnose", "--export", "--test-child"):
                self.assertFalse(is_bravado_process({**record, "command": f'Bravado.exe {flag}'}))
            self.assertTrue(is_bravado_process({**record, "command": 'Bravado.exe --no-browser'}))

        @staticmethod
        def separation_matrix(model, f, rate=48000, channels=8):
            # Independently read the generated Copy/Filter operations. Each row
            # maps the original input channels to one output at each frequency.
            h = np.tile(np.eye(channels, dtype=complex), (len(f), 1, 1))
            lines = []; append_separation(lines, validate(model))
            selected = 0
            for line in lines:
                line = line.strip()
                if line in ('Channel: L', 'Channel: R'):
                    selected = {'Channel: L': 0, 'Channel: R': 1}[line]
                elif line.startswith('Copy:'):
                    old = h.copy()
                    for assignment in line[5:].split():
                        target, expression = assignment.split('=')
                        row = np.zeros((len(f), channels), complex)
                        for term in expression.split('+'):
                            if term == '0.0': continue
                            factor, channel = term.split('*') if '*' in term else ('1', term)
                            row += float(factor)*old[:, {'L': 0, 'R': 1}[channel], :]
                        h[:, {'L': 0, 'R': 1}[target], :] = row
                elif line.startswith('Filter:'):
                    parts = line.split()
                    kind = {'LSC': 'LS', 'HSC': 'HS'}.get(parts[2], parts[2])
                    b = dict(kind=kind, freq=float(parts[4]), gain=float(parts[7]), q=float(parts[10]), enabled=True)
                    h[:, selected, :] *= response([b], f, rate)[:, None]
            return h

        def test_separation_identity_mono_and_narrow(self):
            f = np.array([40., 1000., 10000.])
            m = defaults(); lines = []; append_separation(lines, m)
            self.assertEqual(lines, [])
            original = compile_bundle(m)[0]['filters.txt']
            for amount in (-100, -75, -25):
                m['separation'] = amount
                h = self.separation_matrix(m, f)
                expected = np.eye(8)
                expected[:2, :2] = [[1+amount/200, -amount/200], [-amount/200, 1+amount/200]]
                self.assertTrue(np.allclose(h, expected))
                self.assertTrue(np.allclose(abs(h).sum(axis=2), 1))
            self.assertTrue(np.array_equal(self.separation_matrix({**m, 'separation': -100}, f)[:, 0],
                                           self.separation_matrix({**m, 'separation': -100}, f)[:, 1]))
            m['separation'] = 0
            self.assertEqual(compile_bundle(m)[0]['filters.txt'], original)

        def test_separation_native_response_and_other_channels(self):
            m = {**defaults(), 'separation': 100}
            for rate in RATES:
                f = np.array([0., 40., 2500., rate/2])
                h = self.separation_matrix(m, f, rate)
                # Centered sound follows only M; opposite-polarity sound only S.
                center = h[:, :2, 0] + h[:, :2, 1]
                sides = h[:, :2, 0] - h[:, :2, 1]
                self.assertTrue(np.allclose(center[:, 0], center[:, 1]))
                self.assertTrue(np.allclose(sides[:, 0], -sides[:, 1]))
                self.assertAlmostEqual(20*np.log10(abs(center[2, 0])), 1.5, places=7)
                self.assertAlmostEqual(20*np.log10(abs(sides[0, 0])), -12, places=6)
                self.assertAlmostEqual(20*np.log10(abs(sides[-1, 0])), 4, places=6)
                self.assertTrue(np.array_equal(h[:, 2:], np.tile(np.eye(8)[2:], (len(f), 1, 1))))
                self.assertTrue(np.isfinite(h).all())
            files, report = compile_bundle(m)
            text = files['filters.txt'].decode()
            self.assertIn('If: inputChannelCount >= 2', text)
            self.assertNotIn('Delay:', text)
            self.assertNotIn('Convolution:', text)
            self.assertEqual(compile_bundle(m)[0], files)
            self.assertEqual(report['48000']['all']['applied_db'], m['preamp'])
            self.assertGreater(boost_headroom(m), boost_headroom({**m, 'separation': 0}))

        def test_separation_bypass_mutes_and_room_order(self):
            m = {**defaults(), 'separation': 100, 'room': True}
            self.assertNotIn('Copy:', compile_bundle({**m, 'bypass': True})[0]['filters.txt'].decode())
            text = compile_bundle(m)[0]['filters.txt'].decode()
            self.assertGreater(text.index('# Separation:'), text.rindex('Convolution:'))
            m['banks']['R'] = bank(True); m['banks']['R']['mute'] = True
            h = self.separation_matrix(m, np.array([100., 1000.]))
            self.assertTrue(np.array_equal(h[:, 1], np.zeros((2, 8))))
            m['banks']['all']['mute'] = True
            lines = []; append_separation(lines, m)
            self.assertEqual(lines, [])

        def test_separation_validation_presets_and_apply(self):
            m = defaults(); m.pop('separation')
            self.assertEqual(validate(m)['separation'], 0)
            for value in (-101, 101, True, '50', float('nan'), float('inf')):
                with self.assertRaises(ValueError): validate({**m, 'separation': value})
            m = validate({**m, 'separation': 42})
            self.assertEqual(import_preset(json.dumps(m)), m)
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); apo = root/'config'; apo.mkdir()
                (apo/'config.txt').write_text('Preamp: -10 dB\n')
                e = Engine(root/'data', apo)
                with patch(__name__+'.emergency_windows_mute', side_effect=AssertionError('Unexpected mute')):
                    e.enable(m)
                    self.assertEqual(e.state['model']['separation'], 42)
                    first = compile_bundle(m)[0]['filters.txt']
                    e.apply(m)
                    self.assertEqual(compile_bundle(e.state['model'])[0]['filters.txt'], first)
                    e.disable()
                    self.assertNotIn(b'Copy:', e.root_bytes())

        def test_bass_delay_and_response(self):
            m = validate({**defaults(), 'bass_track': True})
            self.assertEqual(m['bass_delay'], 0)
            for rate in RATES:
                zero = bass_impulse(m, rate)
                delayed = bass_impulse({**m, 'bass_delay': .13}, rate)
                offset = int(round(.13*rate/1000))
                self.assertEqual(delayed[0], 1)
                self.assertTrue(np.array_equal(delayed[1:offset], np.zeros(offset-1)))
                low = impulse([bass_filter()], rate).astype('<f4')
                self.assertTrue(np.array_equal(delayed[offset:], low))
                self.assertAlmostEqual(float(zero.sum()), 2, places=6)
                n = 65536
                f = np.fft.rfftfreq(n, 1/rate)
                actual = np.fft.rfft(delayed, n)
                expected = bass_response({**m, 'bass_delay': .13}, f, rate)
                self.assertLess(float(abs(actual-expected).max()), 1e-6)
            for value in (-.01, 10.01, float('inf'), True):
                with self.assertRaises(ValueError): validate({**m, 'bass_delay': value})

        def test_bass_boost_native_cascade(self):
            m = {**defaults(), 'banks': {'all': bank(True)}, 'preamp': -20,
                 'bass_track': True, 'bass_delay': .15, 'double_track': True, 'room': True}
            files, _ = compile_bundle(m)
            self.assertEqual(len([n for n in files if n.startswith('bass-')]), 6)
            self.assertEqual(json.loads(files['preset.json'])['bass_delay'], .15)
            self.assertNotIn('Delay:', files['filters.txt'].decode())
            boosted, report = compile_bundle({**m, 'preamp': 0})
            self.assertIn('clipping possible', report['48000']['all']['boost_notice'])
            self.assertAlmostEqual(report['48000']['all']['applied_db'], DOUBLE_DB)
            files, _ = compile_bundle({**m, 'preamp': -20, 'bypass': True})
            self.assertFalse(any(n.startswith(('bass-', 'room-')) for n in files))

        def test_effect_defaults_and_roundtrip(self):
            old = defaults()
            for key in ('double_track', 'room', 'room_amount', 'bass_track', 'bass_delay'):
                old.pop(key)
            m = validate(old)
            self.assertFalse(m['double_track'])
            self.assertFalse(m['room'])
            self.assertFalse(m['bass_track'])
            self.assertEqual(m['bass_delay'], 0)
            m.update(double_track=True, room=True, room_amount=28, bass_track=True, bass_delay=.13)
            restored = import_preset(json.dumps(m))
            self.assertEqual(restored, m)
            for key, value in [('double_track', 1), ('room', 'true'), ('room_amount', float('nan')), ('room_amount', 41)]:
                with self.assertRaises(ValueError):
                    validate({**m, key: value})

        def test_double_is_exact_sum_without_added_delay(self):
            m = {**defaults(), 'banks': {'all': bank(True)}, 'preamp': -20}
            before, _ = compile_bundle(m)
            m['double_track'] = True
            after, report = compile_bundle(m)
            emitted = after['filters.txt'].decode()
            gain = sum(float(line.split()[1]) for line in emitted.splitlines() if line.startswith('Preamp:'))
            samples = np.random.default_rng(5).uniform(-1, 1, 10000)
            dry = samples * 10**(-20/20)
            self.assertTrue(np.allclose(samples * 10**(gain/20), dry + dry, rtol=1e-10, atol=1e-12))
            self.assertNotIn('Delay:', emitted)
            self.assertNotIn('Copy:', emitted)
            self.assertNotIn('Convolution:', emitted)
            self.assertAlmostEqual(report['48000']['all']['applied_db'], -20 + DOUBLE_DB)
            for _ in range(3):
                self.assertEqual(compile_bundle(m)[0]['filters.txt'], after['filters.txt'])
            m['double_track'] = False
            self.assertEqual(compile_bundle(m)[0]['filters.txt'], before['filters.txt'])

        def test_double_applies_without_forced_attenuation(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); apo = root/'config'; apo.mkdir()
                (apo/'config.txt').write_text('Preamp: -10 dB\n')
                e = Engine(root/'data', apo)
                m = {**defaults(), 'preamp': 2.6, 'double_track': True, 'ceiling': -24}
                with patch(__name__+'.emergency_windows_mute', side_effect=AssertionError('Unexpected mute')):
                    result = e.enable(m)
                    self.assertIn('clipping possible', result['message'])
                    self.assertEqual(e.state['model']['preamp'], 2.6)
                    self.assertNotIn('ceiling', e.state['model'])
                    self.assertAlmostEqual(result['report']['48000']['all']['applied_db'], 2.6+DOUBLE_DB)
                    first = compile_bundle(m)[0]['filters.txt']
                    e.apply(m)
                    self.assertEqual(compile_bundle(m)[0]['filters.txt'], first)
                    e.disable()
                    self.assertIn(b'Preamp: 0.000000', e.root_bytes())

        def test_legacy_ceiling_is_ignored_everywhere(self):
            m = {**defaults(), 'double_track': True, 'bass_track': True, 'preamp': 2.6}
            expected = compile_bundle(m)[0]
            for ceiling in (-24, -6, 0):
                old = {**m, 'processing': 'guarded', 'ceiling': ceiling}
                self.assertEqual(compile_bundle(old)[0], expected)
                self.assertEqual(preview(old, 'all'), preview(m, 'all'))
                self.assertEqual(validate(old)['processing'], 'native')
            self.assertNotIn('id="ceiling"', HTML)
            self.assertNotIn('id="processing"', HTML)

        def test_stereo_room_serialized_bound_and_timing(self):
            for rate in RATES:
                h = room_impulse(rate, 20)
                self.assertTrue(np.array_equal(h, room_impulse(rate, 20)))
                self.assertTrue(np.allclose(h[0], .8))
                self.assertEqual(np.count_nonzero(h[1:int(rate*.009)]), 0)
                self.assertFalse(np.array_equal(h[:, 0], h[:, 1]))
                data = wav_float(h, rate)
                self.assertEqual(struct.unpack_from('<H', data, 22)[0], 2)
                self.assertEqual(struct.unpack_from('<I', data, 44)[0], len(h))
                serialized = np.frombuffer(data, dtype='<f4', offset=56).reshape(-1, 2)
                self.assertTrue(np.array_equal(serialized, h))
                for channel in range(2):
                    # Adversarial input attains the peak, so this tests arbitrary signals.
                    peak = float(np.dot(serialized[:, channel].astype(float), np.sign(serialized[:, channel])))
                    self.assertLessEqual(peak, 1)
                extreme = room_impulse(rate, 40)
                self.assertLessEqual(float(np.max(np.abs(extreme.astype(float)).sum(axis=0))), 1)
                self.assertTrue(np.array_equal(room_impulse(rate, 0)[0], [1, 1]))

        def test_room_bundle_and_bypass(self):
            m = {**defaults(), 'room': True}
            files, _ = compile_bundle(m)
            self.assertEqual(len([n for n in files if n.startswith('room-')]), 6)
            self.assertEqual(files['filters.txt'].decode().count('Channel: L R'), 6)
            for field, value in [('room', False), ('room_amount', 0), ('bypass', True)]:
                self.assertFalse(any(n.startswith('room-') for n in compile_bundle({**m, field: value})[0]))

        def test_reference(self):
            m = validate(defaults())
            self.assertEqual([b["gain"] for b in m["banks"]["all"]["bands"]], GAINS)
            self.assertEqual(m["preamp"], 0)
            self.assertEqual(m["name"], SIGNATURE)

        def test_validation(self):
            for value in (float("nan"), float("inf"), 31, -61, "-3", True):
                m = defaults(); m["preamp"] = value
                with self.assertRaises(ValueError): validate(m)
            for field, value in (("freq", 0), ("q", 0), ("gain", 31), ("kind", "VST")):
                m = defaults(); m["banks"]["all"]["bands"][0][field] = value
                with self.assertRaises(ValueError): validate(m)

        def test_peak_gain_and_inverse(self):
            for rate in RATES:
                b = {"freq": 1000, "gain": 12, "q": 2, "kind": "PK", "enabled": True}
                got = 20*np.log10(abs(response([b], [1000], rate)[0]))
                self.assertAlmostEqual(float(got), 12, places=7)
                inverse = {**b, "gain": -12}
                self.assertTrue(np.allclose(response([b, inverse], np.geomspace(10, 20000, 1000), rate), 1, atol=1e-9))

        def test_all_filter_types_stable(self):
            for kind in KINDS:
                for rate in RATES:
                    for f in (10, 1000, 20000):
                        for q in (.25, 12):
                            for gain in (-30, 30):
                                v, a = coefficients({"freq": f, "gain": gain, "q": q, "kind": kind}, rate)
                                self.assertLess(max(abs(np.roots(a))), 1)

        def test_import_rejects_injection(self):
            for text in ("Include: malicious.txt", "VSTPlugin: test.dll"):
                with self.assertRaises(ValueError): import_preset(text)
            m, _ = import_preset("Preamp: -3.1 dB\nFilter 1: ON PK Fc 100 Hz Gain 2 dB Q 1.4")
            self.assertEqual(m["banks"]["all"]["bands"][0]["q"], 1.4)

        def test_atomic_storage_and_tamper(self):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                atomic_write(apo/"config.txt", b"first")
                atomic_write(apo/"config.txt", b"second")
                self.assertEqual((apo/"config.txt").read_bytes(), b"second")
                e = Engine(root/"data", apo)
                e.state.update(owned=True, root_hash=digest(b"second"), files={})
                self.assertTrue(e.verify())
                atomic_write(apo/"config.txt", b"tampered")
                with self.assertRaises(ValueError): e.verify()

        def test_transactions_and_restore(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                original = b"Include: peace.txt\r\n"
                atomic_write(apo/"config.txt", original)
                e = Engine(root/"data", apo)
                # All system-affecting calls mocked: this test never mutes hardware.
                with patch(__name__+".emergency_windows_mute", return_value={"ok": True}):
                    e.apply(defaults(), connect=True)
                    self.assertTrue(e.verify())
                    self.assertEqual((e.data/e.state["backup"]).read_bytes(), original)
                    self.assertNotIn(b"peace.txt", e.root_bytes())
                    e.panic()
                    self.assertIn(b"Preamp: -200 dB", e.root_bytes())
                    with self.assertRaises(ValueError): e.apply(defaults())
                    e.acknowledge()
                    self.assertIn(b"Preamp: -200 dB", e.root_bytes())
                    e.restore()
                    self.assertEqual(e.root_bytes(), original)

        def test_normal_actions_never_mute(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                original = b"Preamp: -2 dB\n"
                atomic_write(apo/"config.txt", original)
                e = Engine(root/"data", apo)
                with patch(__name__+".emergency_windows_mute", side_effect=AssertionError("Unexpected mute")):
                    e.enable(defaults()); e.apply(defaults()); e.disable(); e.restore()
                    self.assertEqual(e.root_bytes(), original)
                    e.enable(defaults())
                    atomic_write(apo/"config.txt", original)
                    e.check()
                    self.assertFalse(e.state["owned"])
                    self.assertFalse(e.state["muted"])
                    self.assertFalse(e.trip.is_set())

        def test_native_stacked_chain(self):
            text = "Preamp: 14.5 dB\nFilter: ON PK Fc 30 Hz Gain 10 dB Q 1.41\nPreamp: -3.1 dB\nFilter: ON PK Fc 90 Hz Gain 8.2 dB Q 3"
            m, _ = import_preset(text)
            self.assertAlmostEqual(m["preamp"], 11.4)
            files, report = compile_bundle(m)
            native = files["filters.txt"].decode()
            directives = [re.sub(r"Filter \d+:", "Filter:", l) for l in native.splitlines() if l.startswith(("Filter", "Preamp"))]
            self.assertEqual(directives, text.splitlines())
            self.assertNotIn("Convolution", native)
            self.assertEqual(len(files), 3)
            self.assertAlmostEqual(report["48000"]["all"]["applied_db"], 11.4)

        def test_current_configuration_includes(self):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                atomic_write(apo/"config.txt", b"Include: curve.txt\n")
                atomic_write(apo/"curve.txt", b"Preamp: 2 dB\nFilter: ON PK Fc 90 Hz Gain 8.2 dB Q 3")
                e = Engine(root/"data", apo)
                self.assertEqual(e.current_preset()["model"]["preamp"], 2)
                for text in (b"Include: config.txt", b"Include: ../outside.txt", b"VSTPlugin: test.dll"):
                    atomic_write(apo/"curve.txt", text)
                    with self.assertRaises(ValueError): e.current_preset()

        def test_owned_asset_corruption_keeps_emergency_protection(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                e = Engine(root/"data", apo)
                with patch(__name__+".emergency_windows_mute", return_value={"ok": True}) as mute:
                    e.enable(defaults())
                    mute.assert_not_called()
                    asset = next(iter(e.state["files"]))
                    atomic_write(apo/asset, b"corrupted")
                    e.check()
                    mute.assert_called_once()
                    self.assertTrue(e.trip.is_set())

        def test_enable_disable_and_force_repair(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                original = b"Preamp: -2 dB\n"
                atomic_write(apo/"config.txt", original)
                e = Engine(root/"data", apo)
                with patch(__name__+".emergency_windows_mute", return_value={"ok": True}), patch("subprocess.run", side_effect=AssertionError("No process scans allowed")):
                    e.enable(defaults())
                    self.assertTrue(e.status()["enabled"])
                    e.disable()
                    self.assertFalse(e.status()["enabled"])
                    self.assertTrue(e.verify())
                    self.assertNotIn(b"Convolution:", e.root_bytes())
                    self.assertNotIn(b"Include:", e.root_bytes())
                    self.assertIn(b"Preamp: 0.000000", e.root_bytes())
                    e.disable()  # Idempotent off, no dependency on another program.
                    atomic_write(apo/"config.txt", b"# external change\n")
                    e.check()
                    self.assertFalse(e.trip.is_set())
                    e.enable(defaults())  # Explicit force takeover repairs the fault.
                    self.assertTrue(e.status()["enabled"])
                    self.assertEqual((e.data/e.state["backup"]).read_bytes(), original)
                    self.assertEqual((e.data/e.state["last_takeover_backup"]).read_bytes(), b"# external change\n")

        def test_write_retry_is_bounded(self):
            from unittest.mock import patch
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                atomic_write(apo/"config.txt", b"original")
                e = Engine(root/"data", apo)
                calls = []
                real_write = atomic_write
                def overwritten(path, data):
                    calls.append(path)
                    real_write(path, b"other writer")
                with patch(__name__+".atomic_write", side_effect=overwritten), patch("time.sleep"):
                    with self.assertRaises(RuntimeError):
                        e.commit(b"expected", {"files": {}})
                self.assertEqual(len(calls), 4)

        def test_admin_request_tamper_rejected(self):
            with tempfile.TemporaryDirectory() as d:
                request = Path(d)/("elevate-"+"a"*24+".json")
                request.write_bytes(b"{}")
                with self.assertRaises(ValueError): run_admin_request(request, "0"*64)

        def test_process_selection_does_not_match_other_python_apps(self):
            pid = os.getpid()+100000
            def record(command):
                return {"pid": pid, "exe": r"C:\Python\python.exe", "command": command}
            self.assertTrue(is_bravado_process(record(r'python.exe "C:\HOUSE\Bravado\bravado.py" --no-browser')))
            self.assertTrue(is_bravado_process(record(r'python.exe "C:\HOUSE\Bravado\bravado.py" --admin-request x')))
            self.assertFalse(is_bravado_process(record(r'python.exe other_app.py bravado.py')))
            self.assertFalse(is_bravado_process(record(r'python.exe -c "print(bravado.py)"')))
            self.assertFalse(is_bravado_process(record(r'python.exe bravado.py --self-test')))

        def test_restart_verifies_identity_and_stops_helpers_first(self):
            from unittest.mock import patch, MagicMock
            with tempfile.TemporaryDirectory() as d:
                records = [{"pid": 100001, "command": "bravado.py"},
                           {"pid": 100002, "command": "bravado.py --admin-request x"},
                           {"pid": 100003, "command": "bravado.py"}]
                visited, stopped = [], []
                def opened(pid):
                    visited.append(pid)
                    handle = MagicMock()
                    handle.__enter__.return_value = handle
                    handle.matches.return_value = pid != 100003  # Reused PID: must not kill.
                    handle.stop.side_effect = lambda: stopped.append(pid)
                    return handle
                request = Path(d)/("elevate-"+"a"*24+".json")
                request.write_text("{}")
                with patch(__name__+".discover_controllers", return_value=records), patch(__name__+".ManagedProcess", side_effect=opened):
                    stop_previous(d)
                self.assertEqual(visited, [100002, 100001, 100003])
                self.assertEqual(stopped, [100002, 100001])
                self.assertFalse(request.exists())

        def test_admin_expiry_and_cancellation_prevent_commit(self):
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); apo = root/"apo"; apo.mkdir()
                atomic_write(apo/"config.txt", b"original")
                request = root/"lease.json"; request.write_bytes(b"valid")
                check_admin_lease(request, digest(b"valid"), time.time()+60)
                e = Engine(root/"data", apo)
                e.authorize_commit = lambda: check_admin_lease(request, digest(b"valid"), time.time()-1)
                with self.assertRaises(ValueError): e.commit(b"changed", {})
                self.assertEqual(e.root_bytes(), b"original")
                request.unlink()
                with self.assertRaises(ValueError): check_admin_lease(request, digest(b"valid"), time.time()+60)

        def test_force_stop_only_owned_disposable_process(self):
            from unittest.mock import patch
            command = ([sys.executable, "--test-child"] if getattr(sys, "frozen", False) else
                       [sys.executable, "-c", "import time; time.sleep(60)"])
            child = subprocess.Popen(command, creationflags=0x08000000)
            unrelated = subprocess.Popen(command, creationflags=0x08000000)
            try:
                with ManagedProcess(child.pid, terminate=False) as process:
                    identity = process.identity()
                with tempfile.TemporaryDirectory() as d:
                    with patch(__name__+".discover_controllers", return_value=[identity]):
                        stop_previous(d)
                self.assertIsNotNone(child.poll())
                self.assertIsNone(unrelated.poll())
            finally:
                for process in (child, unrelated):
                    if process.poll() is None: process.terminate()
                    process.wait(timeout=3)

        def test_blocked_uac_times_out_and_releases_engine_lock(self):
            from unittest.mock import patch, MagicMock
            release = threading.Event()
            shell = MagicMock()
            shell.ShellExecuteExW.side_effect = lambda info: (release.wait(2) and False)
            with tempfile.TemporaryDirectory() as d:
                e = Engine(Path(d)/"data", Path(d)/"apo")
                try:
                    with patch.object(ct.windll.shell32, "IsUserAnAdmin", return_value=0), \
                         patch.object(ct, "WinDLL", return_value=shell), \
                         patch(__name__+".ADMIN_TIMEOUT", .05):
                        with self.assertRaisesRegex(RuntimeError, "timed out"):
                            elevated_action(e, "enable", defaults())
                    self.assertFalse(list(e.data.glob("elevate-*.json")))
                    acquired = []
                    def lock_check():
                        ok = e.lock.acquire(timeout=.2); acquired.append(ok)
                        if ok: e.lock.release()
                    t = threading.Thread(target=lock_check); t.start(); t.join(1)
                    self.assertEqual(acquired, [True])
                finally:
                    release.set()

        def test_shutdown_bypasses_busy_operation(self):
            from concurrent.futures import ThreadPoolExecutor
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); ready = root/"ready.json"
                e = Engine(root/"data", root/"apo")
                entered, release = threading.Event(), threading.Event()
                def blocked(model):
                    entered.set(); release.wait(5)
                    return {"message": "test complete"}
                e.enable = blocked
                server = threading.Thread(target=serve, args=(e, 0, False, ready), daemon=True)
                server.start()
                end = time.monotonic()+5
                while not ready.exists() and time.monotonic()<end: time.sleep(.01)
                launch = json.loads(ready.read_text()); base, token = launch["url"].split("#")
                self.assertTrue(owns_local_port(os.getpid(), urllib.parse.urlsplit(base).port))
                self.assertFalse(owns_local_port(os.getpid()+100000, urllib.parse.urlsplit(base).port))
                def post(action):
                    req = urllib.request.Request(base+"api/"+action, data=json_bytes({"model": defaults()}),
                          headers={"X-Bravado-Token": token, "Content-Type": "application/json"})
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as r:
                        return json.load(r)
                with ThreadPoolExecutor() as pool:
                    pending = pool.submit(post, "enable")
                    try:
                        self.assertTrue(entered.wait(2))
                        self.assertIn("closing", post("shutdown")["message"])
                        server.join(2)
                        self.assertFalse(server.is_alive())
                    finally:
                        release.set()
                        pending.result(timeout=2)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    return unittest.TextTestRunner(stream=stream, verbosity=2).run(suite).wasSuccessful()


def desktop_size(work_width, work_height):
    """Choose a fixed logical size that fits the current Windows work area."""
    return min(1120, max(360, work_width - 32)), min(800, max(320, work_height - 32))


def require_desktop_runtime():
    """Check the host prerequisites before pywebview can select legacy MSHTML."""
    import winreg

    framework = False
    runtime = False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full") as key:
            framework = winreg.QueryValueEx(key, "Release")[0] >= 394802
    except OSError:
        pass
    client = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for hive, prefix in ((winreg.HKEY_CURRENT_USER, "SOFTWARE\\"),
                         (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\"),
                         (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\")):
        try:
            with winreg.OpenKey(hive, prefix + client) as key:
                version = str(winreg.QueryValueEx(key, "pv")[0])
                runtime |= int(version.split(".")[0]) >= 86
        except (OSError, ValueError):
            continue
    if not framework or not runtime:
        raise RuntimeError("Bravado needs Microsoft Edge WebView2 Runtime and .NET Framework 4.6.2 or later. "
                           "Install the missing Microsoft runtime, then reopen Bravado.")


def desktop(engine, port=0, ready_file=None, on_ready=lambda: None):
    require_desktop_runtime()
    import webview

    ready = threading.Event()
    host = {}

    def publish(server, url):
        host.update(server=server, url=url)
        ready.set()

    def run_server():
        try:
            serve(engine, port, False, ready_file, on_server=publish)
        except Exception as exc:
            host["error"] = exc
        finally:
            ready.set()

    worker = threading.Thread(target=run_server, name="Bravado service", daemon=True)
    worker.start()
    if not ready.wait(15):
        raise RuntimeError("Bravado could not start its local service. Please try again.")
    if "error" in host:
        raise host["error"]
    # Release the Windows startup mutex on the thread that acquired it.
    on_ready()
    window = None
    try:
        webview.settings.update(ALLOW_DOWNLOADS=True, ALLOW_FILE_URLS=False,
                                OPEN_EXTERNAL_LINKS_IN_BROWSER=False)
        # Force the modern renderer; do not silently fall back to Internet Explorer.
        from webview.guilib import initialize
        initialize("edgechromium")
        from System.Windows.Forms import Screen, Cursor
        area = Screen.FromPoint(Cursor.Position).WorkingArea
        # WinForms exposes device pixels here; WebView's window size is logical.
        dpi = ct.windll.user32.GetDpiForSystem() if os.name == "nt" else 96
        width, height = desktop_size(round(area.Width * 96 / dpi), round(area.Height * 96 / dpi))
        window = webview.create_window("Bravado", host["url"], width=width, height=height,
                                      resizable=False, min_size=(360, 320),
                                      background_color="#101316", text_select=False,
                                      zoomable=False, easy_drag=False)

        def finish():
            host["server"].shutdown()

        def watch():
            worker.join()
            if not window.events.closed.is_set():
                window.destroy()

        def polish():
            # Dark native title bar; retain standard drag, minimize and close behavior.
            try:
                value = ct.c_int(1)
                ct.windll.dwmapi.DwmSetWindowAttribute(
                    ct.c_void_p(window.native.Handle.ToInt64()), 20,
                    ct.byref(value), ct.sizeof(value))
            except (AttributeError, OSError):
                pass

        window.events.shown += polish
        window.events.closed += finish
        icon = Path(getattr(sys, "_MEIPASS", APP_DIR)) / "bravado.ico"
        webview.start(watch, gui="edgechromium", private_mode=True,
                      storage_path=str(engine.data / "webview"),
                      icon=str(icon) if icon.exists() else None)
    finally:
        host["server"].shutdown()
        worker.join(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--export", type=Path, help="Export Signature to a new/existing empty folder")
    parser.add_argument("--report", type=Path, help="Write self-test or diagnostic results to a file")
    parser.add_argument("--test-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--data-dir", type=Path, default=APP_DIR/"bravado-data")
    parser.add_argument("--apo-config", type=Path, help="Override Equalizer APO config directory")
    parser.add_argument("--port", type=int, default=54900)
    parser.add_argument("--no-browser", "--headless", dest="no_browser", action="store_true", help="Run the local service without its desktop window")
    parser.add_argument("--admin-request", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--request-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--ready-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.test_child:
        time.sleep(60)
        return 0
    if args.admin_request:
        return run_admin_request(args.admin_request, args.request_sha256)
    if args.self_test:
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("w", encoding="utf-8") as stream:
                return 0 if self_test(stream) else 1
        return 0 if self_test() else 1
    if args.diagnose:
        result = {"version": VERSION, "python": sys.version, "numpy": np.__version__, "apo": str(find_apo()),
                  "frozen": bool(getattr(sys, "frozen", False)), "executable": sys.executable,
                  "runtime": str(Path(sys.prefix)), "numpy_file": np.__file__,
                  "factory_presets": {name: m["preamp"] for name, m in factory_presets().items()}}
        try:
            with WindowsAudio() as audio:
                result.update(devices=audio.devices(), default_peak=audio.meter())
        except Exception as e:
            result["audio_error"] = str(e)
        if args.report:
            atomic_write(args.report, json_bytes(result))
        else:
            print(json.dumps(result, indent=2))
        return 0
    if args.export:
        if args.export.exists() and any(args.export.iterdir()):
            raise SystemExit("Export destination must be empty")
        files, report = compile_bundle(defaults())
        for name, data in files.items():
            atomic_write(args.export/name, data)
        print(json.dumps(report, indent=2)); return 0
    mutex = None
    release_start = lambda: None
    try:
        if os.name == "nt":
            release_start = startup_lock()
            stop_previous(args.data_dir)
            kernel = ct.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.restype = ct.c_void_p
            kernel.CreateMutexW.argtypes = [ct.c_void_p, ct.c_int, ct.c_wchar_p]
            mutex = kernel.CreateMutexW(None, False, "Local\\Bravado.Audio.Controller.v1")
            if not mutex or ct.get_last_error() == 183:
                raise RuntimeError("A previous Bravado controller could not be stopped. Run Bravado as administrator to replace an elevated instance.")
        engine = Engine(args.data_dir, args.apo_config)
        if args.no_browser:
            serve(engine, args.port, False, args.ready_file, release_start)
        else:
            desktop(engine, args.port, args.ready_file, release_start)
    finally:
        release_start()
        if mutex:
            kernel.CloseHandle.argtypes = [ct.c_void_p]
            kernel.CloseHandle(mutex)
    return 0


if __name__ == "__main__":
    # Windowed builds have no console streams. File reports remain available.
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        report = traceback.format_exc()
        try:
            atomic_write(APP_DIR/"bravado-data"/"startup-error.log", report.encode("utf-8"))
        except OSError:
            pass
        print(report, file=sys.stderr)
        if getattr(sys, "frozen", False) and "--no-browser" not in sys.argv:
            ct.windll.user32.MessageBoxW(None, "Bravado could not start.\n\n" + report.splitlines()[-1] +
                                        "\n\nDetails: bravado-data\\startup-error.log", "Bravado", 0x10)
        raise SystemExit(1)

