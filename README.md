# PPWR conformity page

Publishes the JT-Lizenzen packaging conformity declaration at
<https://ppwr.jt-lizenzen.de/> in German and English.

## Publishing new packaging data

1. Replace the spreadsheet in `data/` (any `.xlsx` name; exactly one file).
2. Commit and push to `main`.

GitHub Actions rebuilds and deploys. If the spreadsheet contains vocabulary the
glossary does not know, the build fails with the offending row, column and text,
and the live site is left untouched until `data/glossary.json` is extended.

## Local build

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m ppwr.build
python3 -m http.server 8000 --directory dist
```

## One-time setup

Configured outside the repository, once, when the site was first deployed:

- Repo → Settings → Pages → Source: GitHub Actions.
- Repo → Settings → Pages → Custom domain: `ppwr.jt-lizenzen.de`.
- Repo → Settings → Pages → Enforce HTTPS: on.
- Repo → Settings → General → visibility: public. GitHub Pages only publishes
  from a private repository on GitHub Pro or higher.

## QR code

One code for everything. It points at the site root, which redirects to German
or English based on the reader's own device, so the same artwork works on every
invoice and every package regardless of which articles are listed.

The build writes it in three formats, downloadable from the live site or found
in `dist/` after a local build:

| File | Use |
| ---- | --- |
| <https://ppwr.jt-lizenzen.de/qr.svg> | vector — scales to any size without pixelation. Prefer this. |
| <https://ppwr.jt-lizenzen.de/qr.png> | 820 px raster, lossless, for tools that will not take vector |
| <https://ppwr.jt-lizenzen.de/qr.jpg> | same raster as JPEG, for tools that accept nothing else |

JPEG is lossy and a QR code is exactly the high-contrast edge detail it handles
worst. At this size and quality it still decodes, but reach for the SVG or PNG
whenever the tool allows it.

Error correction is level H (30% of the symbol recoverable), so the code
survives being folded, stamped or scuffed in transit.

## Branding

`site/static/logo.png` is the single source of truth for the brand. The favicon
and the iOS home-screen icon are cropped from its orange "JT-" ball at build
time, so they cannot drift out of sync with the logo. Replacing the logo with
one that positions the ball differently fails the build with a message naming
the constant to update, rather than silently shipping an icon of whitespace.

## Layout

| Path              | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `data/`           | the spreadsheet and the DE→EN glossary           |
| `ppwr/`           | the build: read, translate, render, QR, branding |
| `site/`           | templates, stylesheet, logo, `CNAME`             |
| `docs/adr/`       | architecture decisions                           |

See `docs/adr/0001-build-time-static-generation.md` for why the site is
generated rather than assembled in the browser.
