/**
 * Reading an import plan.
 *
 * The arbiter is standing in a hall between rounds with people waiting. The
 * diff has to answer one question in one glance -- is it safe to press import
 * -- and separate what is merely worth knowing from what must be acknowledged.
 */

import type { ImportPlan } from "./api";

export type Severity = "blocking" | "acknowledge" | "informational";

export interface PlanNote {
  severity: Severity;
  text: string;
}

export function planNotes(plan: ImportPlan): PlanNote[] {
  const notes: PlanNote[] = [];

  for (const reason of plan.blocked_by ?? []) {
    notes.push({ severity: "blocking", text: reason });
  }

  // The manager is authoritative for earlier rounds, so a disagreement is expected --
  // an arbiter correcting round 2 there is normal. It is never applied
  // silently, though: it is the one thing that must be read before importing.
  for (const disagreement of plan.disagreements ?? []) {
    notes.push({
      severity: "acknowledge",
      text:
        `Round ${disagreement.round_number}, ${disagreement.white_name} vs ` +
        `${disagreement.black_name ?? "bye"}: the manager says "${disagreement.theirs}", ` +
        `we hold "${disagreement.ours}". The manager wins.`,
    });
  }

  for (const dropped of plan.claims_dropped ?? []) {
    notes.push({
      severity: "acknowledge",
      text:
        `${dropped.white_name} vs ${dropped.black_name ?? "bye"} was entered as ` +
        `"${dropped.white_result}" but that pairing is gone. The entry is dropped ` +
        `and stays in the audit log.`,
    });
  }

  for (const code of plan.unknown_result_codes ?? []) {
    notes.push({
      severity: "acknowledge",
      text: `The file uses a result code we do not recognise: "${code}".`,
    });
  }

  if (!plan.is_expected_round) {
    notes.push({
      severity: "acknowledge",
      text: `This file holds round ${plan.file_round}, but round ${plan.expected_round} was expected.`,
    });
  }

  for (const player of plan.players_added ?? []) {
    notes.push({
      severity: "informational",
      text: `New: ${player.name} (rank ${player.start_rank}).`,
    });
  }
  for (const player of plan.players_removed ?? []) {
    notes.push({
      severity: "informational",
      text: `Gone: ${player.name} (rank ${player.start_rank}).`,
    });
  }
  for (const rename of plan.players_renamed ?? []) {
    notes.push({ severity: "informational", text: `Renamed ${rename}.` });
  }
  for (const carried of plan.claims_carried ?? []) {
    notes.push({
      severity: "informational",
      text: `Kept: ${carried.white_name} vs ${carried.black_name ?? "bye"} ("${carried.white_result}").`,
    });
  }

  return notes;
}

export function canImport(plan: ImportPlan): boolean {
  return (plan.blocked_by ?? []).length === 0;
}

export function needsAcknowledgement(plan: ImportPlan): boolean {
  return planNotes(plan).some((note) => note.severity === "acknowledge");
}

export function headline(plan: ImportPlan): string {
  const boards = plan.boards ?? 0;
  const byes = plan.byes ?? 0;
  const byeText = byes > 0 ? ` and ${byes} bye${byes === 1 ? "" : "s"}` : "";
  return (
    `Round ${plan.file_round}: ${boards} board${boards === 1 ? "" : "s"}${byeText}, ` +
    `${plan.players_total} players`
  );
}
