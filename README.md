# mcp-speech-tools

MCP server for local Text-To-Speech (TTS) and Speech-To-Text (STT).

- STT via [whisper.cpp](https://github.com/ggml-org/whisper.cpp)'s
  `whisper-cli.exe` (Vulkan-accelerated Windows build).
- TTS via [Piper](https://github.com/rhasspy/piper)'s `piper.exe`, played
  back through ffmpeg's `ffplay.exe` on the default audio device.

## How it works

**STT** — `transcribe_audio` runs `whisper-cli.exe` against a local audio file:

- By default it captures the plain transcription straight from stdout
  (`-nt`) — fast, no temp files involved.
- With `timestamps=True` it instead asks whisper.cpp for a JSON file
  (`-oj -of <temp prefix>`), since whisper.cpp can't stream structured
  output to stdout. The JSON is read back into per-segment
  start/end/text data and the temp file is deleted immediately after.
- If the input file isn't a format whisper.cpp can read natively
  (`.aac`/`.m4a`/`.wma`/`.opus`, or a video container like `.mp4`), it's
  first converted to a temporary 16kHz mono PCM WAV with `ffmpeg.exe`,
  then transcribed, then the temporary WAV is deleted.
- `offset_seconds`/`duration_seconds` let you transcribe just part of a
  file ("the first 20 seconds", "starting at 0:30") using whisper.cpp's
  own windowing — no separate cutting step, no extra files.

**TTS** — `speak` sends text to `piper.exe` on stdin, which synthesizes a
temporary WAV file; that WAV is then played through `ffplay.exe`
(`-nodisp -autoexit`, no visible window) in the **background**. The tool
call returns as soon as playback *starts*, not when it finishes, so a long
spoken response doesn't block the MCP connection — poll `get_status()` or
pass `wait=True` if you need to know when it's done. The temp WAV is
deleted automatically once playback ends. `synthesize_to_file` does the
same synthesis step without playing anything, for when you just want the
audio file.

## Requirements

- Python 3.10+
- [`mcp`](https://pypi.org/project/mcp/) Python SDK:

  ```bash
  pip install mcp
  ```
- `whisper-cli.exe` + a `ggml-*.bin` model — see
  [bin/whisper/README.md](bin/whisper/README.md) for download instructions.
- `ffmpeg.exe` + `ffplay.exe` — ffmpeg only needed to transcribe
  AAC/M4A/WMA/Opus/video files, ffplay needed for `speak()` playback. See
  [bin/ffmpeg/README.md](bin/ffmpeg/README.md) for download instructions.
- `piper.exe` + a voice (`.onnx` + `.onnx.json`) — see
  [bin/piper/README.md](bin/piper/README.md) for download instructions.

## Directory layout

```
mcp-speech-tools/
├── mcp-speech-tools.py   # server entry point
├── config.json            # runtime configuration
├── bin/
│   ├── whisper/             # whisper.cpp binaries + models (not committed, see bin/whisper/README.md)
│   │   ├── whisper-cli.exe
│   │   └── ggml-base.bin
│   ├── ffmpeg/              # ffmpeg binaries, for STT conversion + TTS playback (not committed, see bin/ffmpeg/README.md)
│   │   ├── ffmpeg.exe
│   │   └── ffplay.exe
│   └── piper/               # Piper binary + voice models (not committed, see bin/piper/README.md)
│       ├── piper.exe
│       ├── <voice>.onnx
│       └── <voice>.onnx.json
└── temp/                    # scratch space: converted/synthesized WAV, timestamp JSON
```

## Configuration

Settings are read from [config.json](config.json) at startup, falling back
to built-in defaults for any key that's missing:

| Key | Default | Description |
| --- | --- | --- |
| `whisper_path` | `bin/whisper/whisper-cli.exe` | Path to the whisper.cpp CLI binary |
| `whisper_model` | `ggml-base.bin` | Default STT model filename, resolved relative to `whisper_path`'s folder |
| `ffmpeg_path` | `bin/ffmpeg/ffmpeg.exe` | Path to ffmpeg, used to convert AAC/M4A/WMA/Opus to WAV before transcription |
| `piper_path` | `bin/piper/piper.exe` | Path to the Piper CLI binary |
| `piper_model` | `jarvis-high.onnx` | Default TTS voice filename, resolved relative to `piper_path`'s folder |
| `ffplay_path` | `bin/ffmpeg/ffplay.exe` | Path to ffplay, used to play back synthesized speech |
| `temp_dir` | `temp/` | Scratch directory for converted/synthesized WAV and timestamp JSON |
| `default_language` | `auto` | STT spoken language used when a call doesn't specify one |
| `command_timeout_seconds` | `600` | Timeout for each `whisper-cli.exe` / `ffmpeg.exe` / `piper.exe` invocation |
| `cleanup_stale_after_seconds` | `3600` | Age (seconds) after which leftover temp files are removed on startup / via `cleanup_temp()` |

**Note:** `whisper_path`, `ffmpeg_path`, `piper_path`, `ffplay_path` and
`temp_dir` in `config.json` must point at paths that actually exist on
your machine — update them if you move or rename this project folder.

## MCP tools

### Speech-to-text

| Tool | Description |
| --- | --- |
| `transcribe_audio(path, language="auto", translate=False, timestamps=False, model=None, offset_seconds=None, duration_seconds=None)` | Transcribes (or translates to English) an audio/video file, optionally windowed to part of it |
| `list_supported_audio_formats()` | Lists native vs. ffmpeg-converted audio/video extensions |
| `list_whisper_models()` | Lists `ggml-*.bin` models found in `bin/whisper` |

**Note on `language`:** this is the language *spoken in the audio*, not the
language of the chat/request. Leave it as `"auto"` unless you know for
certain what's spoken — forcing the wrong language makes whisper
hallucinate fluent-sounding but completely wrong text in that language
instead of failing loudly. `transcribe_audio()`'s response includes both
`requested_language` (what was passed in) and `detected_language` (what
whisper.cpp actually auto-detected, when `language="auto"`), so a mismatch
is easy to spot.

**Note on `offset_seconds`/`duration_seconds`:** use these for "transcribe
the first 20 seconds" / "starting at 0:30" instead of pre-cutting the file
yourself with an external ffmpeg call — whisper.cpp windows the audio
natively (`-ot`/`-d`). Pre-cutting it yourself creates stray WAV files next
to the source file instead of in this server's `temp_dir`, which this tool
is specifically designed to avoid.

**Supported formats:**

- Native (whisper.cpp / miniaudio): `.wav`, `.mp3`, `.ogg`, `.flac`
- Converted via ffmpeg first: `.aac`, `.m4a`, `.wma`, `.opus`, and video
  containers `.mp4`, `.mkv`, `.mov`, `.webm`, `.avi` (audio track only)

Anything else is rejected. Conversion requires `ffmpeg.exe` to be present
(see [bin/ffmpeg/README.md](bin/ffmpeg/README.md)); if it's missing,
transcribing one of the converted formats fails with a clear error
pointing to that README.

### Text-to-speech

| Tool | Description |
| --- | --- |
| `speak(text, voice=None, speaker=None, length_scale=None, interrupt=True, wait=False)` | Synthesizes text and plays it out loud in the background; returns as soon as playback starts |
| `synthesize_to_file(text, output_path=None, voice=None, speaker=None, length_scale=None)` | Synthesizes text to a WAV file without playing it |
| `list_voices()` | Lists installed Piper voices (`.onnx`) in `bin/piper`, and whether each has its required `.onnx.json` config |
| `stop_playback()` | Stops whatever `speak()` is currently playing |
| `get_status()` | Reports whether audio is currently playing, and what text/voice |

**On `speak()` blocking:** a normal MCP tool call is request/response, so
if `speak()` waited for the full audio to finish playing, a long response
would freeze that connection for as long as it takes to read it aloud.
Instead, `speak()` only blocks for synthesis (fast) and returns
`{"status": "playing"}` right after starting playback in the background.
Only one voice channel is tracked at a time: by default a new `speak()`
call stops whatever was already playing (`interrupt=True`); pass
`interrupt=False` to instead fail with `{"status": "busy"}` while
something is still playing.

**Text going into `speak()` should be a short spoken summary, not the full
written answer** — skip code blocks, JSON, file paths, tables and logs.
See "Agent speech behavior" below for how to wire this up automatically.

## Agent speech behavior

The MCP server only exposes the `speak` *capability* — on its own, a model
will only call it when it happens to decide to. Making an agent
consistently *say* its answers out loud is a prompt/instruction concern,
kept deliberately separate from this server: the MCP stays a plain
technical capability, the *when/how* lives in the agent's instructions.

[.claude/skills/speak-replies/SKILL.md](.claude/skills/speak-replies/SKILL.md)
is a ready-made skill for this, in the generic `name` + `description` +
Markdown-instructions format used by both Claude Code and Goose skill
folders (no slash-command syntax — it triggers off its `description`
matching what the user asks for, same as this repo's own skills). Copy
`speak-replies/` into wherever your agent loads skills from — e.g.
Claude Code's `.claude/skills/` (project) or `~/.claude/skills/`
(global), or Goose's `~/.agents/skills/` (or wherever your setup points
Goose at) — and it activates automatically when the user asks for spoken
replies in plain language ("spreek je antwoorden uit", "turn on spoken
replies", "read that aloud", ...), and turns off again when asked to stop.

It's a per-conversation instruction (resets on a new session), and
composes the spoken text following the same rules as above: short,
natural, plain language, no code/JSON/paths/tables/logs.

## Running

The server communicates over stdio, the standard transport when started as
an MCP extension (e.g. by Goose or Claude Desktop):

```bash
python mcp-speech-tools.py
```
