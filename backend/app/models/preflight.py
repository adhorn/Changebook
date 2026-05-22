"""Pre-flight question definitions.

The question structure is served by the API so any client (frontend, LLM agent,
CLI tool) can discover what to ask without prior knowledge of the questions.

Design principles:
- One question, one thought. No compound questions.
- Each section has a cognitive framing sentence (Endsley's situation awareness model).
- Every question has a description (what a good answer looks like) and an example.
- Questions are config-in-code, served via API. Not database rows — the question set
  is version-controlled and changes go through code review.
- Answers are stored as flat JSON on the Change record, keyed by question key.
- Keys are stable and semantic. Never renamed, only deprecated.
"""

PREFLIGHT_SCHEMA_VERSION = "1.0"

PREFLIGHT_SECTIONS = [
    {
        "key": "the_change",
        "title": "The change",
        "framing": "What are you doing and what should happen?",
        "questions": [
            {
                "key": "what_is_this_change",
                "label": "What is this change?",
                "type": "text",
                "required": True,
                "description": "A clear, specific description of what you are changing. Not why — just what.",
                "example": "Increase the connection pool max_connections parameter from 100 to 150 on the primary database.",
            },
            {
                "key": "expected_outcome",
                "label": "What is the expected outcome?",
                "type": "text",
                "required": True,
                "description": "What should be different after this change is applied? Be specific and observable.",
                "example": "The database accepts up to 150 concurrent connections. Connection timeout errors during peak batch processing stop.",
            },
        ],
    },
    {
        "key": "customer_experience",
        "title": "What the customer experiences",
        "framing": "Think from the customer's perspective, not yours.",
        "questions": [
            {
                "key": "customer_notice",
                "label": "Will the customer notice this change?",
                "type": "text",
                "required": True,
                "description": "Yes or no, and explain briefly. Think about what the customer sees, not what you see.",
                "example": "No. The change happens at the database layer. The customer's application behaviour is unchanged.",
            },
            {
                "key": "how_customer_notices",
                "label": "How will they notice it?",
                "type": "text",
                "required": True,
                "description": "If the customer will notice, describe what they will see or experience. If not, say so.",
                "example": "They won't. Connection pooling is transparent to the application layer.",
            },
            {
                "key": "customer_mid_failure",
                "label": "If this change fails mid-way, what is the customer in the middle of doing?",
                "type": "text",
                "required": True,
                "description": "Think about the customer's workflow at the time of the change. What are they likely doing?",
                "example": "Running end-of-day batch reconciliation. They submit jobs that rely on database connections.",
            },
            {
                "key": "customer_work_impact",
                "label": "What happens to their in-progress work if it fails?",
                "type": "text",
                "required": True,
                "description": "Describe the impact on work the customer has already started. Data loss? Retries needed? Blocked?",
                "example": "Batch jobs fail and need to be re-queued. No data loss — the jobs are idempotent. But they lose ~30 minutes of processing time.",
            },
        ],
    },
    {
        "key": "failure_and_recovery",
        "title": "Failure and recovery",
        "framing": "Assume this will go wrong. What then?",
        "questions": [
            {
                "key": "what_if_fails",
                "label": "What happens if this change fails?",
                "type": "text",
                "required": True,
                "description": "Describe the failure scenario. What breaks, who is affected, what does it look like?",
                "example": "New connections are rejected. Existing connections stay alive but no new ones can be established. Batch jobs queue up and eventually time out.",
            },
            {
                "key": "rollback_plan",
                "label": "How do you roll back?",
                "type": "text",
                "required": True,
                "description": "The specific steps to undo this change. Be concrete — commands, not intentions.",
                "example": "Set max_connections back to 100 in the parameter group. Restart the connection pool. No data migration needed.",
            },
            {
                "key": "rollback_duration",
                "label": "How long does rollback take?",
                "type": "text",
                "required": True,
                "description": "Wall-clock time from deciding to roll back to the customer being back to normal.",
                "example": "Under 5 minutes. Parameter change is immediate. Pool restart takes ~30 seconds. Queued jobs retry automatically.",
            },
            {
                "key": "customer_during_rollback",
                "label": "What does the customer experience during rollback?",
                "type": "text",
                "required": True,
                "description": "From the customer's perspective, what happens while you are rolling back?",
                "example": "Brief connection errors for ~30 seconds during pool restart. Batch jobs that were in-flight will fail and auto-retry.",
            },
            {
                "key": "blast_radius",
                "label": "What is the blast radius?",
                "type": "text",
                "required": True,
                "description": "How many customers, services, or environments are affected if this goes wrong?",
                "example": "Single customer, single database instance. No shared infrastructure affected. Other customers on separate instances.",
            },
        ],
    },
    {
        "key": "timing_and_coordination",
        "title": "Timing and coordination",
        "framing": "Is this the right moment — for the customer, not just for you?",
        "questions": [
            {
                "key": "maintenance_window",
                "label": "Is there a maintenance window?",
                "type": "text",
                "required": True,
                "description": "Is this change happening inside a scheduled maintenance window?",
                "example": "Yes. Customer has a weekly maintenance window Saturday 02:00-06:00 UTC.",
            },
            {
                "key": "maintenance_window_when",
                "label": "When is it?",
                "type": "text",
                "required": True,
                "description": "The specific date and time of the maintenance window, or when you plan to execute.",
                "example": "Saturday 2026-05-24, 02:00-06:00 UTC.",
            },
            {
                "key": "lowest_impact_window",
                "label": "Is this the lowest-impact window for the customer, or the most convenient for the operator?",
                "type": "text",
                "required": True,
                "description": "Be honest. Sometimes the operator picks a time that's convenient for them, not optimal for the customer.",
                "example": "Lowest impact for the customer. Saturday early morning is their lowest-traffic period. We confirmed with their ops team.",
            },
            {
                "key": "dependencies",
                "label": "Are there dependencies on other changes or teams?",
                "type": "text",
                "required": True,
                "description": "Does this change depend on something else happening first? Does something else depend on this?",
                "example": "No dependencies. This is a standalone parameter change.",
            },
        ],
    },
    {
        "key": "customer_awareness",
        "title": "Customer awareness and agreement",
        "framing": "Does the customer know?",
        "questions": [
            {
                "key": "customer_aware",
                "label": "Is the customer aware this change is happening?",
                "type": "text",
                "required": True,
                "description": "Has someone told the customer about this change?",
                "example": "Yes. Account manager notified the customer's ops lead on 2026-05-20.",
            },
            {
                "key": "customer_agreed",
                "label": "Has the customer agreed to this change?",
                "type": "text",
                "required": True,
                "description": "Agreement is not the same as awareness. Did the customer explicitly approve?",
                "example": "Yes. Customer signed off via email on 2026-05-20. Reference: TICKET-4521.",
            },
            {
                "key": "maintenance_communicated",
                "label": "Has a maintenance window been communicated to the customer?",
                "type": "text",
                "required": True,
                "description": "Did the customer receive the specific date, time, and expected impact?",
                "example": "Yes. Maintenance notification sent 2026-05-18 with 72h advance notice as per SLA.",
            },
            {
                "key": "customer_contact",
                "label": "Who is the customer contact during this change?",
                "type": "text",
                "required": True,
                "description": "Name and contact method for the person on the customer side who can be reached during execution.",
                "example": "Jane Smith, customer ops lead. Reachable on Slack channel #acme-ops or mobile +44 7700 900000.",
            },
            {
                "key": "completion_notification",
                "label": "How will the customer be notified when the change is complete?",
                "type": "text",
                "required": True,
                "description": "The specific mechanism for telling the customer the change is done.",
                "example": "Email to ops-notifications@acme.com and message in #acme-ops Slack channel.",
            },
        ],
    },
]


def get_preflight_schema() -> dict:
    """Return the full pre-flight question structure for the API."""
    return {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "sections": PREFLIGHT_SECTIONS,
    }


def get_required_question_keys() -> list[str]:
    """Return all required question keys — used for validation."""
    keys = []
    for section in PREFLIGHT_SECTIONS:
        for q in section["questions"]:
            if q["required"]:
                keys.append(q["key"])
    return keys


def validate_preflight_completeness(answers: dict | None) -> list[str]:
    """Check that all required questions have non-empty answers.

    Returns a list of missing/empty question keys. Empty list = valid.
    """
    required_keys = get_required_question_keys()

    if not answers:
        return required_keys

    missing = []
    for key in required_keys:
        value = answers.get(key)
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(key)

    return missing
