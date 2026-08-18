export interface Account {
  id: number;
  group_id: number;
  order_index: number;
  name: string;
  nt8_account: string;
  enabled: boolean;
  color: string;
  ct: number;
  max_positions: number;
  pdll: number;
  pdpt: number;
  tpg: number;
  slg: number;
  tpc: number;
  slc: number;
  status: string;
  balance: number;
  starting_balance: number;
  daily_pnl: number;
  total_pnl: number;
  round_pnl: number;
  round_num: number;
  open_pnl: number;
  symbol: string;
  position: string;
  trades_today: number;
}

export interface Group {
  id: number;
  name: string;
  active: boolean;
  direction: string;
  mode: string;
  stop_on_reset: boolean;
  reset_mode: string;
  include_in_fleet: boolean;
  schedule_enabled: boolean;
  schedule_start_h: number;
  schedule_start_m: number;
  schedule_end_h: number;
  schedule_end_m: number;
  default_ct: number;
  default_max_positions: number;
  default_tpc: number;
  default_slc: number;
  default_pdll: number;
  default_pdpt: number;
  default_tpg: number;
  default_slg: number;
  accounts: Account[];
}

export interface ActivityLogEntry {
  id: number;
  timestamp: string;
  category: string;
  message: string;
  account: string;
  group_id: number | null;
}

export interface DashboardState {
  groups: Group[];
  version: string;
  timestamp: string;
  nt8_connected: boolean;
  engine_active: boolean;
  mt5_connected: boolean;
  last_signal_time: string;
  signal_log: string[];
  activity_log: ActivityLogEntry[];
  nt8_accounts: NT8Account[];
}

export interface NT8Account {
  name: string;
  balance: number;
}

// ========== STATS ==========

export interface StatsSummary {
  n: number;
  wins: number;
  losses: number;
  winrate: number;
  net_pnl: number;
  gross_win: number;
  gross_loss: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  expectancy: number;
  max_dd: number;
  max_dd_pct: number;
  max_dd_date: string;
}

export interface AccountStatsRow extends StatsSummary {
  account_id: number;
  name: string;
  nt8_account: string;
  group_id: number;
  group_name: string;
  color: string;
  balance: number;
  total_pnl: number;
  status: string;
  enabled: boolean;
}

export interface EquityPoint {
  ts: string;
  balance: number;
  equity: number;
  drawdown: number;
}

export interface TradeCloseRecord {
  id: number;
  ts_open: string;
  ts_close: string;
  direction: string;
  instrument: string;
  pnl: number;
  reason: string;
  preset_key: string;
}

export interface BreakdownGroup {
  key: string;
  n: number;
  wins: number;
  winrate: number;
  net_pnl: number;
}

export interface AccountStatsDetail extends StatsSummary {
  account_id: number;
  name: string;
  nt8_account: string;
  group_id: number;
  color: string;
  status: string;
  balance: number;
  total_pnl: number;
  equity: EquityPoint[];
  breakdowns: {
    direction: BreakdownGroup[];
    instrument: BreakdownGroup[];
    reason: BreakdownGroup[];
    weekday: BreakdownGroup[];
    month: BreakdownGroup[];
  };
  trades: TradeCloseRecord[];
}

export interface PresetStats {
  preset_key: string;
  n: number;
  wins: number;
  winrate: number;
  net_pnl: number;
  avg: number;
  profit_factor: number;
  ct: number | null;
  max_positions: number | null;
  tpc: number | null;
  slc: number | null;
  pdpt: number | null;
  pdll: number | null;
  tpg: number | null;
  slg: number | null;
}

export interface GroupStats {
  group_id: number;
  group_name: string;
  accounts: AccountStatsRow[];
  team_net_pnl: number;
  team_trades: number;
  team_max_dd: number;
  avg_winrate: number;
}
