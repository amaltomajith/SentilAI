"""Zero-token media tools: Pillow-forged UPI failure screens, Groq-Whisper STT, edge-tts voice."""
from __future__ import annotations

import asyncio
import hashlib
import io
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

IST = timezone(timedelta(hours=5, minutes=30))
# (code, message) pairs in the style of UPI/NPCI response codes. Presentation only.
NPCI_ERRORS = {
    "U16": "Risk threshold exceeded",
    "U30": "Debit has failed",
    "U53": "Transaction limit exceeded for the day",
    "U09": "Remitter bank not responding",
    "ZM": "Invalid UPI PIN attempts exceeded",
    "UT": "Transaction timed out, amount not debited",
}


def _font(size: int, bold: bool = False):
    for name in (["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def forge_screenshot(vpa: str, amount: str, error_code: str = "U16", *, now: datetime | None = None,
                     payer_bank: str = "State Bank of India") -> tuple[bytes, dict]:
    """Deterministic mobile 'payment failed' screen for the exact VPA/amount the scammer asked for."""
    if error_code not in NPCI_ERRORS:
        raise ValueError(f"unknown error code {error_code}")
    now = (now or datetime.now(IST)).astimezone(IST)
    W, H = 720, 1500
    img = Image.new("RGB", (W, H), (246, 247, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 96], fill=(25, 118, 210))
    d.text((32, 30), now.strftime("%I:%M %p"), font=_font(30, True), fill="white")
    d.text((W - 230, 30), "5G", font=_font(28, True), fill="white")
    for i in range(4):
        d.rectangle([W - 150 + i * 22, 62 - (i + 1) * 9, W - 135 + i * 22, 62], fill="white" if i < 3 else (140, 180, 230))
    d.text((32, 128), "\u2190  Payment status", font=_font(34, True), fill=(40, 40, 40))
    cx, cy = W // 2, 330
    d.ellipse([cx - 78, cy - 78, cx + 78, cy + 78], fill=(211, 47, 47))
    d.line([cx - 32, cy - 32, cx + 32, cy + 32], fill="white", width=16)
    d.line([cx + 32, cy - 32, cx - 32, cy + 32], fill="white", width=16)
    d.text((cx, 470), "Payment Failed", font=_font(48, True), fill=(211, 47, 47), anchor="mm")
    d.text((cx, 560), f"Rs. {amount}", font=_font(72, True), fill=(30, 30, 30), anchor="mm")
    d.text((cx, 640), f"{now.strftime('%d %b %Y, %I:%M %p')}", font=_font(28), fill=(110, 110, 110), anchor="mm")
    d.rounded_rectangle([40, 700, W - 40, 1120], 24, fill="white", outline=(225, 228, 232), width=2)
    rows = [("To", vpa), ("From", f"{payer_bank} ****"), ("Reason", f"{error_code} - {NPCI_ERRORS[error_code]}"),
            ("UPI Ref. No.", "4" + hashlib.sha256(f"{vpa}{amount}{now.isoformat()}".encode()).hexdigest()[:11].translate(str.maketrans("abcdef", "123456")))]
    y = 730
    for k, v in rows:
        d.text((72, y), k, font=_font(26), fill=(120, 120, 120))
        d.text((72, y + 36), v[:42], font=_font(30, True), fill=(30, 30, 30))
        y += 96
    d.text((cx, 1180), "Money debited will be refunded in 3-5 working days.", font=_font(24), fill=(120, 120, 120), anchor="mm")
    d.rounded_rectangle([80, 1250, W - 80, 1340], 45, fill=(25, 118, 210))
    d.text((cx, 1295), "Retry payment", font=_font(34, True), fill="white", anchor="mm")
    meta = PngImagePlugin.PngInfo()
    meta.add_text("sentinel-forged", "1")  # honest provenance marker for our own evidence trail
    buf = io.BytesIO()
    img.save(buf, "PNG", pnginfo=meta)
    data = buf.getvalue()
    return data, {"sha256": hashlib.sha256(data).hexdigest(), "error_code": error_code, "vpa": vpa, "amount": amount,
                  "timestamp": now.isoformat(), "bytes": len(data)}


async def transcribe_voice(audio: bytes, filename: str, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Groq free-tier Whisper: original-language transcript + English translation."""
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")
    hdr = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=60, transport=transport) as c:
        files = {"file": (filename, audio)}
        r1 = await c.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=hdr, files=files,
                          data={"model": "whisper-large-v3", "response_format": "verbose_json"})
        r1.raise_for_status()
        j1 = r1.json()
        lang = j1.get("language", "")
        english = j1.get("text", "")
        if lang and lang.lower() not in ("en", "english"):
            r2 = await c.post("https://api.groq.com/openai/v1/audio/translations", headers=hdr, files={"file": (filename, audio)},
                              data={"model": "whisper-large-v3", "response_format": "json"})
            r2.raise_for_status()
            english = r2.json().get("text", "")
    return {"original": j1.get("text", ""), "language": lang, "english": english}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


async def synthesize_voice(text: str, voice: str = "en-IN-PrabhatNeural") -> dict:
    """edge-tts (free) -> optional ffmpeg 'aging' (band-limit, room noise, slower pace) -> OGG/Opus PTT.
    Without ffmpeg the plain MP3 is returned and flagged so the caller can degrade gracefully."""
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="-12%", pitch="-8Hz")
    mp3 = b"".join([chunk["data"] async for chunk in comm.stream() if chunk["type"] == "audio"])
    if not mp3:
        raise RuntimeError("edge-tts returned no audio")
    if not ffmpeg_available():
        return {"audio": mp3, "mime": "audio/mpeg", "ptt": False, "aged": False, "note": "ffmpeg missing: plain mp3"}
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.mp3", Path(td) / "out.ogg"
        src.write_bytes(mp3)
        flt = ("[0:a]highpass=f=150,lowpass=f=3400,acompressor=threshold=-18dB:ratio=3[v];"
               "anoisesrc=color=brown:amplitude=0.012[n];[v][n]amix=inputs=2:duration=first:normalize=0")
        proc = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-i", str(src), "-filter_complex", flt, "-c:a", "libopus",
                                                    "-b:a", "24k", "-ar", "16000", "-ac", "1", str(dst),
                                                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        if await proc.wait() != 0 or not dst.exists():
            return {"audio": mp3, "mime": "audio/mpeg", "ptt": False, "aged": False, "note": "ffmpeg failed: plain mp3"}
        return {"audio": dst.read_bytes(), "mime": "audio/ogg; codecs=opus", "ptt": True, "aged": True, "note": ""}