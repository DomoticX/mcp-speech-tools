#!/usr/bin/env python3
"""
mcp-speech-tools.py
MCP server for local Text-To-Speech (TTS) and Speech-To-Text (STT).

STT is implemented via whisper.cpp's whisper-cli.exe (Vulkan build).
TTS is not implemented yet.

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
        temp\\
"""

from __future__ import annotations

import json
import re
import subprocess
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
    "whisper_output_dir": str(BASE_DIR / "temp"),
    "default_language": "auto",
    "command_timeout_seconds": 600,
    "cleanup_stale_after_seconds": 3600,
}

# Natively decoded by whisper.cpp (via miniaudio) — no ffmpeg conversion step exists yet.
# AAC/M4A/WMA/Opus/etc. are NOT supported; convert to one of these first.
SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac"}


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


def resolve_model_path(model: str | None) -> Path:
    """Resolve a model filename against the whisper-cli.exe folder, unless already absolute."""
    name = model or CONFIG["whisper_model"]
    p = Path(name).expanduser()
    if not p.is_absolute():
        p = WHISPER_CLI.parent / name
    return p


def run_whisper(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run whisper-cli.exe without opening a console window on Windows."""
    if not WHISPER_CLI.is_file():
        raise FileNotFoundError(
            f"whisper-cli.exe not found: {WHISPER_CLI}. "
            f"Set 'whisper_path' in {CONFIG_FILE} (see bin/whisper/README.md for download info)."
        )

    timeout = timeout or int(CONFIG["command_timeout_seconds"])

    startupinfo = None
    creationflags = 0

    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        creationflags = subprocess.CREATE_NO_WINDOW

    return subprocess.run(
        [str(WHISPER_CLI), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        startupinfo=startupinfo,
        creationflags=creationflags,
        check=False,
    )


def validate_audio_path(path: str) -> Path:
    p = Path(path).expanduser().resolve()

    if not p.exists():
        raise FileNotFoundError(f"Audio file does not exist: {p}")
    if not p.is_file():
        raise ValueError(f"Path is not a file: {p}")
    if p.suffix.lower() not in SUPPORTED_AUDIO_EXTS:
        raise ValueError(
            f"Unsupported audio format '{p.suffix}'. Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTS))}"
        )

    return p


def make_output_prefix(audio: Path) -> Path:
    """Unique temp-file prefix (without extension) for -of, used by JSON/timestamp output."""
    root = Path(CONFIG["whisper_output_dir"]).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    safe_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", audio.stem).strip(" .") or "audio"
    return root / f"{safe_stem}_{int(time.time() * 1000)}"


def cleanup_stale_outputs() -> dict[str, Any]:
    """Remove leftover temp output files older than cleanup_stale_after_seconds."""
    root = Path(CONFIG["whisper_output_dir"]).expanduser()
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
        path: Absolute or relative path to a .wav/.mp3/.ogg/.flac file.
            Call list_supported_audio_formats() to check first if unsure.
        language: Spoken language code (e.g. "en", "nl"), or "auto" to detect.
        translate: If true, translate the result to English instead of transcribing in the source language.
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

    if not timestamps:
        args = ["-m", str(model_path), "-f", str(audio), "-l", lang, "-nt", "-np"]
        if translate:
            args.append("-tr")

        proc = run_whisper(args)

        return {
            "ok": proc.returncode == 0,
            "path": str(audio),
            "language": lang,
            "text": (proc.stdout or "").strip(),
            "return_code": proc.returncode,
            "stderr": (proc.stderr or "").strip() if proc.returncode != 0 else "",
        }

    # Timestamped segments require a JSON output file; whisper.cpp cannot stream JSON to stdout.
    prefix = make_output_prefix(audio)
    args = ["-m", str(model_path), "-f", str(audio), "-l", lang, "-np", "-oj", "-of", str(prefix)]
    if translate:
        args.append("-tr")

    proc = run_whisper(args)
    json_path = prefix.with_suffix(".json")

    if proc.returncode != 0 or not json_path.is_file():
        return {
            "ok": False,
            "path": str(audio),
            "language": lang,
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
        "language": lang,
        "text": " ".join(s["text"] for s in segments).strip(),
        "segments": segments,
        "return_code": proc.returncode,
        "stderr": "",
    }


@mcp.tool()
def list_supported_audio_formats() -> dict[str, Any]:
    """
    List audio file extensions that transcribe_audio() accepts.

    These are natively decoded by whisper.cpp; there is no ffmpeg conversion
    step, so formats like AAC/M4A/WMA/Opus are NOT supported and must be
    converted to one of the listed formats first.
    """
    return {
        "ok": True,
        "supported_extensions": sorted(SUPPORTED_AUDIO_EXTS),
        "note": "Natively decoded by whisper.cpp only; no automatic conversion for other formats (e.g. AAC/M4A/WMA/Opus).",
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
def cleanup_temp() -> dict[str, Any]:
    """Remove temporary whisper output files (e.g. leftover JSON) manually."""
    return cleanup_stale_outputs()


if __name__ == "__main__":
    # Remove leftovers from old sessions before starting.
    cleanup_stale_outputs()
    # stdio is the normal transport when Goose/Claude starts this script as an extension.
    mcp.run()
