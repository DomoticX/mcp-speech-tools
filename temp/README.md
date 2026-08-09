# Temporary files are stored here

Shared scratch space for both STT and TTS:

- STT: `transcribe_audio(..., timestamps=True)` writes a JSON output file
  here, which the server reads back and then deletes. Converting
  AAC/M4A/WMA/Opus to WAV before transcription also happens here, and that
  WAV is deleted right after use. Plain transcriptions (`timestamps=False`)
  never touch this folder — they're read straight from `whisper-cli.exe`'s
  stdout.
- TTS: `speak()` synthesizes here before playback and deletes the WAV once
  playback finishes. `synthesize_to_file()` also writes here when called
  without an explicit `output_path` (pass one if you want to keep the file).

Anything left behind (e.g. after a crash) is cleaned up automatically on
server startup and via the `cleanup_temp()` tool, based on
`cleanup_stale_after_seconds` in `config.json`.
