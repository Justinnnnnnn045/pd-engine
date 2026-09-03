# PD.Radar — professional-development leaderboard from real HN data

A single-page leaderboard of professional-development resources that real engineers
say were worth paying for — sourced from the 540 comments on the (in)famous
Hacker News thread:

> **Ask HN: What is the best money you have spent on professional development?**
> https://news.ycombinator.com/item?id=25136258 — 524 points, 540 comments, Nov 2020

## What it is

- A **static, dependency-free website** (one HTML file + one JSON file).
- A **citation-count leaderboard**: every comment from the thread was matched
  against a curated lexicon of well-known PD resources; each resource's rank is
  the number of distinct comments that named it.
- Grouped into price tiers (Free / Under $50 / $50–$150 / $150+) so readers can
  shop by budget.
- Each ranked item shows **real quotes** from the commenters who cited it.

## How it's built

```
fetch_comments.py   -> pulls the full comment tree from the HN Algolia API
extract_rank.py     -> matches comments against the lexicon, tallies citations,
                       ranks, and writes recommendations.json
site/index.html     -> renders recommendations.json (works from any static host)
```

### Honest scoring notes

- Algolia's API does **not** expose per-comment upvote counts, so ranking is by
  **citation frequency** (number of distinct comments naming a resource), not by
  upvotes. That is the most honest signal available from this data source.
- Prices are **public-knowledge estimates** (marked "est."), frozen at build
  time. Always verify before buying.
- The lexicon is curated; a resource absent from it will not appear even if
  people mentioned it. Coverage is best-effort, not exhaustive.

## Try it live

https://justinnnnnnn045.github.io/pd-engine/

## Rebuild (any day, on any machine)

```bash
python fetch_comments.py   # re-fetches current HN state for the thread
python extract_rank.py     # re-ranks and rewrites recommendations.json
```

## Files

| File | Purpose |
|---|---|
| `site/index.html` | The entire application (CSS + JS inline) |
| `site/recommendations.json` | The ranked data (generated) |
| `fetch_comments.py` | Data fetcher |
| `extract_rank.py` | Extractor + ranker |
| `raw/` | Cached raw API responses (540-comment thread) |

## Repo & data license

Data is from public Hacker News comments (Algolia API). The ranking and page are
original work. Not affiliated with Hacker News, Y Combinator, or any listed product.