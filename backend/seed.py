"""Seed script — clean database and populate with demo data.

Usage:
    cd backend
    python seed.py

Requires a running Postgres instance (docker compose up db).
Wipes all existing data, then creates:
- 1 organisation ("Default")
- 2 customers with services
- 3 environments
- 2 certificate rotation templates with realistic checklists
"""

import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

# Ensure all models are imported so create_all picks them up
import app.models  # noqa: F401
from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.checklist import ChecklistPhase
from app.models.customer import Customer, Service
from app.models.environment import Environment
from app.models.organisation import Organisation
from app.models.team import Team  # noqa: F401 — needed for relationship resolution
from app.models.template import ChangeTemplate, TemplateChecklistItem


def wipe(db: Session) -> None:
    """Drop all data in dependency order."""
    db.execute(text("DELETE FROM audit_events"))
    db.execute(text("DELETE FROM checklist_completions"))
    db.execute(text("DELETE FROM checklist_items"))
    db.execute(text("DELETE FROM reviews"))
    db.execute(text("DELETE FROM template_checklist_items"))
    db.execute(text("DELETE FROM change_templates"))
    db.execute(text("DELETE FROM changes"))
    db.execute(text("DELETE FROM services"))
    db.execute(text("DELETE FROM environments"))
    db.execute(text("DELETE FROM customers"))
    db.execute(text("DELETE FROM teams"))
    db.execute(text("DELETE FROM organisations"))
    db.commit()
    print("  Wiped all tables.")


def create_org(db: Session) -> Organisation:
    org = Organisation(name="Default")
    db.add(org)
    db.flush()
    return org


def create_customers(db: Session, org: Organisation) -> dict:
    # Customer 1: Meridian Capital
    meridian = Customer(
        name="Meridian Capital",
        description="Investment management platform — 400+ Linux VMs across three data centres",
        organisation_id=org.id,
    )
    db.add(meridian)
    db.flush()

    meridian_trading = Service(
        name="Trading Platform",
        description="Order execution and market data services",
        customer_id=meridian.id,
    )
    meridian_risk = Service(
        name="Risk Engine",
        description="Real-time risk calculation and reporting",
        customer_id=meridian.id,
    )
    db.add_all([meridian_trading, meridian_risk])
    db.flush()

    # Customer 2: NorthStar Logistics
    northstar = Customer(
        name="NorthStar Logistics",
        description="Fleet management and route optimisation — hybrid cloud, 60 bare-metal nodes",
        organisation_id=org.id,
    )
    db.add(northstar)
    db.flush()

    northstar_fleet = Service(
        name="Fleet Tracker",
        description="Real-time vehicle position and telemetry ingestion",
        customer_id=northstar.id,
    )
    northstar_api = Service(
        name="Customer API",
        description="REST API for route planning and shipment tracking",
        customer_id=northstar.id,
    )
    db.add_all([northstar_fleet, northstar_api])
    db.flush()

    return {
        "meridian": meridian,
        "northstar": northstar,
    }


def create_environments(db: Session, org: Organisation, customers: dict) -> None:
    envs = [
        Environment(
            name="PROD-EU-01",
            platform="On-prem / RHEL 9",
            description="Primary production — Frankfurt data centre, 120 nodes",
            organisation_id=org.id,
            customer_id=customers["meridian"].id,
        ),
        Environment(
            name="PROD-US-01",
            platform="On-prem / RHEL 9",
            description="US production — Virginia data centre, 80 nodes",
            organisation_id=org.id,
            customer_id=customers["meridian"].id,
        ),
        Environment(
            name="PROD-LON",
            platform="Bare metal / Ubuntu 22.04",
            description="London colocation — fleet tracker primary site, 60 nodes",
            organisation_id=org.id,
            customer_id=customers["northstar"].id,
        ),
    ]
    db.add_all(envs)
    db.flush()


def create_templates(db: Session) -> None:
    _create_tls_cert_rotation_template(db)
    _create_internal_ca_renewal_template(db)


def _create_tls_cert_rotation_template(db: Session) -> None:
    """TLS certificate rotation on a fleet of Linux machines behind a load balancer."""
    template = ChangeTemplate(
        title="TLS certificate rotation — Linux fleet (LB-fronted)",
        description=(
            "Rotate expiring TLS certificates on a fleet of Linux machines served "
            "behind a load balancer. Covers: new cert deployment, per-node service "
            "reload, LB health check validation, and customer-facing verification. "
            "Designed for rolling rotation with zero downtime — nodes are drained "
            "from the LB pool before reload and re-added after health check passes."
        ),
        defence_tags=["certificate-management", "zero-downtime"],
        preflight_answers={
            "what_is_this_change": (
                "Rotate the TLS certificate on all nodes in the target fleet. "
                "The current certificate expires within 30 days. New certificate "
                "is issued by the same CA, same SANs, same key type (ECDSA P-256). "
                "Deployment is per-node: copy cert and key, reload the service "
                "(nginx/haproxy), verify via LB health check, then move to the next node."
            ),
            "expected_outcome": (
                "All nodes serve the new certificate. The old certificate is archived. "
                "No client-visible errors or connection resets during rotation. "
                "LB health checks remain green throughout."
            ),
            "what_if_fails": (
                "If a node fails to reload with the new cert, it stays drained from "
                "the LB pool. Traffic continues on remaining healthy nodes. The failed "
                "node is investigated individually — the fleet is never left in a state "
                "where a bad cert is serving traffic."
            ),
            "rollback_plan": (
                "Per-node rollback: restore the previous cert and key from "
                "/etc/ssl/certs/tls.crt.bak and /etc/ssl/private/tls.key.bak, "
                "reload the service, verify via health check, re-add to LB pool. "
                "If multiple nodes fail, rollback in reverse order of deployment."
            ),
            "rollback_duration": (
                "Under 2 minutes per node. Full fleet rollback depends on fleet size "
                "but each node is independent — rollback is parallelisable if needed."
            ),
            "blast_radius": (
                "Single customer, single fleet. No shared infrastructure affected. "
                "Each node is independent — a bad cert on one node cannot propagate "
                "to others."
            ),
            "dependencies": (
                "New certificate must be issued and available on the deployment host "
                "before starting. CA chain must be unchanged — if the CA rotated its "
                "intermediate, the full chain file needs updating too."
            ),
        },
        author_name="Alice Engineer",
    )
    db.add(template)
    db.flush()

    items = [
        # --- Pre-flight ---
        (
            "pre_flight",
            1,
            "Verify new certificate is valid and matches expected SANs",
            "openssl x509 -in /path/to/new/tls.crt -noout -text | grep -A1 'Subject Alternative Name'",
            "SANs match the expected list for this fleet. Not Before date is today or earlier. Not After is 1 year out.",
            None,
            False,
        ),
        (
            "pre_flight",
            2,
            "Verify certificate chain is complete",
            "openssl verify -CAfile /path/to/ca-chain.pem /path/to/new/tls.crt",
            "Output: /path/to/new/tls.crt: OK",
            None,
            False,
        ),
        (
            "pre_flight",
            3,
            "Verify private key matches certificate",
            "diff <(openssl x509 -in /path/to/new/tls.crt -noout -modulus) <(openssl rsa -in /path/to/new/tls.key -noout -modulus)",
            "No output (modulus values match). Any diff = wrong key for this cert.",
            "Do NOT proceed. Obtain the correct private key or re-issue the certificate.",
            False,
        ),
        (
            "pre_flight",
            4,
            "Confirm current certificate expiry date",
            "openssl s_client -connect <node>:443 -servername <hostname> </dev/null 2>/dev/null | openssl x509 -noout -enddate",
            "Shows the expiry date of the cert currently in production. Confirms this rotation is needed.",
            None,
            False,
        ),
        (
            "pre_flight",
            5,
            "List target nodes and verify LB pool membership",
            "curl -s https://<lb>/api/health | jq '.nodes'",
            "All target nodes are listed and marked healthy in the LB pool.",
            None,
            False,
        ),
        (
            "pre_flight",
            6,
            "Back up current cert and key on all target nodes",
            "for node in $NODES; do ssh $node 'cp /etc/ssl/certs/tls.crt /etc/ssl/certs/tls.crt.bak && cp /etc/ssl/private/tls.key /etc/ssl/private/tls.key.bak'; done",
            "Backup files exist on every node. Verify: ssh $node 'ls -la /etc/ssl/certs/tls.crt.bak'",
            None,
            False,
        ),
        (
            "pre_flight",
            7,
            "Confirm maintenance window is communicated and agreed",
            None,
            "Customer contact has acknowledged the maintenance window. Ticket/email reference recorded.",
            None,
            True,
        ),
        # --- Execution ---
        (
            "execution",
            1,
            "Drain first node from LB pool",
            "curl -X POST https://<lb>/api/nodes/<node1>/drain",
            "Node reports 'draining'. LB stops sending new connections. Existing connections complete.",
            "Re-enable node: curl -X POST https://<lb>/api/nodes/<node1>/enable",
            False,
        ),
        (
            "execution",
            2,
            "Wait for active connections to complete on drained node",
            "ssh <node1> 'ss -tn state established | grep :443 | wc -l'",
            "Connection count drops to 0 (or near 0). Wait up to 60s for graceful drain.",
            None,
            False,
        ),
        (
            "execution",
            3,
            "Deploy new cert and key to first node",
            "scp tls.crt <node1>:/etc/ssl/certs/tls.crt && scp tls.key <node1>:/etc/ssl/private/tls.key",
            "Files copied successfully. Permissions: cert 644, key 600.",
            "Restore from backup: ssh <node1> 'cp /etc/ssl/certs/tls.crt.bak /etc/ssl/certs/tls.crt && cp /etc/ssl/private/tls.key.bak /etc/ssl/private/tls.key'",
            False,
        ),
        (
            "execution",
            4,
            "Reload service on first node",
            "ssh <node1> 'systemctl reload nginx'",
            "Exit code 0. Service stays running. No restart — reload picks up new cert without dropping connections.",
            "If reload fails: check nginx -t for config errors. If cert is the problem, restore from backup and reload again.",
            False,
        ),
        (
            "execution",
            5,
            "Verify new cert is being served on first node",
            "openssl s_client -connect <node1>:443 -servername <hostname> </dev/null 2>/dev/null | openssl x509 -noout -serial -enddate",
            "Serial matches the new certificate. End date matches expected expiry.",
            "If old cert is still served: the reload didn't take. Try systemctl restart nginx (causes brief downtime on this node).",
            False,
        ),
        (
            "execution",
            6,
            "Re-add first node to LB pool and verify health check",
            "curl -X POST https://<lb>/api/nodes/<node1>/enable",
            "Node status changes to 'healthy'. LB health check passes within 10s.",
            "If health check fails: drain node again, check logs, verify cert chain.",
            True,
        ),
        (
            "execution",
            7,
            "Repeat steps 1-6 for each remaining node",
            None,
            "Each node: drain -> wait -> deploy -> reload -> verify cert -> re-add -> health check green. Record each node's completion.",
            "If any node fails, stop. Do not proceed to the next node until the failed node is resolved or rolled back.",
            False,
        ),
        # --- Verification ---
        (
            "verification",
            1,
            "Verify all nodes are healthy in LB pool",
            "curl -s https://<lb>/api/health | jq '.nodes[] | {name, status}'",
            "Every node shows status: healthy. No nodes missing from the pool.",
            None,
            False,
        ),
        (
            "verification",
            2,
            "Verify new certificate via external client connection",
            "curl -vI https://<public-hostname>/ 2>&1 | grep -E 'expire|serial|subject'",
            "Serial and expiry match the new certificate. Subject matches expected hostname.",
            None,
            False,
        ),
        (
            "verification",
            3,
            "Check for TLS errors in service logs",
            'ssh <node1> \'journalctl -u nginx --since "10 minutes ago" | grep -i "ssl\\|tls\\|cert" | grep -i "error\\|fail\\|warn"\'',
            "No TLS-related errors in logs on any node.",
            None,
            False,
        ),
        (
            "verification",
            4,
            "Confirm certificate expiry monitoring is updated",
            None,
            "Monitoring system shows the new expiry date for all nodes. Alert threshold (30 days) is correct.",
            None,
            False,
        ),
        (
            "verification",
            5,
            "Customer confirmation — service is operating normally",
            None,
            "Customer contact confirms no issues observed from their side. Or: customer-facing health endpoint returns 200.",
            None,
            True,
        ),
    ]

    for phase_str, order, desc, command, expected, rollback, hold in items:
        phase = {
            "pre_flight": ChecklistPhase.PRE_FLIGHT,
            "execution": ChecklistPhase.EXECUTION,
            "verification": ChecklistPhase.VERIFICATION,
        }[phase_str]

        db.add(
            TemplateChecklistItem(
                template_id=template.id,
                phase=phase,
                order=order,
                description=desc,
                command=command,
                expected_outcome=expected,
                rollback_action=rollback,
                is_hold_point=hold,
            )
        )


def _create_internal_ca_renewal_template(db: Session) -> None:
    """Internal CA certificate renewal — root or intermediate CA rotation."""
    template = ChangeTemplate(
        title="Internal CA certificate renewal — trust store update",
        description=(
            "Renew an internal CA certificate (root or intermediate) and update "
            "trust stores across the fleet. This is higher-risk than a leaf cert "
            "rotation because every service that validates certificates against "
            "this CA is affected. Requires careful sequencing: deploy new CA cert "
            "to trust stores first, then rotate any leaf certs signed by the old CA."
        ),
        defence_tags=["certificate-management", "high-blast-radius"],
        preflight_answers={
            "what_is_this_change": (
                "Renew the internal CA intermediate certificate and deploy the updated "
                "CA chain to all trust stores across the fleet. The current intermediate "
                "expires in 45 days. All leaf certificates signed by this intermediate "
                "will continue to validate against the new chain because the new "
                "intermediate uses the same key pair (re-issue, not re-key)."
            ),
            "expected_outcome": (
                "All machines trust the new CA chain. Existing leaf certificates "
                "continue to validate. No service-to-service TLS handshake failures. "
                "Certificate validation logs show no errors."
            ),
            "what_if_fails": (
                "If the new CA chain is deployed incorrectly or the chain is incomplete, "
                "services that validate peer certificates will reject connections. "
                "This can cause cascading failures across service-to-service communication. "
                "The blast radius is the entire fleet — every service that uses mTLS."
            ),
            "rollback_plan": (
                "Restore the previous CA bundle from /etc/pki/ca-trust/source/anchors/internal-ca.pem.bak "
                "and run update-ca-trust on each node. If leaf certs were already re-issued, "
                "they must also be rolled back to the previous versions."
            ),
            "rollback_duration": (
                "Trust store rollback: under 1 minute per node, parallelisable across the fleet. "
                "If leaf certs were also rotated: add 2-3 minutes per service per node."
            ),
            "blast_radius": (
                "High. All services using mTLS within the fleet are affected. "
                "This includes service-to-service communication, database connections "
                "using client certs, and any internal APIs that validate the CA chain."
            ),
            "dependencies": (
                "New CA intermediate must be signed by the existing root CA. "
                "The root CA private key must be available (typically offline/HSM). "
                "All leaf certificates should be inventoried before starting — any "
                "leaf cert expiring within 7 days of the CA renewal should be rotated "
                "at the same time."
            ),
        },
        author_name="Alice Engineer",
    )
    db.add(template)
    db.flush()

    items = [
        # --- Pre-flight ---
        (
            "pre_flight",
            1,
            "Verify new CA intermediate certificate is correctly signed by root",
            "openssl verify -CAfile /path/to/root-ca.pem /path/to/new-intermediate.pem",
            "Output: OK. The new intermediate is signed by the trusted root.",
            None,
            False,
        ),
        (
            "pre_flight",
            2,
            "Verify new CA intermediate key matches (if re-keyed)",
            "diff <(openssl x509 -in /path/to/new-intermediate.pem -noout -modulus) <(openssl rsa -in /path/to/intermediate.key -noout -modulus)",
            "No output if same key pair (re-issue). If re-keyed: modulus will differ — all leaf certs must be re-issued.",
            None,
            False,
        ),
        (
            "pre_flight",
            3,
            "Inventory all leaf certificates signed by this CA",
            "find /etc/ssl/certs -name '*.crt' -exec openssl x509 -in {} -noout -issuer \\; | grep 'Internal CA'",
            "Complete list of leaf certs that depend on this CA. Note any expiring within 7 days.",
            None,
            False,
        ),
        (
            "pre_flight",
            4,
            "Build and verify the full chain file",
            "cat new-intermediate.pem root-ca.pem > ca-chain.pem && openssl verify -CAfile ca-chain.pem new-intermediate.pem",
            "Chain file validates. Order: intermediate first, root second.",
            None,
            False,
        ),
        (
            "pre_flight",
            5,
            "Test trust store update on a non-production node",
            "scp ca-chain.pem test-node:/etc/pki/ca-trust/source/anchors/internal-ca.pem && ssh test-node 'update-ca-trust && openssl s_client -connect localhost:8443 -CApath /etc/pki/tls/certs/ </dev/null 2>&1 | grep \"Verify return code\"'",
            "Verify return code: 0 (ok). Services on test node can still validate certs.",
            None,
            True,
        ),
        # --- Execution ---
        (
            "execution",
            1,
            "Back up current CA bundle on all target nodes",
            "for node in $NODES; do ssh $node 'cp /etc/pki/ca-trust/source/anchors/internal-ca.pem /etc/pki/ca-trust/source/anchors/internal-ca.pem.bak'; done",
            "Backup exists on every node.",
            None,
            False,
        ),
        (
            "execution",
            2,
            "Deploy new CA chain to all nodes",
            "for node in $NODES; do scp ca-chain.pem $node:/etc/pki/ca-trust/source/anchors/internal-ca.pem; done",
            "File copied to every node. Verify checksum matches source.",
            "Restore backups: for node in $NODES; do ssh $node 'cp /etc/pki/ca-trust/source/anchors/internal-ca.pem.bak /etc/pki/ca-trust/source/anchors/internal-ca.pem'; done",
            False,
        ),
        (
            "execution",
            3,
            "Update trust stores on all nodes",
            "for node in $NODES; do ssh $node 'update-ca-trust'; done",
            "Exit code 0 on every node. Trust store rebuilt with new CA.",
            "Restore backup and re-run update-ca-trust on affected nodes.",
            False,
        ),
        (
            "execution",
            4,
            "Verify mTLS connections between services still work",
            "ssh <node1> 'curl -v --cacert /etc/pki/tls/certs/ca-bundle.crt https://<node2>:8443/health'",
            "200 OK. TLS handshake succeeds. No certificate validation errors.",
            "If handshake fails: check chain completeness. Most common issue is missing intermediate in the chain file.",
            True,
        ),
        # --- Verification ---
        (
            "verification",
            1,
            "Check certificate validation logs across fleet",
            'for node in $NODES; do echo "=== $node ==="; ssh $node \'journalctl --since "30 minutes ago" | grep -i "certificate\\|ssl\\|tls" | grep -i "error\\|fail\\|reject"\'; done',
            "No certificate errors on any node.",
            None,
            False,
        ),
        (
            "verification",
            2,
            "Verify service-to-service connectivity (sample check)",
            None,
            "Pick 3 representative service pairs and confirm they can communicate over mTLS. No TLS errors in application logs.",
            None,
            False,
        ),
        (
            "verification",
            3,
            "Confirm monitoring shows new CA expiry date",
            None,
            "Certificate monitoring dashboard shows the new intermediate expiry date. Alert thresholds are correct.",
            None,
            False,
        ),
        (
            "verification",
            4,
            "Sign-off: fleet is healthy, no customer-reported issues",
            None,
            "All health checks green. No customer-reported TLS errors. Team lead confirms change is complete.",
            None,
            True,
        ),
    ]

    for phase_str, order, desc, command, expected, rollback, hold in items:
        phase = {
            "pre_flight": ChecklistPhase.PRE_FLIGHT,
            "execution": ChecklistPhase.EXECUTION,
            "verification": ChecklistPhase.VERIFICATION,
        }[phase_str]

        db.add(
            TemplateChecklistItem(
                template_id=template.id,
                phase=phase,
                order=order,
                description=desc,
                command=command,
                expected_outcome=expected,
                rollback_action=rollback,
                is_hold_point=hold,
            )
        )


def main():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding database...")
        wipe(db)

        org = create_org(db)
        print("  Created organisation: Default")

        customers = create_customers(db, org)
        print(f"  Created customers: {', '.join(c.name for c in customers.values())}")

        create_environments(db, org, customers)
        print("  Created environments: PROD-EU-01, PROD-US-01, PROD-LON")

        create_templates(db)
        print("  Created templates: TLS cert rotation, Internal CA renewal")

        db.commit()
        print("\nDone. Database is clean with demo data.")
        print("People (from auth): Alice Engineer, Bob Reviewer, Carol Operator, Dave Manager")

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
