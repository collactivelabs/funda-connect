from app.services.reference_data import list_curricula, list_grade_level_groups, list_topics


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


def test_topics_can_be_filtered_by_subject_curriculum_and_query():
    topics = list_topics(subject="mathematics", curriculum="CAPS", q="functions")

    assert topics
    assert all(topic.subject == "mathematics" for topic in topics)
    assert all(topic.curriculum == "CAPS" for topic in topics)
    assert any("Functions" in topic.name for topic in topics)


def test_topics_term_filter_only_returns_matching_term():
    topics = list_topics(term=3)

    assert topics
    assert all(topic.term == 3 for topic in topics)
