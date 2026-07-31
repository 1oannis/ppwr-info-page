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

## QR stickers

`dist/labels.html` is a print-ready A4 sheet of identical stickers, and
`dist/qr.svg` is the artwork on its own. Every sticker points at the site root,
which redirects to German or English based on the scanner's device, so one
sticker design works on every package.

## Layout

| Path              | Purpose                                          |
| ----------------- | ------------------------------------------------ |
| `data/`           | the spreadsheet and the DE→EN glossary           |
| `ppwr/`           | the build: read, translate, render, QR           |
| `site/`           | templates, stylesheet, `CNAME`                   |
| `docs/adr/`       | architecture decisions                           |

See `docs/adr/0001-build-time-static-generation.md` for why the site is
generated rather than assembled in the browser.
