# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-24: Fixed the leakage hook for Windows. It called `python3` (a Microsoft Store stub here) and matched only `/` paths, so it exited 0 on every edit without running the tests. Switched to `python` and normalised `\` to `/`; verified exit 2 with a deliberately broken `feature_columns`.
- 2026-11-25: Agent model is local `qwen3.5:9b` (`bikeshare-coder`) on a CPU-only laptop (integrated AMD GPU), measured at ~34 tok/s prompt and ~6 tok/s output. `make model` failed on Windows (`ollama create -f -` rejects stdin), so built with `-f model/Modelfile`. Per instructor guidance: `num_ctx` 64k -> 128k with `OLLAMA_KV_CACHE_TYPE=q8_0`, and API/stream timeouts raised to 30 min, because Claude Code cut off requests at 5-10 min and kept retrying. Ollama Cloud returned 402 for every model on the free account; NRP namespace shows "LLM off".
- 2026-11-25: Step 2 check of the agent's data characterisation, every fact verified with pandas. Correct: 728 x 18, 2011-01-03 to 2012-12-31, missing 2011-03-10, text labels (weather GOOD/MISTY/BAD), `casual + registered == cnt`. Wrong: called `cnt_2d_bfr` leakage (it is a lag known at prediction time, excluded only because its alignment is unverified); called `instant`/`dteday` leakage (time indexes, not leakage) and missed `yr` and `days_since_2011`; skipped the random-split question.
