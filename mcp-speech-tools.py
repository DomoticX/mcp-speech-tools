#!/usr/bin/env python3
"""
mcp-speech-tools.py
MCP server for local Text-To-Speech (TTS) and Speech-To-Text (STT).

STT is implemented via whisper.cpp's whisper-cli.exe (Vulkan build).
TTS is implemented via Piper (piper.exe), played back with ffmpeg's ffplay.exe.

Requires:
    pip install mcp

Directory example:
    K:\\mcp-tools\\mcp-speech-tools\\
        mcp-speech-tools.py
        config.json
        bin\\
            whisper\\
                whisper-cli.exe
                ggml-base.bin
            ffmpeg\\
                ffmpeg.exe
                ffplay.exe
            piper\\
                piper.exe
                <voice>.onnx
                <voice>.onnx.json
        temp\\
"""

from __future__ import annotations

import atexit
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

# MCP SDK v2; keep a fallback for older v1 installations.
try:
    from mcp.server import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_CONFIG = {
    "whisper_path": str(BASE_DIR / "bin" / "whisper" / "whisper-cli.exe"),
    "whisper_model": "ggml-base.bin",
    "ffmpeg_path": str(BASE_DIR / "bin" / "ffmpeg" / "ffmpeg.exe"),
    "piper_path": str(BASE_DIR / "bin" / "piper" / "piper.exe"),
    "piper_model": "nl_NL-pim-medium.onnx",
    "ffplay_path": str(BASE_DIR / "bin" / "ffmpeg" / "ffplay.exe"),
    "temp_dir": str(BASE_DIR / "temp"),
    "default_language": "auto",
    "command_timeout_seconds": 600,
    "cleanup_stale_after_seconds": 3600,
}

# Natively decoded by whisper.cpp (via miniaudio) — no conversion needed.
NATIVE_AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac"}
# Not readable by whisper.cpp directly; converted to WAV via ffmpeg first.
CONVERTIBLE_AUDIO_EXTS = {".aac", ".m4a", ".wma", ".opus"}
SUPPORTED_AUDIO_EXTS = NATIVE_AUDIO_EXTS | CONVERTIBLE_AUDIO_EXTS


def load_config() -> dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        try:
            user_cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
        except Exception as exc:
            raise RuntimeError(f"Invalid config.json: {exc}") from exc

    return cfg


CONFIG = load_config()
WHISPER_CLI = Path(CONFIG["whisper_path"]).expanduser()
FFMPEG = Path(CONFIG["ffmpeg_path"]).expanduser()
PIPER = Path(CONFIG["piper_path"]).expanduser()
FFPLAY = Path(CONFIG["ffplay_path"]).expanduser()


def resolve_model_path(model: str | None) -> Path:
    """Resolve a model filename against the whisper-cli.exe folder, unless already absolute."""
    name = model or CONFIG["whisper_model"]
    p = Path(name).expanduser()
    if not p.is_absolute():
        p = WHISPER_CLI.parent / name
    return p


def resolve_voice_path(voice: str | None) -> Path:
    """Resolve a Piper voice filename against the piper.exe folder, unless already absolute."""
    name = voice or CONFIG["piper_model"]
    p = Path(name).expanduser()
    if not p.is_absolute():
        p = PIPER.parent / name
    return p


def require_voice_files(voice_path: Path) -> Path:
    if not voice_path.is_file():
        raise FileNotFoundError(
            f"Piper voice model not found: {voice_path}. "
            f"Download a voice into {voice_path.parent} (see bin/piper/README.md)."
        )

    config_path = Path(str(voice_path) + ".json")
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Piper voice config not found: {config_path}. "
            f"Each voice needs both the .onnx file and its .onnx.json config, downloaded together."
        )

    return voice_path


def _run_hidden(exe: Path, args: list[str], timeout: int, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """
    Run an executable without opening a console window on Windows.

    input_text is sent on stdin when given; otherwise stdin is explicitly
    closed (DEVNULL) so the child never inherits this MCP server's own
    stdio transport pipe.
    """
    startupinfo = None
    creationflags = 0

    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    kwargs: dict[str, Any] = {}
    if input_text is not None:
        kwargs["input"] = input_text
    else:
        kwargs["stdin"] = subprocess.DEVNULL

    return subprocess.run(
        [str(exe), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        startupinfo=startupinfo,
        creationflags=creationflags,
        check=False,
        **kwargs,
    )


def run_whisper(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    if not WHISPER_CLI.is_file():
        raise FileNotFoundError(
            f"whisper-cli.exe not found: {WHISPER_CLI}. "
            f"Set 'whisper_path' in {CONFIG_FILE} (see bin/whisper/README.md for download info)."
        )

    return _run_hidden(WHISPER_CLI, args, timeout or int(CONFIG["command_timeout_seconds"]))


def run_ffmpeg(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    if not FFMPEG.is_file():
        raise FileNotFoundError(
            f"ffmpeg.exe not found: {FFMPEG}. "
            f"Set 'ffmpeg_path' in {CONFIG_FILE} (see bin/ffmpeg/README.md for download info)."
        )

    return _run_hidden(FFMPEG, args, timeout or int(CONFIG["command_timeout_seconds"]))


def run_piper(args: list[str], input_text: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    if not PIPER.is_file():
        raise FileNotFoundError(
            f"piper.exe not found: {PIPER}. "
            f"Set 'piper_path' in {CONFIG_FILE} (see bin/piper/README.md for download info)."
        )

    return _run_hidden(PIPER, args, timeout or int(CONFIG["command_timeout_seconds"]), input_text=input_text)


def synthesize_wav(
    text: str,
    voice_path: Path,
    out_wav: Path,
    speaker: int | None = None,
    length_scale: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run Piper to synthesize text (sent on stdin) to a WAV file."""
    args = ["-m", str(voice_path), "-f", str(out_wav), "-q"]

    espeak_data_dir = PIPER.parent / "espeak-ng-data"
    if espeak_data_dir.is_dir():
        args += ["--espeak_data", str(espeak_data_dir)]

    if speaker is not None:
        args += ["-s", str(speaker)]
    if length_scale is not None:
        args += ["--length_scale", str(length_scale)]

    return run_piper(args, input_text=text)


def convert_to_wav(audio: Path) -> Path:
    """Convert a non-natively-supported audio file to a temp 16kHz mono PCM WAV via ffmpeg."""
    out_path = make_temp_prefix(audio.stem).with_suffix(".wav")

    proc = run_ffmpeg(["-y", "-i", str(audio), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(out_path)])

    if proc.returncode != 0 or not out_path.is_file():
        raise RuntimeError(
            f"ffmpeg conversion failed (code {proc.returncode}) for {audio}: "
            f"{(proc.stderr or '').strip()[-2000:]}"
        )

    return out_path


def validate_audio_path(path: str) -> Path:
    p = Path(path).expanduser().resolve()

    if not p.exists():
        raise FileNotFoundError(f"Audio file does not exist: {p}")
    if not p.is_file():
        raise ValueError(f"Path is not a file: {p}")
    if p.suffix.lower() not in SUPPORTED_AUDIO_EXTS:
        raise ValueError(
            f"Unsupported audio format '{p.suffix}'. "
            f"Native: {', '.join(sorted(NATIVE_AUDIO_EXTS))}. "
            f"Converted via ffmpeg: {', '.join(sorted(CONVERTIBLE_AUDIO_EXTS))}."
        )

    return p


def make_temp_prefix(label: str) -> Path:
    """Unique temp-file prefix (without extension) under temp_dir, for any tool's scratch output."""
    root = Path(CONFIG["temp_dir"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    safe_label = re.sub(r"[^A-Za-z0-9._ -]+", "_", label).strip(" .") or "audio"
    return root / f"{safe_label}_{int(time.time() * 1000)}"


def cleanup_stale_outputs() -> dict[str, Any]:
    """Remove leftover temp files (converted/synthesized WAV, timestamp JSON, ...) older than cleanup_stale_after_seconds."""
    root = Path(CONFIG["temp_dir"]).expanduser()
    if not root.exists():
        return {"ok": True, "removed": []}

    max_age = int(CONFIG.get("cleanup_stale_after_seconds", 3600))
    now = time.time()
    removed: list[str] = []

    for child in root.iterdir():
        if not child.is_file():
            continue
        try:
            age = now - child.stat().st_mtime
            if age >= max_age:
                child.unlink(missing_ok=True)
                removed.append(str(child))
        except OSError:
            continue

    return {"ok": True, "removed": removed}


_DETECTED_LANGUAGE_RE = re.compile(r"auto-detected language:\s*(\w+)")


def parse_detected_language(stderr: str | None) -> str | None:
    """Extract whisper.cpp's 'auto-detected language: xx' log line, if present."""
    match = _DETECTED_LANGUAGE_RE.search(stderr or "")
    return match.group(1) if match else None


# --- Playback state (speak() runs ffplay in the background so tool calls return immediately) ---

_playback_lock = threading.Lock()
_PLAYBACK: dict[str, Any] = {
    "process": None,
    "text": "",
    "voice": "",
    "wav_path": None,
    "started_at": None,
}


def _playback_watcher(proc: subprocess.Popen, wav_path: Path) -> None:
    """Runs in a background thread; cleans up once ffplay exits on its own."""
    proc.wait()
    with _playback_lock:
        if _PLAYBACK.get("process") is proc:
            _PLAYBACK["process"] = None
            _PLAYBACK["wav_path"] = None
    wav_path.unlink(missing_ok=True)


def _stop_current_playback() -> bool:
    """Terminate any currently playing ffplay process and remove its temp WAV. Returns True if something was stopped."""
    with _playback_lock:
        proc = _PLAYBACK.get("process")
        wav_path = _PLAYBACK.get("wav_path")
        _PLAYBACK["process"] = None
        _PLAYBACK["wav_path"] = None

    if proc is None or proc.poll() is not None:
        return False

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

    if wav_path is not None:
        wav_path.unlink(missing_ok=True)

    return True


def _play_wav_async(wav_path: Path, text: str, voice_name: str) -> subprocess.Popen:
    """Launch ffplay in the background (no window, not waited on) and track it for get_status()/stop_playback()."""
    if not FFPLAY.is_file():
        raise FileNotFoundError(
            f"ffplay.exe not found: {FFPLAY}. "
            f"Set 'ffplay_path' in {CONFIG_FILE} (see bin/ffmpeg/README.md for download info)."
        )

    startupinfo = None
    creationflags = 0

    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        [str(FFPLAY), "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "quiet", str(wav_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )

    with _playback_lock:
        _PLAYBACK["process"] = proc
        _PLAYBACK["text"] = text
        _PLAYBACK["voice"] = voice_name
        _PLAYBACK["wav_path"] = wav_path
        _PLAYBACK["started_at"] = time.time()

    threading.Thread(target=_playback_watcher, args=(proc, wav_path), daemon=True).start()
    return proc


atexit.register(_stop_current_playback)


mcp = MCPServer("Speech Tools")


@mcp.tool()
def transcribe_audio(
    path: str,
    language: str = "auto",
    translate: bool = False,
    timestamps: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Transcribe (or translate to English) an audio file using whisper.cpp.

    Args:
        path: Absolute or relative path to an audio file. Natively supported:
            .wav/.mp3/.ogg/.flac. Also accepted via automatic ffmpeg conversion:
            .aac/.m4a/.wma/.opus. Call list_supported_audio_formats() if unsure.
        language: The language actually SPOKEN in the audio (e.g. "en", "nl") —
            this is completely independent of the language the user is chatting
            in. Never guess this from the conversation language. Leave it as
            "auto" (the default) unless you already know for certain what
            language is spoken; forcing the wrong language causes whisper to
            hallucinate garbled text in that language instead of transcribing
            correctly. The response's "detected_language" field reports what
            was actually detected/used.
        translate: If true, translate the spoken content to English instead of transcribing it in its original language. Unrelated to what language you reply in.
        timestamps: If true, also return per-segment start/end timestamps (writes a temporary JSON file, then removes it).
        model: Optional model filename (relative to bin/whisper) or absolute path. Defaults to config's whisper_model.
    """
    audio = validate_audio_path(path)
    model_path = resolve_model_path(model)

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Whisper model not found: {model_path}. "
            f"Download a ggml model into {model_path.parent} (see bin/whisper/README.md)."
        )

    lang = language or CONFIG.get("default_language", "auto")

    converted_path: Path | None = None
    try:
        if audio.suffix.lower() in CONVERTIBLE_AUDIO_EXTS:
            converted_path = convert_to_wav(audio)
            whisper_input = converted_path
        else:
            whisper_input = audio

        if not timestamps:
            args = ["-m", str(model_path), "-f", str(whisper_input), "-l", lang, "-nt"]
            if translate:
                args.append("-tr")

            proc = run_whisper(args)

            return {
                "ok": proc.returncode == 0,
                "path": str(audio),
                "requested_language": lang,
                "detected_language": parse_detected_language(proc.stderr),
                "text": (proc.stdout or "").strip(),
                "return_code": proc.returncode,
                "stderr": (proc.stderr or "").strip() if proc.returncode != 0 else "",
            }

        # Timestamped segments require a JSON output file; whisper.cpp cannot stream JSON to stdout.
        prefix = make_temp_prefix(audio.stem)
        args = ["-m", str(model_path), "-f", str(whisper_input), "-l", lang, "-oj", "-of", str(prefix)]
        if translate:
            args.append("-tr")

        proc = run_whisper(args)
        json_path = prefix.with_suffix(".json")
        detected_language = parse_detected_language(proc.stderr)

        if proc.returncode != 0 or not json_path.is_file():
            return {
                "ok": False,
                "path": str(audio),
                "requested_language": lang,
                "detected_language": detected_language,
                "text": "",
                "segments": [],
                "return_code": proc.returncode,
                "stderr": (proc.stderr or "").strip(),
            }

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        finally:
            json_path.unlink(missing_ok=True)

        segments = [
            {
                "start_ms": seg.get("offsets", {}).get("from"),
                "end_ms": seg.get("offsets", {}).get("to"),
                "text": (seg.get("text") or "").strip(),
            }
            for seg in data.get("transcription", [])
        ]

        return {
            "ok": True,
            "path": str(audio),
            "requested_language": lang,
            "detected_language": detected_language,
            "text": " ".join(s["text"] for s in segments).strip(),
            "segments": segments,
            "return_code": proc.returncode,
            "stderr": "",
        }
    finally:
        if converted_path is not None:
            converted_path.unlink(missing_ok=True)


@mcp.tool()
def list_supported_audio_formats() -> dict[str, Any]:
    """
    List audio file extensions that transcribe_audio() accepts.

    "native" formats are decoded by whisper.cpp directly. "convert_via_ffmpeg"
    formats are transparently converted to a temporary WAV file with ffmpeg
    before transcription — this requires ffmpeg.exe to be present (see
    bin/ffmpeg/README.md). Any other extension is rejected.
    """
    return {
        "ok": True,
        "native": sorted(NATIVE_AUDIO_EXTS),
        "convert_via_ffmpeg": sorted(CONVERTIBLE_AUDIO_EXTS),
        "ffmpeg_available": FFMPEG.is_file(),
    }


@mcp.tool()
def list_whisper_models() -> dict[str, Any]:
    """List available whisper.cpp ggml model files in bin/whisper."""
    model_dir = WHISPER_CLI.parent
    models = sorted(p.name for p in model_dir.glob("ggml-*.bin")) if model_dir.is_dir() else []

    return {
        "ok": True,
        "model_dir": str(model_dir),
        "models": models,
        "default_model": CONFIG["whisper_model"],
    }


@mcp.tool()
def speak(
    text: str,
    voice: str | None = None,
    speaker: int | None = None,
    length_scale: float | None = None,
    interrupt: bool = True,
    wait: bool = False,
) -> dict[str, Any]:
    """
    Synthesize text with Piper and play it out loud on the default audio device.

    Synthesis happens first (usually well under a second), then playback
    starts in the background via ffplay — this call returns right after
    playback *starts*, it does NOT wait for the audio to finish (unless
    wait=True). Use get_status() to poll whether it's still playing, and
    stop_playback() to cut it off early.

    Args:
        text: Text to speak out loud. Pass a short, natural spoken summary —
            never raw code, JSON, file paths, tables, stack traces or long
            logs; for a long written answer, speak a 1-3 sentence summary
            of it instead of the whole thing.
        voice: Optional Piper voice filename (.onnx, relative to bin/piper) or absolute path. Defaults to config's piper_model. Call list_voices() to see what's installed.
        speaker: Optional speaker id, for multi-speaker voice models (default: 0).
        length_scale: Optional speech speed multiplier (>1 slower, <1 faster). Piper's own default is 1.0.
        interrupt: If true (default), stop any audio already playing before speaking this text. If false, this call fails while something else is still playing.
        wait: If true, block until playback finishes instead of returning immediately after it starts.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    voice_path = require_voice_files(resolve_voice_path(voice))

    if interrupt:
        _stop_current_playback()
    elif _PLAYBACK.get("process") is not None and _PLAYBACK["process"].poll() is None:
        return {"ok": False, "status": "busy", "text": text, "message": "Audio is already playing; pass interrupt=True or wait for it to finish."}

    out_wav = make_temp_prefix("speak").with_suffix(".wav")
    proc = synthesize_wav(text, voice_path, out_wav, speaker=speaker, length_scale=length_scale)

    if proc.returncode != 0 or not out_wav.is_file():
        out_wav.unlink(missing_ok=True)
        return {
            "ok": False,
            "status": "error",
            "text": text,
            "return_code": proc.returncode,
            "stderr": (proc.stderr or "").strip(),
        }

    playback = _play_wav_async(out_wav, text, voice_path.name)

    if wait:
        playback.wait()
        return {"ok": True, "status": "done", "text": text, "voice": voice_path.name}

    return {"ok": True, "status": "playing", "text": text, "voice": voice_path.name}


@mcp.tool()
def synthesize_to_file(
    text: str,
    output_path: str | None = None,
    voice: str | None = None,
    speaker: int | None = None,
    length_scale: float | None = None,
) -> dict[str, Any]:
    """
    Synthesize text to a WAV file with Piper, without playing it.

    Args:
        text: Text to synthesize.
        output_path: Where to save the WAV file. If omitted, a file is created under temp_dir (still subject to cleanup_stale_after_seconds — pass an explicit path for anything you want to keep).
        voice: Optional Piper voice filename (.onnx, relative to bin/piper) or absolute path. Defaults to config's piper_model.
        speaker: Optional speaker id, for multi-speaker voice models (default: 0).
        length_scale: Optional speech speed multiplier (>1 slower, <1 faster). Piper's own default is 1.0.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    voice_path = require_voice_files(resolve_voice_path(voice))

    if output_path:
        out_wav = Path(output_path).expanduser().resolve()
        out_wav.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_wav = make_temp_prefix("tts").with_suffix(".wav")

    proc = synthesize_wav(text, voice_path, out_wav, speaker=speaker, length_scale=length_scale)

    return {
        "ok": proc.returncode == 0 and out_wav.is_file(),
        "path": str(out_wav),
        "voice": voice_path.name,
        "return_code": proc.returncode,
        "stderr": (proc.stderr or "").strip() if proc.returncode != 0 else "",
    }


@mcp.tool()
def list_voices() -> dict[str, Any]:
    """List available Piper voice models (.onnx) in bin/piper, and whether each has its required .onnx.json config."""
    voice_dir = PIPER.parent
    voices = []

    if voice_dir.is_dir():
        for onnx in sorted(voice_dir.glob("*.onnx")):
            voices.append({
                "name": onnx.name,
                "has_config": Path(str(onnx) + ".json").is_file(),
            })

    return {
        "ok": True,
        "voice_dir": str(voice_dir),
        "voices": voices,
        "default_voice": CONFIG["piper_model"],
    }


@mcp.tool()
def stop_playback() -> dict[str, Any]:
    """Stop any audio currently being spoken via speak(), if any."""
    return {"ok": True, "stopped": _stop_current_playback()}


@mcp.tool()
def get_status() -> dict[str, Any]:
    """Check whether audio started by speak() is currently playing."""
    with _playback_lock:
        proc = _PLAYBACK.get("process")
        text = _PLAYBACK.get("text", "")
        voice = _PLAYBACK.get("voice", "")
        started_at = _PLAYBACK.get("started_at")

    playing = proc is not None and proc.poll() is None

    return {
        "ok": True,
        "playing": playing,
        "text": text if playing else "",
        "voice": voice if playing else "",
        "elapsed_seconds": round(time.time() - started_at, 1) if playing and started_at else None,
    }


@mcp.tool()
def cleanup_temp() -> dict[str, Any]:
    """Remove temporary files (converted/synthesized WAV, timestamp JSON) manually."""
    return cleanup_stale_outputs()


if __name__ == "__main__":
    # Remove leftovers from old sessions before starting.
    cleanup_stale_outputs()
    # stdio is the normal transport when Goose/Claude starts this script as an extension.
    mcp.run()
