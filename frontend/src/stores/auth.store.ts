"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { setAccessToken as setApiToken, apiClient } from "@/lib/api";

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setAccessToken: (token: string) => void;
  logout: () => Promise<void>;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isLoading: false,

      setUser: (user) => set({ user }),

      setAccessToken: (token) => {
        setApiToken(token);
        set({ token });
      },

      logout: async () => {
        await apiClient.auth.logout().catch(() => null);
        setApiToken(null);
        set({ user: null, token: null });
      },

      fetchMe: async () => {
        set({ isLoading: true });
        try {
          const { data } = await apiClient.auth.me();
          set({ user: data });
        } catch {
          set({ user: null });
        } finally {
          set({ isLoading: false });
        }
      },
    }),
    {
      name: "funda-auth",
      partialize: (state) => ({ user: state.user, token: state.token }),
      onRehydrateStorage: () => (state) => {
        // Restore the in-memory axios token from persisted state
        if (state?.token) {
          setApiToken(state.token);
        }
      },
    }
  )
);
