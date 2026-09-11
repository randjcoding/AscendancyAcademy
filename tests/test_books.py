"""Book code cleanup and kind guesses — no live network."""
from app.models import BookKind
from app.services.books import code_variants, guess_kind, isbn13_to_isbn10, normalize_code


def test_normalize_isbn():
    assert normalize_code("978-0-13-468599-1") == "9780134685991"
    assert normalize_code("978-1-4838-1169-7") == "9781483811697"
    assert normalize_code("0-306-40615-2") == "0306406152"
    assert normalize_code("0-306-40615-X") == "030640615X"
    assert normalize_code("ISBN 9780134685991") == "9780134685991"
    assert normalize_code("Saxon Math") == ""
    assert normalize_code("") == ""


def test_isbn13_to_isbn10():
    assert isbn13_to_isbn10("9781483811697") == "1483811697"
    assert code_variants("978-1-4838-1169-7") == ["9781483811697", "1483811697"]


def test_guess_kind():
    assert guess_kind("Saxon Math Workbook", []) == BookKind.WORKBOOK
    assert guess_kind("Story of the World", ["curriculum", "homeschool"]) == BookKind.CURRICULUM
    assert guess_kind("Charlotte's Web", ["juvenile fiction"]) == BookKind.NOVEL
    assert guess_kind("Algebra 1", ["textbook"]) == BookKind.TEXTBOOK
    assert guess_kind("Random Title", []) == BookKind.OTHER
