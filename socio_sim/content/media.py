"""Real media synthesis (Spec §6 was "media simulated as typed objects only").

Deterministic, offline, zero-dependency procedural raster synthesis: a seeded
numpy composition (gradient field + soft colour blobs) encoded to real PNG bytes
with a tiny stdlib (zlib) encoder. Seeded by content id, so every item gets a
unique, reproducible image; replays are bit-identical. `synth_video` encodes a
real, playable animated-PNG (APNG) container; `synth_frames` exposes the raw
frames. Deliberate generative art — not an AI-image aesthetic.

An external diffusion/image-model backend can be plugged in via
`set_image_backend`; the deterministic procedural path stays the default so the
simulator remains offline and reproducible.
"""

from __future__ import annotations

import struct
import zlib

import numpy as np

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png(rgb: np.ndarray) -> bytes:
    """Encode an (H, W, 3) uint8 array to PNG bytes (filter 0, colour type 2)."""
    h, w, _ = rgb.shape
    raw = bytearray()
    row = rgb.reshape(h, w * 3)
    for y in range(h):
        raw.append(0)                    # per-scanline filter type 0 (None)
        raw.extend(row[y].tobytes())
    comp = zlib.compress(bytes(raw), 6)

    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)   # 8-bit RGB
    return PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")


def _compose(seed: int, w: int, h: int, phase: float = 0.0) -> np.ndarray:
    """Seeded procedural RGB field: diagonal gradient + soft colour blobs.
    `phase` animates blob positions for video frames."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    nx, ny = xx / max(w - 1, 1), yy / max(h - 1, 1)
    c1 = rng.integers(40, 200, 3).astype(float)
    c2 = rng.integers(40, 220, 3).astype(float)
    t = (nx + ny) / 2.0
    img = c1[None, None, :] * (1 - t)[..., None] + c2[None, None, :] * t[..., None]
    for _ in range(int(rng.integers(3, 6))):
        bx = (rng.random() + 0.15 * np.sin(2 * np.pi * (phase + rng.random()))) * w
        by = (rng.random() + 0.15 * np.cos(2 * np.pi * (phase + rng.random()))) * h
        r = (0.12 + rng.random() * 0.3) * w
        col = rng.integers(0, 255, 3).astype(float)
        d = np.sqrt((xx - bx) ** 2 + (yy - by) ** 2)
        mask = np.clip(1 - d / r, 0, 1)[..., None]
        img = img * (1 - 0.5 * mask) + col[None, None, :] * 0.5 * mask
    return np.clip(img, 0, 255).astype(np.uint8)


#: Optional pluggable image backend: a callable (seed, w, h) -> PNG bytes (e.g.
#: a diffusion model). None -> the deterministic offline procedural default.
_image_backend = None


def set_image_backend(fn) -> None:
    """Plug an external image backend (e.g. a diffusion model). Pass None to
    restore the deterministic offline procedural default."""
    global _image_backend
    _image_backend = fn


def synth_image(seed: int, w: int = 256, h: int = 256) -> bytes:
    """Deterministic procedural PNG image (real bytes) for a content item, or the
    registered backend's output if one is plugged in."""
    if _image_backend is not None:
        return _image_backend(int(seed), w, h)
    return _png(_compose(int(seed), w, h))


def synth_frames(seed: int, n_frames: int = 8, w: int = 128, h: int = 128) -> list:
    """Deterministic frame sequence (real PNG bytes per frame)."""
    return [_png(_compose(int(seed), w, h, phase=i / max(n_frames, 1)))
            for i in range(n_frames)]


def _idat_bytes(rgb: np.ndarray) -> bytes:
    h, w, _ = rgb.shape
    raw = bytearray()
    row = rgb.reshape(h, w * 3)
    for y in range(h):
        raw.append(0)
        raw.extend(row[y].tobytes())
    return zlib.compress(bytes(raw), 6)


def synth_video(seed: int, n_frames: int = 8, w: int = 128, h: int = 128,
                delay_ms: int = 120) -> bytes:
    """Deterministic animated PNG (APNG) — a real, playable video container,
    zero-dependency. Players without APNG support show the first frame."""
    frames = [_compose(int(seed), w, h, phase=i / max(n_frames, 1))
              for i in range(n_frames)]

    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    out = bytearray(PNG_SIG)
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    out += chunk(b"acTL", struct.pack(">II", len(frames), 0))   # frames, loops(0=inf)

    def fctl(seq: int) -> bytes:
        return chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0,
                                          delay_ms, 1000, 0, 0))

    seq = 0
    out += fctl(seq)
    seq += 1
    out += chunk(b"IDAT", _idat_bytes(frames[0]))               # frame 0
    for fr in frames[1:]:
        out += fctl(seq)
        seq += 1
        out += chunk(b"fdAT", struct.pack(">I", seq) + _idat_bytes(fr))
        seq += 1
    out += chunk(b"IEND", b"")
    return bytes(out)
