# inpixels09 — archive

A complete archive of the WordPress.com blog **[in Pixels](https://inpixels09.wordpress.com/)**
(`inpixels09.wordpress.com`), written by Jay Hack between September 2009 and
January 2010 during a 5.5-month student exchange in Nagano, Japan.

The archive captures all 26 published posts, their original rendered HTML
pages, and every embedded image, in formats that should outlive the original
site.

## What's in here

```
.
├── README.md
├── scripts/
│   └── build_archive.py        # Rebuilds posts-md/, mirror/, assets/ from posts-json/all-posts.json
├── posts-json/
│   ├── site.json               # Site metadata from the WordPress.com REST API
│   ├── tags.json               # All tags
│   ├── categories.json         # All categories
│   ├── all-posts.json          # Single-file dump of every post (source of truth)
│   └── posts/                  # One pretty-printed JSON file per post
├── posts-md/
│   ├── INDEX.md                # Chronological table of contents
│   └── YYYY-MM-DD-<slug>.md    # One Markdown file per post (with YAML frontmatter)
├── mirror/
│   └── YYYY-MM-DD-<slug>.html  # The original rendered HTML page for each post
└── assets/
    └── <slug>/                 # Images embedded in each post, downloaded locally
```

## Format choices

Three independent representations are kept on purpose, because each one fails
in a different way over time:

1. **JSON (`posts-json/`)** — structured, machine-readable, lossless. Pulled
   straight from the WordPress.com public REST API (`/sites/<host>/posts`).
   Contains the full HTML body, dates, tags, categories, author info, etc.
   This is the canonical source the other formats are derived from.
2. **Markdown (`posts-md/`)** — human-readable, plain-text, future-proof.
   Image links in the Markdown have been rewritten to point at the local
   copies in `assets/`, so you can read these files entirely offline.
3. **HTML mirror (`mirror/`)** — the original rendered page, exactly as
   WordPress.com served it at archive time. Useful if you ever want to see the
   posts with their original styling and surrounding chrome.

## Rebuilding

The Markdown, HTML mirror, and image assets are all regenerable from
`posts-json/all-posts.json`:

```bash
python3 scripts/build_archive.py
```

The script is dependency-free (standard library only) and idempotent — it
skips any HTML page or image that is already present on disk.

## Re-fetching from WordPress.com

If you ever want to pull a fresh copy of the source data from the live site:

```bash
HOST=inpixels09.wordpress.com
curl -sS "https://public-api.wordpress.com/rest/v1.1/sites/$HOST" -o posts-json/site.json
curl -sS "https://public-api.wordpress.com/rest/v1.1/sites/$HOST/posts/?number=100&fields=ID,date,modified,title,URL,slug,excerpt,content,tags,categories,author" -o posts-json/all-posts.json
curl -sS "https://public-api.wordpress.com/rest/v1.1/sites/$HOST/tags?number=200" -o posts-json/tags.json
curl -sS "https://public-api.wordpress.com/rest/v1.1/sites/$HOST/categories?number=200" -o posts-json/categories.json
python3 scripts/build_archive.py
```

## Posts

See [`posts-md/INDEX.md`](./posts-md/INDEX.md) for the full chronological list.
The first post is [Tokyo (2009-09-06)](./posts-md/2009-09-06-tokyo.md) and the
last is
[消滅のやり方 / How to Disappear Completely (2010-01-09)](./posts-md/2010-01-09-消滅のやり方--how-to-disappear-completely.md).
