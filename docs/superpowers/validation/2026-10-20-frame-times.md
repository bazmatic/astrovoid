# Frame times: Creatures, stages 1–2

Measured with `venv/bin/python -m tools.frame_timer --levels 1 8 9 40 --frames 600 --seed 1`: a real `Game` on a
1352×878 surface, dummy video and audio, rules hunter pilot, 60 warm-up frames, then 600 timed frames. Each number is
the median of three runs. Times in milliseconds per frame.

Machine: Apple M2 Pro, macOS 26.3, Python 3.10.13, pygame 2.6.1. Date: 2026-10-20.

The gate: a frame (update + draw) on each level may be at most 20% slower than the baseline.

## Baseline (420b0e2)

Measured at `d3638c0`, which only adds docs on top of `420b0e2`.

| level | enemies | update_ms_mean | update_ms_p95 | draw_ms_mean | frame (update + draw) | 20% limit |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | 0.161 | 0.176 | 3.131 | 3.292 | 3.950 |
| 8 | 33 | 1.422 | 1.829 | 3.455 | 4.877 | 5.852 |
| 9 | 22 | 1.959 | 2.558 | 4.627 | 6.586 | 7.903 |
| 40 | 32 | 1.428 | 1.734 | 7.990 | 9.418 | 11.302 |
