#!/usr/bin/env python3
"""Build the in-pixels archive from a saved WordPress.com REST API dump.

- Reads posts-json/all-posts.json
- Writes posts-json/<date>-<slug>.json for each post (pretty)
- Writes posts-md/<date>-<slug>.md for each post (HTML -> Markdown)
- Downloads each post's original rendered HTML page into mirror/
- Downloads embedded images into assets/<post-slug>/ and rewrites Markdown to use the local copies
- Writes posts-md/INDEX.md (chronological table of contents)
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALL_POSTS = ROOT / "posts-json" / "all-posts.json"
ALL_COMMENTS = ROOT / "posts-json" / "all-comments.json"
POSTS_JSON_DIR = ROOT / "posts-json" / "posts"
POSTS_MD_DIR = ROOT / "posts-md"
MIRROR_DIR = ROOT / "mirror"
ASSETS_DIR = ROOT / "assets"

POSTS_JSON_DIR.mkdir(parents=True, exist_ok=True)
POSTS_MD_DIR.mkdir(parents=True, exist_ok=True)
MIRROR_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def safe_slug(slug: str) -> str:
    """WordPress percent-encoded slugs (e.g. CJK characters) are unwieldy on disk.

    Decode them to UTF-8 and strip filesystem-unfriendly characters; if the result
    is empty (pure punctuation), fall back to a hash of the original.
    """
    try:
        decoded = urllib.parse.unquote(slug)
    except Exception:
        decoded = slug
    cleaned = re.sub(r"[^\w\-]+", "-", decoded, flags=re.UNICODE).strip("-")
    return cleaned or f"post-{abs(hash(slug)) % 10**8}"


def html_to_markdown(content: str) -> str:
    """Very small, dependency-free HTML -> Markdown converter.

    The WordPress REST API returns clean, well-formed HTML for these posts so
    handling a small subset of tags is enough to produce readable Markdown.
    """
    if not content:
        return ""

    text = content

    # Normalize Windows line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Headings.
    for level in range(6, 0, -1):
        text = re.sub(
            rf"<h{level}[^>]*>(.*?)</h{level}>",
            lambda m, lv=level: "\n" + ("#" * lv) + " " + m.group(1).strip() + "\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Bold / italic / strikethrough.
    text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<(del|s|strike)[^>]*>(.*?)</\1>", r"~~\2~~", text, flags=re.DOTALL | re.IGNORECASE)

    # Inline / block code.
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"<pre[^>]*>(.*?)</pre>",
        lambda m: "\n```\n" + re.sub(r"<[^>]+>", "", m.group(1)) + "\n```\n",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Blockquotes.
    def blockquote(match: re.Match) -> str:
        inner = match.group(1).strip()
        inner = re.sub(r"<[^>]+>", "", inner)
        lines = [f"> {ln}" for ln in inner.splitlines() if ln.strip()]
        return "\n" + "\n".join(lines) + "\n"

    text = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", blockquote, text, flags=re.DOTALL | re.IGNORECASE)

    # Images. <img src="..." alt="...">
    def img_tag(match: re.Match) -> str:
        attrs = match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', attrs, flags=re.IGNORECASE)
        src = src_match.group(1) if src_match else ""
        alt = alt_match.group(1) if alt_match else ""
        return f"![{alt}]({src})"

    text = re.sub(r"<img[^>]*>", img_tag, text, flags=re.IGNORECASE)

    # Links. <a href="...">text</a>. Note: <img> tags inside have already been
    # converted to Markdown image syntax (![alt](src)) by this point.
    def link(match: re.Match) -> str:
        attrs, body = match.group(1), match.group(2)
        href_match = re.search(r'href=["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
        href = href_match.group(1) if href_match else ""
        body_clean = re.sub(r"<[^>]+>", "", body).strip()
        # If the body is just a Markdown image, return image-inside-link form.
        img_only = re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", body_clean)
        if href and img_only:
            return f"[{body_clean}]({href})"
        if href:
            return f"[{body_clean or href}]({href})"
        return body_clean

    text = re.sub(r"<a\b([^>]*)>(.*?)</a>", link, text, flags=re.DOTALL | re.IGNORECASE)

    # Lists.
    def ul(match: re.Match) -> str:
        items = re.findall(r"<li[^>]*>(.*?)</li>", match.group(1), flags=re.DOTALL | re.IGNORECASE)
        return "\n" + "\n".join(f"- {re.sub(r'<[^>]+>', '', it).strip()}" for it in items) + "\n"

    def ol(match: re.Match) -> str:
        items = re.findall(r"<li[^>]*>(.*?)</li>", match.group(1), flags=re.DOTALL | re.IGNORECASE)
        return "\n" + "\n".join(
            f"{i + 1}. {re.sub(r'<[^>]+>', '', it).strip()}" for i, it in enumerate(items)
        ) + "\n"

    text = re.sub(r"<ul[^>]*>(.*?)</ul>", ul, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<ol[^>]*>(.*?)</ol>", ol, text, flags=re.DOTALL | re.IGNORECASE)

    # Horizontal rule.
    text = re.sub(r"<hr[^>]*/?>", "\n\n---\n\n", text, flags=re.IGNORECASE)

    # Line breaks.
    text = re.sub(r"<br[^>]*/?>", "  \n", text, flags=re.IGNORECASE)

    # Paragraphs become blank-line separated blocks.
    text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p[^>]*>", "\n\n", text, flags=re.IGNORECASE)

    # Strip remaining unhandled tags (divs, spans, figure, figcaption, etc.).
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities (&amp;, &nbsp;, &#8217;, ...).
    text = html.unescape(text)

    # Collapse 3+ blank lines into 2.
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"

    return text


def fetch(url: str, dest: Path) -> bool:
    """Best-effort download; return True on success."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "inpixels09-archiver/1.0 (+https://github.com/)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except Exception as exc:
        print(f"  ! download failed: {url} ({exc})", file=sys.stderr)
        return False


def localize_assets(markdown: str, slug: str) -> tuple[str, list[str]]:
    """Find image URLs in the Markdown, download each, and rewrite to ../assets/...

    Returns (rewritten_markdown, list_of_local_paths_relative_to_repo_root).
    """
    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    saved: list[str] = []

    def replace(match: re.Match) -> str:
        alt, url = match.group(1), match.group(2).strip()
        if not url.startswith(("http://", "https://")):
            return match.group(0)
        parsed = urllib.parse.urlparse(url)
        ext = os.path.splitext(parsed.path)[1] or ".bin"
        name_base = os.path.basename(parsed.path) or f"img-{abs(hash(url)) % 10**8}{ext}"
        # WordPress sometimes appends ?w=... query params; keep base name only.
        name = re.sub(r"[^\w.\-]+", "_", name_base)
        post_assets_dir = ASSETS_DIR / slug
        local_path = post_assets_dir / name
        # Avoid collisions for identical filenames with different content.
        i = 1
        while local_path.exists() and local_path.stat().st_size > 0 and url not in match.group(0):
            stem, dot_ext = os.path.splitext(name)
            local_path = post_assets_dir / f"{stem}-{i}{dot_ext}"
            i += 1
        if fetch(url, local_path):
            saved.append(str(local_path.relative_to(ROOT)))
            rel = os.path.relpath(local_path, POSTS_MD_DIR)
            return f"![{alt}]({rel})"
        return match.group(0)

    return pattern.sub(replace, markdown), saved


def build() -> None:
    data = json.loads(ALL_POSTS.read_text())
    posts = sorted(data.get("posts", []), key=lambda p: p["date"])

    # Group comments by post ID so each post's Markdown can include them inline.
    comments_by_post: dict[int, list[dict]] = {}
    if ALL_COMMENTS.exists():
        cdata = json.loads(ALL_COMMENTS.read_text())
        for c in cdata.get("comments", []):
            pid = (c.get("post") or {}).get("ID")
            if pid is not None:
                comments_by_post.setdefault(pid, []).append(c)
        # Show oldest comments first under each post.
        for pid, lst in comments_by_post.items():
            lst.sort(key=lambda c: c.get("date", ""))
        print(
            f"Building archive for {len(posts)} posts and "
            f"{sum(len(v) for v in comments_by_post.values())} comments..."
        )
    else:
        print(f"Building archive for {len(posts)} posts (no comments file found)...")

    index_lines = ["# in Pixels — archive index", "", "Posts in chronological order:", ""]

    for post in posts:
        slug_safe = safe_slug(post["slug"])
        date_short = post["date"][:10]
        base = f"{date_short}-{slug_safe}"

        # 1. Per-post pretty JSON.
        (POSTS_JSON_DIR / f"{base}.json").write_text(
            json.dumps(post, indent=2, ensure_ascii=False, sort_keys=True)
        )

        # 2. Markdown rendering.
        title_html = post.get("title") or "(untitled)"
        title = html.unescape(re.sub(r"<[^>]+>", "", title_html)).strip() or "(untitled)"
        body_md = html_to_markdown(post.get("content", ""))
        body_md, _saved = localize_assets(body_md, slug_safe)

        tags = sorted((post.get("tags") or {}).keys())
        cats = sorted((post.get("categories") or {}).keys())
        author = (post.get("author") or {}).get("name", "")

        post_comments = comments_by_post.get(post["ID"], [])
        front = [
            "---",
            f'title: "{title.replace(chr(34), chr(39))}"',
            f"date: {post['date']}",
            f'slug: "{post["slug"]}"',
            f"url: {post['URL']}",
            f'author: "{author}"',
            f"tags: [{', '.join(json.dumps(t) for t in tags)}]",
            f"categories: [{', '.join(json.dumps(c) for c in cats)}]",
            f"comment_count: {len(post_comments)}",
            "---",
            "",
            f"# {title}",
            "",
            f"*Originally posted {date_short} at <{post['URL']}>*",
            "",
            "",
        ]

        comments_md = ""
        if post_comments:
            lines = ["", "---", "", f"## Comments ({len(post_comments)})", ""]
            for c in post_comments:
                cauth = (c.get("author") or {}).get("name") or "anonymous"
                cdate = (c.get("date") or "")[:10]
                body = html_to_markdown(c.get("content", "")).strip()
                # Indent each line so the comment renders as a Markdown blockquote.
                quoted = "\n".join(f"> {ln}" if ln else ">" for ln in body.splitlines())
                lines.append(f"**{cauth}** — {cdate}")
                lines.append("")
                lines.append(quoted)
                lines.append("")
            comments_md = "\n".join(lines) + "\n"

        (POSTS_MD_DIR / f"{base}.md").write_text(
            "\n".join(front) + body_md + comments_md,
            encoding="utf-8",
        )

        # 3. Mirror the rendered HTML page.
        fetch(post["URL"], MIRROR_DIR / f"{base}.html")

        index_lines.append(f"- {date_short} — [{title}](./{base}.md)")
        print(f"  ✓ {base}")

    (POSTS_MD_DIR / "INDEX.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print("done.")


if __name__ == "__main__":
    build()
