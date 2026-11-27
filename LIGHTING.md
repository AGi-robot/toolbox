# Expressive lighting

Toolbox owns the expressive lighting renderer and its own OpenRGB SDK client. Grace can compose an effect through `PUT /api/lighting`, inspect it through `GET /api/lighting`, and stop it through `DELETE /api/lighting`. One effect controls the configured device as a whole. Per-LED spatial effects are not implemented.

Effects replace each other and survive ordinary activity updates. Optional expiry or explicit stop restores the latest activity state. Service shutdown releases expressive control. No calendar, news, emotion or activity state automatically selects a custom effect. The caller chooses freely; this API does not add a scheduler or news source.

| Field | Meaning and default |
|---|---|
| `start_color` | `#RRGGBB`; default `#58C77E` |
| `end_color` | Optional final colour |
| `transition_colors` | Ordered intermediate colour stops; at most 16 |
| `transition_speed` | `fast` = 2, `normal` = 5, `slow` = 10 seconds per palette traversal |
| `transition_seconds` | Optional 1–120 second traversal time, overrides speed |
| `intermediate_steps` | 0–256 interpolated steps; default 64. Zero jumps between stops |
| `brightness` | 0–1; default 0.5 |
| `rhythm` | `steady`, `stationary`, `blink`, `blink_fast`, `blink_slow`, `heartbeat`, `random`, `morse`, `pattern` |
| `rhythm_seconds` | 1–60 seconds; default 2. Heartbeat has two pulses; random changes brightness once per cycle |
| `rainbow` | Default false. Uses the hue wheel instead of palette interpolation |
| `loop` | Default true. Palettes move forward and backward; rainbow wraps. False holds the final colour after one traversal |
| `duration_seconds` | Optional 0.1–3600 seconds. Omit or use null to continue until replaced, stopped or the lighting service shuts down |
| `morse_text` | Up to 120 ASCII letters, digits and spaces; required for Morse |
| `morse_unit_seconds` | 0.25–2 seconds per dot; default 0.25 |

`steady` keeps brightness constant while colours transition. `stationary` holds the starting colour. Fast blink has a 1-second cycle, slow blink 4 seconds. Morse follows 1-unit dots, 3-unit dashes, and 1/3/7-unit gaps; messages repeat until expiry. Inspect the effect status for the text. Timing is software driven and approximate.

For example, a looping gradient:

```bash
curl -X PUT http://127.0.0.1:8854/api/lighting \
  -H 'Content-Type: application/json' \
  -d '{"start_color":"#FF0000","transition_colors":["#FFFFFF"],"end_color":"#00FF00","transition_speed":"slow","intermediate_steps":64,"brightness":0.4,"rhythm":"steady","loop":true,"duration_seconds":120}'
```

Other compositions could use orange/purple colour stops, pink gradients, a low-brightness stationary colour, heartbeat pulses, or `rainbow: true`. These are examples rather than situation rules.

The response reports whether an effect is active and whether the SDK device is connected. Accepted software state does not prove physical LEDs changed. Disabled/unavailable OpenRGB returns 503 for new effects; invalid fields return 422. SDK write failures cancel the effect and release device ownership; a new effect request can reconnect. The service binds to loopback; remote models call it through the local tool host.

## Connect Grace

Install Toolbox with `pip install -e '.[lighting]'` and run `grace-lighting` on the OpenRGB host. The SDK server must already be running. Configure Interactive with:

```bash
export AGI_LIGHTING_SERVICE_URL=http://127.0.0.1:8854
```

Interactive exposes `set_lighting`, `lighting_status`, and `stop_lighting` with automatic tool choice during normal chat. Up to three tool rounds are followed by a final streamed answer. The model must support OpenAI-compatible tool calls. No idle activity is introduced. Tool errors are returned to the model. Reported token metrics describe the final LLM request; latency covers the entire turn.

For a separate model capability test, Agentic supports `--lighting-url http://127.0.0.1:8854`.

## Hardware coordination

The service connects to `AGI_OPENRGB_HOST` (default `127.0.0.1`), `AGI_OPENRGB_PORT` (6742), and `AGI_OPENRGB_DEVICE` (`MSI Z790 GAMING PLUS WIFI`). `AGI_OPENRGB_ENABLED=false` disables effect activation. It does not start or stop the shared SDK server.

On Linux, the capability holds an exclusive file lock throughout a custom effect. Console only acquires the same lock for each automatic activity frame and yields while it is held. Both processes must run as the same user on the OpenRGB host with the same `AGI_OPENRGB_LOCK_PATH` (default `~/.agi/openrgb-device.lock`). Do not delete the lock file while processes are running. A second expressive service cannot claim a busy device. Stop, expiry, process exit, or service shutdown releases control; Console resumes its latest state within its next frame, including resting. Device-write failures cancel the effect and release control. Without a running Console, automatic lighting cannot resume; the hardware retains its last colour.

Console can start the SDK server as a convenience but leaves it running on exit, so independent clients remain connected. The host manages the shared server's shutdown. The lock coordinates these two applications only; unrelated OpenRGB clients do not observe it.

## Editable Markdown catalogue

The seed catalogue is [`lighting_catalog.md`](src/agi_toolbox/lighting_catalog.md). The editable runtime copy defaults to `~/.agi/lighting.md`; set `AGI_LIGHTING_CATALOG` to choose a different path. Until a runtime file exists, the seed is read. The first saved preset creates the runtime file. Restart is unnecessary: the next catalogue read or effect selection sees edits. An already playing effect keeps its original values until replaced.

The file contains prose and exactly one fenced `json` block with `colors` and `effects`. Add colour names, palettes, brightness settings, transition speeds, Morse messages, and effects there. `PUT /api/lighting/catalog` accepts `name`, `effect`, and optional `colors`; it validates the result and atomically updates the file while preserving prose. `GET /api/lighting/catalog` reads it. Grace receives `lighting_catalog` and `save_lighting_preset` tools as well as the play/status/stop tools. Saving a preset does not start it. Use `{"preset":"effect_name"}` in a lighting request, optionally overriding fields.

All effect definitions live in the catalogue. Grace chooses among them or composes a new effect using the current conversation, mood, history, or timing. Presets are editable starting points, with no fixed occasion or keyword triggers. Asking for normal lighting selects `default`; asking for another look lets Grace choose a fitting replacement. Newly added built-in presets are available alongside existing runtime entries, with user-defined colors and effects taking precedence.

For entirely new rhythms without code changes, use `rhythm: "pattern"` and `rhythm_pattern: [0, 1, 0.2, 0.7, 0, 0]`. These are successive brightness multipliers over `rhythm_seconds`, with at least 0.25 seconds per step and at most 64 steps. Software still implements timing, interpolation, validation and hardware access; Markdown supplies the chosen data. The catalogue allows up to 128 colours, 128 effects and 64 KiB. Invalid manual edits return an error rather than silently choosing a different effect.

## Default lighting, reasons and personal codes

The built-in `default` catalogue option yields to Console’s existing activity renderer: resting mint `#58C77E`, online dark rose `#682D3F`, with rose `#B84669` pulses. Selecting `default` releases the device lock so Console can resume its latest activity state. No copy of Console's activity settings is maintained in the capability. If Console is not running, release does not change the last visible colour. `default` is reserved and cannot be overwritten by catalogue saves. Select `{"preset":"default","reason":"I want our usual lighting again"}` or use the stop tool. Explicit effect overrides do not apply to this preset.

Effects can carry `reason` and `meaning` strings (up to 1000 characters each). `reason` is a brief explanation for a decision. `meaning` describes a personal signal, such as “two pink pulses mean hello.” Both are retained in saved presets. Model-facing set/save/stop tools require a reason. Normal Interactive chat records the chosen arguments and result in regular Memory's conversation database immediately after each attempted action, including failed actions and actions followed by an incomplete reply. This records actions and their outcomes, not proof of a visible hardware change.

Install the matching Memory event support as well as Toolbox and Interactive. Related/recent lighting events are recalled into subsequent chat context and available through `lighting_history`. Grace can explain past choices when asked, or mention them in her reply without being asked. The record is scoped to the active conversation and persists across restarts. Saving a catalogue definition alone does not add it to regular memory; Interactive records the model's save action. Standalone Agentic trials do not use Grace's conversation memory.

A custom effect can continue until Grace replaces it or selects default: leave `duration_seconds` unspecified or null. She can alternatively choose a duration. Morse permits 120 characters per effect; longer text needs separate effects. Status reports `morse_message_seconds` so the caller can choose enough time for a full transmission. Blink codes and colour transitions can have any personal meaning she saves; no vocabulary of meanings is imposed. A scheduler is still needed for activity outside chat or other existing triggers.
