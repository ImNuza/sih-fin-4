# sih-fin-4

Singapore-India Hackathon 2026, FinTech / InsurTech track. Brief: Income Insurance wants climate-risk insurance (heat, rain, haze, flood) for vulnerable households, workers and SMEs in Singapore. The deliverable is a product proposal. This repo holds the data work, the analysis and the team dashboard that support it.

## Layout

- `docs/problem-statements.md`: the official brief (all 4 tracks). Our track is section 1.
- `docs/resources/`: team research and sample documents. Index in `docs/resources/README.md`.
- `docs/notes/`: overview notes, meeting notes, transcripts.
- `docs/reference/data-gov-sg-api.md`: **read before calling any data.gov.sg API.**
- `data/raw/`: raw API downloads. Gitignored. Stays on the server.
- `data/`: other folders hold small processed tables (Parquet or CSV) that are committed.

## Rules

- **API key:** data.gov.sg calls send `x-api-key: $DATA_GOV_SG_API_KEY`. The key is in `.env` (gitignored). Load it with `set -a; . ./.env; set +a` or `python-dotenv`. Never print the key, put it in a URL or code, or commit it. Keys expire 08 Dec 2026.
- **Rate limits:** limits reset every 10 seconds. Back off and retry on HTTP 429. Check the response `code` field (0 = success).
- **Git size:** GitHub rejects files over 100 MB. Commit scripts and small processed data only. Raw multi-year data goes in `data/raw/`.
- **Personal data:** survey answers, photos or anything that identifies SME owners or workers goes in `survey/private/` (gitignored), never in git. PDPA applies.
- **Real data first.** Data made by an LLM ("synthetic") must be stored separately and labelled as synthetic in file names and charts. Never mix it into real NEA data.
- **Heat threshold:** MOM requires paid 10-minute rest breaks every hour for heavy outdoor work at **WBGT 32°C and above**. Use the numeric `wbgt` value, not the `heatStress` label.
