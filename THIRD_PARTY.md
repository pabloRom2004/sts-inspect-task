# Third-party material

`src/sts_hawk/assets/wiki.md` contains text from the Slay the Spire Wiki at
https://slay-the-spire.fandom.com/, contributed by that wiki's editors. It is
a user-provided scrape converted to Markdown, with each article's title and
source URL retained. Article histories and contributor attribution are available
through those linked source pages. The text is redistributed under the
[Creative Commons Attribution-ShareAlike 3.0 Unported license](https://creativecommons.org/licenses/by-sa/3.0/),
consistent with [Fandom's licensing policy](https://www.fandom.com/licensing).
The exact scrape date was not included in the provided archive.

`src/sts_hawk/assets/computer/` is copied from Inspect AI's computer-tool backend
at upstream commit `099d83a` (Inspect 0.3.289 source tree). Its MIT license is
retained in that directory.

Slay the Spire, its game files, ModTheSpire and game mods are not included in
this repository or its release assets. Users must supply an appropriately
licensed private runtime separately.

Local modification: `_x11_client.py` checks for Firefox ESR before browser actions and returns an ordinary tool error when it is absent. Screenshot/input behavior is unchanged.

Local modification: duration arguments accept fractional seconds for waiting and holding keys. Upstream's integer parser can terminate an evaluation when a model supplies a fractional duration; the backend's existing sleep operation already accepts it.

Local modification: parser and explicit action-input errors return the backend's JSON error response, which stock Inspect exposes to the model as a recoverable `ToolError`. Durations must be finite and non-negative. Unexpected backend failures retain their nonzero exit status.

`src/sts_hawk/inspect_compat.py` backports `resolve_tool_model_input` from Inspect AI 0.3.289 (upstream commit `099d83a`, `src/inspect_ai/model/_model.py`). It corrects the per-tool message count only on Hawk's exact 0.3.286.dev10+g3a44082ca build. The upstream MIT license is retained at `src/sts_hawk/assets/computer/LICENSE`.
