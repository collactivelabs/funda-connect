"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { setAccessToken, apiClient } from "@/lib/api";

interface AuthState {
  user: User | null;
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
      isLoading: false,

      setUser: (user) => set({ user }),

      setAccessToken: (token) => {
        setAccessToken(token);
      },

      logout: async () => {
        await apiClient.auth.logout().catch(() => null);
        setAccessToken(null);
        set({ user: null });
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
      partialize: (state) => ({ user: state.user }),
    }
  )
);
