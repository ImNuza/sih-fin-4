# data.gov.sg API: how we use it

Sources (checked 8 Nov 2026):
- https://guide.data.gov.sg/developer-guide/api-overview/how-to-use-your-api-key
- https://guide.data.gov.sg/developer-guide/api-overview/api-rate-limits
- https://guide.data.gov.sg/developer-guide/real-time-apis
- Full doc index: https://guide.data.gov.sg/llms.txt (add `.md` to any guide URL to get Markdown)

## API key

- All APIs work without a key, but with the lowest rate limit. We hit the limit (HTTP 429 / response `code` 24) after a few requests without a key.
- Send the key in a request header:

  ```
  x-api-key: <key>
  ```

- Keys live in `.env` at the repo root (gitignored). Variable names:
  - `DATA_GOV_SG_API_KEY`: production tier, highest limit. Use this by default.
  - `DATA_GOV_SG_API_KEY_DEV`: development tier.
- Both keys expire **08 Dec 2026, 22:10 SGT**. The owner (Dewa) gets email reminders before expiry.
- Never print a key, put it in a URL, commit it, or send it to the browser (client-side code). Server-side only.

```bash
set -a; . ./.env; set +a
curl -s -H "x-api-key: $DATA_GOV_SG_API_KEY" \
  "https://api-open.data.gov.sg/v2/real-time/api/weather?api=wbgt&date=2025-03-01"
```

```python
import os, requests
headers = {"x-api-key": os.environ["DATA_GOV_SG_API_KEY"]}
r = requests.get("https://api-open.data.gov.sg/v2/real-time/api/air-temperature",
                 params={"date": "2025-03-01"}, headers=headers, timeout=30)
r.raise_for_status()
```

## Rate limits

- Limits reset every **10 seconds**. Over the limit returns HTTP `429`.
- Tiers: no key (lowest) < development key < production key (highest). The guide page did not show the exact numbers in text form.
- Bulk downloads must back off on 429 and retry. Keep requests sequential, or use a small fixed pause.

## Real-time weather APIs we use

Base URL: `https://api-open.data.gov.sg/v2/real-time/api`

| Data | Endpoint | Interval | First day with data (binary search, 8 Nov 2026) |
|---|---|---|---|
| WBGT heat stress | `/weather?api=wbgt` | 15 min, **8 stations** | Late **Jan 2025** (15 Jan = no data, 31 Jan = data) |
| Air temperature | `/air-temperature` | 1 min, ~19 stations | 2016-05-05 |
| Relative humidity | `/relative-humidity` | 1 min | 2016-11-16 |
| Wind speed | `/wind-speed` | 1 min | 2016-12-08 |
| Wind direction | `/wind-direction` | 1 min | 2016-12-01 |
| Rainfall | `/rainfall` | 5 min, ~55 stations | 2016-12-02 |
| PSI (haze) | `/psi` | hourly, by region | 2016-03-09 |
| PM2.5 | `/pm25` | hourly, by region | 2016-03-09 |

The "first day" search assumes data is continuous after that day. Gaps inside the range are possible and must be checked per feed. **No feed gives solar radiation or globe temperature**, which WBGT needs. Rebuilding past WBGT needs an outside source for sunlight (for example ERA5 reanalysis) or a model calibrated on the 2025-2026 overlap.

**HTTP client note:** the API returns **HTTP 403** for Python's default User-Agent (`Python-urllib`). Always send a User-Agent header. `scripts/dgs.py` does this.

**Missing values:** readings can be the string `"NA"`. Parse to null, do not crash.

Query parameters:
- `date=YYYY-MM-DD`: all readings for that day (SGT).
- `date=YYYY-MM-DDTHH:mm:ss`: the latest reading at that moment.
- No `date`: the latest reading.
- `paginationToken`: when a dated request has more pages, the response `data.paginationToken` is set. Pass it back to get the next page. Loop until it is empty.

Response shape (all endpoints): `{"code": 0, "errorMsg": "", "data": {...}}`. `code` 0 means success. Check `code`, not only the HTTP status.

WBGT response example (one station, one record):

```json
{"datetime": "2025-03-01T23:45:00+08:00",
 "item": {"isStationData": true,
  "readings": [{"station": {"id": "S124", "name": "Upper Changi Road North", "townCenter": "Changi"},
                "location": {"latitude": "1.36777", "longitude": "103.982262"},
                "wbgt": "25.5", "heatStress": "Low"}]}}
```

Note: `wbgt` is a string. Convert to a number. Use the number, not the `heatStress` label, for the MOM 32°C rule, because the label bands may not split at 32.

## Dataset APIs (not real-time)

For static datasets (for example PUB flood data if published as a dataset), use the Dataset APIs: list rows, search and filter, download. See https://guide.data.gov.sg/developer-guide/dataset-apis.md. A dataset ID is the `d_...` part of a data.gov.sg dataset URL.
