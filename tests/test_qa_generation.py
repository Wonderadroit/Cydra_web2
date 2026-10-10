from cydra_web2.qa_generation import generate_test_candidates


def test_checkbox_candidate_is_grounded_in_observed_control_count():
    candidates = generate_test_candidates({"checkbox_count": 2})
    assert len(candidates) == 1
    assert candidates[0]["id"] == "checkbox_toggle_restore"
    assert candidates[0]["evidence"] == {"checkbox_count": 2}


def test_required_candidate_survives_missing_required_attribute_when_label_signals_intent():
    candidates = generate_test_candidates({
        "checkbox_count": 0,
        "form_controls": [{
            "label": "Email *",
            "type": "email",
            "required": False,
            "required_hint": True,
        }],
    })
    assert len(candidates) == 1
    assert candidates[0]["id"] == "required_validation_0"
    assert candidates[0]["evidence"]["required_attribute"] is False
    assert candidates[0]["confidence"] == "medium"


def test_does_not_invent_form_constraints_without_dom_evidence():
    assert generate_test_candidates({
        "checkbox_count": 0,
        "form_controls": [{"label": "Nickname", "type": "text", "required": False, "required_hint": False}],
    }) == []


def test_required_attribute_is_evidence_even_without_label_hint():
    candidates = generate_test_candidates({
        "form_controls": [{"label": "Email", "type": "email", "required": True, "required_hint": False}],
    })
    assert candidates[0]["evidence"]["required_attribute"] is True
