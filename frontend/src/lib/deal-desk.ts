import Papa from "papaparse";

type RawRow = Record<string, string>;

export interface VcLeadRow {
  id: string;
  priorityRank: number | null;
  fundName: string;
  website: string;
  geography: string;
  fundType: string;
  fitScore: number | null;
  routeQuality: string;
  contactName: string;
  contactRole: string;
  contactConfidence: string;
  email: string;
  emailStatus: string;
  contactMethod: string;
  contactUrl: string;
  evidenceUrl: string;
  evidenceSummary: string;
  outreachAngle: string;
  suggestedSubject: string;
  firstAction: string;
  validationStatus: string;
  validationFlags: string;
  raw: RawRow;
}

export interface VcLeadParseResult {
  rows: VcLeadRow[];
  errors: string[];
}

export interface OutreachDraftPreview {
  id: string;
  fundName: string;
  reviewStatus: string;
  subjectLines: string[];
  firstTouchEmail: string;
  followUp: string;
  personalizationRationale: string;
  evidenceUsed: string[];
  missingEvidence: string[];
  manualSendChecklist: string[];
}

const REQUIRED_VC_COLUMNS = ["fund_name", "fit_score"];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function cleanArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => clean(item)).filter(Boolean);
}

function parseNumber(value: string): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function leadId(row: RawRow, index: number): string {
  const rank = clean(row.priority_rank) || String(index + 1);
  const fund = clean(row.fund_name).toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `${rank}-${fund || "lead"}`;
}

export function parseVcLeadCsv(csv: unknown): VcLeadParseResult | null {
  if (typeof csv !== "string" || !csv.trim()) return null;

  const parsed = Papa.parse<RawRow>(csv, {
    header: true,
    skipEmptyLines: true,
  });

  const fields = parsed.meta.fields ?? [];
  const hasRequiredColumns = REQUIRED_VC_COLUMNS.every((column) => fields.includes(column));
  const rows = parsed.data
    .filter((row) => clean(row.fund_name))
    .map((row, index): VcLeadRow => ({
      id: leadId(row, index),
      priorityRank: parseNumber(clean(row.priority_rank)),
      fundName: clean(row.fund_name),
      website: clean(row.website),
      geography: clean(row.geography),
      fundType: clean(row.fund_type),
      fitScore: parseNumber(clean(row.fit_score)),
      routeQuality: clean(row.route_quality),
      contactName: clean(row.contact_name),
      contactRole: clean(row.contact_role),
      contactConfidence: clean(row.contact_confidence),
      email: clean(row.email),
      emailStatus: clean(row.email_status),
      contactMethod: clean(row.contact_method),
      contactUrl: clean(row.contact_url),
      evidenceUrl: clean(row.evidence_url),
      evidenceSummary: clean(row.evidence_summary),
      outreachAngle: clean(row.outreach_angle),
      suggestedSubject: clean(row.suggested_subject),
      firstAction: clean(row.first_action),
      validationStatus: clean(row.validation_status),
      validationFlags: clean(row.validation_flags),
      raw: row,
    }));

  if (!hasRequiredColumns || rows.length === 0) return null;

  return {
    rows,
    errors: parsed.errors.map((error) => error.message),
  };
}

export function normalizeOutreachDrafts(value: unknown): OutreachDraftPreview[] {
  if (!Array.isArray(value)) return [];

  return value.filter(isRecord).map((draft, index) => {
    const fundName = clean(draft.fund_name) || `Draft ${index + 1}`;
    const slug = fundName.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    return {
      id: `${index + 1}-${slug || "draft"}`,
      fundName,
      reviewStatus: clean(draft.review_status) || "needs_review",
      subjectLines: cleanArray(draft.subject_lines),
      firstTouchEmail: clean(draft.first_touch_email),
      followUp: clean(draft.follow_up),
      personalizationRationale: clean(draft.personalization_rationale),
      evidenceUsed: cleanArray(draft.evidence_used),
      missingEvidence: cleanArray(draft.missing_evidence),
      manualSendChecklist: cleanArray(draft.manual_send_checklist),
    };
  });
}

export function resultString(result: Record<string, unknown> | null | undefined, key: string): string {
  const value = result?.[key];
  return typeof value === "string" ? value : "";
}

export function resultNumber(result: Record<string, unknown> | null | undefined, key: string): number | null {
  const value = result?.[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") return parseNumber(value);
  return null;
}
