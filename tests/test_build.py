from pathlib import Path

from ppwr import build

GERMAN_MARKERS = (
    "Wellkiste",
    "Stanzverpackung",
    "geleimt",
    "gebündelt",
    "palettiert",
    "beträgt",
    "Wellenstoff",
    "Testliner braun",
    "Kraftliner braun",
    "Recyclinganteil",
    "Artikelnummer",
    "Innenmaß",
)

ARTICLE_NUMBERS = (
    "00412488-01", "00412490-01", "00412491-01", "00412492-01", "00412493-01",
    "00440528-01", "00440533-01", "00448685-01", "00453666-01", "00453667-01",
    "00469859-01", "00469860-01", "00469861-01", "00473038-01", "00476810-01",
    "00476935-01", "00477037-01", "00483144-01", "00483153-01",
)


def build_into(tmp_path):
    out = tmp_path / "dist"
    assert build.main(["--out", str(out)]) == 0
    return out


def test_build_writes_every_expected_file(tmp_path):
    out = build_into(tmp_path)

    for name in ("index.html", "de/index.html", "en/index.html", "style.css", "CNAME", "qr.svg", "labels.html"):
        assert (out / name).is_file(), f"missing {name}"


def test_both_languages_list_every_article(tmp_path):
    out = build_into(tmp_path)

    for language in ("de", "en"):
        page = (out / language / "index.html").read_text(encoding="utf-8")
        for number in ARTICLE_NUMBERS:
            assert number in page, f"{number} missing from {language}"


def test_the_english_page_has_no_german_left(tmp_path):
    page = (build_into(tmp_path) / "en" / "index.html").read_text(encoding="utf-8")

    for marker in GERMAN_MARKERS:
        assert marker not in page, f"untranslated German on the English page: {marker}"


def test_the_english_page_uses_english_number_notation(tmp_path):
    page = (build_into(tmp_path) / "en" / "index.html").read_text(encoding="utf-8")

    assert "1,190 x 430 x 270 mm" in page
    assert "1.190 x 430 x 270 mm" not in page


def test_the_german_page_keeps_the_spreadsheets_own_notation(tmp_path):
    page = (build_into(tmp_path) / "de" / "index.html").read_text(encoding="utf-8")

    assert "1.190 x 430 x 270 mm" in page
    assert "Der Recyclinganteil an dieser Verpackung beträgt ca. 72%" in page


def test_the_address_is_not_translated(tmp_path):
    page = (build_into(tmp_path) / "en" / "index.html").read_text(encoding="utf-8")

    assert "Wilhelmstr. 162" in page
    assert "72805 Lichtenstein" in page


def test_the_cname_names_the_custom_domain(tmp_path):
    assert (build_into(tmp_path) / "CNAME").read_text(encoding="utf-8").strip() == "ppwr.jt-lizenzen.de"


def test_the_qr_encodes_the_site_url(tmp_path):
    labels = (build_into(tmp_path) / "labels.html").read_text(encoding="utf-8")

    assert "https://ppwr.jt-lizenzen.de/" in labels
    assert "<svg" in labels


def test_the_qr_svg_scales_instead_of_cropping(tmp_path):
    # Regression: an <svg> root without a viewBox does not rescale when CSS
    # overrides its width/height, it clips to the intrinsic pixel size - a
    # sticker sheet that shrinks the code to 22mm showed just its corner
    # square instead of the whole code. Only a viewBox lets the browser
    # rescale the artwork to fit the box CSS gives it.
    svg = (build_into(tmp_path) / "qr.svg").read_text(encoding="utf-8")
    root = svg[: svg.index(">") + 1]

    assert "viewBox=" in root
    assert "width=" not in root
    assert "height=" not in root


def test_the_labels_sheet_inlines_a_scalable_svg(tmp_path):
    # The standalone qr.svg being correct isn't enough: labels.html is what
    # actually reaches the printed sticker, and it inlines the SVG markup
    # separately. That's the copy that must carry viewBox too.
    labels = (build_into(tmp_path) / "labels.html").read_text(encoding="utf-8")
    start = labels.index("<svg")
    root = labels[start : labels.index(">", start) + 1]

    assert "viewBox=" in root


def test_a_missing_spreadsheet_fails_without_writing_a_site(tmp_path, capsys):
    empty = tmp_path / "data"
    empty.mkdir()
    out = tmp_path / "dist"

    assert build.main(["--data", str(empty), "--out", str(out)]) == 1
    assert "no .xlsx file" in capsys.readouterr().err
    assert not out.exists()
