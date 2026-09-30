"""
Cubic³ Market Scan — weekly pipeline.

Steps: scan (web search per domain) -> curate (score + write) -> review (QA)
       -> render (Jinja + WeasyPrint, must be 2 pages) -> email -> archive.

Run locally:   python scan.py            (full run, sends email)
Dry run:       python scan.py --no-email (renders PDF, skips send)
Re-render:     python scan.py --from-json editions/2026-W37.json --no-email
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

import anthropic
import yaml
from jinja2 import Environment, FileSystemLoader
from pypdf import PdfReader
from weasyprint import HTML

ROOT = Path(__file__).parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
RUBRIC = (ROOT / "rubric.md").read_text()
EDITIONS = ROOT / "editions"
EDITIONS.mkdir(exist_ok=True)

DOMAINS = ["automotive", "robotics", "energy", "agri"]
LENSES = ["sdv", "connectivity", "ai", "data", "twins"]
DOMAIN_LABEL = {
    "automotive": "Automotive",
    "robotics": "Robotics / AV",
    "energy": "Energy",
    "agri": "Agri / industrial",
}
LENS_LABEL = {
    "sdv": "SDV", "connectivity": "Connectivity", "ai": "AI",
    "data": "Data mgmt", "twins": "Digital twins",
}
DOMAIN_BRIEF = {
    "automotive": "automotive OEMs (passenger and commercial vehicle makers and their captive software units)",
    "robotics": "robotics OEMs and autonomous-vehicle companies (humanoid, warehouse, industrial robots; robotaxi and AV developers)",
    "energy": "energy (charge-point operators, utilities and grid operators, battery and storage OEMs, V2G)",
    "agri": "agricultural, construction, mining and off-highway equipment OEMs",
}

client = anthropic.Anthropic()


# ----------------------------------------------------------------- helpers
def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.UTC):%H:%M:%S}] {msg}", flush=True)


def text_of(resp) -> str:
    return "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def parse_json(raw: str):
    """Tolerate ```json fences and leading prose."""
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start = min(i for i in (raw.find("{"), raw.find("[")) if i >= 0)
    return json.loads(raw[start:])


def week_window(today: dt.date | None = None):
    """Monday..Sunday of the most recent complete week (scan runs on Monday)."""
    today = today or dt.date.today()
    this_monday = today - dt.timedelta(days=today.weekday())
    start = this_monday - dt.timedelta(days=7) if today.weekday() == 0 else this_monday
    end = start + dt.timedelta(days=6)
    iso = start.isocalendar()
    label = (
        f"Week of {start.day}–{end.day} {end:%B %Y}"
        if start.month == end.month
        else f"Week of {start.day} {start:%b} – {end.day} {end:%b %Y}"
    )
    return start, end, f"{iso.year}-W{iso.week:02d}", label


def next_edition_number() -> int:
    return len(list(EDITIONS.glob("*.json"))) + 1


# ------------------------------------------------------------------- scan
def scan(start: dt.date, end: dt.date) -> list[dict]:
    """One web-search-enabled call per domain; returns raw candidates."""
    candidates: list[dict] = []
    for d in DOMAINS:
        log(f"scan: {d}")
        prompt = f"""You are the research assistant for a weekly market scan.

Domain: {DOMAIN_BRIEF[d]}.
Lenses: SDV (vehicle OS, OTA, feature-on-demand, central compute); connectivity (eSIM, MVNO deals,
satellite/NTN, roaming, network APIs); AI (edge inference, fleet models, copilots, autonomy licensing);
data management (platforms, marketplaces, data-access regulation); digital twins (live asset/fleet models).

Search the web for news published between {start:%d %B %Y} and {end:%d %B %Y} in this domain that touches at
least one lens. Run one search per lens, then up to three more to chase anything promising. Prefer company
newsrooms, regulators and standards bodies, and trade press over general or aggregator sites. Search in English;
also run one search in Japanese for Japanese companies in this domain.

Return ONLY a JSON array (no prose) of up to 15 candidates, each:
{{"headline": "...", "actors": ["..."], "lenses": ["sdv"|"connectivity"|"ai"|"data"|"twins"],
  "gist": "2 sentences of facts", "outlet": "...", "date": "YYYY-MM-DD", "url": "...",
  "tier": 1|2|3}}
tier: 1 = company newsroom / regulator / standards body / SoftBank Group; 2 = trade press or analyst; 3 = general press or social.
Exclude anything outside the date window. De-duplicate the same event across outlets (keep the best source)."""
        resp = client.messages.create(
            model=CFG["models"]["scan"],
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": CFG["scan"]["max_searches_per_domain"]}],
        )
        try:
            items = parse_json(text_of(resp))
        except Exception as exc:  # noqa: BLE001
            log(f"  could not parse scan output for {d}: {exc}")
            items = []
        for it in items:
            it["domain"] = d
        log(f"  {len(items)} candidates")
        candidates.extend(items)
    return candidates


# ----------------------------------------------------------------- curate
def curate(candidates: list[dict], edition: int, week_label: str, start: dt.date, end: dt.date) -> dict:
    log("curate")
    prompt = f"""You are the editor of the Cubic³ Market Scan. Apply the rubric below exactly.

<rubric>
{RUBRIC}
</rubric>

Edition {edition}, {week_label} ({start} to {end}). Today's date is {dt.date.today()}.

<candidates>
{json.dumps(candidates, ensure_ascii=False, indent=1)}
</candidates>

Tasks, in order:
1. Merge duplicates. Score every candidate per rubric §3, using the actor list in Appendix A and extending
   categories to comparable companies as the appendix instructs (flag those with "inferred").
2. Apply the selection rules in §4.
3. Write every item to the house style in §6 and the word limits in §5. British English.
4. Compute the heat-map and counts. Write the read-across (two paragraphs) and the implications box last.

Return ONLY a JSON object with this exact shape (no prose, no markdown fences):
{{
  "edition": {edition},
  "week_label": "{week_label}",
  "generated": "{dt.date.today()}",
  "counts": {{"screened": <int>, "qualified": <int>, "customer_relevant": <int>}},
  "heatmap": {{"automotive": {{"sdv":0,"connectivity":0,"ai":0,"data":0,"twins":0}}, "robotics": {{...}}, "energy": {{...}}, "agri": {{...}}}},
  "signal": "<item id>",
  "read_across": ["...", "..."],
  "implications": {{"position": "...", "pipeline": "...", "portfolio": "...", "softbank": "" }},
  "items": [ <item objects per rubric §5, ALL scored candidates with total >= 4, each with a unique "id"> ]
}}"""
    resp = client.messages.create(
        model=CFG["models"]["curate"],
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json(text_of(resp))


# ----------------------------------------------------------------- review
def review(edition: dict) -> dict:
    log("review")
    prompt = f"""You are the sub-editor. Check this Market Scan edition against the rubric and return a corrected
version. Fix, do not comment.

<rubric>
{RUBRIC}
</rubric>

Checks: every qualifying item (score.total >= 6) has at least one source with tier 1 or 2 and a date; "signal"
is the id of the highest-scoring item; heatmap counts equal the number of items with total >= 6 tagged with
each domain x lens; counts.qualified equals the number of items with total >= 6; no actor appears in more than
two domain cards; headlines <= 14 words, summaries <= 60 words, so_what <= 25 words, read_across paragraphs
<= 70 words each, implications <= 35 words each; British English; no banned words (game-changing, leverage,
ecosystem play). Every item keeps its id.

<edition>
{json.dumps(edition, ensure_ascii=False)}
</edition>

Return ONLY the corrected JSON object, same shape."""
    resp = client.messages.create(
        model=CFG["models"]["review"],
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json(text_of(resp))


# ----------------------------------------------------------------- render
def heat_class(v: int) -> str:
    return "h0" if v == 0 else "h1" if v <= 2 else "h2" if v <= 5 else "h3"


def render(edition: dict, out_pdf: Path, max_per_domain: int = 3, watch_n: int = 6, deals_n: int = 6) -> int:
    items = edition["items"]
    by_id = {it["id"]: it for it in items}
    qualifying = sorted((it for it in items if it["score"]["total"] >= 6), key=lambda x: -x["score"]["total"])
    signal = by_id.get(edition.get("signal")) or (qualifying[0] if qualifying else items[0])
    by_domain = {d: [it for it in qualifying if it["domain"] == d and it is not signal][:max_per_domain] for d in DOMAINS}
    deals = [dict(it["deal"], domain=it["domain"]) for it in qualifying if it.get("deal") and it["deal"].get("who")][:deals_n]
    watch = [it for it in items if 4 <= it["score"]["total"] <= 5][:watch_n]

    env = Environment(loader=FileSystemLoader(ROOT), autoescape=True)
    html = env.get_template("template.html").render(
        e=edition, signal=signal, by_domain=by_domain, deals=deals, watch=watch,
        domains=DOMAINS, lenses=LENSES, domain_label=DOMAIN_LABEL, lens_label=LENS_LABEL, heat_class=heat_class,
    )
    HTML(string=html, base_url=str(ROOT)).write_pdf(out_pdf)
    return len(PdfReader(str(out_pdf)).pages)


def render_two_pages(edition: dict, out_pdf: Path) -> None:
    """Progressively trim optional content until the PDF is exactly two pages."""
    for max_per_domain, watch_n, deals_n in [(3, 6, 6), (3, 3, 4), (3, 0, 4), (3, 0, 0), (2, 0, 0)]:
        pages = render(edition, out_pdf, max_per_domain, watch_n, deals_n)
        log(f"render: {pages} pages (cards {max_per_domain}, watch {watch_n}, deals {deals_n})")
        if pages == 2:
            return
        if pages < 2:
            raise SystemExit("Edition rendered to fewer than 2 pages — check content.")
    raise SystemExit("Could not fit the edition on two pages; shorten item copy in the rubric limits.")


# ------------------------------------------------------------------ email
def send_email(pdf: Path, edition: dict, signal_headline: str) -> None:
    user = os.environ["EMAIL_USER"]
    pwd = os.environ["EMAIL_APP_PASSWORD"]
    msg = EmailMessage()
    msg["From"] = f"{CFG['email']['from_name']} <{user}>"
    msg["To"] = ", ".join(CFG["email"]["to"])
    msg["Subject"] = f"Market Scan {edition['edition']:03d} — {signal_headline}"
    body = (
        f"{edition['week_label']}\n\nSignal of the week: {signal_headline}\n\n"
        + "\n\n".join(edition["read_across"])
        + "\n\nThe two-page PDF is attached."
    )
    msg.set_content(body)
    msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf", filename=pdf.name)
    with smtplib.SMTP_SSL(CFG["email"]["smtp_host"], CFG["email"]["smtp_port"]) as s:
        s.login(user, pwd)
        s.send_message(msg)
    log(f"email sent to {msg['To']}")


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--from-json", help="skip scan/curate/review; render this edition JSON")
    args = ap.parse_args()

    start, end, week_id, week_label = week_window()
    json_path = EDITIONS / f"{week_id}.json"
    pdf_path = EDITIONS / f"Cubic3-Market-Scan-{week_id}.pdf"

    if args.from_json:
        edition = json.loads(Path(args.from_json).read_text())
    else:
        edition_no = next_edition_number()
        candidates = scan(start, end)
        if not candidates:
            raise SystemExit("Scan returned no candidates — aborting before spending on curation.")
        edition = curate(candidates, edition_no, week_label, start, end)
        edition["counts"]["screened"] = max(edition["counts"].get("screened", 0), len(candidates))
        edition = review(edition)
        json_path.write_text(json.dumps(edition, ensure_ascii=False, indent=1))
        log(f"saved {json_path.name}")

    render_two_pages(edition, pdf_path)
    signal = next((it for it in edition["items"] if it["id"] == edition.get("signal")), edition["items"][0])
    if not args.no_email:
        send_email(pdf_path, edition, signal["headline"])
    log(f"done: {pdf_path.name}")


if __name__ == "__main__":
    sys.exit(main())
