# bin/ffmpeg

This folder is where the ffmpeg Windows binaries go, used by
`mcp-speech-tools.py` for two things:

- `ffmpeg.exe` converts audio formats whisper.cpp can't read natively
  (AAC, M4A, WMA, Opus) to WAV before transcription.
- `ffplay.exe` plays Piper's synthesized WAV output out loud on the
  default audio device for `speak()`.

Binaries are not committed to the repository (see `.gitignore`) —
download them yourself.

## Download

- https://www.gyan.dev/ffmpeg/builds/

Download the "essentials" build zip:

```
ffmpeg-release-essentials.7z
```

(Direct link on that page under "release builds".)

## Extracting

1. Download and extract `ffmpeg-release-essentials.7z` (7-Zip or similar).
2. It contains a folder like `ffmpeg-<version>-essentials_build/`, with a
   `bin/` subfolder inside it.
3. Copy the **contents of that inner `bin/` folder** directly into this
   folder (`bin/ffmpeg/`, the same folder this README is in), so you end
   up with e.g.:

```
bin/ffmpeg/
├── ffmpeg.exe    # required — used by mcp-speech-tools.py for conversion
├── ffplay.exe
├── ffprobe.exe
└── README.md     # this file
```

## Required files

- `ffmpeg.exe` — used for AAC/M4A/WMA/Opus → WAV conversion before STT.
- `ffplay.exe` — used to play back Piper's synthesized WAV for `speak()`.
- `ffprobe.exe` is not used but harmless to leave in place.

## What it's used for

`transcribe_audio()` in `mcp-speech-tools.py` calls `ffmpeg.exe` only for
audio files whisper.cpp cannot decode itself (`.aac`, `.m4a`, `.wma`,
`.opus`). It converts them to a temporary 16kHz mono PCM WAV file in
`temp/`, runs whisper-cli.exe against that, then deletes the temporary
WAV. Natively supported formats (`.wav`, `.mp3`, `.ogg`, `.flac`) go
straight to whisper-cli.exe — ffmpeg is skipped entirely for those.

`speak()` calls `ffplay.exe` (`-nodisp -autoexit`, no visible window) on
the WAV file Piper just synthesized, on the default audio output device.
Playback runs in the background so the tool call returns as soon as
playback starts, not when it finishes.
