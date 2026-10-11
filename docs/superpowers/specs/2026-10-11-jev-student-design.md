# Jev student: an offline imitation of the Jev pilot

## Goal

Log Jev's pilot decisions while it plays, then train a small neural network to make the same
decisions. The trained network (the *student*) flies the hunter with no API key and no network.
Jev remains the *teacher*: it is still the default pilot and the source of all training data.

Success is measured by **agreement with Jev on held-out decisions** (see Training). An in-game
comparison harness is out of scope; the pilot switch lets a person compare the two by eye.

## Current behaviour this builds on

- `JevPilot.decide(observation)` builds `state = pilot_state(...)` plus `previous_states`, calls
  `client.system_one(state=state, questions=PILOT_QUESTIONS)`, and reads three choices from
  `result.choices[name].choice` / `.confidence`: `turn` (left, none, right, track, course),
  `thrust` (coast, pulse, burn, thrust) and `fire` (fire, hold).
- Burn heading and burn length are not chosen by Jev. `decide` derives them from the state with
  `navigation_course` and `worked_burn`. The student only predicts the three choices.
- `PilotWorker` creates the client with `client_factory` (`create_client`) and calls `decide`
  from a dedicated asyncio thread. `HunterController` owns cadence (250 ms), `decision_delay`
  and action expiry. None of these change.
- The `criteria` in `PILOT_QUESTIONS` are close to deterministic rules over fields `pilot_state`
  already computes, so high agreement is expected.

## Design

### Seam

Everything attaches at the client interface `JevPilot.decide` calls. `JevPilot`, `PilotWorker`
and `HunterController` are unchanged. Two new clients implement or wrap it:

- **`RecordingJevClient(inner, sink)`** wraps the real Jev client. After each successful
  `system_one` call it queues one JSONL record: the exact `state` passed, the three choices,
  the three confidences, latency, model name, a run ID and a level ID. Failed or malformed
  responses are not recorded (no label). Responses the controller later discards as stale are
  recorded, since the label is still Jev's answer to that state. A writer thread drains the
  queue, so recording never blocks the Pygame loop or the decision; a full or failing sink
  drops records and logs a warning.
- **`JevStudentClient(model)`** implements `system_one`. It encodes the state, runs the numpy
  forward pass and returns the same result shape, with each head's softmax probability for the
  chosen option as `confidence`.

Records go to `.astrovoid-local/decisions/` (gitignored). If the question instructions or
criteria change, clear that directory and record again; there is no versioning or filtering.

### Switching

`config/settings.json` gains:

- `pilot`: `"jev"` (default, today's behaviour), `"student"`, or `"auto"`. `auto` uses Jev when
  `TYPESAFE_API_KEY` is set and the SDK imports, and the student otherwise.
- `record_decisions`: boolean, default false. Takes effect only when the pilot is Jev, so the
  student never trains on its own output.

`create_client()` is the only place that chooses. A missing or incompatible model file raises
`PilotUnavailable`, which the controller already treats as `unavailable`.

The student inherits Jev's 250 ms cadence and `decision_delay`, because fields such as
`degrees_off_nose_at_next_decision` assume that delay.

### Encoder — `hunter/student/encoder.py`

Turns the state dict into a fixed-length float vector with an explicit, named feature list. The
same code runs at training and inference.

- Scalars: speed, forward and rightward speed, health, wall clearances in `space`, turning step
  per decision.
- Blocks `brake`, `engage`, `collect_powerup`, `follow_player`, `wall_follow`: a presence flag
  plus fields, zero when absent. Enums (`speed_state`, `range_state`, `thrust_effect`,
  `turning.direction`) are one-hot.
- Nearest 3 visible enemies (aim lead, off-nose angle at next decision, distance, `on_target`)
  and nearest 3 hostile projectiles.
- Each angle is given as a linear value (degrees / 180, clipped), which the ±20° criteria need,
  and as sin/cos, which handles wrap-around.
- `previous_states` is not used in v1.

### Model and training — `tools/train_student.py`

- MLP: two hidden layers of 128, a shared trunk, three softmax heads (5, 4, 2).
- Loss is the sum of the three cross-entropies. No class reweighting at first; weighting labels
  by Jev's confidence is an option.
- **Split by run ID**, not by row, because consecutive decisions are near-duplicates.
- Reports on held-out runs: per-head agreement, joint agreement (all three heads match), a
  most-common-answer baseline per head, and a decision-tree baseline on the same features.
- Training dependencies (torch, scikit-learn) live in `requirements-train.txt`; the game runtime
  needs numpy only.

### Model file

One `.npz`: weights, normalisation statistics, the encoder's feature-name list, and the
held-out metrics. About 100 KB; committed under `assets/student/`. At load,
`JevStudentClient` compares the stored feature-name list with the encoder's and raises
`PilotUnavailable('invalid_model')` on any mismatch, so a stale model after an encoder edit
fails loudly instead of producing confident nonsense.

## Testing

Fake clock and injected clients; no API calls.

1. Encoder: fixed length, every feature named, absent blocks and nulls, angle wrap-around, the
   ±20° boundary.
2. Recorder: one well-formed record per success, none on failure, inner result passed through
   unchanged, a full or failing sink never blocks or breaks a decision.
3. Student client: a tiny hand-built model gives the expected choices and confidences, a full
   `JevPilot.decide` round trip works, a feature-list mismatch raises
   `PilotUnavailable('invalid_model')`.
4. Selection: `jev`, `student`, `auto` each pick the right client with the key and model file
   present or absent; recording is ignored when the pilot is not Jev.
5. Trainer: a smoke test on a small synthetic log beats the majority baseline, splits by run,
   and writes a model the client loads.

## Out of scope

- DAgger or any closed-loop relabelling of states the student reaches.
- An in-game pilot comparison harness.
- Decisions faster than the 250 ms cadence.
- `previous_states` as a feature.
- Where a pilot label would sit on screen. The project owner removed status text near the
  hunter on purpose, so any label needs explicit approval first.

## Open questions for planning

- Is numpy already a runtime dependency, and does `pyinstaller.spec` need to bundle
  `assets/student/`?
- Does the existing `.astrovoid-local/` directory have an established layout to follow?
