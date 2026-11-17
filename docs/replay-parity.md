# Replay parity

Reference messages came from the supplied Epoch `.eval` files. The StS1 system prompt is identical in the November 4 Ironclad/Watcher examples and the recovered November 5 Luna/Defect header and initial messages. The latter header was decompressed from its first ZIP entry and CRC checked; its full replay remains incomplete.

| Setting | Reference | This task |
| --- | --- | --- |
| StS1 instructions | Captured system and user messages | Original system; only character, ascension and seed substitutions in the user message |
| StS2 instructions | Captured system; already-started Custom run | Original system; user navigates Custom and enters seed |
| Difficulty and objective | A20 Heart / A10 three Acts | Same requested objectives; verify actual UI selection |
| Screen | 1280×720 / 1280×800 | Same configured viewport |
| Actions | Pixel mouse/keyboard tools; unlimited StS1 queues / up to eight StS2 inputs | Same descriptions and schemas, translated to existing Inspect X11 backend |
| Notes | Empty `/memories/notes.md`, persists through compaction | Inspect memory with the captured schema and per-sample store |
| References | `wiki_search(query)` / `wiki_fetch(url)` | Same schemas; wiki-only Tavily search; independent article Markdown retrieval |
| Compaction | Summary, threshold 300000, memory true | Same strategy and threshold for replay profile |
| Images | Provider-dependent pruning; exact count unavailable | No fixed cap by default; complete Sonnet replay reached 102 images; optional provider cap |
| End of run | Epoch terminal-state handling and `give_up` | Original `give_up` plus requested integer `submit`; no automatic grader |
| Limits | Headers include 40000 messages and a 4000-minute setup deadline | 40000 messages; 240000-second Inspect deadline; clock/scope differ from external watchdog |
| API retries | Seven in the recovered Luna header | Maintained default 140 at user request; `original.yaml` retains seven. This retries the same model request and does not restart the game. |

The backend is an adapter, not Epoch's private playpen service. Screen-change detection compares captured image bytes; settling inherits the stock backend's two-second post-input delay. Animation, cursor changes or compression can count as a change. Epoch's exact settling/difference algorithm is unavailable. Queues are validated before execution and abort on an unchanged click/drag/key/scroll; a runtime error can still happen after earlier steps executed.

Drag input now pauses 100 ms after hovering the starting point, pressing the button and moving to the destination, then releases in a `finally` block. A controlled GPU test found the stock instantaneous drag left Defend selected but unplayed, whereas a separated press/move/release played the same card at the same coordinates and granted 5 Block. The original private service's drag timing is unavailable; the tool schema is unchanged. This fixes an input delivery difference rather than adding gameplay advice.

Desktop schemas for each game were recovered separately, including all StS1 schemas from the incomplete November 5 Luna replay. That StS1 version allows any number of queued inputs, unlike the eight-input StS2 version. The literal original system prompt calls these “playpen MCP tools”; this port exposes compatible function tools through Inspect, not that service or transport.

Tavily's original search depth and the original fetch/conversion code are unavailable. This implementation uses basic search, up to five results with 400-character snippets, and direct wiki article-body conversion. The live wiki can drift, especially from frozen StS2 v0.107.1. Tool schema parity is verified; byte-for-byte fetched-page parity is not claimed.

The complete Sonnet replay’s reconstructed API requests contained up to 102 images. Its four summary compactions reset image history to zero. The incomplete Luna archive contains 185 complete model events and exact tool/API settings, but its message-reference pool is missing, so its precise image history cannot be reconstructed. Do not apply Sonnet’s observed image count as a Luna provider limit. The prior OpenRouter/Azure route rejected more than 50 images; verify the actual route and set an appropriate explicit cap before a paid Luna run.

Game startup, mods, unlocked progress and the Neow bonus require separate in-game verification. Epoch corrected the missing StS1 Neow bonus on November 5. This task does not intentionally reproduce the older bug. The runtime includes the verified opt-in VirtualGL/T4 path from the StS2 integration. Its saved-combat GPU test verifies rendering; replay-agent first-combat and complete-run behavior still require separate verification. The user-requested fixed startup-wait notice has been removed.

No full replay, game archive, personal instructions or credential is packaged with these assets. Captured prompt provenance is recorded in `assets/epoch/provenance.json`.
