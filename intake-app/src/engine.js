/**
 * Deterministic triage engine -- JS port of engine/triage_engine.py.
 *
 * Must stay logically identical to the Python engine (same rules.json source,
 * same decision logic). If these two ever diverge, that's a bug: the rule
 * engine must give the same answer regardless of which client runs it.
 */

let rulesCache = null;

export async function loadRules() {
  if (rulesCache) return rulesCache;
  const res = await fetch("./src/rules.json");
  rulesCache = await res.json();
  return rulesCache;
}

function uuid() {
  return crypto.randomUUID ? crypto.randomUUID() : "case-" + Date.now() + "-" + Math.random().toString(16).slice(2);
}

/**
 * @param {object} rules - loaded rules.json
 * @param {{patientToken: string, complaintId: string, redFlagIds: string[]}} intake
 * @returns triage result object, same shape as the Python engine's audit record
 */
export function score(rules, intake) {
  const { patientToken, complaintId, redFlagIds = [] } = intake;
  const flagById = Object.fromEntries(rules.red_flags.map((f) => [f.id, f]));
  const hitFlags = redFlagIds.filter((id) => id in flagById);
  const timestamp = new Date().toISOString();

  if (!(complaintId in rules.complaints)) {
    return {
      case_id: uuid(),
      patient_token: patientToken,
      tier: "unrecognized",
      tier_label: "Unrecognized -- human review required",
      department: "Front-desk triage (manual)",
      matched_rules: ["no complaint category matched -> mandatory human review"],
      escalate: true,
      escalate_reason: "unrecognized_complaint",
      protocol_version: rules.version,
      timestamp,
      status: "pending_review",
    };
  }

  const complaint = rules.complaints[complaintId];
  let tier = complaint.base_tier;
  let department = complaint.department;
  const matched = [`complaint_rule:${complaintId} -> base_tier=${tier}, dept=${department}`];

  let escalate = false;
  let escalateReason = null;

  if (hitFlags.length > 0) {
    tier = "emergency";
    department = "Emergency (staff review required)";
    for (const fid of hitFlags) {
      matched.push(`red_flag:${fid} (${flagById[fid].label}) -> tier=emergency`);
    }
    escalate = true;
    escalateReason = "red_flag";
  } else if (rules.escalation.emergency_requires_human_review && tier === "emergency") {
    escalate = true;
    escalateReason = "emergency_tier";
  }

  return {
    case_id: uuid(),
    patient_token: patientToken,
    tier,
    tier_label: rules.tiers[tier].label,
    department,
    matched_rules: matched,
    escalate,
    escalate_reason: escalateReason,
    protocol_version: rules.version,
    timestamp,
    status: escalate ? "pending_review" : "routed",
  };
}
