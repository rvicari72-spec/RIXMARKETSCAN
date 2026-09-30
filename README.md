# Cubic³ Market Scan

A weekly two-page PDF scanning news across automotive, robotics/AV, energy and agri/industrial OEMs through
the lenses of SDV, connectivity, AI, data management and digital twins. Runs itself every Monday morning on
GitHub Actions and emails the PDF.

## One-time setup (about 15 minutes)

1. **Create a private GitHub repo** and push this folder to it.

2. **Set the recipient.** Edit `config.yaml` → `email.to` with your work address.

3. **Get an Anthropic API key** at https://console.anthropic.com (Settings → API keys). In the same console,
   an organisation admin must enable **web search** for the API (Settings → Privacy / Tools).

4. **Create a Gmail app password** for the sending mailbox (rixmarketscan@gmail.com):
   Google Account → Security → turn on 2-Step Verification → App passwords → create one named "market scan".
   Copy the 16-character code. This is *not* the account password.

5. **Add three repository secrets** (repo → Settings → Secrets and variables → Actions → New repository secret):

   | Secret | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | the key from step 3 |
   | `EMAIL_USER` | `rixmarketscan@gmail.com` |
   | `EMAIL_APP_PASSWORD` | the 16-character app password from step 4 |

6. **First run:** repo → Actions → "Weekly Market Scan" → Run workflow. Untick *Send the email* the first
   time to get a render-only run; the PDF appears under the run's Artifacts and in `editions/`.

From then on it runs every Monday at 05:00 UTC. Change the time in `.github/workflows/weekly.yml`.

## How it works

`scan.py` runs four passes:

| Pass | Model (config.yaml) | What it does |
|---|---|---|
| scan | `models.scan` | One web-search call per domain, one search per lens plus Japanese and follow-ups |
| curate | `models.curate` | Applies `rubric.md`: scores, selects, writes every item in house style |
| review | `models.review` | Checks word limits, sources, heat-map arithmetic; corrects in place |
| render | — | Fills `template.html`, renders A4 with WeasyPrint, trims optional blocks until exactly 2 pages |

Every edition is saved as `editions/<year>-W<week>.json` (all scored items, including the ones that didn't make
the page) and `editions/Cubic3-Market-Scan-<year>-W<week>.pdf`.

## Steering it

- **What counts as interesting:** edit `rubric.md`. It is pasted into the curate and review prompts verbatim.
- **Who matters:** edit Appendix A of `rubric.md` (accounts, competitors, partners). Names are examples; the
  agent extends each category and marks additions `"inferred"` in the JSON so you can confirm or reject them.
- **Look and feel:** edit `template.html`. Keep the fixed slots — the two-page fit depends on them.
- **Cost:** lower `scan.max_searches_per_domain` or point `models.curate` at Sonnet.
- **Models:** check current model names at https://docs.claude.com/en/docs/about-claude/models before
  changing `config.yaml`.

## Running locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  EMAIL_USER=...  EMAIL_APP_PASSWORD=...
python scan.py --no-email                                   # full scan, no send
python scan.py --from-json editions/2026-W37.json --no-email  # re-render after editing the JSON or template
```
