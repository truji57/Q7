const BASE = '/api';

function qs(params: Record<string, string | number | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const hasBody = options?.body;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) { const err = await res.text(); throw new Error(err || res.statusText); }
  return res.json();
}

export const api = {
  getDashboard: () => request<any>('/dashboard'),
  sendManualSignal: (action: string) => request<any>('/signal', { method: 'POST', body: JSON.stringify({ action }) }),

  // Groups
  getGroups: () => request<any[]>('/groups'),
  createGroup: (data: any) => request<any>('/groups', { method: 'POST', body: JSON.stringify(data) }),
  updateGroup: (id: number, data: any) => request<any>(`/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteGroup: (id: number) => request<any>(`/groups/${id}`, { method: 'DELETE' }),
  activateGroup: (id: number) => request<any>(`/groups/${id}/activate`, { method: 'POST' }),
  deactivateGroup: (id: number) => request<any>(`/groups/${id}/deactivate`, { method: 'POST' }),
  resetGroup: (id: number) => request<any>(`/groups/${id}/reset`, { method: 'POST' }),

  // Accounts
  createAccount: (groupId: number, data: any) => request<any>(`/groups/${groupId}/accounts`, { method: 'POST', body: JSON.stringify(data) }),
  updateAccount: (id: number, data: any) => request<any>(`/accounts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAccount: (id: number) => request<any>(`/accounts/${id}`, { method: 'DELETE' }),
  testAccount: (id: number) => request<any>(`/accounts/${id}/test`, { method: 'POST' }),

  getConfig: () => request<any>('/config'),
  updateConfig: (data: any) => request<any>('/config', { method: 'PUT', body: JSON.stringify(data) }),
  getSymbols: () => request<any>('/symbols'),
  saveSymbols: (data: any) => request<any>('/symbols', { method: 'PUT', body: JSON.stringify(data) }),
  getVersion: () => request<{version: string; date: string}>('/version'),
  getChangelog: () => request<{version: string; date: string; description: string}[]>('/changelog'),
  checkUpdate: () => request<{local: string; remote: string; has_update: boolean}>('/check-update'),
  getActivity: (limit: number = 100) => request<any[]>(`/activity?limit=${limit}`),
  installAddon: () => request<any>('/config/install-addon', { method: 'POST' }),

  // Stats
  getStatsAccounts: (from?: string, to?: string) => request<any[]>(`/stats/accounts${qs({ from, to })}`),
  getStatsAccount: (id: number, from?: string, to?: string) => request<any>(`/stats/accounts/${id}${qs({ from, to })}`),
  getStatsEquity: (id: number, bucket: number = 300, from?: string, to?: string) =>
    request<any>(`/stats/accounts/${id}/equity${qs({ bucket, from, to })}`),
  getStatsGroup: (id: number, from?: string, to?: string) => request<any>(`/stats/groups/${id}${qs({ from, to })}`),
  getStatsPresets: (from?: string, to?: string) => request<any[]>(`/stats/presets${qs({ from, to })}`),

  // History
  getHistoryTrades: () => request<any[]>('/history/trades'),

  // Fleets
  getFleets: () => request<any[]>('/fleets'),
  createFleet: (data: any) => request<any>('/fleets', { method: 'POST', body: JSON.stringify(data) }),
  updateFleet: (id: number, data: any) => request<any>(`/fleets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteFleet: (id: number) => request<any>(`/fleets/${id}`, { method: 'DELETE' }),
  addGroupToFleet: (fleetId: number, groupId: number) => request<any>(`/fleets/${fleetId}/groups/${groupId}`, { method: 'POST' }),
  removeGroupFromFleet: (fleetId: number, groupId: number) => request<any>(`/fleets/${fleetId}/groups/${groupId}`, { method: 'DELETE' }),
  reorderFleet: (fleetId: number, groupIds: number[]) => request<any>(`/fleets/${fleetId}/order`, { method: 'PUT', body: JSON.stringify({ group_ids: groupIds }) }),
  activateFleet: (id: number) => request<any>(`/fleets/${id}/activate`, { method: 'POST' }),
  deactivateFleet: (id: number) => request<any>(`/fleets/${id}/deactivate`, { method: 'POST' }),
};
