from bancavoz.speech import sale_logged


def test_sale_speech_contains_real_numbers_and_stays_short():
    text = sale_logged(135000, 67500, "maria")
    assert "1,350.00" in text
    assert "675.00" in text
    assert len(text.split()) <= 25
