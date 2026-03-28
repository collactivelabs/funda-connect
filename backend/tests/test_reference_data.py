from app.services.reference_data import list_curricula, list_grade_level_groups


def test_curricula_reference_data_is_stable():
    curricula = list_curricula()

    assert [curriculum.code for curriculum in curricula] == ["CAPS", "Cambridge", "IEB"]
    assert all(curriculum.label for curriculum in curricula)


def test_grade_levels_are_grouped_and_cover_grade_r_to_12():
    groups = list_grade_level_groups()
    flattened = [item.value for group in groups for item in group.items]

    assert [group.phase for group in groups] == [
        "Foundation Phase",
        "Intermediate Phase",
        "Senior Phase",
        "FET Phase",
    ]
    assert flattened[0] == "Grade R"
    assert flattened[-1] == "Grade 12"
    assert len(flattened) == 13
