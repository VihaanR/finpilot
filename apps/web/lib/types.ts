/** Wire shapes returned by services/api. Mirrors app/services/views.py. */

export interface Citation {
  label: string;
  value_paise: number;
  txn_ids: string[];
}

export interface Badge {
  code: "SILENT" | "HIGH_LIMIT" | "PRICE_UP" | "DUPLICATE" | "TRIAL_TO_PAID" | "DORMANT";
  label: string;
  tone: "alert" | "warn" | "info" | "muted";
  tooltip: string;
}

export interface Account {
  id: string;
  bank_code: string;
  account_type: string;
  display_name: string;
  last4: string;
  current_balance_paise: number;
  balance_as_of: string;
}

export interface Obligation {
  series_key: string;
  normalized_merchant: string;
  category_slug: string;
  due_date: string;
  amount_paise: number;
  afa_band: string;
  mandate_channel: string;
  acknowledged: boolean;
}

export interface SafeToSpend {
  as_of: string;
  next_income_date: string | null;
  next_income_paise: number;
  current_balance_paise: number;
  committed_paise: number;
  goal_due_paise: number;
  discretionary_paise: number;
  days_remaining: number;
  safe_daily_paise: number;
  obligations: Obligation[];
  citations: Citation[];
}

export interface MonthSummary {
  month: string;
  income_paise: number;
  expense_paise: number;
  net_paise: number;
  savings_rate_pct?: number;
  txn_count?: number;
}

export interface CategorySlice {
  category_slug: string;
  category_name: string;
  group: string;
  amount_paise: number;
  txn_ids: string[];
}

export interface Anomaly {
  key: string;
  type: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
  period_start: string;
  period_end: string;
  txn_ids: string[];
  explanation: string;
  series_key: string | null;
  metric: Record<string, unknown>;
}

export interface LeakScore {
  score: number;
  band: string;
  label: string;
  contributions: { reason: string; count: number; deduction: number }[];
}

export interface BudgetStatus {
  category_slug: string;
  category_name: string;
  limit_paise: number;
  spent_paise: number;
  remaining_paise: number;
  pct_used: number;
  days_elapsed: number;
  days_in_period: number;
  projected_spend_paise: number;
  pace: string;
  txn_ids: string[];
}

export interface Dashboard {
  as_of: string;
  accounts: Account[];
  balance_paise: number;
  card_outstanding_paise?: number;
  safe_to_spend: SafeToSpend;
  month: MonthSummary;
  trend: MonthSummary[];
  categories: CategorySlice[];
  anomalies: Anomaly[];
  leak_score: LeakScore;
  budgets: BudgetStatus[];
  transaction_count: number;
}

export interface Transaction {
  id: string;
  account_id: string;
  txn_date: string;
  amount_paise: number;
  direction: "DEBIT" | "CREDIT";
  raw_narration: string;
  normalized_merchant: string;
  channel: string;
  category_slug: string;
  category_source: string;
  category_confidence: number;
  service_type: string | null;
  balance_paise: number | null;
}

export interface RadarItem {
  series_key: string;
  merchant: string;
  category_slug: string;
  category_name: string;
  due_date: string;
  days_away: number;
  amount_paise: number;
  cadence: string;
  mandate_channel: string;
  afa_band: string;
  acknowledged: boolean;
  within_banner: boolean;
  badges: Badge[];
}

export interface RevokeKit {
  channel: string;
  steps: string[];
  email_template: string;
}

export interface Series {
  key: string;
  normalized_merchant: string;
  category_slug: string;
  category_name: string;
  direction: string;
  cadence: string;
  median_amount_paise: number;
  median_gap_days: number;
  occurrence_count: number;
  first_seen: string;
  last_seen: string;
  next_expected_date: string | null;
  confidence: number;
  mandate_channel: string;
  afa_band: string;
  status: string;
  txn_ids: string[];
  acknowledged: boolean;
  service_type: string | null;
  badges: Badge[];
  revoke_kit: RevokeKit;
}

export interface Radar {
  as_of: string;
  horizon_days: number;
  banner_days: number;
  weeks: { week: number; starts_on: string; items: RadarItem[]; total_paise: number }[];
  banner: { count: number; total_paise: number; items: RadarItem[] };
  series: Series[];
  leak_score: LeakScore;
}

export interface GoalProjection {
  goal_id: string;
  name: string;
  target_paise: number;
  current_paise: number;
  shortfall_paise: number;
  target_date: string;
  months_remaining: number;
  required_monthly_paise: number;
  allocated_monthly_paise: number;
  projected_eta: string | null;
  months_delta: number;
  verdict: "AHEAD" | "ON_TRACK" | "BEHIND" | "UNREACHABLE";
}

export interface CancellableSeries {
  series_key: string;
  merchant: string;
  category_slug: string;
  category_name: string;
  monthly_paise: number;
  cadence: string;
  service_type: string | null;
}

export interface GoalsView {
  as_of: string;
  monthly_surplus_paise: number;
  goals: GoalProjection[];
  cancellable_series: CancellableSeries[];
  categories: string[];
}

export interface SimulationResult {
  goals: {
    goal_id: string;
    name: string;
    eta_before: string | null;
    eta_after: string | null;
    months_delta: number;
  }[];
  monthly_surplus_before_paise: number;
  monthly_surplus_after_paise: number;
  monthly_surplus_delta_paise: number;
  safe_daily_before_paise: number;
  safe_daily_after_paise: number;
  safe_daily_delta_paise: number;
  cancelled_monthly_paise: number;
  narration_facts: {
    cancelled_count: number;
    one_off_total_paise: number;
    category_delta_paise: number;
  };
}

export interface Category {
  slug: string;
  name: string;
  icon: string | null;
  is_income: boolean;
  parent_slug: string | null;
  sort_order: number;
}

export interface Vault {
  consent_artefact: {
    version: string;
    purpose: string;
    data_types: string[];
    processing: string[];
    third_parties: { name: string; role: string; region: string }[];
    retention: string;
    frequency: string;
    revocation: string;
  };
  consents: { version: string; scope: string; granted: boolean; changed_at: string }[];
  scopes: Record<string, boolean>;
  disclosures: {
    id: string;
    created_at: string;
    purpose: string;
    model: string;
    fields: string[];
    txn_count: number;
  }[];
  storage_inventory: { table: string; rows: number; oldest?: string | null }[];
  retention_days: number;
  redaction_example: {
    before: string;
    after: string;
    field_types: Record<string, number>;
    note: string;
  };
  ai_configured: boolean;
}
