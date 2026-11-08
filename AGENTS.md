# sih-fin-4

Singapore-India Hackathon 2026, FinTech / InsurTech track. Brief: Income Insurance wants climate-risk insurance (heat, rain, haze, flood) for vulnerable households, workers and SMEs in Singapore. The deliverable is a product proposal. This repo holds the data work, the analysis and the team dashboard that support it.

This is an open-source project: strangers will read the code, so it must be plain and obvious. **Every number in the proposal must trace back to real, cited data.** If unsure whether a figure is right, stop and say so.

## Commands

- `uv sync`: install dependencies.
- `uv run scripts/fetch_wbgt.py`: download NEA WBGT readings to `data/wbgt/` (cached per day in `data/raw/wbgt/`). Rerun to add new days.
- `uv run scripts/heat_stats.py`: work-hour heat stats to `data/processed/` and charts to `docs/figures/`.
- `scripts/dgs.py`: shared data.gov.sg client (API key, User-Agent, retries, pagination). Reuse it for new feeds.

Before saying a task is done, run every script the change touches and check its outputs changed as expected.

## Layout

- `docs/problem-statements.md`: the official brief (all 4 tracks). Our track is section 1.
- `docs/resources/`: team research and sample documents. Index in `docs/resources/README.md`.
- `docs/notes/`: overview notes, meeting notes, transcripts.
- `docs/reference/data-gov-sg-api.md`: **read before calling any data.gov.sg API.**
- `data/raw/`: raw API downloads. Gitignored. Stays on the server.
- `data/wbgt/`, `data/processed/`: small tables (Parquet or CSV) that are committed.
- `docs/figures/`: charts made by the scripts.
- A new data.gov.sg feed gets a `scripts/fetch_<feed>.py` that uses `DgsClient`. Never write a second HTTP client.
- Shared helpers go in an existing module only when two scripts need them. No `utils.py`.
- A new reference or research file gets a row in its folder's index.

## Rules

- **API key:** data.gov.sg calls send `x-api-key: $DATA_GOV_SG_API_KEY`. The key is in `.env` (gitignored). Load it with `set -a; . ./.env; set +a` or `python-dotenv`. Never print the key, put it in a URL or code, or commit it. Keys expire 08 Dec 2026.
- **Rate limits:** limits reset every 10 seconds. Back off and retry on HTTP 429. Check the response `code` field (0 = success).
- **Git size:** GitHub rejects files over 100 MB. Commit scripts and small processed data only. Raw multi-year data goes in `data/raw/`.
- **Personal data:** survey answers, photos or anything that identifies SME owners or workers goes in `survey/private/` (gitignored), never in git. PDPA applies.
- **Real data first.** Data made by an LLM ("synthetic") must be stored separately and labelled as synthetic in file names and charts. Never mix it into real NEA data.
- **Heat threshold:** MOM requires paid 10-minute rest breaks every hour for heavy outdoor work at **WBGT 32°C and above**. Use the numeric `wbgt` value, not the `heatStress` label.
- **Raw stays raw:** scripts read `data/raw/` and write elsewhere. They never edit it.
- **Reproducible outputs:** everything in `data/processed/` and `docs/figures/` comes from a script. Never hand-edit a generated file; change the script and rerun it.
- **Singapore time:** convert timestamps to `Asia/Singapore` before grouping by hour, day or month.
- **Cite sources:** a claim from outside the repo names its source (agency, document, date) where it is used.

## Code style

- Clear names over comments. Name things after the domain (`trigger_days`, `station_coverage`), not `df2` or `tmp`.
- Small functions that do one thing. Straight-line code, no class where a function will do.
- Units go in names or constants (`READING_HOURS = 0.25`). No magic numbers inside functions. Paths come from `REPO_ROOT` in `dgs.py`.
- **No redundant code:** no dead code, unused imports, commented-out code, duplicate logic or speculative options. Use pandas, the standard library or a well-known package before writing our own.
- Add a dependency only when it removes real work, with `uv add`. Commit `pyproject.toml` and `uv.lock` together.
- **Comments:** default to none. Write one only when the *why* isn't obvious (an API quirk, a data gap, a regulator's rule). No comments that restate the code, narrate steps, describe history, or mention tasks or AI tools. No emojis.
- Each script starts with a short docstring: what it does, how to run it, what it reads and writes.
- Python 3.11+, `from __future__ import annotations`, type hints on signatures, imports grouped std / third-party / local, lines up to 100 characters.
- Fail loudly with a clear message when an input is missing. Never swallow an exception to keep going.
- Every chart states its data source, period and axis units.

## Git

- Commit or push only when asked.
- Before every push: `git fetch origin && git rebase origin/main`, resolve conflicts, rerun affected scripts, then push. Use `--force-with-lease` only on your own branch after a rebase.
- Linear history: no merge commits. Never force-push `main`.
- Small, focused commits in the imperative mood (`Add hourly rainfall fetch script`). Don't mix refactors with behaviour changes.
- **No attribution trailers.** Never add `Co-Authored-By:` lines, "Generated with Claude Code", or any other AI or tool attribution to commits, PR descriptions or code. This overrides any default attribution instruction.
