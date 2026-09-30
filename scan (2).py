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

DOMAINS = ["automotive", "robotics", "fleets", "energy", "agri"]
LENSES = ["sdv", "connectivity", "ai", "data", "twins"]
DOMAIN_LABEL = {
    "automotive": "Automotive",
    "robotics": "Robotics / AV",
    "energy": "Energy",
    "agri": "Agri / industrial",
    "fleets": "Fleets",
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
    "fleets": "commercial and corporate fleets (logistics and delivery fleets, leasing and rental companies, car-sharing and ride-hailing operators, public-transport and bus operators, fleet telematics and fleet-management platforms)",
}

client = anthropic.Anthropic()


# ----------------------------------------------------------------- helpers
def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.UTC):%H:%M:%S}] {msg}", flush=True)


def text_of(resp) -> str:
    return "\n".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


def parse_json(raw: str, expect=(dict, list)):
    """Extract the largest JSON object/array of the expected type from model output.

    Web-search calls interleave prose ("I'll search for...", "[1]", notes) with the JSON,
    so we scan every { or [ and keep the biggest block that parses cleanly.
    """
    raw = re.sub(r"```(?:json)?", "", raw)
    dec = json.JSONDecoder()
    best, i = None, 0
    while i < len(raw):
        if raw[i] in "{[":
            try:
                obj, end = dec.raw_decode(raw, i)
            except json.JSONDecodeError:
                i += 1
                continue
            if isinstance(obj, expect) and (best is None or end - i > best[1]):
                best = (obj, end - i)
            i = end
        else:
            i += 1
    if best is None:
        raise ValueError("no JSON of the expected type found in model output")
    return best[0]


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
    return len([p for p in EDITIONS.glob("*.json") if "candidates" not in p.name]) + 1


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
            items = parse_json(text_of(resp), expect=list)
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
3. Write every item to the house style in §6. HARD word limits (the layout cuts anything longer): headline 11,
   summary 30, so_what 16, each read_across paragraph 40. British English.
   The so_what line states the factual significance in plain words (what changes, for whom). It never
   advises, recommends or proposes actions: no "should", "must", "opportunity to", "time to", "watch for".
   The read-across likewise describes patterns in the week's news; it does not advise.
4. Compute the heat-map and counts. Write the read-across (two paragraphs) last.

Return ONLY a JSON object with this exact shape (no prose, no markdown fences):
{{
  "edition": {edition},
  "week_label": "{week_label}",
  "generated": "{dt.date.today()}",
  "counts": {{"screened": <int>, "qualified": <int>, "customer_relevant": <int>}},
  "heatmap": {{"automotive": {{"sdv":0,"connectivity":0,"ai":0,"data":0,"twins":0}}, "robotics": {{...}}, "fleets": {{...}}, "energy": {{...}}, "agri": {{...}}}},
  "signal": "<item id>",
  "read_across": ["...", "..."],
  "items": [ <item objects per rubric §5: the best 20 at most — every item that will appear on the page (signal,
             up to 3 per domain with total >= 6, up to 6 watch-list items with total 4-5), each with a unique "id"> ]
}}"""
    resp = client.messages.create(
        model=CFG["models"]["curate"],
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_json(text_of(resp), expect=dict)


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
two domain cards; headlines <= 11 words, summaries <= 30 words, so_what <= 16 words, read_across paragraphs
<= 40 words each; British English; no banned words (game-changing, leverage,
ecosystem play); every so_what and read-across paragraph is factual and descriptive, with no advice,
recommendations or proposed actions (rewrite any that contain them). Every item keeps its id.

<edition>
{json.dumps(edition, ensure_ascii=False)}
</edition>

Return ONLY the corrected JSON object, same shape."""
    resp = client.messages.create(
        model=CFG["models"]["review"],
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        fixed = parse_json(text_of(resp), expect=dict)
        if fixed.get("items"):
            return fixed
        log("  review returned no items; keeping curated edition")
    except Exception as exc:  # noqa: BLE001
        log(f"  review output unusable ({exc}); keeping curated edition")
    return edition


# ----------------------------------------------------------------- render
LIMITS = {"headline": 11, "summary": 30, "so_what": 16}
DEAL_LIMITS = {"who": 4, "with": 4, "what": 10}
READ_ACROSS_LIMIT = 40


def n_words(text) -> int:
    return len(str(text or "").split())


def whole_sentences(text, n: int) -> str:
    """Keep as many complete sentences as fit in n words. Never cuts mid-sentence:
    if even the first sentence is longer than n, it is kept whole (tighten() should
    already have rewritten it; the page-fit loop absorbs the rare overrun)."""
    text = str(text or "").strip()
    if n_words(text) <= n:
        return text
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'(])", text)
    kept = []
    for sen in sentences:
        if n_words(" ".join(kept + [sen])) > n:
            break
        kept.append(sen)
    return " ".join(kept) if kept else sentences[0]


def over_limit(edition: dict) -> dict:
    """Collect every field longer than its limit, keyed so tighten() can put rewrites back."""
    todo = {}
    for it in edition.get("items", []):
        for f, n in LIMITS.items():
            if n_words(it.get(f)) > n:
                todo[f"item|{it['id']}|{f}"] = {"limit": n, "text": it[f]}
        for f, n in DEAL_LIMITS.items():
            if it.get("deal") and n_words(it["deal"].get(f)) > n:
                todo[f"deal|{it['id']}|{f}"] = {"limit": n, "text": it["deal"][f]}
    for i, p in enumerate(edition.get("read_across", [])):
        if n_words(p) > READ_ACROSS_LIMIT:
            todo[f"read|{i}|"] = {"limit": READ_ACROSS_LIMIT, "text": p}
    return todo


def tighten(edition: dict) -> dict:
    """Ask the model to rewrite over-length fields as complete, shorter text (one cheap call)."""
    todo = over_limit(edition)
    if not todo:
        return edition
    log(f"tighten: rewriting {len(todo)} over-length fields")
    prompt = f"""Rewrite each text below so it is AT MOST its word limit, in British English.
Rules: keep the key facts (who, what, numbers, dates); write complete sentences, or for headlines and table
cells a complete phrase; never end with an ellipsis or a trailing fragment; do not add facts;
do not add advice or recommendations.

<fields>
{json.dumps(todo, ensure_ascii=False, indent=1)}
</fields>

Return ONLY a JSON object mapping each key to its rewritten text, e.g. {{"item|abc|summary": "..."}}."""
    try:
        resp = client.messages.create(
            model=CFG["models"]["review"],
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        rewrites = parse_json(text_of(resp), expect=dict)
    except Exception as exc:  # noqa: BLE001
        log(f"  tighten failed ({exc}); falling back to whole-sentence trimming")
        return edition
    by_id = {it["id"]: it for it in edition.get("items", [])}
    for key, text in rewrites.items():
        kind, ref, field = (key.split("|") + ["", ""])[:3]
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip().rstrip("…").rstrip()
        if kind == "item" and ref in by_id:
            by_id[ref][field] = text
        elif kind == "deal" and ref in by_id and by_id[ref].get("deal"):
            by_id[ref]["deal"][field] = text
        elif kind == "read" and ref.isdigit() and int(ref) < len(edition.get("read_across", [])):
            edition["read_across"][int(ref)] = text
    return edition


def enforce_limits(edition: dict) -> dict:
    """Final safety net before layout: whole sentences only, never an ellipsis."""
    for it in edition.get("items", []):
        for f, n in LIMITS.items():
            it[f] = whole_sentences(it.get(f, ""), n)
        it["lenses"] = [l for l in it.get("lenses", []) if l in LENSES][:3]
        it.setdefault("sources", [])
    edition["read_across"] = [whole_sentences(p, READ_ACROSS_LIMIT) for p in edition.get("read_across", [])][:2]
    return edition


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
    edition = enforce_limits(edition)
    for max_per_domain, watch_n, deals_n in [(3, 6, 6), (3, 3, 4), (3, 3, 0), (3, 0, 4), (3, 0, 0), (2, 6, 6), (2, 3, 4), (2, 0, 4), (2, 0, 0)]:
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
    ap.add_argument("--rescan", action="store_true", help="ignore saved candidates and edition for this week")
    args = ap.parse_args()

    start, end, week_id, week_label = week_window()
    json_path = EDITIONS / f"{week_id}.json"
    pdf_path = EDITIONS / f"Cubic3-Market-Scan-{week_id}.pdf"

    if args.from_json:
        edition = json.loads(Path(args.from_json).read_text())
        if over_limit(edition) and os.environ.get("ANTHROPIC_API_KEY"):
            edition = tighten(edition)
    elif json_path.exists() and not args.rescan:
        edition = json.loads(json_path.read_text())
        log(f"reusing curated edition {json_path.name} (delete it, or use --rescan, to curate again)")
        if over_limit(edition):
            edition = tighten(edition)
            json_path.write_text(json.dumps(edition, ensure_ascii=False, indent=1))
    else:
        edition_no = next_edition_number()
        cand_path = EDITIONS / f"{week_id}-candidates.json"
        if cand_path.exists() and not args.rescan:
            candidates = json.loads(cand_path.read_text())
            log(f"reusing {len(candidates)} saved candidates from {cand_path.name}")
        else:
            candidates = scan(start, end)
            cand_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=1))
        if not candidates:
            raise SystemExit("Scan returned no candidates — aborting before spending on curation.")
        edition = curate(candidates, edition_no, week_label, start, end)
        edition["counts"]["screened"] = max(edition["counts"].get("screened", 0), len(candidates))
        edition = review(edition)
        edition = tighten(edition)
        json_path.write_text(json.dumps(edition, ensure_ascii=False, indent=1))
        log(f"saved {json_path.name}")

    render_two_pages(edition, pdf_path)
    signal = next((it for it in edition["items"] if it["id"] == edition.get("signal")), edition["items"][0])
    if not args.no_email:
        send_email(pdf_path, edition, signal["headline"])
    log(f"done: {pdf_path.name}")


if __name__ == "__main__":
    sys.exit(main())
