#!/usr/bin/env python3
"""Validate OmniGate release-gate policy and evaluate the current status."""
import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "omnigate-platform"


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def validate(policy, release_status):
    errors = []
    gates = policy.get("gates", [])
    gate_ids = [gate.get("id") for gate in gates]
    if len(gate_ids) != len(set(gate_ids)) or not gate_ids:
        errors.append("gate IDs must be non-empty and unique")
    known = set(gate_ids)
    allowed = set(policy.get("verdicts", []))
    for gate in gates:
        for field in ("id", "name", "scope", "required_evidence", "pass_criteria"):
            if not gate.get(field):
                errors.append("gate %s has no %s" % (gate.get("id", "?"), field))
    for name, release_class in policy.get("release_classes", {}).items():
        required = set(release_class.get("required_gates", []))
        limited = set(release_class.get("limitations_allowed_at", []))
        if not required <= known:
            errors.append("release class %s references unknown gates" % name)
        if not limited <= required:
            errors.append("release class %s allows limitations outside required gates" % name)
    assessment = release_status.get("gate_assessment", {})
    if set(assessment) != known:
        errors.append("gate_assessment must contain exactly: %s" % ", ".join(sorted(known)))
    for gate_id, result in assessment.items():
        if result.get("status") not in allowed:
            errors.append("%s has invalid status %r" % (gate_id, result.get("status")))
        if result.get("status") in ("passed", "passed-with-limitations") and not result.get("evidence"):
            errors.append("%s passes without evidence references" % gate_id)
        if result.get("status") == "passed-with-limitations" and not result.get("limitations"):
            errors.append("%s has limited status without limitations" % gate_id)
        if result.get("status") == "not-applicable" and not result.get("reason"):
            errors.append("%s is not-applicable without a reason" % gate_id)
    return errors


def evaluate(policy, release_status, release_class, profile, claim_fieldbus):
    rule = policy["release_classes"][release_class]
    required = list(rule["required_gates"])
    conditional = policy.get("conditional_gates", {})
    if profile == "enhanced":
        required.append(conditional["enhanced_profile"])
    if claim_fieldbus:
        required.append(conditional["fieldbus_interoperability_claim"])
    required = list(dict.fromkeys(required))
    limitations_allowed = set(rule.get("limitations_allowed_at", []))
    blockers = []
    for gate_id in required:
        status = release_status["gate_assessment"][gate_id]["status"]
        if status == "passed":
            continue
        if status == "passed-with-limitations" and gate_id in limitations_allowed:
            continue
        blockers.append({"gate": gate_id, "status": status})
    verdict = "passed-with-limitations" if not blockers and any(
        release_status["gate_assessment"][gate_id]["status"] == "passed-with-limitations"
        for gate_id in required
    ) else ("passed" if not blockers else "failed")
    return {"release_class": release_class, "profile": profile,
            "required_gates": required, "verdict": verdict, "blockers": blockers}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-class", choices=("development", "release-candidate", "production"),
                        default="development")
    parser.add_argument("--profile", choices=("lite", "enhanced"), default="lite")
    parser.add_argument("--claim-fieldbus", action="store_true")
    parser.add_argument("--policy", type=Path,
                        default=PLATFORM / "gates" / "system-gates.json")
    parser.add_argument("--status", type=Path,
                        default=PLATFORM / "release-status.json")
    args = parser.parse_args()
    policy = load(args.policy)
    status = load(args.status)
    errors = validate(policy, status)
    if errors:
        print(json.dumps({"verdict": "invalid", "errors": errors}, ensure_ascii=False, indent=2))
        return 2
    result = evaluate(policy, status, args.release_class, args.profile,
                      args.claim_fieldbus)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
