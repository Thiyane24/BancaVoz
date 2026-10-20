from bancavoz.digest import digest_facts


def test_digest_uses_live_summary_fields_and_previous_week_facts():
    facts = digest_facts(
        {"sales": 100, "expenses": 30, "profit": 70, "credit_given": 5,
         "credit_collected": 2, "entry_count": 3},
        [{"product": "rice", "sold": 100}],
        {"sales": 80, "expenses": 20, "profit": 60, "credit_given": 4,
         "credit_collected": 1, "entry_count": 2},
    )
    assert facts["net_minor"] == 70
    assert facts["previous"]["net_minor"] == 60
