# Temporary files are stored here

Only used when `transcribe_audio(..., timestamps=True)` is called — whisper.cpp
writes a JSON output file here, which the server reads back and then deletes.
Plain transcriptions (`timestamps=False`, the default) never touch this folder;
they're read straight from `whisper-cli.exe`'s stdout.

Anything left behind (e.g. after a crash) is cleaned up automatically on
server startup and via the `cleanup_temp()` tool, based on
`cleanup_stale_after_seconds` in `config.json`.
