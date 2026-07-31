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
  tpc: number;
  slc: number;
  status: string;
  balance: number;
  daily_pnl: number;
  round_pnl: number;
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
  accounts: Account[];
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
  nt8_accounts: NT8Account[];
}

export interface NT8Account {
  name: string;
  balance: number;
}
