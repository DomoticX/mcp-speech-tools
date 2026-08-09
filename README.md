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

## Requirements

- Python 3.10+
- [`mcp`](https://pypi.org/project/mcp/) Python SDK:

  ```bash
  pip install mcp
  ```
- `whisper-cli.exe` + a `ggml-*.bin` model — see
  [bin/whisper/README.md](bin/whisper/README.md) for download instructions.

## Directory layout

```
mcp-speech-tools/
├── mcp-speech-tools.py   # server entry point
├── config.json            # runtime configuration
├── bin/
│   └── whisper/            # whisper.cpp binaries + models (not committed, see bin/whisper/README.md)
│       ├── whisper-cli.exe
│       └── ggml-base.bin
└── temp/                    # temporary JSON output for timestamped transcriptions
```

## Configuration

Settings are read from [config.json](config.json) at startup, falling back
to built-in defaults for any key that's missing:

| Key | Default | Description |
| --- | --- | --- |
| `whisper_path` | `bin/whisper/whisper-cli.exe` | Path to the whisper.cpp CLI binary |
| `whisper_model` | `ggml-base.bin` | Default model filename, resolved relative to `whisper_path`'s folder |
| `whisper_output_dir` | `temp/` | Where temporary JSON output is written when `timestamps=True` |
| `default_language` | `auto` | Spoken language used when a call doesn't specify one |
| `command_timeout_seconds` | `600` | Timeout for each `whisper-cli.exe` invocation |
| `cleanup_stale_after_seconds` | `3600` | Age (seconds) after which leftover temp files are removed on startup / via `cleanup_temp()` |

**Note:** `whisper_path` and `whisper_output_dir` in `config.json` must
point at paths that actually exist on your machine — update them if you
move or rename this project folder.

## MCP tools

| Tool | Description |
| --- | --- |
| `transcribe_audio(path, language="auto", translate=False, timestamps=False, model=None)` | Transcribes (or translates to English) a `.wav`/`.mp3`/`.ogg`/`.flac` file |
| `list_supported_audio_formats()` | Lists the accepted audio extensions |
| `list_whisper_models()` | Lists `ggml-*.bin` models found in `bin/whisper` |
| `cleanup_temp()` | Manually removes stale temporary JSON output |

**Supported formats:** `.wav`, `.mp3`, `.ogg`, `.flac` — these are the only
formats whisper.cpp can decode natively (via miniaudio). **AAC/M4A/WMA/Opus
are not supported** and there's currently no ffmpeg conversion step to
handle them; convert those to one of the supported formats first.

## Running

The server communicates over stdio, the standard transport when started as
an MCP extension (e.g. by Goose or Claude Desktop):

```bash
python mcp-speech-tools.py
```
