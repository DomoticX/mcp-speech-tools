# bin/ffmpeg

This folder is where the ffmpeg Windows binaries go, used by
`mcp-speech-tools.py` to convert audio formats that whisper.cpp can't read
natively (AAC, M4A, WMA, Opus) to WAV before transcription. Binaries are
not committed to the repository (see `.gitignore`) — download them
yourself.

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

- `ffmpeg.exe` — the only binary actually invoked by the MCP server.
  `ffplay.exe` / `ffprobe.exe` are not used but harmless to leave in place.

## What it's used for

`transcribe_audio()` in `mcp-speech-tools.py` calls `ffmpeg.exe` only for
audio files whisper.cpp cannot decode itself (`.aac`, `.m4a`, `.wma`,
`.opus`). It converts them to a temporary 16kHz mono PCM WAV file in
`temp/`, runs whisper-cli.exe against that, then deletes the temporary
WAV. Natively supported formats (`.wav`, `.mp3`, `.ogg`, `.flac`) go
straight to whisper-cli.exe — ffmpeg is skipped entirely for those.
