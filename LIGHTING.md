# Expressive lighting

Toolbox owns the expressive lighting renderer and its own OpenRGB SDK client. Grace can compose an effect through `PUT /api/lighting`, inspect it through `GET /api/lighting`, and stop it through `DELETE /api/lighting`. One effect controls the configured device as a whole. Per-LED spatial effects are not implemented.

Effects replace each other and survive ordinary Console activity updates. Selected effects and runtime response/speech overlays release control when none remain; explicit stop/default cancels them. Service shutdown releases control. Model-selected effects have no fixed calendar, news or emotion triggers. The runtime response and speech overlays are described below; this API does not add a scheduler or news source.

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
| `speech_mode` | `auto` (default), `follow`, `keep`, or `blend`; controls brightness during playback without changing the palette |
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

On Linux, the capability holds an exclusive file lock throughout a custom effect. Console only acquires the same lock for each automatic activity frame and yields while it is held. Both processes must run as the same user on the OpenRGB host with the same `AGI_OPENRGB_LOCK_PATH` (default `~/.agi/openrgb-device.lock`). Do not delete the lock file while processes are running. A second expressive service cannot claim a busy device. When the last effect or runtime overlay ends, or on explicit stop/default, process exit, or service shutdown, control is released; Console resumes its latest state within its next frame, including resting. Device-write failures cancel the effect and release control. Without a running Console, automatic lighting cannot resume; the hardware retains its last colour.

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

## Response heartbeat and future speech

Interactive starts a background response report when its first visible reply text appears. It sends `start`, renews with `keepalive` every 0.5 seconds, and sends `stop` when the turn finishes, fails, or is cancelled. Thinking before the first reply text does not start this overlay. No per-token lighting request runs on the text streaming thread; an unavailable service is logged without failing the reply. A turn producing text before a later tool round stays in response activity until the turn ends. Very short replies may finish before the background report is sent.

`PUT /api/lighting/response` accepts `stream_id`, `event` (`start`, `keepalive`, `stop`), and `sequence`, using the same bounded session and ordering rules as speech. Start uses sequence zero; subsequent sequences must increase. A missing renewal expires response activity after three seconds. This is a host/runtime API, not a model tool, and these activity notifications are not saved as model decisions in conversation memory.

```json
{"stream_id": "reply-42", "event": "start", "sequence": 0}
```

The response overlay applies a temporary 0.4-second double heartbeat to the renderer's current palette and peak brightness, without reading physical RGB colours or modifying the saved effect. If there is no selected effect, `AGI_LIGHTING_RESPONSE_PRESET` (default `double_pulse`) supplies its fallback palette, resolved once per new response. Its preset duration is ignored; response activity controls the overlay lifetime. `default` is not a valid colour fallback.

Live speech volume has priority over this heartbeat. If playback stops while reply text is still streaming, the heartbeat resumes; if text finishes before audio playback, voice lighting continues until playback ends. With neither signal active, a selected effect uses its original rhythm; with no effect selected, the service releases control to Console's automatic activity lights. `speech_mode` governs both the current response placeholder and future voice modulation: `auto` preserves Morse, `keep` preserves any chosen rhythm, `follow` temporarily replaces brightness rhythm, and `blend` gently scales it. Both retain the effect's colours and configured brightness limit.

Selecting `default` or stopping lighting cancels both overlays for their current sessions. Late response renewals or voice samples cannot reactivate them; the next new reply/playback session can activate lighting again. Status includes a `response` object and a `modulation` field identifying the available source (`speech`, `response`, `preset`, or `default`).

## Prepared speech lighting input

TTS is not implemented here. The future audio player sends a normalized playback-volume envelope to `PUT /api/lighting/speech`; it never reads the physical RGB colour or edits a preset's palette. Send samples when audio is actually played, rather than when text or an audio file is generated. Compute RMS/peak levels over short PCM windows in the playback component, normalize them to 0–1, and send approximately 20 updates per second from a worker so HTTP cannot block audio playback. Raw audio does not pass through this API, and the model does not generate these events.

Each utterance gets a new `stream_id` of 1–64 letters, digits, underscores or hyphens. Send `event: "start"` with `sequence: 0`, then `event: "level"` with increasing integer sequences, and `event: "stop"` when playback completes or is cancelled. Levels must be finite numbers from 0 to 1; zero means a silent portion of active playback. Sequence values must be integers from 0 to 2^53−1. A stop may omit the level. Delayed, duplicate, or wrong-session events return `accepted: false`; the renderer remembers the most recent 32 ended session IDs. Use a single playback-event producer. A new session supersedes the previous one.

```json
{"stream_id": "utterance-42", "event": "start", "sequence": 0, "level": 0.0}
```

```json
{"stream_id": "utterance-42", "event": "level", "sequence": 1, "level": 0.72}
```

```json
{"stream_id": "utterance-42", "event": "stop", "sequence": 2}
```

The service smooths volume levels with a 40 ms attack and 150 ms release. It retains the selected effect's palette, colour transitions, and peak brightness:

| `speech_mode` | During active playback |
|---|---|
| `auto` | Follow the voice, except Morse keeps its timing |
| `follow` | Replace only brightness rhythm with the smoothed volume envelope (8–100% of configured peak brightness) |
| `keep` | Preserve the effect's original rhythm |
| `blend` | Preserve the original rhythm and gently scale its brightness by 65–100% according to voice volume |

Grace can save `speech_mode` in any normal preset or override it when selecting an effect. The original effect is not rewritten. On playback stop, its original rhythm becomes visible again on its continuously advancing timeline, unless an ongoing text response still supplies the heartbeat placeholder. If the player stops sending updates, speech control times out after one second and the response heartbeat or selected effect resumes. Calling the normal stop/default tool also cancels the current speech overlay; late levels from that utterance cannot reactivate it.

With no custom effect selected, speech uses the palette from `AGI_LIGHTING_SPEECH_PRESET` (default `double_pulse`, the existing rose preset). This fallback is resolved from the same catalogue once per new playback session; its duration is governed by the playback session, not its preset's duration. `default` cannot be used as a speech fallback because it releases hardware control rather than defining a palette. Without speech, response activity, or a selected effect, the capability releases its device lock so Console can render the automatic activity lights. If a custom effect expires while speech continues, the configured speech fallback takes over until playback ends.

`LightingClient.speech_event(...)` is available to a future host adapter; it is deliberately absent from the model tool list. Hosts sending frequent updates can use a persistent HTTP connection to the same endpoint. Status includes a `speech` object with the current stream, smoothed level, effective policy, and active flag. No live microphone, TTS engine, or audio device is opened by this feature; no lighting control is claimed until a custom effect or accepted response/speech start event arrives.
