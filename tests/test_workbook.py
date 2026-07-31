import openpyxl
import pytest

from ppwr.workbook import WorkbookError, find_workbook, read_declaration


def _workbook(tmp_path, rows, name="sheet.xlsx"):
    """Build a real .xlsx on disk from a list of row lists."""
    book = openpyxl.Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    path = tmp_path / name
    book.save(path)
    return path


def test_finds_header_regardless_of_its_row_position(tmp_path):
    path = _workbook(tmp_path, [
        ["Verpackungen nach PPWR"],
        [None],
        [None],
        ["Artikelnummer", "Fertigung"],
        ["00412488-01", "geleimt"],
    ])

    declaration = read_declaration(path)

    assert declaration.columns == ("Artikelnummer", "Fertigung")
    assert declaration.rows == (("00412488-01", "geleimt"),)


def test_reads_title_and_distributor_block(tmp_path):
    path = _workbook(tmp_path, [
        ["Verpackungen nach PPWR - Konformitaetserklaerungen"],
        [None],
        ["In Verkehrbringer:"],
        ["JT-Lizenzen - 1 A Fulfillment"],
        ["Wilhelmstr. 162"],
        [None],
        ["Artikelnummer"],
        ["00412488-01"],
    ])

    declaration = read_declaration(path)

    assert declaration.title == "Verpackungen nach PPWR - Konformitaetserklaerungen"
    assert declaration.distributor_label == "In Verkehrbringer:"
    assert declaration.distributor_lines == (
        "JT-Lizenzen - 1 A Fulfillment",
        "Wilhelmstr. 162",
    )


def test_stops_at_the_first_blank_article_number(tmp_path):
    path = _workbook(tmp_path, [
        ["Artikelnummer"],
        ["00412488-01"],
        ["00412490-01"],
        [None],
        ["00999999-01"],
    ])

    assert read_declaration(path).rows == (("00412488-01",), ("00412490-01",))


def test_blank_cells_become_empty_strings(tmp_path):
    path = _workbook(tmp_path, [
        ["Artikelnummer", "Aussenmass"],
        ["00412488-01", None],
    ])

    assert read_declaration(path).rows == (("00412488-01", ""),)


def test_missing_header_row_is_an_error(tmp_path):
    path = _workbook(tmp_path, [["Verpackungen"], ["no header anywhere"]])

    with pytest.raises(WorkbookError, match="no header row"):
        read_declaration(path)


def test_find_workbook_returns_the_single_spreadsheet(tmp_path):
    (tmp_path / "PPWR JT Lizenzen.xlsx").touch()

    assert find_workbook(tmp_path).name == "PPWR JT Lizenzen.xlsx"


def test_find_workbook_ignores_excel_lock_files(tmp_path):
    (tmp_path / "PPWR JT Lizenzen.xlsx").touch()
    (tmp_path / "~$PPWR JT Lizenzen.xlsx").touch()

    assert find_workbook(tmp_path).name == "PPWR JT Lizenzen.xlsx"


def test_find_workbook_rejects_an_empty_directory(tmp_path):
    with pytest.raises(WorkbookError, match="no .xlsx file"):
        find_workbook(tmp_path)


def test_find_workbook_rejects_more_than_one_spreadsheet(tmp_path):
    (tmp_path / "old.xlsx").touch()
    (tmp_path / "new.xlsx").touch()

    with pytest.raises(WorkbookError, match="expected exactly one"):
        find_workbook(tmp_path)
