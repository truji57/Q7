import { create } from 'zustand';
import type { DashboardState } from '../types';

interface Store {
  state: DashboardState | null;
  wsConnected: boolean;
  debugMode: boolean;
  setState: (s: DashboardState) => void;
  setWsConnected: (c: boolean) => void;
  setDebugMode: (d: boolean) => void;
}

export const useStore = create<Store>((set) => ({
  state: null,
  wsConnected: false,
  debugMode: false,
  setState: (s) => set({ state: s }),
  setWsConnected: (c) => set({ wsConnected: c }),
  setDebugMode: (d) => set({ debugMode: d }),
}));
