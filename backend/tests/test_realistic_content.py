"""Tests with realistic long content — issue #7.

Real infrastructure changes don't have 2-word descriptions and single-flag
commands. This module verifies the system handles production-scale content:
- Multi-flag CLI commands with long ARNs and JSON
- Multi-sentence descriptions with caveats
- 8-15 items per phase
- Multi-line pasted terminal output in completions
- Long pre-flight answers with paragraphs
"""


def _complete_preflight_realistic(client):
    """Build realistic pre-flight answers — full sentences, not stubs."""
    resp = client.get("/api/v1/preflight-questions")
    answers = {}
    for section in resp.json()["sections"]:
        for q in section["questions"]:
            if q["required"]:
                answers[q["key"]] = REALISTIC_PREFLIGHT_ANSWERS.get(
                    q["key"],
                    f"Detailed answer for {q['key']} covering the specifics of this "
                    f"database migration including rollback strategy and customer impact.",
                )
    return answers


REALISTIC_PREFLIGHT_ANSWERS = {
    "what_is_this_change": (
        "We are migrating the primary connection pool configuration from a static "
        "pool size of 20 to a dynamic pool that scales between 10 and 50 connections "
        "based on active query load. This involves updating the HikariCP configuration "
        "on 3 application nodes behind the load balancer, applying a new connection "
        "timeout of 30s (down from 60s), and enabling connection validation queries. "
        "The change also updates the monitoring dashboards to track pool utilisation "
        "and adds alerting thresholds at 80% and 95% capacity."
    ),
    "expected_outcome": (
        "After the change, p95 connection acquisition latency should drop from ~800ms "
        "to under 200ms. The number of connection timeout errors (currently ~15/hour "
        "during peak) should drop to near zero. The pool will auto-scale during the "
        "daily batch processing window (02:00-04:00 UTC) instead of requiring manual "
        "intervention to increase pool size."
    ),
    "how_customer_notices": (
        "During the rolling restart of application nodes, the customer will see "
        "increased latency (est. +200ms per request) for approximately 45 seconds per "
        "node. With 3 nodes and sequential restarts, total degraded window is ~3 minutes. "
        "No errors should be visible. The load balancer will drain connections before "
        "each restart. If the customer is running real-time portfolio calculations "
        "during the window, those may take 10-15% longer to complete."
    ),
    "customer_mid_failure": (
        "If the new pool configuration causes connection exhaustion, the application "
        "will return 503 errors to API consumers and the Dimension UI will show "
        "'Service temporarily unavailable'. The blast radius is limited to the "
        "Data Platform service — Portfolio Management and Compliance modules run "
        "on separate infrastructure and are unaffected."
    ),
    "what_if_fails": (
        "Connection pool exhaustion leading to 503 errors for API consumers. The "
        "Dimension UI would show 'Service temporarily unavailable'. Recovery is a "
        "config rollback (revert HikariCP YAML and restart) — estimated 5 minutes."
    ),
    "rollback_plan": (
        "Apply the previous HikariCP configuration (version-controlled and tagged) "
        "via Ansible playbook (same as deployment, different config version), then "
        "rolling restart. The database itself is not modified — this is application-layer "
        "only. Estimated rollback time: 8 minutes including verification."
    ),
    "rollback_duration": "8 minutes including verification across all 3 nodes.",
    "customer_during_rollback": (
        "Same experience as the initial deployment — increased latency (~200ms per "
        "request) for ~45 seconds per node during rolling restart. No data loss. "
        "Total degraded window during rollback: ~3 minutes."
    ),
    "blast_radius": (
        "Limited to the Data Platform service for SimCorp. Portfolio Management and "
        "Compliance modules run on separate infrastructure and are unaffected. The "
        "3 custom REST API integrations will experience brief reconnection during "
        "node restarts but will auto-recover."
    ),
    "maintenance_window": "Yes — the customer has a 4-hour weekly maintenance window.",
    "maintenance_window_when": "Sundays 02:00-06:00 UTC (agreed with customer ops team).",
    "lowest_impact_window": (
        "Sunday 02:00-04:00 UTC — overlaps with the start of the batch processing "
        "window but before the customer's business hours (08:00 CET). The batch "
        "processing can tolerate the brief latency increase during node restarts."
    ),
    "dependencies": (
        "Load balancer drain timeout must be set to 60s. On-call engineer must be "
        "available for 30 minutes post-change. Grafana dashboards must be updated "
        "to track new pool metrics before execution."
    ),
    "customer_aware": "Yes — discussed in the weekly ops sync on 2025-01-13.",
    "customer_agreed": (
        "Yes — customer ops team (Maria Santos) approved the maintenance window "
        "and acknowledged the brief latency increase during rolling restarts."
    ),
    "maintenance_communicated": (
        "Yes — maintenance notification sent via ServiceNow INC-2025-0142 on "
        "2025-01-13. Customer acknowledged receipt. Follow-up reminder scheduled "
        "for 24h before execution."
    ),
    "customer_contact": "Maria Santos (maria.santos@simcorp.com, +45 33 44 55 66).",
    "completion_notification": (
        "Email to Maria Santos and the SimCorp ops distribution list, plus an "
        "update to INC-2025-0142 in ServiceNow. Include before/after metrics "
        "comparison from Grafana."
    ),
}

# Realistic checklist items — the kind of thing you'd actually see in a
# production database connection pool change.
REALISTIC_ITEMS = {
    "pre_flight": [
        {
            "description": "Verify current connection pool metrics are within normal range — check that active connections < 80% of pool size and no connection leak warnings in the last 24h",
            "command": "kubectl exec -n prod deploy/data-platform -- curl -s localhost:8080/actuator/metrics/hikaricp.connections.active | jq '.measurements[0].value'",
        },
        {
            "description": "Confirm the target Ansible playbook version matches what was tested in staging (tag: v2.14.3-pool-migration)",
            "command": "cd /opt/ansible/data-platform && git log --oneline -1 && git describe --tags --exact-match HEAD",
        },
        {
            "description": "Check that the staging environment has been running with the new pool configuration for at least 48h without connection errors",
            "command": "kubectl logs -n staging deploy/data-platform --since=48h | grep -c 'HikariPool.*Connection is not available' || echo '0 errors'",
        },
        {
            "description": "Verify the customer's batch processing window is not currently active — check the scheduler status and confirm no batch jobs are in-flight",
            "command": "kubectl exec -n prod deploy/data-platform -- curl -s localhost:8080/api/v1/scheduler/status | jq '{active_jobs: .activeJobs, next_batch_window: .nextBatchWindow, current_time: now | strftime(\"%Y-%m-%dT%H:%M:%SZ\")}'",
        },
        {
            "description": "Take a snapshot of current dashboard metrics (connection pool size, active connections, pending connections, connection timeout count, p95 acquisition time) for before/after comparison",
            "command": "curl -s 'https://grafana.internal/api/dashboards/uid/hikari-pool-prod' -H 'Authorization: Bearer $GRAFANA_TOKEN' | jq '.dashboard.panels[] | {title, targets: [.targets[].expr]}' > /tmp/pool-metrics-before.json && cat /tmp/pool-metrics-before.json",
        },
        {
            "description": "Confirm load balancer health checks are passing on all 3 nodes and the drain timeout is set to 60s (sufficient for in-flight queries to complete)",
            "command": "aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/data-platform-prod/abc123def456 --query 'TargetHealthDescriptions[*].{Target:Target.Id,Health:TargetHealth.State,Port:Target.Port}' --output table",
        },
        {
            "description": "Verify database server has capacity headroom — current active connections should be under 60% of max_connections (PostgreSQL default 100, our config: 200)",
            "command": "kubectl exec -n prod deploy/data-platform -- psql $DATABASE_URL -t -c \"SELECT count(*) as active, (SELECT setting::int FROM pg_settings WHERE name='max_connections') as max_conn, round(count(*) * 100.0 / (SELECT setting::int FROM pg_settings WHERE name='max_connections'), 1) as pct_used FROM pg_stat_activity WHERE state = 'active';\"",
        },
        {
            "description": (
                "Notify the on-call engineer that the change is starting and confirm "
                "they are available for the next 30 minutes in case rollback is needed"
            ),
        },
    ],
    "execution": [
        {
            "description": "Put node 1 (data-platform-prod-001) into drain mode on the load balancer and wait for active connections to reach zero",
            "command": "aws elbv2 deregister-targets --target-group-arn arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/data-platform-prod/abc123def456 --targets Id=i-0abc123def456789a && echo 'Draining...' && until [ $(aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/data-platform-prod/abc123def456 --query \"TargetHealthDescriptions[?Target.Id=='i-0abc123def456789a'].TargetHealth.State\" --output text) = 'unused' ]; do sleep 5; echo 'waiting...'; done && echo 'Drained'",
        },
        {
            "description": "Deploy new HikariCP configuration to node 1 via Ansible and restart the application",
            "command": "cd /opt/ansible/data-platform && ansible-playbook -i inventory/prod -l data-platform-prod-001 playbooks/deploy-pool-config.yml --extra-vars 'hikari_min_pool=10 hikari_max_pool=50 hikari_connection_timeout=30000 hikari_validation_timeout=5000 hikari_idle_timeout=600000' -v",
            "is_hold_point": True,
        },
        {
            "description": "Verify node 1 started successfully with new pool configuration — check application logs for HikariCP initialization and confirm pool size parameters",
            "command": "kubectl logs -n prod pod/data-platform-prod-001 --tail=50 | grep -A5 'HikariPool.*Started' && kubectl exec -n prod pod/data-platform-prod-001 -- curl -s localhost:8080/actuator/health | jq '.'",
        },
        {
            "description": "Re-register node 1 with the load balancer and wait for it to pass health checks",
            "command": "aws elbv2 register-targets --target-group-arn arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/data-platform-prod/abc123def456 --targets Id=i-0abc123def456789a && until [ $(aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/data-platform-prod/abc123def456 --query \"TargetHealthDescriptions[?Target.Id=='i-0abc123def456789a'].TargetHealth.State\" --output text) = 'healthy' ]; do sleep 10; echo 'waiting for healthy...'; done && echo 'Node 1 healthy'",
        },
        {
            "description": "Wait 5 minutes with node 1 serving traffic, then check for any connection errors or increased latency before proceeding to node 2",
            "command": "echo 'Waiting 5 minutes for soak...' && sleep 300 && kubectl logs -n prod pod/data-platform-prod-001 --since=5m | grep -c 'Connection is not available' || echo '0 connection errors in last 5m'",
            "is_hold_point": True,
        },
        {
            "description": "Repeat drain → deploy → verify → register cycle for node 2 (data-platform-prod-002)",
            "command": "cd /opt/ansible/data-platform && ansible-playbook -i inventory/prod -l data-platform-prod-002 playbooks/rolling-pool-migration.yml --extra-vars 'hikari_min_pool=10 hikari_max_pool=50 hikari_connection_timeout=30000 hikari_validation_timeout=5000 hikari_idle_timeout=600000 drain_wait=true verify_after=true' -v",
        },
        {
            "description": "Repeat drain → deploy → verify → register cycle for node 3 (data-platform-prod-003)",
            "command": "cd /opt/ansible/data-platform && ansible-playbook -i inventory/prod -l data-platform-prod-003 playbooks/rolling-pool-migration.yml --extra-vars 'hikari_min_pool=10 hikari_max_pool=50 hikari_connection_timeout=30000 hikari_validation_timeout=5000 hikari_idle_timeout=600000 drain_wait=true verify_after=true' -v",
        },
        {
            "description": "Verify all 3 nodes are registered, healthy, and serving traffic with the new pool configuration",
            "command": "aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:eu-west-1:123456789012:targetgroup/data-platform-prod/abc123def456 --output table && for pod in data-platform-prod-{001,002,003}; do echo \"--- $pod ---\" && kubectl exec -n prod pod/$pod -- curl -s localhost:8080/actuator/metrics/hikaricp.connections.max | jq '.measurements[0].value'; done",
        },
    ],
    "verification": [
        {
            "description": "Check connection pool metrics across all nodes — active connections should be within the new min/max range (10-50) and no pending connection requests",
            "command": "for pod in data-platform-prod-{001,002,003}; do echo \"--- $pod ---\" && kubectl exec -n prod pod/$pod -- curl -s localhost:8080/actuator/metrics/hikaricp.connections | jq '{active: .measurements[0].value, idle: .measurements[1].value, pending: .measurements[2].value, max: .measurements[3].value}'; done",
        },
        {
            "description": "Verify p95 connection acquisition latency has improved — should be under 200ms (was ~800ms before)",
            "command": 'kubectl exec -n prod deploy/data-platform -- curl -s localhost:8080/actuator/metrics/hikaricp.connections.acquire | jq \'{p95_ms: (.measurements[] | select(.statistic=="PERCENTILE_95") | .value * 1000 | round), count: (.measurements[] | select(.statistic=="COUNT") | .value)}\'',
        },
        {
            "description": "Check application error rate in the last 15 minutes — should be zero connection timeout errors",
            "command": "kubectl logs -n prod deploy/data-platform --since=15m | grep -c 'HikariPool.*Connection is not available' && kubectl logs -n prod deploy/data-platform --since=15m | grep -c 'SQLTransientConnectionException' || echo 'No connection errors found'",
        },
        {
            "description": "Verify the customer's API integrations are functioning — check the 3 persistent connections are re-established and recent API calls are succeeding",
            "command": "kubectl exec -n prod deploy/data-platform -- curl -s localhost:8080/api/v1/integrations/health | jq '.integrations[] | {name, status, last_successful_call, connection_pool_id}'",
        },
        {
            "description": "Compare Grafana dashboard metrics with the pre-change snapshot — connection pool utilisation should be lower, acquisition time faster, timeout count zero",
            "command": "diff <(cat /tmp/pool-metrics-before.json | jq -S .) <(curl -s 'https://grafana.internal/api/dashboards/uid/hikari-pool-prod' -H 'Authorization: Bearer $GRAFANA_TOKEN' | jq -S '.dashboard.panels[] | {title, targets: [.targets[].expr]}') || echo 'Dashboards have been updated with new metrics'",
        },
        {
            "description": "Run a synthetic load test at 50% of peak traffic for 2 minutes to verify pool scaling behaviour under load",
            "command": "kubectl run loadtest --rm -i --image=grafana/k6:latest --restart=Never -- run --vus 50 --duration 2m - <<'SCRIPT'\nimport http from 'k6/http';\nimport { check } from 'k6';\nexport default function() {\n  const res = http.get('https://data-platform.prod.internal/api/v1/health');\n  check(res, { 'status 200': (r) => r.status === 200 });\n}\nSCRIPT",
            "is_hold_point": True,
        },
        {
            "description": "Notify the on-call engineer that the change is complete and update the incident channel with the results. Include before/after metrics comparison.",
        },
    ],
}

# Realistic multi-line terminal output for completion records
REALISTIC_OUTPUTS = {
    "pool_metrics": """NAMESPACE   NAME                      ACTIVE   IDLE   PENDING   MAX
prod        data-platform-prod-001    12       8      0         50
prod        data-platform-prod-002    15       5      0         50
prod        data-platform-prod-003    11       9      0         50

Total active connections: 38/150 (25.3%)
No pending requests in queue.""",
    "health_check": """{
  "status": "UP",
  "components": {
    "db": {
      "status": "UP",
      "details": {
        "database": "PostgreSQL",
        "validationQuery": "isValid()",
        "result": "validated"
      }
    },
    "diskSpace": {
      "status": "UP",
      "details": {
        "total": 107374182400,
        "free": 85899345920,
        "threshold": 10485760
      }
    },
    "hikariPool": {
      "status": "UP",
      "details": {
        "pool": "HikariPool-1",
        "activeConnections": 12,
        "idleConnections": 8,
        "totalConnections": 20,
        "maxPoolSize": 50,
        "minIdle": 10,
        "connectionTimeout": 30000
      }
    }
  }
}""",
    "target_health": """--------------------------------------------------------------------
|                     DescribeTargetHealth                          |
+------------------------+-----------+-----+                       |
|       Target.Id        |  Health   | Port|                       |
+------------------------+-----------+-----+                       |
| i-0abc123def456789a    |  healthy  | 8080|                       |
| i-0bcd234efg567890b    |  healthy  | 8080|                       |
| i-0cde345fgh678901c    |  healthy  | 8080|                       |
+------------------------+-----------+-----+""",
    "ansible_output": """PLAY [Deploy pool config to data-platform-prod-001] ****************************

TASK [Gathering Facts] ********************************************************
ok: [data-platform-prod-001]

TASK [backup current config] **************************************************
changed: [data-platform-prod-001]

TASK [deploy hikari config] ***************************************************
changed: [data-platform-prod-001] => {
    "changed": true,
    "dest": "/opt/data-platform/config/hikari.yml",
    "checksum": "a8f5f167f44f4964e6c998dee827110c",
    "gid": 1000,
    "group": "app",
    "mode": "0644",
    "owner": "app",
    "size": 482
}

TASK [restart application] ****************************************************
changed: [data-platform-prod-001]

TASK [wait for health check] **************************************************
ok: [data-platform-prod-001] => {
    "msg": "Health check passed after 12 seconds"
}

PLAY RECAP ********************************************************************
data-platform-prod-001     : ok=5    changed=3    unreachable=0    failed=0    skipped=0""",
}


def _create_executing_change_realistic(client, sample_change_data):
    """Create a change with realistic long content and move it to executing."""
    resp = client.post(
        "/api/v1/changes",
        json={
            "title": "Migrate HikariCP connection pool to dynamic scaling (PROD-EU, SimCorp Data Platform)",
            "description": (
                "The Data Platform service for SimCorp is experiencing intermittent "
                "connection timeout errors during peak hours (~15/hour) due to the "
                "fixed connection pool size of 20. This change migrates to a dynamic "
                "pool (10-50 connections) with shorter timeouts and validation queries. "
                "The change was tested in staging for 72h with no errors. Rolling "
                "deployment across 3 nodes behind the load balancer."
            ),
            "author_name": "Adrian Hornsby",
            **sample_change_data,
            "preflight_answers": _complete_preflight_realistic(client),
            "defence_tags": ["database", "application"],
        },
    )
    assert resp.status_code in (200, 201), f"Failed to create change: {resp.json()}"
    change_id = resp.json()["id"]

    # Add all realistic checklist items
    created_items = {}
    for phase, item_list in REALISTIC_ITEMS.items():
        created_items[phase] = []
        for item_data in item_list:
            payload = {"phase": phase, **item_data}
            r = client.post(
                f"/api/v1/changes/{change_id}/checklist",
                json=payload,
            )
            assert r.status_code in (200, 201), f"Failed to add item: {r.json()}"
            created_items[phase].append(r.json())

    # Move to executing: draft → in_review → approved → executing
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "in_review", "actor_name": "Adrian Hornsby"},
    )
    review = client.post(
        f"/api/v1/changes/{change_id}/reviewers",
        json={"reviewer_name": "Senior Engineer"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/reviewers/{review.json()['id']}/decision",
        json={"decision": "approved", "comment": "Staging results look solid. Approved."},
    )
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "approved", "actor_name": "Adrian Hornsby"},
    )
    client.post(
        f"/api/v1/changes/{change_id}/transition",
        params={"target_status": "executing", "actor_name": "Adrian Hornsby"},
    )

    return change_id, created_items


class TestRealisticContent:
    """Verify the system handles production-scale content without truncation or errors."""

    def test_change_created_with_long_content(self, client, sample_change_data):
        """All content is stored and returned without truncation."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        # Verify the change
        resp = client.get(f"/api/v1/changes/{change_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["title"]) > 70  # Long title
        assert len(data["description"]) > 200  # Long description
        assert data["defence_tags"] == ["database", "application"]

        # Verify preflight answers are full paragraphs
        for key, answer in data["preflight_answers"].items():
            assert len(answer) > 50, f"Answer for {key} seems truncated"

    def test_many_items_per_phase(self, client, sample_change_data):
        """8+ items per phase are stored and ordered correctly."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/checklist")
        assert resp.status_code == 200
        checklist = resp.json()

        # Count items per phase
        by_phase = {}
        for item in checklist:
            by_phase.setdefault(item["phase"], []).append(item)

        assert len(by_phase["pre_flight"]) == 8
        assert len(by_phase["execution"]) == 8
        assert len(by_phase["verification"]) == 7

        # Verify ordering is preserved
        for phase_items in by_phase.values():
            orders = [item["order"] for item in phase_items]
            assert orders == sorted(orders), f"Items not in order: {orders}"

    def test_long_commands_stored_exactly(self, client, sample_change_data):
        """Long multi-flag commands with pipes, ARNs, and JSON are stored verbatim."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/checklist")
        checklist = resp.json()

        # Find the longest command and verify it's intact
        commands = [item["command"] for item in checklist if item["command"]]
        longest = max(commands, key=len)
        assert len(longest) > 300, f"Longest command only {len(longest)} chars"

        # Verify pipes and special chars survived
        pipe_commands = [c for c in commands if "|" in c]
        assert len(pipe_commands) > 0, "No piped commands found"

        arn_commands = [c for c in commands if "arn:aws:" in c]
        assert len(arn_commands) > 0, "No ARN-containing commands found"

    def test_hold_points_on_realistic_items(self, client, sample_change_data):
        """Hold points are correctly set on specific execution items."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/checklist")
        checklist = resp.json()

        hold_points = [item for item in checklist if item["is_hold_point"]]
        assert len(hold_points) == 3  # 2 in execution, 1 in verification

    def test_completion_with_long_pasted_output(self, client, sample_change_data):
        """Multi-line terminal output can be pasted as the observed result."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        # Complete all pre-flight items with realistic output
        for i, pf_item in enumerate(items["pre_flight"]):
            output = REALISTIC_OUTPUTS.get(
                "pool_metrics" if i == 0 else "health_check",
                f"Step {i + 1} completed successfully.\n"
                f"Checked at: 2025-01-15T14:30:{i:02d}Z\n"
                f"Result: PASS — all values within expected range.\n"
                f"Details logged to /var/log/changebook/change-{change_id[:8]}.log",
            )
            resp = client.post(
                f"/api/v1/changes/{change_id}/checklist/{pf_item['id']}/complete",
                json={
                    "observed_result": output,
                    "status": "completed",
                    "completed_by": "Adrian Hornsby",
                },
            )
            assert resp.status_code == 200
            # Verify the full output is returned
            assert resp.json()["observed_result"] == output

    def test_execution_status_with_many_items(self, client, sample_change_data):
        """Execution status correctly tracks progress across 23 items."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/execution-status")
        data = resp.json()
        assert data["total_items"] == 23  # 8 + 8 + 7
        assert data["completed_items"] == 0
        assert data["current_phase"] == "pre_flight"
        assert data["phases"]["pre_flight"]["total"] == 8
        assert data["phases"]["execution"]["total"] == 8
        assert data["phases"]["verification"]["total"] == 7

    def test_full_lifecycle_with_realistic_content(self, client, sample_change_data):
        """Complete all 23 items and transition to done — the full lifecycle."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        # Complete all items across all phases
        all_items = items["pre_flight"] + items["execution"] + items["verification"]
        hold_point_ids = set()

        for i, item_data in enumerate(all_items):
            # Check if this is a hold point from our definition
            if item_data.get("is_hold_point"):
                hold_point_ids.add(item_data["id"])

            # If previous item was a hold point, verify it first
            if i > 0 and all_items[i - 1]["id"] in hold_point_ids:
                prev_id = all_items[i - 1]["id"]
                client.post(
                    f"/api/v1/changes/{change_id}/checklist/{prev_id}/hold-point-verify",
                    json={"verified_by": "Senior Engineer"},
                )

            resp = client.post(
                f"/api/v1/changes/{change_id}/checklist/{item_data['id']}/complete",
                json={
                    "observed_result": REALISTIC_OUTPUTS.get(
                        "ansible_output"
                        if "ansible" in (item_data.get("command") or "").lower()
                        else "target_health"
                        if "describe-target" in (item_data.get("command") or "")
                        else "health_check",
                        f"Step {i + 1}/{len(all_items)} completed. Output verified against expected outcome.",
                    ),
                    "status": "completed",
                    "completed_by": "Adrian Hornsby",
                },
            )
            assert resp.status_code == 200, (
                f"Failed to complete item {i + 1} ({item_data['description'][:60]}): {resp.json()}"
            )

        # Verify the last hold point (in verification phase)
        last_hold = [i for i in all_items if i["id"] in hold_point_ids][-1]
        client.post(
            f"/api/v1/changes/{change_id}/checklist/{last_hold['id']}/hold-point-verify",
            json={"verified_by": "Senior Engineer"},
        )

        # Check execution status — all done
        resp = client.get(f"/api/v1/changes/{change_id}/execution-status")
        data = resp.json()
        assert data["completed_items"] == 23
        assert data["all_complete"] is True

        # Transition to done
        resp = client.post(
            f"/api/v1/changes/{change_id}/transition",
            params={"target_status": "done", "actor_name": "Adrian Hornsby"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_markdown_export_with_realistic_content(self, client, sample_change_data):
        """Markdown export handles long content without truncation."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        resp = client.get(f"/api/v1/changes/{change_id}/export/markdown")
        assert resp.status_code == 200
        md = resp.text

        # Verify key content is present
        assert "HikariCP" in md
        assert "SimCorp" in md or "Data Platform" in md
        assert "pre_flight" in md.lower() or "pre-flight" in md.lower()
        assert "execution" in md.lower()
        assert "verification" in md.lower()

        # Verify it's substantial
        assert len(md) > 2000, f"Export seems too short: {len(md)} chars"

    def test_duplicate_preserves_long_content(self, client, sample_change_data):
        """Duplicating a change with realistic content preserves everything."""
        change_id, items = _create_executing_change_realistic(client, sample_change_data)

        resp = client.post(
            f"/api/v1/changes/{change_id}/duplicate",
            json={"author_name": "Another Engineer"},
        )
        assert resp.status_code in (200, 201)
        clone = resp.json()

        # Verify content carried over
        assert "HikariCP" in clone["title"]
        assert len(clone["description"]) > 200
        assert clone["preflight_answers"] is not None
        assert len(clone["preflight_answers"]) > 0
        assert clone["defence_tags"] == ["database", "application"]
        assert clone["status"] == "draft"

        # Verify checklist items were cloned
        resp = client.get(f"/api/v1/changes/{clone['id']}/checklist")
        cloned_checklist = resp.json()
        assert len(cloned_checklist) == 23
