# -*- coding: utf-8 -*-
"""Extract real PD recommendations from the HN thread and rank them.

Uses the actual 540 comments + story tree fetched from Algolia.
Scoring is based on REAL citation counts (how many distinct comments name
the resource), not invented upvotes. Price is a public-knowledge estimate
and is labelled as such on the page.
"""
import json, os, re, html, datetime
from datetime import timezone

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "raw")

def flatten_comments(node, out):
    """Recursively flatten the HN story tree into comment dicts."""
    for kid in node.get("children", []):
        cid = str(kid.get("id"))  # normalize to string so tree + flat merges dedupe (int vs str ids were double-counting)
        text = kid.get("text") or ""
        if text and cid:
            out[cid] = {
                "id": cid,
                "author": kid.get("author") or "anon",
                "text": clean(text),
                "created_at": kid.get("created_at") or "",
                "points": kid.get("points"),  # None for most items via Algolia
            }
        if kid.get("children"):
            flatten_comments(kid, out)
    return out

def clean(text):
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)          # strip tags
    text = re.sub(r"\s+", " ", text).strip()
    return text

def load_flat(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for hit in json.load(f):
            cid = str(hit.get("objectID"))  # string, same as normalized tree ids
            txt = hit.get("comment_text") or ""
            if txt and cid:
                out[cid] = {
                    "id": cid,
                    "author": hit.get("author") or "anon",
                    "text": clean(txt),
                    "created_at": hit.get("created_at") or "",
                    "points": None,
                }
    return out

# --- Curated lexicon of well-known professional-development resources.
# Each title is verified against the actual comments; only matched items
# appear in the output. price_est is a public-knowledge estimate (labelled).
LEXICON = [
    # Books
    {"title": "Designing Data-Intensive Applications", "type": "book", "creator": "Martin Kleppmann", "price_est": 45, "roles": ["engineer", "data"], "hotkey": ["ddia", "designing data-intensive"]},
    {"title": "The Pragmatic Programmer", "type": "book", "creator": "Hunt & Thomas", "price_est": 45, "roles": ["engineer"], "hotkey": ["pragmatic programmer"]},
    {"title": "Staff Engineer: Leadership Beyond the Management Track", "type": "book", "creator": "Will Larson", "price_est": 35, "roles": ["engineer", "staff"], "hotkey": ["staff engineer"]},
    {"title": "A Philosophy of Software Design", "type": "book", "creator": "John Ousterhout", "price_est": 30, "roles": ["engineer"], "hotkey": ["philosophy of software design", "ousterhout"]},
    {"title": "Refactoring", "type": "book", "creator": "Martin Fowler", "price_est": 45, "roles": ["engineer"], "hotkey": ["refactoring"]},
    {"title": "High Output Management", "type": "book", "creator": "Andy Grove", "price_est": 20, "roles": ["manager", "founder"], "hotkey": ["high output management", "andy grove"]},
    {"title": "Code: The Hidden Language of Computer Hardware and Software", "type": "book", "creator": "Charles Petzold", "price_est": 25, "roles": ["engineer"], "hotkey": ["code: the hidden language"]},
    {"title": "The Mythical Man-Month", "type": "book", "creator": "Fred Brooks", "price_est": 20, "roles": ["engineer", "manager"], "hotkey": ["mythical man-month"]},
    {"title": "Working Effectively with Legacy Code", "type": "book", "creator": "Michael Feathers", "price_est": 40, "roles": ["engineer"], "hotkey": ["legacy code"]},
    {"title": "Crucial Conversations", "type": "book", "creator": "Patterson et al.", "price_est": 15, "roles": ["manager", "all"], "hotkey": ["crucial conversations"]},
    {"title": "The Manager's Path", "type": "book", "creator": "Camille Fournier", "price_est": 30, "roles": ["manager"], "hotkey": ["manager's path"]},
    {"title": "An Elegant Puzzle", "type": "book", "creator": "Will Larson", "price_est": 30, "roles": ["manager"], "hotkey": ["elegant puzzle"]},
    {"title": "Accelerate", "type": "book", "creator": "Forsgren, Humble & Kim", "price_est": 30, "roles": ["manager", "engineer"], "hotkey": ["accelerate"]},
    {"title": "The Goal", "type": "book", "creator": "Eliyahu Goldratt", "price_est": 20, "roles": ["manager", "founder"], "hotkey": ["the goal"]},
    {"title": "Thinking in Systems", "type": "book", "creator": "Donella Meadows", "price_est": 18, "roles": ["all"], "hotkey": ["thinking in systems"]},
    {"title": "How to Win Friends and Influence People", "type": "book", "creator": "Dale Carnegie", "price_est": 15, "roles": ["all"], "hotkey": ["how to win friends"]},
    {"title": "Never Split the Difference", "type": "book", "creator": "Chris Voss", "price_est": 20, "roles": ["founder", "manager"], "hotkey": ["never split the difference"]},
    {"title": "Thinking, Fast and Slow", "type": "book", "creator": "Daniel Kahneman", "price_est": 20, "roles": ["all"], "hotkey": ["thinking fast and slow"]},
    {"title": "Deep Work", "type": "book", "creator": "Cal Newport", "price_est": 18, "roles": ["engineer", "all"], "hotkey": ["deep work"]},
    {"title": "Clean Code", "type": "book", "creator": "Robert C. Martin", "price_est": 35, "roles": ["engineer"], "hotkey": ["clean code"]},
    {"title": "The Clean Coder", "type": "book", "creator": "Robert C. Martin", "price_est": 30, "roles": ["engineer"], "hotkey": ["clean coder"]},
    {"title": "Domain-Driven Design", "type": "book", "creator": "Eric Evans", "price_est": 55, "roles": ["engineer"], "hotkey": ["domain-driven design", "ddd"]},
    {"title": "Building Microservices", "type": "book", "creator": "Sam Newman", "price_est": 45, "roles": ["engineer"], "hotkey": ["building microservices"]},
    {"title": "Site Reliability Engineering", "type": "book", "creator": "Google (Beyer et al.)", "price_est": 35, "roles": ["engineer", "sre"], "hotkey": ["site reliability engineering", "sre book"]},
    {"title": "The Phoenix Project", "type": "book", "creator": "Kim, Behr & Spafford", "price_est": 20, "roles": ["manager", "engineer"], "hotkey": ["phoenix project"]},
    {"title": "Continuous Delivery", "type": "book", "creator": "Humble & Farley", "price_est": 40, "roles": ["engineer"], "hotkey": ["continuous delivery"]},
    {"title": "The Effective Executive", "type": "book", "creator": "Peter Drucker", "price_est": 18, "roles": ["manager", "founder"], "hotkey": ["effective executive"]},
    {"title": "Getting Things Done", "type": "book", "creator": "David Allen", "price_est": 15, "roles": ["all"], "hotkey": ["getting things done", "gtd"]},
    {"title": "The Art of Doing Science and Engineering", "type": "book", "creator": "Richard Hamming", "price_est": 30, "roles": ["engineer"], "hotkey": ["hamming"]},
    {"title": "The Structure of Scientific Revolutions", "type": "book", "creator": "Thomas Kuhn", "price_est": 18, "roles": ["all"], "hotkey": ["structure of scientific revolutions"]},
    # Courses / programs
    {"title": "CS50x: Intro to Computer Science", "type": "course", "creator": "Harvard (David Malan)", "price_est": 0, "roles": ["engineer", "beginner"], "hotkey": ["cs50"]},
    {"title": "The Odin Project", "type": "course", "creator": "Open source", "price_est": 0, "roles": ["engineer", "beginner"], "hotkey": ["odin project"]},
    {"title": "freeCodeCamp", "type": "course", "creator": "Open source", "price_est": 0, "roles": ["engineer", "beginner"], "hotkey": ["freecodecamp"]},
    {"title": "MIT OpenCourseWare", "type": "course", "creator": "MIT", "price_est": 0, "roles": ["all"], "hotkey": ["mit opencourseware", "mit ocw"]},
    {"title": "Coursera Specializations", "type": "course", "creator": "Various universities", "price_est": 50, "roles": ["all"], "hotkey": ["coursera"]},
    {"title": "The Cult of Done", "type": "course", "creator": "Bre Pettis & Kio Stark", "price_est": 10, "roles": ["founder", "all"], "hotkey": ["cult of done"]},
    {"title": "Lambda School", "type": "course", "creator": "Bloom Institute", "price_est": 0, "roles": ["engineer"], "hotkey": ["lambda school"]},
    # Tools / services / communities
    {"title": "Anki", "type": "tool", "creator": "Anki (open source)", "price_est": 0, "roles": ["all"], "hotkey": ["anki"]},
    {"title": "Roam Research", "type": "tool", "creator": "Roam", "price_est": 15, "roles": ["all"], "hotkey": ["roam"]},
    {"title": "Notion", "type": "tool", "creator": "Notion", "price_est": 0, "roles": ["all"], "hotkey": ["notion"]},
    {"title": "LeetCode", "type": "tool", "creator": "LeetCode", "price_est": 35, "roles": ["engineer"], "hotkey": ["leetcode"]},
    {"title": "HackerRank", "type": "tool", "creator": "HackerRank", "price_est": 0, "roles": ["engineer"], "hotkey": ["hackerrank"]},
    {"title": "Exercism", "type": "tool", "creator": "Exercism", "price_est": 0, "roles": ["engineer"], "hotkey": ["exercism"]},
    {"title": "Khan Academy", "type": "tool", "creator": "Khan Academy", "price_est": 0, "roles": ["all"], "hotkey": ["khan academy"]},
    {"title": "Brilliant", "type": "tool", "creator": "Brilliant", "price_est": 15, "roles": ["all"], "hotkey": ["brilliant"]},
    {"title": "MasterClass", "type": "tool", "creator": "MasterClass", "price_est": 15, "roles": ["all"], "hotkey": ["masterclass"]},
    {"title": "Y Combinator Startup School", "type": "tool", "creator": "Y Combinator", "price_est": 0, "roles": ["founder"], "hotkey": ["startup school"]},
    {"title": "Stripe Atlas", "type": "tool", "creator": "Stripe", "price_est": 500, "roles": ["founder"], "hotkey": ["stripe atlas"]},
    {"title": "Toastmasters", "type": "tool", "creator": "Toastmasters International", "price_est": 10, "roles": ["all"], "hotkey": ["toastmasters"]},
    {"title": "Engineering Management Mentor (community)", "type": "tool", "creator": "r/ExperiencedDevs & peers", "price_est": 0, "roles": ["manager"], "hotkey": ["experienceddevs"]},
    {"title": "Writing / blogging practice", "type": "tool", "creator": "Personal practice", "price_est": 0, "roles": ["all"], "hotkey": ["blog", "writing"]},
    {"title": "Therapy / coaching", "type": "tool", "creator": "Professional services", "price_est": 100, "roles": ["all"], "hotkey": ["therapy", "coach"]},
]

def matches(lex_item, text):
    t = text.lower()
    for key in lex_item["hotkey"]:
        if key in t:
            return True
    # also match full title (case-insensitive)
    if lex_item["title"].lower() in t:
        return True
    return False

def main():
    # 1. Collect all comments (tree = hierarchy + flat = completeness)
    all_comments = {}
    with open(os.path.join(RAW, "story_tree.json"), encoding="utf-8") as f:
        tree = json.load(f)
    flatten_comments(tree, all_comments)
    all_comments.update(load_flat(os.path.join(RAW, "comments_p0.json")))
    print(f"total unique comments: {len(all_comments)}")

    # 2. Match lexicon against comments, tally citations
    results = []
    for item in LEXICON:
        citing = [c for c in all_comments.values() if matches(item, c["text"])]
        if not citing:
            continue
        citing_sorted = sorted(citing, key=lambda c: c.get("points") or 0, reverse=True)
        top = []
        for c in citing_sorted[:3]:
            snippet = c["text"][:200]
            top.append({"author": c["author"], "snippet": snippet, "id": c["id"]})
        results.append({
            "title": item["title"],
            "type": item["type"],
            "creator": item["creator"],
            "price_est": item["price_est"],
            "price_label": "est." if item["price_est"] else "free",
            "roles": item["roles"],
            "citations": len(citing),
            "top_comments": top,
            "score": round(len(citing) * 1.0, 1),
            "source": "Ask HN: What is the best money you have spent on professional development? (id 25136258, 524 pts, 540 comments, 2020-11-18)",
        })

    # 3. Rank, add tier by price
    results.sort(key=lambda r: (-r["citations"], r["title"].lower()))
    def tier(p):
        if p == 0: return "Free"
        if p < 50: return "Under $50"
        if p < 150: return "$50-$150"
        return "$150+"
    for r in results:
        r["tier"] = tier(r["price_est"])
        r["rank"] = results.index(r) + 1

    # 4. Write outputs
    out_dir = BASE
    with open(os.path.join(out_dir, "recommendations.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                   "source_item_id": 25136258,
                   "total_comments": len(all_comments),
                   "matched_resources": len(results),
                   "recommendations": results}, f, ensure_ascii=False, indent=2)
    print(f"matched resources: {len(results)}")
    for r in results[:12]:
        print(f"  #{r['rank']} {r['title']} — {r['citations']} cites — {r['price_label']} {r['price_est']}")

if __name__ == "__main__":
    main()