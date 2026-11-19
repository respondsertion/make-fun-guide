#!/usr/bin/env python3
"""Render README.md into a GitHub-styled guide.html.

A small, dependency-free Markdown renderer covering exactly what the guide
uses: ATX headings (with GitHub-style slug ids), paragraphs, flat lists,
blockquotes, horizontal rules, fenced code blocks, inline code, images,
links, bold/italic, bare-URL autolinks and raw HTML passthrough (<sub>).

Usage: python3 render_guide.py [README.md] [guide.html]
"""
import html
import re
import sys

CSS = """
body { margin: 0; background: #ffffff; color: #1f2328;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans",
    Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.6;
  word-wrap: break-word; }
.markdown-body { max-width: 900px; margin: 0 auto; padding: 40px 32px 64px; }
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {
  margin-top: 24px; margin-bottom: 16px; font-weight: 600; line-height: 1.25; }
.markdown-body h1 { font-size: 2em; padding-bottom: .3em;
  border-bottom: 1px solid #d1d9e0; }
.markdown-body h2 { font-size: 1.5em; padding-bottom: .3em;
  border-bottom: 1px solid #d1d9e0; }
.markdown-body h3 { font-size: 1.25em; }
.markdown-body p { margin-top: 0; margin-bottom: 16px; }
.markdown-body a { color: #0969da; text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body img { max-width: 100%; background-color: #ffffff; }
.markdown-body code { padding: .2em .4em; margin: 0; font-size: 85%;
  background-color: #eff1f3; border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.markdown-body pre { padding: 16px; overflow: auto; font-size: 85%;
  line-height: 1.45; background-color: #f6f8fa; border-radius: 6px; }
.markdown-body pre code { padding: 0; background-color: transparent;
  border-radius: 0; }
.markdown-body blockquote { padding: 0 1em; margin: 0 0 16px;
  color: #59636e; border-left: .25em solid #d1d9e0; }
.markdown-body ul, .markdown-body ol { padding-left: 2em; margin: 0 0 16px; }
.markdown-body li + li { margin-top: .25em; }
.markdown-body hr { height: .25em; padding: 0; margin: 24px 0;
  background-color: #d1d9e0; border: 0; }
.markdown-body sub { font-size: 75%; }
"""


def slugify(text):
    text = re.sub(r"[`*_]", "", text).lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


class Stash:
    """Placeholder store so generated HTML survives escaping/emphasis."""

    def __init__(self):
        self.items = []

    def put(self, rendered):
        self.items.append(rendered)
        return "\x00%d\x00" % (len(self.items) - 1)

    def restore(self, text):
        while "\x00" in text:
            text = re.sub(
                r"\x00(\d+)\x00",
                lambda m: self.items[int(m.group(1))],
                text,
            )
        return text


def inline(text):
    stash = Stash()
    # 1. code spans
    text = re.sub(
        r"`([^`]+)`",
        lambda m: stash.put(
            "<code>%s</code>" % html.escape(m.group(1))
        ),
        text,
    )
    # 2. raw HTML tags (e.g. <sub>) pass through untouched
    text = re.sub(r"<[^>\n]+>", lambda m: stash.put(m.group(0)), text)
    # 3. escape the rest
    text = html.escape(text, quote=False)
    # 4. images (badge pattern [![alt](img)](url) is handled here + step 5)
    def image(m):
        return stash.put(
            '<img alt="%s" src="%s">' % (m.group(1), m.group(2))
        )

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", image, text)
    # 5. links
    def link(m):
        return stash.put('<a href="%s">%s</a>' % (m.group(2), m.group(1)))

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    # 6. bare URLs autolink
    text = re.sub(
        r"https?://[^\s<\x00]+",
        lambda m: stash.put('<a href="{0}">{0}</a>'.format(m.group(0))),
        text,
    )
    # 7. emphasis
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w/])\*([^*\n]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"(?<![\w/])_([^_\n]+)_", r"<em>\1</em>", text)
    return stash.restore(text)


def render(md):
    lines = md.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(
                "<pre><code>%s</code></pre>" % html.escape("\n".join(buf))
            )
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            out.append(
                '<h%d id="%s">%s</h%d>'
                % (level, slugify(text), inline(text), level)
            )
            i += 1
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
            continue
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            out.append(
                "<blockquote>%s</blockquote>" % inline(" ".join(buf))
            )
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            items = []
            while i < len(lines) and re.match(
                r"^\s*([-*]|\d+\.)\s+", lines[i]
            ):
                items.append(
                    re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])
                )
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(
                "<%s>%s</%s>"
                % (
                    tag,
                    "".join(
                        "<li>%s</li>" % inline(it) for it in items
                    ),
                    tag,
                )
            )
            continue
        if line.strip() == "":
            i += 1
            continue
        buf = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip() != ""
            and not lines[i].startswith(("```", "#", ">"))
            and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i])
            and not re.match(r"^\s*(-{3,}|\*{3,})\s*$", lines[i])
        ):
            buf.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % inline("\n".join(buf)))
    return "\n".join(out)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "README.md"
    dst = sys.argv[2] if len(sys.argv) > 2 else "guide.html"
    with open(src, encoding="utf-8") as f:
        body = render(f.read())
    page = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>make-fun-guide</title>\n<style>%s</style>\n</head>\n"
        "<body>\n<article class=\"markdown-body\">\n%s\n</article>\n"
        "</body>\n</html>\n" % (CSS, body)
    )
    with open(dst, "w", encoding="utf-8") as f:
        f.write(page)
    print("wrote %s (%d bytes)" % (dst, len(page)))


if __name__ == "__main__":
    main()
