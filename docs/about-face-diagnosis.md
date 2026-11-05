# About-face learning diagnosis — 4 November 2026

## Finding

The current online imitation teacher is not a reliable expert for the states the learner visits. It advances a timed motor sequence even when the learner has not executed the preceding actions. This is a concrete fault in run219's proposed remedy, not evidence that a neural network cannot represent an about-face. It does not explain failures predating DAgger by itself.

The physical task is achievable. With unchanged physics, rewards and initial conditions, the scripted controller succeeds where the frozen run219/iter0091 policy fails.

## Reproduction

Run from the repository root:

```sh
PYTHONPATH=. venv/bin/python .astrovoid-local/diagnostics/about_face_probe.py
PYTHONPATH=. venv/bin/python .astrovoid-local/diagnostics/about_face_trace.py
PYTHONPATH=. venv/bin/python .astrovoid-local/diagnostics/about_face_teacher_counterfactual.py
```

The first command intentionally fails its learned-policy success assertion. Checkpoint: `.astrovoid-local/neural/rl/run219/iter0091.npz`; level 4, stage 8, seed 2000000800, 120-second horizon. These are local diagnostic artifacts, not production changes.

| Controller | Success | Duration | Final distance | No-grip fraction |
| --- | --- | --- | --- | --- |
| Learned, sampled | No | 120 s | 244.76 px | 98.54% |
| Learned, greedy | No | 120 s | 165.09 px | 0% |
| Scripted | Yes | 42.98 s | 13.85 px | 0% |

Changing inference to greedy suppresses the detached motion but does not restore the turn.

## Why the supervision is wrong

`learning/adapters/inchworm_scenario.py:330` labels every about-face learner decision using `teacher_action`. That calls the mutable scripted controller, advancing its timer by six frames even though its commands are only labels and the policy executes different commands.

In `creatures/inchworm_control.py:63`, the loop phase ends after 180 frames regardless of actual curl or facing. The next phase accepts any existing front grip as a successful landing, including the original grip of a worm which has not turned. After another 240 frames the controller assumes unfolding is complete. About-face has a marker rather than prey, so the adapter passes `target=None`; the controller's target-behind automatic turn retry never runs.

With a stationary learner holding both grips:

- At 3.3 seconds, the teacher enters `turn_unfold` although facing alignment is still approximately -1 and the body remains straight.
- At 7.4 seconds, it enters forward crawling, still facing away from the goal.
- The remaining labels teach crawling in the wrong direction instead of correcting the missed turn.

The greedy learned rollout exhibits the same phase mismatch. The sampled rollout loses both grips before landing; the teacher times out into recovery and never retries turning.

## Controlled intervention

Hold the body still for ten seconds while calling the actual teacher labeller. Then execute its commands exactly. Compare with the identical physical setup, changing only a call to `teacher.request_turn` before takeover.

For seed 2000000800, the unchanged teacher fails and ends 573.34 px from the target. Resetting only its phase succeeds at 52.88 seconds, ending 13.90 px from the target. This isolates controller history from physical capability. Across all three tested held-out seeds (2000000800–2000000802), the stale teacher fails 3/3 and resetting its phase succeeds 3/3. Results are saved in `.astrovoid-local/diagnostics/teacher-counterfactual.jsonl`.

## Other constraints and limits

Successful scripted play is also charged 202.90 px of backward travel (8.12 reward units) on the first case, leaving a total return of only +2.72. This metric accumulates rear-link movement per physics frame; it is not net wrong-way displacement. The resulting weak margin merits separate investigation, but the successful script still beats staying still (-0.24). The evidence does not establish rewards as the sole cause.

Both imitation losses train the tanh of the continuous means, not their sampled variance (`learning/imitation.py` and `learning/ppo.py`). Thus fitting demonstration means does not guarantee a reliable sampled motor sequence. Greedy failure rules out sampling noise as the only issue here.

## Recommended next change

Make the online expert respond to actual posture and support: require a completed curl before landing, verify the new front support before releasing the rear, and retry or recover when prerequisites fail. Validate it on deliberately delayed, stalled and perturbed learner states, not just its own successful trajectory. Only then restart a versioned training experiment. A phase reset in this diagnostic is a causal probe, not a general recovery algorithm.

Separately measure reward components during a successful turn and gait, and verify that fitting the expert makes sampled execution reliable. No production controller, training settings or running job was changed during this investigation. Demonstrating corrected neural learning still requires a subsequent training experiment.

## Landing and support transfer follow-up — run222/iter0096

Three sampled held-out cases (level 4, seeds 2000000800–2000000802) all failed.
Their first front grip while facing the goal occurred at 12.2, 2.9 and 2.4 seconds.
The scripted baseline on the first case gripped at 3.3 seconds and succeeded.
The first learned case often held the front link 19–36 px from the surface during
its initial curl, outside the 17.5 px leg reach. Foot orientation sometimes also
failed the physical grip conditions.

Landing is not the only problem. Instrumenting `_release_foot` found explicit
policy release commands leaving the other foot unplanted: for example, seed
2000000802 lands at 2.4 s, then releases its front grip at 2.8 s with no rear
support. Seed 2000000800 releases its front grip at 14.1 s without rear support.
These recorded releases are commanded, not overload slips.

A controlled override enabling the front-grip request whenever the worm faces
the goal, remains folded, and retains rear support reduces the first case's
landing delay to 5.1 s. All three still fail. Requesting a grip alone does not
solve the posture and subsequent support-transfer problems.

Local reproductions: `.astrovoid-local/diagnostics/about_face_landing.py`,
`about_face_landing_override.py`, and `about_face_grip_loss.py` in that directory.
The first two save results to `landing.jsonl` and `landing-override.jsonl` when
redirected as in this investigation. Production code and training are unchanged.
A focused landing/support-transfer drill should teach holding the new front
anchor through unfolding and establishing rear support before releasing it.
This is a proposed next experiment, not a demonstrated learning fix.
