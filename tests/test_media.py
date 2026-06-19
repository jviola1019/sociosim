"""Real procedural media synthesis: valid, deterministic PNG bytes."""

import struct
import zlib

from socio_sim.content.media import PNG_SIG, synth_frames, synth_image


def _ihdr_dims(png: bytes):
    # IHDR width/height live at bytes 16..24 (after 8-sig + 4 len + 4 'IHDR')
    return struct.unpack(">II", png[16:24])


def test_synth_image_is_valid_and_deterministic_png():
    a = synth_image(123, 64, 48)
    b = synth_image(123, 64, 48)
    assert a == b                          # deterministic (same seed)
    assert a[:8] == PNG_SIG                # real PNG signature
    assert _ihdr_dims(a) == (64, 48)       # correct dimensions
    assert synth_image(124, 64, 48) != a   # seed changes the image


def test_synth_image_decodes_to_right_pixel_count():
    png = synth_image(7, 32, 24)
    # extract IDAT, inflate, check raw size = h*(1 filter byte + w*3)
    idat_start = png.index(b"IDAT") + 4
    length = struct.unpack(">I", png[idat_start - 8:idat_start - 4])[0]
    raw = zlib.decompress(png[idat_start:idat_start + length])
    assert len(raw) == 24 * (1 + 32 * 3)


def test_synth_frames_distinct_and_deterministic():
    f1 = synth_frames(5, n_frames=6, w=32, h=32)
    f2 = synth_frames(5, n_frames=6, w=32, h=32)
    assert len(f1) == 6 and f1 == f2            # deterministic sequence
    assert all(fr[:8] == PNG_SIG for fr in f1)  # all real PNGs
    assert len(set(f1)) > 1                      # frames differ (animation)
