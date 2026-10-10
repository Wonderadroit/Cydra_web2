from cydra_web2.qa_results import classify_exception


def test_explicit_behavior_assertion_is_a_failure():
    assert classify_exception(AssertionError("expected 2 controls, found 1")) == (
        "FAIL",
        "BEHAVIOR_ASSERTION",
    )


def test_timeout_is_inconclusive_not_a_confirmed_defect():
    assert classify_exception(TimeoutError("browser did not become ready")) == (
        "INCONCLUSIVE",
        "EXECUTION_OR_ENVIRONMENT",
    )


def test_unexpected_runtime_error_is_inconclusive():
    assert classify_exception(RuntimeError("renderer closed")) == (
        "INCONCLUSIVE",
        "EXECUTION_OR_ENVIRONMENT",
    )
