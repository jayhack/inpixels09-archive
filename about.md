---
layout: page
title: About this archive
permalink: /about/
---

This site is a static Jekyll-rendered archive of
[inpixels09.wordpress.com](https://inpixels09.wordpress.com/), a blog Jay Hack
kept during a 5.5-month student exchange in Nagano, Japan, between September
2009 and January 2010.

## How it was built

The source data was pulled from the public WordPress.com REST API. Three
independent representations are stored alongside each other in the
[GitHub repo](https://github.com/jayhack/inpixels09-archive):

- **JSON** — structured, lossless dumps in `posts-json/`
- **Markdown** — portable plain-text copies in `posts-md/`, with image links
  rewritten to point at locally cached files
- **HTML mirror** — the original rendered pages from WordPress.com in `mirror/`

The version of each post you're reading on this site is the Markdown copy,
rendered by GitHub Pages with the [minima](https://github.com/jekyll/minima)
theme.

## Source

[github.com/jayhack/inpixels09-archive](https://github.com/jayhack/inpixels09-archive)
