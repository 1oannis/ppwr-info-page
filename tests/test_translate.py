import json

import pytest

from ppwr.glossary import load_glossary
from ppwr.translate import TranslationError, translate
from ppwr.workbook import Declaration


def make_glossary(tmp_path, **sections):
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps(sections, ensure_ascii=False), encoding="utf-8")
    return load_glossary(path)


def make_declaration(columns, rows, title="Titel", label="In Verkehrbringer:"):
    return Declaration(
        title=title,
        distributor_label=label,
        distributor_lines=("JT-Lizenzen", "Wilhelmstr. 162"),
        columns=columns,
        rows=rows,
    )


BASE_TERMS = {"Titel": "Title", "In Verkehrbringer:": "Placed on the market by:"}


def test_translates_column_headers(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Fertigung": "Manufacture"},
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Fertigung",), (("",),))

    assert translate(declaration, glossary).columns == ("Manufacture",)


def test_passthrough_columns_keep_their_text(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Sorte": "Board grade"},
        passthrough_columns=["Sorte"],
        no_number_localisation_columns=["Sorte"],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Sorte",), (("C 1-4003 b/b / VDW 1.40 C",),))

    assert translate(declaration, glossary).rows == (("C 1-4003 b/b / VDW 1.40 C",),)


def test_passthrough_columns_are_still_number_localised(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Innenmaß": "Internal dimensions"},
        passthrough_columns=["Innenmaß"],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Innenmaß",), (("1.190 x 430 x 270 mm",),))

    assert translate(declaration, glossary).rows == (("1,190 x 430 x 270 mm",),)


def test_matches_a_whole_cell_pattern(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Recyclinganteil": "Recycled content"},
        patterns=[{
            "de": r"^Der Recyclinganteil an dieser Verpackung beträgt ca\. (?P<share>[\d.,]+)%$",
            "en": "The recycled content of this packaging is approx. {share}%",
        }],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(
        ("Recyclinganteil",),
        (("Der Recyclinganteil an dieser Verpackung beträgt ca. 72%",),),
    )

    assert translate(declaration, glossary).rows == (
        ("The recycled content of this packaging is approx. 72%",),
    )


def test_splits_on_commas_and_looks_up_each_segment(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Fertigung": "Manufacture"},
        terms={**BASE_TERMS, "ohne Druck": "unprinted", "geleimt": "glued", "palettiert": "palletised"},
    )
    declaration = make_declaration(("Fertigung",), (("ohne Druck, geleimt, palettiert",),))

    assert translate(declaration, glossary).rows == (("unprinted, glued, palletised",),)


def test_resolves_a_captured_group_through_terms(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Zusammensetzung": "Composition"},
        patterns=[{"de": r"^(?P<grams>[\d.,]+) g (?P<material>.+)$", "en": "{grams} g {material|term}"}],
        terms={**BASE_TERMS, "Wellenstoff": "fluting", "Testliner braun": "brown testliner"},
    )
    declaration = make_declaration(
        ("Zusammensetzung",),
        (("100 g Wellenstoff, 120 g Testliner braun",),),
    )

    assert translate(declaration, glossary).rows == (
        ("100 g fluting, 120 g brown testliner",),
    )


def test_drops_a_trailing_comma_from_the_source(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Artikelbeschreibung": "Article description"},
        terms={**BASE_TERMS, "Stanzverpackung": "Die-cut packaging"},
    )
    declaration = make_declaration(("Artikelbeschreibung",), (("Stanzverpackung,",),))

    assert translate(declaration, glossary).rows == (("Die-cut packaging",),)


def test_addresses_are_never_translated(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Artikelnummer": "Article number"},
        passthrough_columns=["Artikelnummer"],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Artikelnummer",), (("00412488-01",),))

    assert translate(declaration, glossary).distributor_lines == ("JT-Lizenzen", "Wilhelmstr. 162")


def test_unknown_segment_reports_row_and_column(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Fertigung": "Manufacture"},
        terms={**BASE_TERMS, "geleimt": "glued"},
    )
    declaration = make_declaration(
        ("Fertigung",),
        (("geleimt",), ("geleimt, heißsiegelbeschichtet",)),
    )

    with pytest.raises(TranslationError) as caught:
        translate(declaration, glossary)

    failure = caught.value.failures[0]
    assert failure.row == 2
    assert failure.column == "Fertigung"
    assert failure.text == "heißsiegelbeschichtet"
    assert "heißsiegelbeschichtet" in str(caught.value)
    assert "glossary.json" in str(caught.value)


def test_unknown_column_header_is_reported(tmp_path):
    glossary = make_glossary(tmp_path, columns={}, terms=BASE_TERMS)
    declaration = make_declaration(("Kantenschutz",), (("",),))

    with pytest.raises(TranslationError, match="Kantenschutz"):
        translate(declaration, glossary)


def test_an_unresolvable_group_term_is_reported_not_silently_german(tmp_path):
    glossary = make_glossary(
        tmp_path,
        columns={"Zusammensetzung": "Composition"},
        patterns=[{"de": r"^(?P<grams>[\d.,]+) g (?P<material>.+)$", "en": "{grams} g {material|term}"}],
        terms=BASE_TERMS,
    )
    declaration = make_declaration(("Zusammensetzung",), (("100 g Schrenzpapier",),))

    with pytest.raises(TranslationError, match="Schrenzpapier"):
        translate(declaration, glossary)


def test_all_failures_are_collected_before_raising(tmp_path):
    glossary = make_glossary(tmp_path, columns={"Fertigung": "Manufacture"}, terms=BASE_TERMS)
    declaration = make_declaration(("Fertigung",), (("erstes",), ("zweites",)))

    with pytest.raises(TranslationError) as caught:
        translate(declaration, glossary)

    assert [failure.text for failure in caught.value.failures] == ["erstes", "zweites"]
