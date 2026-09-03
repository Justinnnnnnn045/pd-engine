# -*- coding: utf-8 -*-
"""Fetch real HN comments for the PD thread via Algolia API and cache raw JSON.

Fetches BOTH the flat comment list (pages) and the story tree (hierarchy),
because extract_rank.py reads story_tree.json for structure and the flat
pages for completeness. Pure stdlib: runs on any machine, including
GitHub Actions runners.
"""
import json, os, sys, urllib.request

STORY_ID = "25136258"  # Ask HN: What is the best money you have spent on professional development? (2020-11-18, 524 pts, 540 comments)
RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
os.makedirs(RAW_DIR, exist_ok=True)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "starnet-pd-engine/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    total = 0
    # 1. Flat comment pages (the completeness source)
    for page in range(3):
        url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{STORY_ID}&hitsPerPage=1000&page={page}"
        data = get(url)
        hits = data.get("hits", [])
        nb_hits = data.get("nbHits", 0)
        total += len(hits)
        if hits:
            out = os.path.join(RAW_DIR, f"comments_p{page}.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(hits, f, ensure_ascii=False)
            print(f"page {page}: wrote {len(hits)} comments -> {out} ({os.path.getsize(out)} bytes)")
        if page * 1000 + len(hits) >= nb_hits or not hits:
            break
    # 2. Story tree (the hierarchy source extract_rank.py flattens)
    tree_url = f"https://hn.algolia.com/api/v1/items/{STORY_ID}"
    try:
        tree = get(tree_url)
        tree_out = os.path.join(RAW_DIR, "story_tree.json")
        with open(tree_out, "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False)
        print(f"story tree: wrote {os.path.getsize(tree_out)} bytes -> {tree_out}")
    except Exception as e:
        print(f"WARNING: could not fetch story tree ({e}); extract_rank.py may produce fewer matches", file=sys.stderr)
    print(f"TOTAL comments fetched: {total}")


if __name__ == "__main__":
    main()