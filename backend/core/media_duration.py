"""Media duration probing for audio that is billed by TIME, not by tokens.

Whisper (and the OpenAI audio transcription family) is priced per audio
second/minute, so a spend reservation needs the real media duration. A byte
length divided by a made-up bitrate is not a duration: compressed audio can be
8 kbps Opus or 320 kbps MP3, and container headers are authoritative.

This module reads the duration from common container/codec headers with the
standard library, then optionally falls back to ``ffprobe`` when it is already
installed. It never invents a duration: an unreadable blob returns ``None`` and
the accounting layer treats that as explicit unknown liability (hard_stop
refuses before dispatch).
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from typing import Any, Optional

logger = logging.getLogger(__name__)

# A tiny invalid blob should not pay the cost of spawning ffprobe.
_FFPROBE_MIN_BYTES = 256


def _positive_finite(value: Any) -> Optional[float]:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        return None
    if seconds <= 0:
        return None
    return seconds


# ---------------------------------------------------------------------------
# WAV
# ---------------------------------------------------------------------------
def _wav_duration(data: bytes) -> Optional[float]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            rate = int(reader.getframerate() or 0)
            frames = int(reader.getnframes() or 0)
            if rate > 0 and frames >= 0:
                return frames / float(rate)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# FLAC
# ---------------------------------------------------------------------------
def _flac_duration(data: bytes) -> Optional[float]:
    if len(data) < 42 or data[:4] != b"fLaC":
        return None
    try:
        offset = 4
        while offset + 4 <= len(data):
            header = data[offset]
            last = bool(header & 0x80)
            block_type = header & 0x7F
            length = int.from_bytes(data[offset + 1:offset + 4], "big")
            payload = data[offset + 4:offset + 4 + length]
            if block_type == 0 and len(payload) >= 18:
                packed = int.from_bytes(payload[10:18], "big")
                sample_rate = (packed >> 44) & 0xFFFFF
                total_samples = packed & 0xFFFFFFFFF
                if sample_rate > 0 and total_samples > 0:
                    return total_samples / float(sample_rate)
                return None
            offset += 4 + length
            if last:
                break
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# MPEG audio (MP3 / MP2)
# ---------------------------------------------------------------------------
_MPEG_BITRATES = {
    # (version_group, layer): kbps table indexed by bitrate_index
    (1, 1): (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448, 0),
    (1, 2): (0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384, 0),
    (1, 3): (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0),
    (2, 1): (0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256, 0),
    (2, 2): (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
    (2, 3): (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
}
_MPEG_SAMPLE_RATES = {
    1: (44100, 48000, 32000),
    2: (22050, 24000, 16000),
    25: (11025, 12000, 8000),
}


def _skip_id3v2(data: bytes) -> int:
    if len(data) < 10 or data[:3] != b"ID3":
        return 0
    size = (
        ((data[6] & 0x7F) << 21)
        | ((data[7] & 0x7F) << 14)
        | ((data[8] & 0x7F) << 7)
        | (data[9] & 0x7F)
    )
    footer = 10 if (data[5] & 0x10) else 0
    return min(len(data), 10 + size + footer)


def _mp3_frame_header(data: bytes, offset: int) -> Optional[dict]:
    if offset + 4 > len(data):
        return None
    b0, b1, b2, b3 = data[offset:offset + 4]
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None
    version_bits = (b1 >> 3) & 0x03  # 0=2.5, 1=reserved, 2=2, 3=1
    layer_bits = (b1 >> 1) & 0x03   # 0=reserved, 1=III, 2=II, 3=I
    if version_bits == 1 or layer_bits == 0:
        return None
    version = {0: 25, 2: 2, 3: 1}[version_bits]
    layer = {1: 3, 2: 2, 3: 1}[layer_bits]
    bitrate_index = (b2 >> 4) & 0x0F
    sample_rate_index = (b2 >> 2) & 0x03
    if bitrate_index in (0, 15) or sample_rate_index == 3:
        return None
    group = 1 if version == 1 else 2
    bitrate = _MPEG_BITRATES[(group, layer)][bitrate_index] * 1000
    sample_rate = _MPEG_SAMPLE_RATES[version][sample_rate_index]
    if bitrate <= 0 or sample_rate <= 0:
        return None
    padding = (b2 >> 1) & 0x01
    if layer == 1:
        frame_length = (12 * bitrate // sample_rate + padding) * 4
        samples_per_frame = 384
    elif layer == 3 and version != 1:
        frame_length = 72 * bitrate // sample_rate + padding
        samples_per_frame = 576
    else:
        frame_length = 144 * bitrate // sample_rate + padding
        samples_per_frame = 1152
    if frame_length < 4:
        return None
    return {
        "frame_length": int(frame_length),
        "sample_rate": int(sample_rate),
        "samples_per_frame": int(samples_per_frame),
        "layer": layer,
        "version": version,
    }


def _mp3_duration(data: bytes) -> Optional[float]:
    if not data:
        return None
    start = _skip_id3v2(data)
    # Find first valid frame within a bounded resync window.
    first = None
    for offset in range(start, min(len(data), start + 65536)):
        header = _mp3_frame_header(data, offset)
        if header is not None:
            first = (offset, header)
            break
    if first is None:
        return None
    offset, header = first
    # Xing/Info VBR header: number of frames is authoritative.
    side_info = 17 if header["version"] == 1 else 9
    if header["layer"] == 3:
        for marker in (b"Xing", b"Info"):
            pos = offset + 4 + side_info
            if data[pos:pos + 4] == marker and pos + 12 <= len(data):
                flags = int.from_bytes(data[pos + 4:pos + 8], "big")
                if flags & 0x01:
                    frames = int.from_bytes(data[pos + 8:pos + 12], "big")
                    if frames > 0:
                        return (
                            frames * header["samples_per_frame"]
                            / float(header["sample_rate"])
                        )
    # VBRI header (Fraunhofer) sits 32 bytes after the frame header.
    if header["layer"] == 3 and data[offset + 4 + 32:offset + 4 + 36] == b"VBRI":
        pos = offset + 4 + 36
        if pos + 18 <= len(data):
            frames = int.from_bytes(data[pos + 14:pos + 18], "big")
            if frames > 0:
                return (
                    frames * header["samples_per_frame"]
                    / float(header["sample_rate"])
                )
    # Walk frames. This handles CBR and headerless VBR without trusting one
    # frame's bitrate for the whole file.
    total_samples = 0
    cursor = offset
    frames = 0
    while cursor + 4 <= len(data) and frames < 2_000_000:
        current = _mp3_frame_header(data, cursor)
        if current is None:
            # Tolerate one damaged byte, then stop: trailing tags are not
            # audio frames and must not extend the billed duration.
            cursor += 1
            continue
        total_samples += current["samples_per_frame"]
        frames += 1
        cursor += current["frame_length"]
    if total_samples > 0:
        return total_samples / float(header["sample_rate"])
    return None


# ---------------------------------------------------------------------------
# MP4 / M4A
# ---------------------------------------------------------------------------
def _mp4_duration(data: bytes) -> Optional[float]:
    if len(data) < 12 or data[4:8] not in (b"ftyp", b"moov", b"free", b"mdat"):
        return None

    def _boxes(start: int, end: int):
        offset = start
        while offset + 8 <= end:
            size = int.from_bytes(data[offset:offset + 4], "big")
            box_type = data[offset + 4:offset + 8]
            header = 8
            if size == 1:
                if offset + 16 > end:
                    return
                size = int.from_bytes(data[offset + 8:offset + 16], "big")
                header = 16
            elif size == 0:
                size = end - offset
            if size < header or offset + size > end:
                return
            yield box_type, offset + header, offset + size
            offset += size

    def _mvhd_fields(start: int, end: int):
        """``(timescale, duration_units)``; 0 means absent/unknown.

        An all-ones duration is the spec's "unknown", not a 49-day movie:
        billing it would reserve (and later charge) a fabricated quantity.
        """
        if start + 4 > end:
            return 0, 0
        if data[start] == 1:
            if start + 32 > end:
                return 0, 0
            timescale = int.from_bytes(data[start + 20:start + 24], "big")
            duration = int.from_bytes(data[start + 24:start + 32], "big")
            if duration == 0xFFFFFFFFFFFFFFFF:
                duration = 0
            return timescale, duration
        if start + 20 > end:
            return 0, 0
        timescale = int.from_bytes(data[start + 12:start + 16], "big")
        duration = int.from_bytes(data[start + 16:start + 20], "big")
        if duration == 0xFFFFFFFF:
            duration = 0
        return timescale, duration

    def _mehd_units(start: int, end: int) -> int:
        """Fragment duration from ``mvex/mehd`` (same timebase as ``mvhd``)."""
        if start + 4 > end:
            return 0
        if data[start] == 1:
            if start + 12 > end:
                return 0
            return int.from_bytes(data[start + 4:start + 12], "big")
        if start + 8 > end:
            return 0
        return int.from_bytes(data[start + 4:start + 8], "big")

    try:
        for box_type, content_start, content_end in _boxes(0, len(data)):
            if box_type != b"moov":
                continue
            timescale = 0
            fragment_units = 0
            for child, child_start, child_end in _boxes(
                    content_start, content_end):
                if child == b"mvhd":
                    box_timescale, duration = _mvhd_fields(
                        child_start, child_end)
                    if box_timescale > 0 and duration > 0:
                        return duration / float(box_timescale)
                    timescale = box_timescale or timescale
                elif child == b"mvex":
                    # Fragmented MP4 often carries duration=0 in mvhd; the
                    # movie timeline then lives in mehd (same timescale).
                    for inner, inner_start, inner_end in _boxes(
                            child_start, child_end):
                        if inner == b"mehd":
                            fragment_units = _mehd_units(
                                inner_start, inner_end) or fragment_units
            if timescale > 0 and fragment_units > 0:
                return fragment_units / float(timescale)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# WebM / Matroska
# ---------------------------------------------------------------------------
def _read_vint(data: bytes, offset: int, *, keep_marker: bool):
    if offset >= len(data):
        return None, offset
    first = data[offset]
    if first == 0:
        return None, offset
    width = 1
    mask = 0x80
    while width <= 8 and not (first & mask):
        width += 1
        mask >>= 1
    if width > 8 or offset + width > len(data):
        return None, offset
    raw = int.from_bytes(data[offset:offset + width], "big")
    if keep_marker:
        return raw, offset + width
    value = raw & ((1 << (7 * width)) - 1)
    return value, offset + width


def _ebml_elements(data: bytes, start: int, end: int):
    offset = start
    while offset < end:
        element_id, after_id = _read_vint(data, offset, keep_marker=True)
        if element_id is None:
            return
        size, after_size = _read_vint(data, after_id, keep_marker=False)
        if size is None:
            return
        unknown_size = size == (1 << (7 * (after_size - after_id))) - 1
        content_start = after_size
        content_end = end if unknown_size else min(end, content_start + size)
        if content_end < content_start:
            return
        yield element_id, content_start, content_end
        if unknown_size:
            # Unknown-size Segment/Cluster extends to the end (or next
            # same-level element); we only descend into known containers.
            if element_id in (0x18538067, 0x1F43B675, 0x1549A966):
                offset = content_start
                continue
            return
        offset = content_end


def _webm_duration(data: bytes) -> Optional[float]:
    if len(data) < 4 or data[:4] != b"\x1a\x45\xdf\xa3":
        return None
    try:
        for element_id, start, end in _ebml_elements(data, 0, len(data)):
            if element_id != 0x18538067:  # Segment
                continue
            timecode_scale = 1_000_000
            duration_units = None
            for child_id, child_start, child_end in _ebml_elements(
                    data, start, end):
                if child_id != 0x1549A966:  # Info
                    continue
                for info_id, info_start, info_end in _ebml_elements(
                        data, child_start, child_end):
                    if info_id == 0x2AD7B1:  # TimecodeScale
                        timecode_scale = int.from_bytes(
                            data[info_start:info_end], "big") or 1_000_000
                    elif info_id == 0x4489:  # Duration
                        payload_len = info_end - info_start
                        if payload_len == 4:
                            duration_units = struct.unpack(
                                ">f", data[info_start:info_end])[0]
                        elif payload_len == 8:
                            duration_units = struct.unpack(
                                ">d", data[info_start:info_end])[0]
                if duration_units is not None:
                    return duration_units * timecode_scale / 1_000_000_000.0
            break
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# OGG (Vorbis / Opus)
# ---------------------------------------------------------------------------
def _ogg_duration(data: bytes) -> Optional[float]:
    if len(data) < 28 or data[:4] != b"OggS":
        return None
    try:
        # First page payload identifies the codec and its sample rate.
        segments = data[26]
        payload_start = 27 + segments
        payload = data[payload_start:payload_start + 64]
        sample_rate = None
        granule_rate = None
        if payload.startswith(b"\x01vorbis") and len(payload) >= 16:
            sample_rate = int.from_bytes(payload[12:16], "little")
            granule_rate = sample_rate
        elif payload.startswith(b"OpusHead") and len(payload) >= 16:
            # Opus granules are always 48 kHz regardless of input rate.
            sample_rate = int.from_bytes(payload[12:16], "little")
            granule_rate = 48000
        if not sample_rate or not granule_rate:
            return None
        # Last completed page's granule position is the total sample count.
        last = data.rfind(b"OggS")
        if last < 0 or last + 14 > len(data):
            return None
        granule = int.from_bytes(data[last + 6:last + 14], "little", signed=True)
        if granule > 0:
            return granule / float(granule_rate)
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# ffprobe fallback (already-installed local binary; never network)
# ---------------------------------------------------------------------------
def _ffprobe_duration(data: bytes, filename: Optional[str]) -> Optional[float]:
    if len(data) < _FFPROBE_MIN_BYTES:
        return None
    executable = shutil.which("ffprobe")
    if not executable:
        return None
    suffix = os.path.splitext(filename)[1] if isinstance(filename, str) else ""
    suffix = suffix or ".bin"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False) as handle:
            temp_path = handle.name
            handle.write(data)
        result = subprocess.run(
            [executable, "-v", "error",
             # Uploaded audio is untrusted input. Restrict the demuxers to the
             # local file protocol so a playlist/segment payload (`.m3u8`) or
             # an MP4 external-data reference cannot make this "local" probe
             # fetch a remote URL (SSRF) — it fails instead, and the duration
             # stays explicitly unknown.
             "-protocol_whitelist", "file",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", temp_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        return _positive_finite(result.stdout.strip())
    except Exception:
        return None
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _filename_for(file: Any) -> Optional[str]:
    name = getattr(file, "name", None)
    if isinstance(name, str) and name:
        return name
    if isinstance(file, (tuple, list)) and len(file) >= 1:
        first = file[0]
        if isinstance(first, str):
            return first
    return None


def media_duration_seconds(
    data: Optional[bytes],
    filename: Optional[str] = None,
    *,
    file: Any = None,
    allow_ffprobe: bool = True,
) -> Optional[float]:
    """Return the media duration in seconds, or ``None`` when unproven.

    Pure-header readers run first (WAV, FLAC, MP3/MP2, MP4/M4A, WebM,
    OGG/Opus/Vorbis). ``ffprobe`` is only a last-resort local probe for
    formats this module does not parse; it is protocol-restricted so it never
    contacts a provider or any remote URL.

    ``file`` is consulted only for a filename hint. A duration declared on an
    arbitrary object (``duration_seconds``/``duration``) is deliberately NOT
    trusted: upload metadata is caller-controlled and could under-report the
    quantity actually billed. Only bytes in a known container are evidence.
    """
    if not isinstance(filename, str) or not filename:
        filename = _filename_for(file)
    if data:
        seconds = None
        # Select by container magic FIRST. Blindly trying the MP3 frame
        # scanner over an MP4/WebM/OGG payload finds false sync words and
        # reports a bogus fractional duration.
        if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            seconds = _wav_duration(data)
        elif data[:4] == b"fLaC":
            seconds = _flac_duration(data)
        elif data[:4] == b"OggS":
            seconds = _ogg_duration(data)
        elif data[:4] == b"\x1a\x45\xdf\xa3":
            seconds = _webm_duration(data)
        elif len(data) >= 12 and data[4:8] in (
                b"ftyp", b"moov", b"free", b"mdat", b"wide", b"skip"):
            seconds = _mp4_duration(data)
        elif data[:3] == b"ID3" or (
                len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            seconds = _mp3_duration(data)
        if seconds is not None and _positive_finite(seconds):
            return _positive_finite(seconds)
        if allow_ffprobe:
            seconds = _ffprobe_duration(data, filename)
            if seconds is not None:
                return _positive_finite(seconds)
    return None
