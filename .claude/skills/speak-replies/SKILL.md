---
name: speak-replies
description: Speak responses out loud using the `speak` tool from the mcp-speech-tools MCP extension (Piper TTS), played back via ffplay. Use when the user asks to hear replies spoken or read aloud, wants voice/audio responses, says something like "spreek je antwoorden uit" or "turn on spoken replies", or asks to stop/mute spoken replies.
---

# Speak Replies

When the user asks for spoken replies, start following this behavior for
the rest of the conversation: after every subsequent user-facing
response, call the `speak` tool from the mcp-speech-tools MCP extension.
Keep doing this on every turn until the user asks to stop (mute, turn it
off, "hou op met spreken", etc.) — then stop calling `speak` for future
responses and confirm it's off without speaking that confirmation.

If the mcp-speech-tools extension or its `speak` tool isn't available,
say so and stop — don't try to produce audio another way.

## Modes

- **Summary (default):** write the normal, complete response first. Then
  compose a short spoken version specifically for `speak`, and send only
  that to the tool.
- **Full, if the user asks for it** (e.g. "read the whole thing", "spreek
  het hele antwoord uit"): speak the substance of the full response, not
  just a summary — but still never verbatim-read code, JSON, tables, or
  paths (see exclusions below); rephrase those parts in words or skip
  them, rather than skipping the whole response.

## Composing the spoken text

- Contain the main conclusion, answer, or next step.
- Be concise and natural when spoken aloud — normally 1-3 sentences in
  summary mode.
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
- Match the language the user is chatting in (Dutch in, Dutch spoken).

## Example

Written response:

> De fout komt doordat Piper het voice-model niet kan vinden. Controleer
> of `en_US-lessac-medium.onnx` en het bijbehorende `.json`-bestand in
> dezelfde map staan. Je kunt daarna Piper starten met `--model ...`.

Spoken version sent to `speak`:

> Piper kan het voice-model niet vinden. Controleer of het model en het
> JSON-bestand in dezelfde map staan en probeer het daarna opnieuw.

## Notes

- This is a per-conversation instruction, not persistent config — it
  resets when a new conversation starts.
- Speak *after* the written response is finalized, not instead of it, and
  not before — the full written answer is always still shown.
- Don't narrate the act of calling `speak` ("I'll now read this aloud");
  just call it.
