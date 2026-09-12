# -*- coding: utf-8 -*-
"""PD.Radar self-updating engine.

Runs daily via GitHub Actions (.github/workflows/auto-update.yml). Does two jobs:

1. RE-MINE the flagship thread (25136258) so its numbers stay fresh —
   rewrites recommendations.json only when something actually changed.
2. DISCOVER new Ask HN question threads (points>=80, comments>=80),
   mine them with the same citation lexicon, and add the ones that
   qualify (>=5 resources matched with >=3 citations each) as new
   leaderboards under data/threads/. The site picks them up from
   data/threads.json — no manual commits, no code changes.

Honesty rules preserved:
- citations = distinct comments naming the resource (verifiable against the thread)
- a thread only gets published if the lexicon genuinely matches it — no fabricated data
- prices remain public-knowledge estimates, labelled on the page

Pure stdlib. Runs anywhere, including GitHub Actions runners.
"""
import json, os, re, html, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
THREADS_DIR = os.path.join(DATA_DIR, "threads")
INDEX_PATH = os.path.join(DATA_DIR, "threads.json")
STATE_PATH = os.path.join(DATA_DIR, "discovery_state.json")
RECS_PATH = os.path.join(BASE, "recommendations.json")
LAST_CHECKED_PATH = os.path.join(DATA_DIR, "last_checked.json")

FLAGSHIP_ID = "25136258"
FLAGSHIP_TITLE = "Ask HN: What is the best money you have spent on professional development?"
FLAGSHIP_META = "(id 25136258, 524 pts, 540 comments, 2020-11-18)"

# Only import the lexicon + matchers from the existing pipeline so the
# ranking method stays IDENTICAL across threads.
from extract_rank import LEXICON, matches, flatten_comments, clean, load_flat

MIN_POINTS = 80
MIN_COMMENTS = 80
MIN_RESOURCES = 5      # a new thread needs >=5 resources matched
MIN_CITES = 3          # ...each with >=3 citations, to publish
MAX_NEW_PER_RUN = 3    # gentle on the Algolia API; quality over volume
SKIP_DAYS = 45         # days to remember a rejected thread before re-checking

# A thread is only mined if its title asks for recommendations. This is the
# honesty gate: rant/vent/news threads ("Is all of FAANG like this?") produce
# nothing but lexicon false-positives and must never become leaderboards.
INTENT_KEYWORDS = ["best", "book", "books", "recommend", "course", "learn",
                   "resource", "resources", "worth", "advice", "skill",
                   "skills", "career", "study"]
RANT_PATTERNS = ["like this", "rant", "vent", "just me", "wtf", "nuke",
                 "stopped", "banned", "shut down", "died", "layoff"]

def title_has_intent(title):
    t = title.lower()
    has_intent = any(k in t for k in INTENT_KEYWORDS)
    has_rant = any(p in t for p in RANT_PATTERNS)
    # A title with genuine recommendation intent (best/books/course/etc.)
    # is never auto-rejected just because a rant word appears as a substring —
    # e.g. "Best career books to read after a layoff?" should pass.
    if has_intent and not has_rant:
        return True
    if has_intent and has_rant:
        # Only reject if the rant phrasing is a strong, standalone signal,
        # not an incidental substring inside an otherwise recommendation-shaped title.
        strong_rant = ["is this just me", "wtf", "rant:", "vent:"]
        return not any(p in t for p in strong_rant)
    return False

DISCOVERY_QUERIES = [
    "best money you have spent",
    "what books changed your career",
    "best books",
    "books worth reading",
    "best course",
    "worth paying for",
    "best investment in your career",
]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pd-engine-auto/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def write_heartbeat():
    """
    Writes on EVERY successful run, regardless of whether the flagship or
    any thread actually changed. Deliberately separate from
    recommendations.json's generated_at, which only updates on real
    content changes. Without this, the site's displayed date can look
    stale for weeks even though the pipeline checked every single day.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_CHECKED_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_checked": now_iso()}, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- fetching
def fetch_story_comments(story_id):
    """Tree (hierarchy) + flat pages (completeness), deduped by string id."""
    all_comments = {}
    try:
        tree = get(f"https://hn.algolia.com/api/v1/items/{story_id}")
        flatten_comments(tree, all_comments)
    except Exception as e:
        print(f"  WARNING: story tree fetch failed for {story_id}: {e}", file=sys.stderr)
    page = 0
    while page < 5:
        url = (f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}"
               f"&hitsPerPage=1000&page={page}")
        data = get(url)
        hits = data.get("hits", [])
        nb_hits = data.get("nbHits", 0)
        for hit in hits:
            cid = str(hit.get("objectID"))
            txt = hit.get("comment_text") or ""
            if txt and cid and cid not in all_comments:
                all_comments[cid] = {
                    "id": cid,
                    "author": hit.get("author") or "anon",
                    "text": clean(txt),
                    "created_at": hit.get("created_at") or "",
                    "points": None,
                }
        if page * 1000 + len(hits) >= nb_hits or not hits:
            break
        page += 1
    return all_comments

# ---------------------------------------------------------------- mining
def mine_comments(all_comments, source_label, min_cites=1):
    """Same matching method as the flagship extract_rank.py.

    min_cites=1 for the flagship (byte-compatible with the original
    extract_rank.py ranking: every resource with >=1 citation appears).
    Discovered threads pass MIN_CITES explicitly so weak matches never
    publish — see the call site in process_new_threads below.
    """
    results = []
    for item in LEXICON:
        citing = [c for c in all_comments.values() if matches(item, c["text"])]
        if len(citing) < min_cites:
            continue
        citing_sorted = sorted(citing, key=lambda c: c.get("points") or 0, reverse=True)
        top = [{"author": c["author"], "snippet": c["text"][:200], "id": c["id"]}
               for c in citing_sorted[:3]]
        results.append({
            "title": item["title"], "type": item["type"], "creator": item["creator"],
            "price_est": item["price_est"],
            "price_label": "est." if item["price_est"] else "free",
            "roles": item["roles"], "citations": len(citing),
            "top_comments": top, "score": round(len(citing) * 1.0, 1),
            "source": source_label,
        })
    results.sort(key=lambda r: (-r["citations"], r["title"].lower()))
    def tier(p):
        if p == 0: return "Free"
        if p < 50: return "Under $50"
        if p < 150: return "$50-$150"
        return "$150+"
    for i, r in enumerate(results):
        r["tier"] = tier(r["price_est"])
        r["rank"] = i + 1
    return results

def thread_doc(story, results, total_comments):
    return {
        "generated_at": now_iso(),
        "source_item_id": int(story["id"]),
        "total_comments": total_comments,
        "matched_resources": len(results),
        "recommendations": results,
    }

# ---------------------------------------------------------------- index I/O
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def load_index():
    idx = load_json(INDEX_PATH, None)
    if idx:
        return idx
    # bootstrap the index from the current flagship recommendations.json
    recs = load_json(RECS_PATH, {})
    return [{
        "id": FLAGSHIP_ID,
        "title": FLAGSHIP_TITLE,
        "short": FLAGSHIP_TITLE.replace("Ask HN: ", ""),
        "points": 524, "comments": recs.get("total_comments", 540),
        "resources": recs.get("matched_resources", 24),
        "updated_at": recs.get("generated_at", now_iso()),
        "file": "recommendations.json",
        "flagship": True,
    }]

def save_index(idx):
    # Flagship always first (it's the brand); remaining threads by points.
    idx.sort(key=lambda t: (0 if t.get("flagship") else 1, -int(t.get("points", 0)), str(t.get("id"))))
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- flagship re-mine
def remine_flagship():
    print("[1/3] re-mining flagship thread ...")
    comments = fetch_story_comments(FLAGSHIP_ID)
    results = mine_comments(comments, FLAGSHIP_TITLE + " " + FLAGSHIP_META, min_cites=1)
    new_doc = thread_doc({"id": FLAGSHIP_ID}, results, len(comments))
    old_doc = load_json(RECS_PATH, {})
    old_map = {r["title"]: r["citations"] for r in old_doc.get("recommendations", [])}
    new_map = {r["title"]: r["citations"] for r in new_doc["recommendations"]}
    changed = (old_doc.get("total_comments") != new_doc["total_comments"] or
               old_doc.get("matched_resources") != new_doc["matched_resources"] or
               old_map != new_map)
    if changed:
        with open(RECS_PATH, "w", encoding="utf-8") as f:
            json.dump(new_doc, f, ensure_ascii=False, indent=2)
        print(f"  flagship CHANGED: {new_doc['total_comments']} comments, "
              f"{new_doc['matched_resources']} resources -> recommendations.json rewritten")
    else:
        print("  flagship unchanged")
    return changed

# ---------------------------------------------------------------- discovery
def discover_candidates():
    print("[2/3] discovering candidate threads ...")
    found = {}
    for q in DISCOVERY_QUERIES:
        url = ("https://hn.algolia.com/api/v1/search?tags=ask_hn&query="
               + urllib.parse.quote(q)
               + f"&numericFilters=points%3E={MIN_POINTS},num_comments%3E={MIN_COMMENTS}"
               + "&hitsPerPage=30")
        try:
            hits = get(url).get("hits", [])
        except Exception as e:
            print(f"  query '{q}' failed: {e}", file=sys.stderr)
            continue
        for h in hits:
            sid = str(h.get("objectID"))
            if sid and sid != FLAGSHIP_ID and sid not in found:
                found[sid] = {
                    "id": sid,
                    "title": h.get("title") or "",
                    "points": h.get("points") or 0,
                    "comments": h.get("num_comments") or 0,
                    "created_at": h.get("created_at") or "",
                }
    print(f"  discovery found {len(found)} unique candidates")
    return found

def load_state():
    return load_json(STATE_PATH, {"skipped": {}})  # skipped: {id: iso_date}

def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)

def days_since(iso):
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).days
    except Exception:
        return SKIP_DAYS + 1

def process_new_threads(candidates, index, state):
    print("[3/3] mining new threads ...")
    known = {t["id"] for t in index}
    skipped = state.get("skipped", {})
    fresh = [c for c in candidates.values()
             if c["id"] not in known
             and (c["id"] not in skipped or days_since(skipped[c["id"]]) > SKIP_DAYS)]
    fresh.sort(key=lambda c: (-c["points"], -c["comments"]))
    added = 0
    for c in fresh[:MAX_NEW_PER_RUN]:
        if not title_has_intent(c["title"]):
            skipped[c["id"]] = now_iso()
            save_state(state | {"skipped": skipped})
            print(f"  skipped (no recommendation intent in title): {c['title']}")
            continue
        print(f"  trying: {c['title']} ({c['points']} pts, {c['comments']} comments)")
        comments = fetch_story_comments(c["id"])
        label = f"{c['title']} (id {c['id']}, {c['points']} pts, {c['comments']} comments, {c['created_at'][:10]})"
        # FIXED: was calling mine_comments without min_cites, silently
        # defaulting to 1 instead of the intended MIN_CITES=3 — meaning
        # single-citation resources could leak into newly published
        # threads despite the module's own stated design intent.
        results = mine_comments(comments, label, min_cites=MIN_CITES)
        if len(results) >= MIN_RESOURCES:
            doc = thread_doc(c, results, len(comments))
            os.makedirs(THREADS_DIR, exist_ok=True)
            out = os.path.join(THREADS_DIR, f"{c['id']}.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            index.append({
                "id": c["id"], "title": c["title"],
                "short": re.sub(r"^Ask HN:\s*", "", c["title"])[:70],
                "points": c["points"], "comments": c["comments"],
                "resources": len(results),
                "updated_at": doc["generated_at"],
                "file": f"data/threads/{c['id']}.json",
                "flagship": False,
            })
            added += 1
            print(f"  ADDED: {c['title']} -> {out} ({len(results)} resources)")
        else:
            skipped[c["id"]] = now_iso()
            save_state(state | {"skipped": skipped})
            print(f"  skipped (only {len(results)} resources matched < {MIN_RESOURCES})")
    return added

def main():
    os.chdir(BASE)
    flag_changed = remine_flagship()
    index = load_index()
    state = load_state()
    candidates = discover_candidates()
    added = process_new_threads(candidates, index, state)
    save_index(index)
    write_heartbeat()  # runs every time, independent of flag_changed/added
    print(f"done: flagship_changed={flag_changed} new_threads_added={added} total_threads={len(index)}")

if __name__ == "__main__":
    main()
