#!/usr/bin/env python3
"""
Static blog builder.
Converts Markdown posts in /posts into HTML pages using templates.
Usage: python3 build.py
"""

import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
POSTS_DIR = BASE_DIR / "posts"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "dist"

# Base URL for GitHub Pages (e.g. "/blog" if hosted at username.github.io/blog)
# Set to "" for root hosting or local preview
BASE_URL = "/blog"

# ---------------------------------------------------------------------------
# Minimal Markdown → HTML converter (no dependencies)
# ---------------------------------------------------------------------------

def md_to_html(md: str) -> str:
    """Convert a subset of Markdown to HTML. Supports headings, bold, italic,
    links, images, code blocks, inline code, blockquotes, unordered/ordered
    lists, and paragraphs."""
    lines = md.split("\n")
    html_lines: list[str] = []
    in_code_block = False
    in_ul = False
    in_ol = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Fenced code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                lang = line.strip().lstrip("`").strip()
                cls = f' class="language-{lang}"' if lang else ""
                html_lines.append(f"<pre><code{cls}>")
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            html_lines.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            i += 1
            continue

        # Close open lists if current line isn't a list item
        if in_ul and not re.match(r"^\s*[-*]\s", line):
            html_lines.append("</ul>")
            in_ul = False
        if in_ol and not re.match(r"^\s*\d+\.\s", line):
            html_lines.append("</ol>")
            in_ol = False

        # Blank lines
        if line.strip() == "":
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            text = inline(m.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        # Blockquotes
        if line.strip().startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            html_lines.append(f"<blockquote><p>{inline(' '.join(quote_lines))}</p></blockquote>")
            continue

        # Unordered list
        m = re.match(r"^\s*[-*]\s+(.*)", line)
        if m:
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        # Ordered list
        m = re.match(r"^\s*\d+\.\s+(.*)", line)
        if m:
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            html_lines.append("<hr>")
            i += 1
            continue

        # Paragraph – collect consecutive non-blank lines
        para = []
        while i < len(lines) and lines[i].strip() != "" and not lines[i].strip().startswith("#") and not lines[i].strip().startswith("```") and not lines[i].strip().startswith(">"):
            para.append(lines[i])
            i += 1
        html_lines.append(f"<p>{inline(' '.join(para))}</p>")
        continue

    # Close any dangling lists
    if in_ul:
        html_lines.append("</ul>")
    if in_ol:
        html_lines.append("</ol>")

    return "\n".join(html_lines)


def inline(text: str) -> str:
    """Process inline Markdown: images, links, bold, italic, inline code."""
    # Images
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1" loading="lazy">', text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text

# ---------------------------------------------------------------------------
# Front-matter parser
# ---------------------------------------------------------------------------

def parse_post(filepath: Path) -> dict:
    """Parse a Markdown file with YAML-like front-matter."""
    raw = filepath.read_text(encoding="utf-8")
    meta = {}
    body = raw

    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip('"').strip("'")
            body = parts[2].strip()

    slug = meta.get("slug", filepath.stem)
    date_str = meta.get("date", "2025-01-01")
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        date = datetime.now()

    return {
        "title": meta.get("title", filepath.stem.replace("-", " ").title()),
        "date": date,
        "date_str": date.strftime("%B %d, %Y"),
        "description": meta.get("description", ""),
        "image": meta.get("image", ""),
        "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        "slug": slug,
        "body_html": md_to_html(body),
        "filepath": filepath,
    }

# ---------------------------------------------------------------------------
# Template engine (simple {{var}} and {{#each}} / {{#if}})
# ---------------------------------------------------------------------------

def render_template(template_str: str, ctx: dict) -> str:
    """Minimal template rendering with variable substitution."""
    result = template_str

    # {{#each posts}} ... {{/each}}
    each_pattern = re.compile(r"\{\{#each (\w+)\}\}(.*?)\{\{/each\}\}", re.DOTALL)
    def replace_each(m):
        key = m.group(1)
        inner = m.group(2)
        items = ctx.get(key, [])
        parts = []
        for item in items:
            rendered = inner
            for k, v in item.items():
                rendered = rendered.replace("{{" + k + "}}", str(v))
            parts.append(rendered)
        return "".join(parts)
    result = each_pattern.sub(replace_each, result)

    # Simple variable replacement
    for key, val in ctx.items():
        if isinstance(val, str):
            result = result.replace("{{" + key + "}}", val)

    return result

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    # Clean output
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Copy static assets
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    # Load templates
    base_html = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    home_html = (TEMPLATES_DIR / "home.html").read_text(encoding="utf-8")
    post_html = (TEMPLATES_DIR / "post.html").read_text(encoding="utf-8")

    # Parse all posts
    posts = []
    for f in sorted(POSTS_DIR.glob("*.md")):
        posts.append(parse_post(f))

    # Sort by date descending
    posts.sort(key=lambda p: p["date"], reverse=True)

    # Build post data for JSON (used by JS sorting)
    posts_json = []
    for idx, p in enumerate(posts):
        posts_json.append({
            "title": p["title"],
            "date": p["date"].isoformat(),
            "date_str": p["date_str"],
            "description": p["description"],
            "image": p["image"],
            "slug": p["slug"],
            "tags": p["tags"],
            "index": idx,
        })

    # Write posts JSON for client-side sorting
    (OUTPUT_DIR / "static" / "js").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "static" / "js" / "posts.json").write_text(
        json.dumps(posts_json, indent=2), encoding="utf-8"
    )

    # Generate individual post pages
    for p in posts:
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in p["tags"])
        post_content = render_template(post_html, {
            "title": p["title"],
            "date_str": p["date_str"],
            "description": p["description"],
            "image": p["image"],
            "tags_html": tags_html,
            "body": p["body_html"],
            "slug": p["slug"],
            "base_url": BASE_URL,
        })
        page = render_template(base_html, {
            "title": p["title"] + " — I came up here to freeze",
            "content": post_content,
            "body_class": "post-page",
            "base_url": BASE_URL,
        })
        post_dir = OUTPUT_DIR / p["slug"]
        post_dir.mkdir(parents=True, exist_ok=True)
        (post_dir / "index.html").write_text(page, encoding="utf-8")

    # Generate homepage
    post_cards = []
    for p in posts:
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in p["tags"])
        post_cards.append({
            "title": p["title"],
            "date_str": p["date_str"],
            "description": p["description"],
            "image": p["image"],
            "slug": p["slug"],
            "tags_html": tags_html,
            "base_url": BASE_URL,
        })

    home_content = render_template(home_html, {
        "posts": post_cards,
        "base_url": BASE_URL,
    })
    page = render_template(base_html, {
        "title": "I came up here to freeze",
        "content": home_content,
        "body_class": "home-page",
        "base_url": BASE_URL,
    })
    (OUTPUT_DIR / "index.html").write_text(page, encoding="utf-8")

    print(f"✓ Built {len(posts)} posts → {OUTPUT_DIR}")
    print(f"  Preview: python3 -m http.server 8000 -d {OUTPUT_DIR}")


if __name__ == "__main__":
    build()
