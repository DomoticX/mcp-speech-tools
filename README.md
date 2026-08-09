# mcp-speech-tools

MCP server for local Text-To-Speech (TTS) and Speech-To-Text (STT).

STT is implemented via [whisper.cpp](https://github.com/ggml-org/whisper.cpp)'s
`whisper-cli.exe` (Vulkan-accelerated Windows build). TTS is not implemented
yet.

## How it works

`transcribe_audio` runs `whisper-cli.exe` against a local audio file:

- By default it captures the plain transcription straight from stdout
  (`-nt -np`) — fast, no temp files involved.
- With `timestamps=True` it instead asks whisper.cpp for a JSON file
  (`-oj -of <temp prefix>`), since whisper.cpp can't stream structured
  output to stdout. The JSON is read back into per-segment
  start/end/text data and the temp file is deleted immediately after.
- If the input file isn't a format whisper.cpp can read natively
  (`.aac`/`.m4a`/`.wma`/`.opus`), it's first converted to a temporary
  16kHz mono PCM WAV with `ffmpeg.exe`, then transcribed, then the
  temporary WAV is deleted.

## Requirements

- Python 3.10+
- [`mcp`](https://pypi.org/project/mcp/) Python SDK:

  ```bash
  pip install mcp
  ```
- `whisper-cli.exe` + a `ggml-*.bin` model — see
  [bin/whisper/README.md](bin/whisper/README.md) for download instructions.
- `ffmpeg.exe` — only needed to transcribe AAC/M4A/WMA/Opus files, see
  [bin/ffmpeg/README.md](bin/ffmpeg/README.md) for download instructions.

## Directory layout

```
mcp-speech-tools/
├── mcp-speech-tools.py   # server entry point
├── config.json            # runtime configuration
├── bin/
│   ├── whisper/             # whisper.cpp binaries + models (not committed, see bin/whisper/README.md)
│   │   ├── whisper-cli.exe
│   │   └── ggml-base.bin
│   └── ffmpeg/              # ffmpeg binary, for AAC/M4A/WMA/Opus conversion (not committed, see bin/ffmpeg/README.md)
│       └── ffmpeg.exe
└── temp/                    # temporary WAV/JSON output for conversion and timestamped transcriptions
```

## Configuration

Settings are read from [config.json](config.json) at startup, falling back
to built-in defaults for any key that's missing:

| Key | Default | Description |
| --- | --- | --- |
| `whisper_path` | `bin/whisper/whisper-cli.exe` | Path to the whisper.cpp CLI binary |
| `whisper_model` | `ggml-base.bin` | Default model filename, resolved relative to `whisper_path`'s folder |
| `whisper_output_dir` | `temp/` | Where temporary WAV (converted audio) and JSON (timestamped) output is written |
| `ffmpeg_path` | `bin/ffmpeg/ffmpeg.exe` | Path to ffmpeg, used only to convert AAC/M4A/WMA/Opus to WAV before transcription |
| `default_language` | `auto` | Spoken language used when a call doesn't specify one |
| `command_timeout_seconds` | `600` | Timeout for each `whisper-cli.exe` / `ffmpeg.exe` invocation |
| `cleanup_stale_after_seconds` | `3600` | Age (seconds) after which leftover temp files are removed on startup / via `cleanup_temp()` |

**Note:** `whisper_path`, `ffmpeg_path` and `whisper_output_dir` in
`config.json` must point at paths that actually exist on your machine —
update them if you move or rename this project folder.

## MCP tools

| Tool | Description |
| --- | --- |
| `transcribe_audio(path, language="auto", translate=False, timestamps=False, model=None)` | Transcribes (or translates to English) an audio file |
| `list_supported_audio_formats()` | Lists native vs. ffmpeg-converted audio extensions |
| `list_whisper_models()` | Lists `ggml-*.bin` models found in `bin/whisper` |
| `cleanup_temp()` | Manually removes stale temporary WAV/JSON output |

**Note on `language`:** this is the language *spoken in the audio*, not the
language of the chat/request. Leave it as `"auto"` unless you know for
certain what's spoken — forcing the wrong language makes whisper
hallucinate fluent-sounding but completely wrong text in that language
instead of failing loudly. `transcribe_audio()`'s response includes both
`requested_language` (what was passed in) and `detected_language` (what
whisper.cpp actually auto-detected, when `language="auto"`), so a mismatch
is easy to spot.

**Supported formats:**

- Native (whisper.cpp / miniaudio): `.wav`, `.mp3`, `.ogg`, `.flac`
- Converted via ffmpeg first: `.aac`, `.m4a`, `.wma`, `.opus`

Anything else is rejected. Conversion requires `ffmpeg.exe` to be present
(see [bin/ffmpeg/README.md](bin/ffmpeg/README.md)); if it's missing,
transcribing an AAC/M4A/WMA/Opus file fails with a clear error pointing to
that README.

## Running

The server communicates over stdio, the standard transport when started as
an MCP extension (e.g. by Goose or Claude Desktop):

```bash
python mcp-speech-tools.py
```
