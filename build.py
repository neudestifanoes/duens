#!/usr/bin/env python3
"""
duen blog - static site builder
Usage: python3 build.py

Drop .md files in posts/ with this format:
    ---
    title: Your Post Title
    date: 2026-09-06
    ---

    Your markdown content here...

Then run: python3 build.py
"""

import os
import re
from pathlib import Path
from datetime import datetime

SITE_TITLE = "duen blog"
POSTS_DIR = Path("posts")
POST_OUTPUT = Path("p")
ROOT = Path(".")


# --- Markdown to HTML converter (no dependencies) ---

def inline_format(text):
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def md_to_html(text):
    lines = text.split("\n")
    parts = []
    i = 0
    in_list = False
    in_code = False
    code_lines = []
    paragraph = []

    def flush_p():
        nonlocal paragraph
        if paragraph:
            parts.append("<p>" + inline_format(" ".join(paragraph)) + "</p>")
            paragraph = []

    def flush_list():
        nonlocal in_list
        if in_list:
            parts.append("</ul>")
            in_list = False

    while i < len(lines):
        line = lines[i]

        # code block toggle
        if line.strip().startswith("```"):
            if in_code:
                parts.append("<pre><code>" + "\n".join(code_lines) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                flush_p()
                flush_list()
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            i += 1
            continue

        # blank line
        if line.strip() == "":
            flush_p()
            flush_list()
            i += 1
            continue

        # headers
        m = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m:
            flush_p()
            flush_list()
            lvl = len(m.group(1))
            parts.append(f"<h{lvl}>{inline_format(m.group(2))}</h{lvl}>")
            i += 1
            continue

        # horizontal rule
        if re.match(r'^---+\s*$', line):
            flush_p()
            flush_list()
            parts.append("<hr>")
            i += 1
            continue

        # unordered list
        m = re.match(r'^[-*]\s+(.+)$', line.strip())
        if m:
            flush_p()
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{inline_format(m.group(1))}</li>")
            i += 1
            continue

        # blockquote
        m = re.match(r'^>\s*(.*)$', line)
        if m:
            flush_p()
            flush_list()
            parts.append(f"<blockquote><p>{inline_format(m.group(1))}</p></blockquote>")
            i += 1
            continue

        # regular text
        flush_list()
        paragraph.append(line)
        i += 1

    flush_p()
    flush_list()
    return "\n".join(parts)


# --- Frontmatter parser ---

def parse_post(filepath):
    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    end = content.find("---", 3)
    if end == -1:
        return None

    front = content[3:end].strip()
    body = content[end + 3:].strip()

    meta = {}
    for line in front.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()

    if "title" not in meta or "date" not in meta:
        print(f"  SKIP {filepath.name} (missing title or date)")
        return None

    slug = re.sub(r'[^a-z0-9]+', '-', meta["title"].lower()).strip('-')
    date_obj = datetime.strptime(meta["date"], "%Y-%m-%d")
    date_display = date_obj.strftime("%B %d, %Y")

    return {
        "title": meta["title"],
        "date": meta["date"],
        "date_obj": date_obj,
        "date_display": date_display,
        "slug": slug,
        "body_html": md_to_html(body),
        "source": filepath.name,
    }


# --- HTML templates ---

def page_head(title, css_path="style.css", root=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="icon" type="image/svg+xml" href="{root}favicon.svg">
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<div id="container">"""


def page_nav(home_path="index.html", css_prefix=""):
    return f"""<div id="header">
<h1><a href="{home_path}"><img src="{css_prefix}favicon.svg" alt="" class="site-logo">{SITE_TITLE}</a></h1>
<div id="nav">
<a href="{home_path}">home</a> &middot;
<a href="{css_prefix}archive.html">archive</a> &middot;
<a href="{css_prefix}about.html">about</a>
</div>
</div>
<hr>"""


PAGE_FOOT = """</div>
</body>
</html>"""


def build_post_page(post):
    html = page_head(f"{post['title']} - {SITE_TITLE}", css_path="../style.css", root="../")
    html += page_nav(home_path="../index.html", css_prefix="../")
    html += f"""
<div class="post">
<div class="post-date">{post['date_display']}</div>
<h2 class="post-title">{post['title']}</h2>
<div class="post-body">
{post['body_html']}
</div>
</div>
<hr>
<div id="footer">
<a href="../index.html">&laquo; back to home</a>
</div>
"""
    html += PAGE_FOOT
    return html


def get_post_icon(title):
    """Pick a notepad/document icon based on the post."""
    # simple rotation of retro-looking text icons
    icons = [
        "&#128196;",  # page facing up
        "&#128221;",  # memo
        "&#128195;",  # page with curl
        "&#128220;",  # clipboard
        "&#128466;",  # notepad
    ]
    return icons[hash(title) % len(icons)]


def build_index(posts):
    html = page_head(SITE_TITLE)
    # override body class for homepage teal desktop
    html = html.replace("<body>", '<body class="home">')
    html += page_nav()
    html += '<div class="desktop">\n'
    for post in posts:
        icon = get_post_icon(post['title'])
        html += f"""<a class="win-window" href="p/{post['slug']}.html">
<div class="win-titlebar">
<span class="win-titlebar-text">{post['title']}</span>
<div class="win-buttons"><span class="win-btn">_</span><span class="win-btn">&#9633;</span><span class="win-btn">x</span></div>
</div>
<div class="win-body">
<div class="win-icon">{icon}</div>
<div class="win-label">{post['title']}</div>
</div>
<div class="win-statusbar">{post['date_display']}</div>
</a>
"""
    html += '</div>\n'
    html += f"""<div id="footer">&copy; {datetime.now().year} {SITE_TITLE}</div>
"""
    html += PAGE_FOOT
    return html


def build_archive(posts):
    html = page_head(f"archive - {SITE_TITLE}")
    html += page_nav()
    html += "<h2>archive</h2>\n<ul class=\"archive-list\">\n"
    for post in posts:
        html += (f'<li><span class="archive-date">{post["date"]}</span>'
                 f'<a href="p/{post["slug"]}.html">{post["title"]}</a></li>\n')
    html += "</ul>\n<hr>\n"
    html += f"""<div id="footer">&copy; {datetime.now().year} {SITE_TITLE}</div>
"""
    html += PAGE_FOOT
    return html


def build_about():
    html = page_head(f"about - {SITE_TITLE}")
    html += page_nav()
    html += """
<h2>about</h2>
<p>This is duen blog. A simple blog on the internet.</p>
<p>No ads. No tracking. No JavaScript. Just words.</p>
<hr>
"""
    html += f"""<div id="footer">&copy; {datetime.now().year} {SITE_TITLE}</div>
"""
    html += PAGE_FOOT
    return html


# --- Main build ---

def build():
    print(f"Building {SITE_TITLE}...")

    # ensure output dir
    POST_OUTPUT.mkdir(exist_ok=True)

    # read all posts
    md_files = sorted(POSTS_DIR.glob("*.md"))
    if not md_files:
        print("  No .md files found in posts/")
        return

    posts = []
    for f in md_files:
        post = parse_post(f)
        if post:
            posts.append(post)
            print(f"  + {post['title']} ({post['date']})")

    # sort newest first
    posts.sort(key=lambda p: p["date_obj"], reverse=True)

    # write individual post pages
    for post in posts:
        out = POST_OUTPUT / f"{post['slug']}.html"
        out.write_text(build_post_page(post), encoding="utf-8")

    # write index
    (ROOT / "index.html").write_text(build_index(posts), encoding="utf-8")
    print("  + index.html")

    # write archive
    (ROOT / "archive.html").write_text(build_archive(posts), encoding="utf-8")
    print("  + archive.html")

    # write about (only if it doesn't exist, so user edits are preserved)
    about_path = ROOT / "about.html"
    if not about_path.exists():
        about_path.write_text(build_about(), encoding="utf-8")
        print("  + about.html (created)")
    else:
        print("  . about.html (kept existing)")

    print(f"Done. {len(posts)} post(s) built.")


if __name__ == "__main__":
    build()
