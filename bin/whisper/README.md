# bin/whisper

This folder is where the whisper.cpp Windows binaries and ggml models go for
STT support in `mcp-speech-tools.py`. Binaries are not committed to the
repository (see `.gitignore`) — download them yourself.

## Download

Prebuilt Windows binaries (with Vulkan GPU support) are distributed via:

- https://github.com/DomoticX/whisper.cpp-windows-vulkan

Download the latest release zip and extract it.

## Required files

Copy the **contents** of the release zip directly into this folder
(`bin/whisper/`, the same folder this README is in), so you end up with e.g.:

```
bin/whisper/
├── whisper-cli.exe      # required — main STT executable, used by mcp-speech-tools.py
├── whisper.dll
├── ggml.dll
├── ggml-base.dll
├── ggml-cpu.dll
├── ggml-vulkan.dll
├── whisper-bench.exe
├── whisper-quantize.exe
├── whisper-server.exe
├── whisper-vad-speech-segments.exe
├── main.exe
├── bench.exe
├── test-vad.exe
├── test-vad-full.exe
└── README.md            # this file
```

Only `whisper-cli.exe` (plus its DLLs) is actually used by the MCP server;
the other `.exe` tools are extra utilities from the whisper.cpp project and
can be left in place or removed.

## Models

Download one or more `ggml-*.bin` models and place them **directly in this
folder** (`bin/whisper/`), next to `whisper-cli.exe`. Model download links
and details: https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md

The default model configured in `config.json` (`whisper_model`) is:

```
ggml-base.bin
```

Larger models (e.g. `ggml-large-v3.bin`) give better accuracy at the cost of
speed and VRAM; you can pass a different `model` filename per call to the
`transcribe_audio` tool, or change the default in `config.json`.

## Example CLI usage (for manual testing)

```
whisper-cli.exe -m ggml-base.bin -f file-to-stt.wav
```
