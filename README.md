# PD.Radar — self-updating leaderboards from real HN data

A static leaderboard site that **updates itself**: a daily pipeline re-mines the
flagship thread, discovers new Hacker News recommendation threads, ranks the
resources people actually name, and commits the fresh data — no human required.

**Live:** https://justinnnnnnn045.github.io/pd-engine/

## The flagship

> **Ask HN: What is the best money you have spent on professional development?**
> https://news.ycombinator.com/item?id=25136258 — 524 points, 540 comments, Nov 2020

Ranked by **citation count** — how many distinct commenters named each resource —
not by marketing or upvotes. The #1 answer is "therapy" (51 citations), which no
marketing-driven list would ever put first.

## How the self-updating engine works

```
.github/workflows/auto-update.yml   — daily cron (06:17 UTC) + manual trigger
auto_update.py                      — the engine, pure stdlib:
   1. re-mines the flagship thread (fresh citation counts)
   2. discovers new Ask HN threads (points>=80, comments>=80)
   3. mines qualifying ones with the SAME lexicon + citation method
   4. writes data/threads.json (the index the site renders as tabs)
   5. commits any changes; GitHub Pages redeploys automatically
```

### Honesty gates (enforced in code)

- **Intent gate**: only threads whose *title asks for recommendations* are mined.
  Rant/vent/news threads produce lexicon false-positives and are skipped
  (`title_has_intent()`).
- **Quality gate**: a discovered thread is published only if ≥5 resources match,
  each with ≥3 citations (`MIN_RESOURCES`, `MIN_CITES`). The flagship keeps its
  original ≥1-citation rule so its ranking stays byte-compatible.
- **Rejected threads are remembered** for 45 days (`discovery_state.json`) so the
  same junk thread is never re-mined daily.
- Citations are always verifiable against the live thread in seconds. Prices are
  public-knowledge estimates, labelled. Affiliate links are disclosed and never
  affect ranking.

## Files

| File | Purpose |
|---|---|
| `index.html` | The whole app — renders the thread index as switchable tabs |
| `recommendations.json` | Flagship leaderboard (regenerated daily) |
| `data/threads.json` | Index of all published threads (the tabs read this) |
| `data/threads/<id>.json` | Each discovered thread's leaderboard |
| `auto_update.py` | The self-updating engine |
| `fetch_comments.py` / `extract_rank.py` | Original flagship pipeline (lexicon lives here) |
| `.github/workflows/auto-update.yml` | The daily cron |

## Run it yourself

```bash
python auto_update.py        # full pipeline: re-mine + discover + publish
# or just the flagship:
python fetch_comments.py && python extract_rank.py
```

## Repo & data license

Data is from public Hacker News comments (Algolia API). The ranking and page are
original work. Not affiliated with Hacker News, Y Combinator, or any listed
product.
