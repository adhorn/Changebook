"""Pre-flight answers are stored as JSONB on the Change model for flexibility.

This module defines the default question structure for reference and validation.
Templates will override these with their own question sets.
"""

DEFAULT_PREFLIGHT_QUESTIONS = {
    "the_change": [
        {"key": "what_is_this_change", "label": "What is this change?", "type": "text"},
        {
            "key": "systems_affected",
            "label": "What systems/services are affected?",
            "type": "text",
        },
        {"key": "expected_outcome", "label": "What is the expected outcome?", "type": "text"},
    ],
    "customer_impact": [
        {
            "key": "who_is_using",
            "label": "Who is using this system right now? What are they trying to do?",
            "type": "text",
        },
        {
            "key": "customer_notice",
            "label": "Will the customer notice this change? How?",
            "type": "text",
        },
        {
            "key": "customer_mid_failure",
            "label": (
                "If this change fails mid-execution, what is the customer in the middle of doing? "
                "What happens to their work?"
            ),
            "type": "text",
        },
    ],
    "failure_and_recovery": [
        {
            "key": "what_if_fails",
            "label": "What happens if this change fails?",
            "type": "text",
        },
        {"key": "rollback_plan", "label": "How do you roll back?", "type": "text"},
        {
            "key": "rollback_duration",
            "label": (
                "How long does rollback take? What is the customer's experience during rollback?"
            ),
            "type": "text",
        },
        {
            "key": "blast_radius",
            "label": "What is the blast radius? (customers/systems/environments)",
            "type": "text",
        },
    ],
    "timing": [
        {
            "key": "maintenance_window",
            "label": "Is there a maintenance window? When?",
            "type": "text",
        },
        {
            "key": "why_this_time",
            "label": (
                "Why this time? Is this the lowest-impact window for the customer, "
                "or the most convenient for the operator?"
            ),
            "type": "text",
        },
        {
            "key": "dependencies",
            "label": "Are there dependencies on other changes or teams?",
            "type": "text",
        },
        {
            "key": "customer_informed",
            "label": "Has the customer been informed? Do they need to be?",
            "type": "text",
        },
    ],
}


# Flatten for easy iteration
def get_all_default_questions() -> list[dict]:
    questions = []
    for section_questions in DEFAULT_PREFLIGHT_QUESTIONS.values():
        questions.extend(section_questions)
    return questions


class PreflightAnswer:
    """Not a database model — pre-flight answers live as JSONB on Change.

    This class provides validation and structure.
    """

    pass
