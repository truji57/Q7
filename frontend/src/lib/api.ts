const BASE = '/api';

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
  getVersion: () => request<{version: string; date: string}>('/version'),
  getChangelog: () => request<{version: string; date: string; description: string}[]>('/changelog'),
  checkUpdate: () => request<{local: string; remote: string; has_update: boolean}>('/check-update'),
  installAddon: () => request<any>('/config/install-addon', { method: 'POST' }),
};
