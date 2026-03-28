# widget-templates

AI-controlled widget templates for Claude artifacts. Enables outer Claude agents to share interactive control of widgets with users via a CDN loader pattern.

## Files

- **`SKILL.md`** — Full documentation of the pattern, for Claude agents
- **`calculator_widget.html`** — Reference implementation (4-operation calculator)
- **`inject_state.py`** — CLI tool for injecting JSON state into template files

## How it works

1. Widget template lives here on GitHub, served via jsdelivr CDN
2. Claude renders a tiny loader (~20 lines) via `show_widget` with state JSON
3. Loader fetches template from CDN, replaces `BAKED_STATE` client-side, injects into DOM
4. User interacts with widget, clicks "Send to Claude" → `sendPrompt()` relays state to chat
5. Claude reads state, modifies it, renders new loader with updated state

See [SKILL.md](SKILL.md) for complete documentation.
