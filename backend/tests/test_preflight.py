"""Tests for Feature 2: Pre-flight questions.

The pre-flight question structure is served by the API so any client
(frontend, LLM agent, CLI) can discover what to ask without prior knowledge.
Answers are validated on transition to in_review — all required questions
must have non-empty answers.
"""


class TestPreflightQuestionEndpoint:
    """GET /api/v1/preflight-questions returns the full self-describing structure."""

    def test_returns_sections(self, client):
        """The endpoint returns all five pre-flight sections."""
        resp = client.get("/api/v1/preflight-questions")
        assert resp.status_code == 200
        data = resp.json()

        assert "sections" in data
        assert "schema_version" in data

        section_keys = [s["key"] for s in data["sections"]]
        assert section_keys == [
            "the_change",
            "customer_experience",
            "failure_and_recovery",
            "timing_and_coordination",
            "customer_awareness",
        ]

    def test_sections_have_framing(self, client):
        """Each section has a cognitive framing sentence."""
        resp = client.get("/api/v1/preflight-questions")
        sections = resp.json()["sections"]

        for section in sections:
            assert "framing" in section, f"Section '{section['key']}' missing framing"
            assert len(section["framing"]) > 0

    def test_sections_have_titles(self, client):
        """Each section has a human-readable title."""
        resp = client.get("/api/v1/preflight-questions")
        sections = resp.json()["sections"]

        for section in sections:
            assert "title" in section, f"Section '{section['key']}' missing title"
            assert len(section["title"]) > 0

    def test_questions_are_self_describing(self, client):
        """Every question has key, label, type, required, description, and example."""
        resp = client.get("/api/v1/preflight-questions")
        sections = resp.json()["sections"]

        required_fields = {"key", "label", "type", "required", "description", "example"}

        for section in sections:
            assert len(section["questions"]) > 0, (
                f"Section '{section['key']}' has no questions"
            )
            for q in section["questions"]:
                missing = required_fields - set(q.keys())
                assert not missing, (
                    f"Question '{q.get('key', '?')}' missing fields: {missing}"
                )

    def test_question_keys_are_unique(self, client):
        """Every question key is globally unique across all sections."""
        resp = client.get("/api/v1/preflight-questions")
        sections = resp.json()["sections"]

        all_keys = []
        for section in sections:
            for q in section["questions"]:
                all_keys.append(q["key"])

        assert len(all_keys) == len(set(all_keys)), (
            f"Duplicate question keys found: "
            f"{[k for k in all_keys if all_keys.count(k) > 1]}"
        )

    def test_one_question_one_thought(self, client):
        """No question label contains a compound question (no '?' followed by more text)."""
        resp = client.get("/api/v1/preflight-questions")
        sections = resp.json()["sections"]

        for section in sections:
            for q in section["questions"]:
                label = q["label"]
                # A compound question would have a '?' followed by more question text
                question_marks = label.count("?")
                assert question_marks <= 1, (
                    f"Compound question detected in '{q['key']}': '{label}' "
                    f"has {question_marks} question marks. One question, one thought."
                )

    def test_question_count_matches_spec(self, client):
        """The total number of questions matches the spec (21 questions across 5 sections)."""
        resp = client.get("/api/v1/preflight-questions")
        sections = resp.json()["sections"]

        counts = {s["key"]: len(s["questions"]) for s in sections}
        assert counts["the_change"] == 2
        assert counts["customer_experience"] == 4
        assert counts["failure_and_recovery"] == 5
        assert counts["timing_and_coordination"] == 4
        assert counts["customer_awareness"] == 5

    def test_schema_version_is_present(self, client):
        """The response includes a schema version for answer compatibility."""
        resp = client.get("/api/v1/preflight-questions")
        data = resp.json()

        assert "schema_version" in data
        assert isinstance(data["schema_version"], str)
        assert len(data["schema_version"]) > 0


class TestPreflightAnswers:
    """Pre-flight answers are saved as a dict keyed by question key."""

    def test_save_preflight_answers_on_create(self, client, sample_change_data):
        """Pre-flight answers can be provided when creating a change."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Pool size update",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
                "preflight_answers": {
                    "what_is_this_change": "Increase connection pool from 100 to 150",
                    "expected_outcome": "More concurrent connections supported",
                },
            },
        )
        assert resp.status_code == 201
        answers = resp.json()["preflight_answers"]
        assert answers["what_is_this_change"] == "Increase connection pool from 100 to 150"
        assert answers["expected_outcome"] == "More concurrent connections supported"

    def test_save_partial_answers_on_draft(self, client, sample_change_data):
        """Partial answers can be saved — operator fills in incrementally."""
        create_resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Partial answers",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
                "preflight_answers": {
                    "what_is_this_change": "Updating firewall rules",
                },
            },
        )
        assert create_resp.status_code == 201

        change_id = create_resp.json()["id"]

        # Update with more answers
        update_resp = client.patch(
            f"/api/v1/changes/{change_id}",
            json={
                "preflight_answers": {
                    "what_is_this_change": "Updating firewall rules",
                    "expected_outcome": "New IP ranges allowed",
                    "what_if_fails": "Traffic blocked, rollback immediately",
                },
            },
        )
        assert update_resp.status_code == 200
        assert len(update_resp.json()["preflight_answers"]) == 3

    def test_schema_version_recorded_on_change(self, client, sample_change_data):
        """When preflight answers are saved, the schema version is recorded on the change."""
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Version tracked change",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
                "preflight_answers": {
                    "what_is_this_change": "Something",
                },
            },
        )
        assert resp.status_code == 201
        assert resp.json()["preflight_schema_version"] is not None


class TestPreflightValidationOnTransition:
    """Cannot transition to in_review without complete pre-flight answers."""

    def _create_change(self, client, sample_change_data, preflight_answers=None):
        resp = client.post(
            "/api/v1/changes",
            json={
                "title": "Test change",
                "author_name": "Adrian Hornsby",
                **sample_change_data,
                "preflight_answers": preflight_answers,
            },
        )
        return resp.json()["id"]

    def _get_all_question_keys(self, client):
        """Fetch all required question keys from the endpoint."""
        resp = client.get("/api/v1/preflight-questions")
        keys = []
        for section in resp.json()["sections"]:
            for q in section["questions"]:
                if q["required"]:
                    keys.append(q["key"])
        return keys

    def _make_complete_answers(self, client):
        """Build a complete answer dict by discovering questions from the API."""
        keys = self._get_all_question_keys(client)
        return {key: f"Answer for {key}" for key in keys}

    def test_cannot_submit_without_answers(self, client, sample_change_data):
        """A change with no pre-flight answers cannot move to in_review."""
        change_id = self._create_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422
        assert "pre-flight" in resp.json()["detail"].lower()

    def test_cannot_submit_with_partial_answers(self, client, sample_change_data):
        """A change with incomplete pre-flight answers cannot move to in_review."""
        change_id = self._create_change(
            client,
            sample_change_data,
            preflight_answers={
                "what_is_this_change": "Partial answer only",
            },
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422
        assert "pre-flight" in resp.json()["detail"].lower()

    def test_cannot_submit_with_empty_string_answers(self, client, sample_change_data):
        """Empty string answers don't count — the operator must actually write something."""
        keys = self._get_all_question_keys(client)
        answers = {key: "" for key in keys}

        change_id = self._create_change(client, sample_change_data, preflight_answers=answers)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 422

    def test_can_submit_with_complete_answers(self, client, sample_change_data):
        """A change with all required answers filled in can move to in_review."""
        answers = self._make_complete_answers(client)
        change_id = self._create_change(
            client, sample_change_data, preflight_answers=answers
        )

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_review"

    def test_validation_only_on_review_transition(self, client, sample_change_data):
        """Abort is always allowed — pre-flight validation only gates in_review."""
        change_id = self._create_change(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "aborted", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "aborted"
