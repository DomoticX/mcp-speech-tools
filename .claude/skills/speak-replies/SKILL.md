---
name: speak-replies
description: Turn spoken replies on or off for the rest of the conversation, using the `speak` tool from the mcp-speech-tools MCP server (Piper TTS). Use when the user asks Claude to talk out loud, read answers aloud, enable voice/audio replies, or stop/mute spoken replies. Not for one-off "read this file aloud" requests — use the `speak` tool directly for those.
user-invocable: true
---

# /speak-replies — spoken replies via mcp-speech-tools

Arguments passed: `$ARGUMENTS` — one of `summary` (default), `all`, or `off`.

This skill does not itself produce a reply. It sets a standing behavior
for the rest of this conversation: after every subsequent user-facing
response, call the `speak` tool from the `mcp-speech-tools` MCP server.
Keep doing this on every turn until the user turns it off (`/speak-replies
off`, or asks in plain language to stop/be quiet/mute).

If the `mcp-speech-tools` MCP server or its `speak` tool isn't available,
say so and stop — don't guess at another way to produce audio.

## Modes

- **`summary`** (default, `/speak-replies` or `/speak-replies summary`):
  write the normal, complete response first. Then compose a short spoken
  version specifically for `speak`, and send only that to the tool.
- **`all`** (`/speak-replies all`): speak the substance of the full
  response, not just a summary — but still never verbatim-read code,
  JSON, tables, or paths (see exclusions below); rephrase those parts in
  words or skip them, rather than skipping the whole response.
- **`off`** (`/speak-replies off`): stop calling `speak` for future
  responses. Confirm it's off; don't speak this confirmation.

## Composing the spoken text (all modes)

- Contain the main conclusion, answer, or next step.
- Be concise and natural when spoken aloud — normally 1-3 sentences in
  `summary` mode.
- Use plain conversational language, as if explaining it to someone out
  loud, not reading a document.
- Preserve important warnings or actions the user needs to take.
- Never include: code blocks, raw JSON, file paths, URLs, long logs,
  stack traces, tables, or other low-level technical detail. If the
  answer is mostly that kind of content, speak a plain-language
  description of what happened instead of the content itself (e.g. "the
  fix updates the config file and adds error handling" rather than
  reading the diff).
- Don't repeat long lists item by item — summarize them ("there are five
  options, the main tradeoff is...").
- If the written response is already short and speech-appropriate, the
  spoken version may be identical to it — don't force a rewrite for its
  own sake.

## Example

Written response:

> The fout komt doordat Piper het voice-model niet kan vinden. Controleer
> of `en_US-lessac-medium.onnx` en het bijbehorende `.json`-bestand in
> dezelfde map staan. Je kunt daarna Piper starten met `--model ...`.

Spoken version sent to `speak`:

> Piper kan het voice-model niet vinden. Controleer of het model en het
> JSON-bestand in dezelfde map staan en probeer het daarna opnieuw.

## Notes

- This is a per-conversation instruction, not persistent config — it
  resets when a new conversation starts. Re-invoke `/speak-replies` to
  turn it on again in a new session.
- Speak *after* the written response is finalized, not instead of it, and
  not before — the full written answer is always still shown.
- Don't narrate the act of calling `speak` ("I'll now read this aloud");
  just call it.
