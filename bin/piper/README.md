# bin/piper

This folder is where the [Piper](https://github.com/rhasspy/piper) TTS
binaries and voice models go, used by `mcp-speech-tools.py` for
text-to-speech. Binaries and voices are not committed to the repository
(see `.gitignore`) — download them yourself.

## Download

- https://sourceforge.net/projects/piper-tts.mirror/files/2023.11.14-2/piper_windows_amd64.zip/download

Download `piper_windows_amd64.zip` and extract it.

## Extracting

The zip contains a `piper/` folder. Copy its **contents** directly into
this folder (`bin/piper/`, the same folder this README is in), so you end
up with e.g.:

```
bin/piper/
├── piper.exe                       # required — used by mcp-speech-tools.py
├── piper_phonemize.dll
├── onnxruntime.dll
├── onnxruntime_providers_shared.dll
├── espeak-ng.dll
├── libtashkeel_model.ort
├── espeak-ng-data/                  # required — phoneme data, referenced automatically
├── <voice>.onnx                     # a voice model, see below
├── <voice>.onnx.json                # its matching config, see below
└── README.md                        # this file
```

## Voices

Piper voices come in **pairs**: a `.onnx` model file and a `.onnx.json`
config file with the same base name (e.g. `jarvis-high.onnx` +
`jarvis-high.onnx.json`). Both must sit directly in this folder — Piper
looks for the config next to the model by default, and
`mcp-speech-tools.py` checks for both before synthesizing.

Voices can be found at:

- https://github.com/rhasspy/piper/blob/master/VOICES.md
- https://huggingface.co/rhasspy/piper-voices

The default voice configured in `config.json` (`piper_model`) is:

```
jarvis-high.onnx
```

Download whatever voice(s) you like (any language/quality tier) and drop
both files here. Call `list_voices()` to see what's installed and whether
each voice's config file was found; pass a different `voice` filename per
call to `speak()` / `synthesize_to_file()`, or change the default in
`config.json`.

## Example CLI usage (for manual testing)

Piper reads the text to speak from stdin:

```
echo This is a test. | piper.exe -m jarvis-high.onnx -f out.wav
```
