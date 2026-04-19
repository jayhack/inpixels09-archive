#!/usr/bin/env python3
"""Generate Jekyll-friendly _posts/ from posts-md/.

Why a separate folder?
- posts-md/ is meant to be a portable, self-contained Markdown archive that
  works when you just open the files on disk (relative `../assets/...` paths).
- _posts/ is what GitHub Pages / Jekyll renders. Image paths there need to be
  resolved against the site root, and slugs / filenames must be ASCII so the
  generated URLs are not full of percent-encoding.

This script rewrites image paths from `../assets/<slug>/img.jpg` to
`{{ '/assets/<slug>/img.jpg' | relative_url }}` and renames non-ASCII files
to safe ASCII equivalents while preserving the original title in the YAML
frontmatter.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "posts-md"
DEST = ROOT / "_posts"


def ascii_slug(text: str, fallback: str) -> str:
    """Return an ASCII-only, URL-safe slug. Falls back when text is empty."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return cleaned or fallback


def rewrite_image_paths(markdown: str) -> str:
    """Rewrite ../assets/... image links to absolute, baseurl-aware paths."""
    pattern = re.compile(r"(!?\[[^\]]*\])\((\.\./assets/[^)]+)\)")

    def repl(match: re.Match) -> str:
        prefix, path = match.group(1), match.group(2)
        # Strip the leading ../ so the path is rooted at the site.
        rooted = "/" + path[len("../"):]
        # Use Liquid so it works whether or not baseurl is set.
        return f"{prefix}({{{{ '{rooted}' | relative_url }}}})"

    return pattern.sub(repl, markdown)


def transform(src_path: Path) -> tuple[str, str]:
    """Return (jekyll_filename, transformed_contents) for a source post."""
    text = src_path.read_text(encoding="utf-8")

    # Filename pattern: YYYY-MM-DD-<original-slug>.md
    name_match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", src_path.name)
    if not name_match:
        raise ValueError(f"Unexpected filename: {src_path.name}")
    date_part, original_slug = name_match.groups()

    # Pull title out of frontmatter so we can derive an ASCII slug from it.
    title_match = re.search(r'^title:\s*"([^"]*)"', text, flags=re.MULTILINE)
    title = title_match.group(1) if title_match else original_slug
    slug = ascii_slug(title, fallback=ascii_slug(original_slug, "post"))

    text = rewrite_image_paths(text)

    # Drop the redundant `# {title}` body heading. The Jekyll layout already
    # renders the title from frontmatter, so it would appear twice otherwise.
    text = re.sub(
        r"(?ms)^(---\n.*?\n---\n\n)# [^\n]+\n+",
        r"\1",
        text,
        count=1,
    )

    return f"{date_part}-{slug}.md", text


def main() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    sources = sorted(p for p in SRC.glob("*.md") if p.name != "INDEX.md")
    used: dict[str, int] = {}
    for src in sources:
        name, contents = transform(src)
        # Avoid filename collisions when two titles produce the same slug.
        if name in used:
            used[name] += 1
            stem, ext = name.rsplit(".", 1)
            name = f"{stem}-{used[name]}.{ext}"
        else:
            used[name] = 0
        (DEST / name).write_text(contents, encoding="utf-8")
        print(f"  ✓ {src.name} -> _posts/{name}")
    print(f"wrote {len(sources)} posts into {DEST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
