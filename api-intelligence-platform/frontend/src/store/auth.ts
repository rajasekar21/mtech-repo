import { create } from "zustand";
import { persist } from "zustand/middleware";
import { get as apiGet, post, setToken, removeToken } from "@/lib/api";
import type { User, AuthTokens, LoginRequest } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, getState: () => AuthState) => ({
      user: null,
      token: null,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const loginReq: LoginRequest = { email, password };
          const tokens = await post<AuthTokens>("/api/auth/login", loginReq);
          setToken(tokens.access_token);
          set({ token: tokens.access_token, isLoading: false });
          await apiGet<User>("/api/auth/me")
            .then((user) => {
              set({ user });
            })
            .catch(() => {
            // User fetch failed, but login was successful
            });
        } catch (err) {
          const message =
            err instanceof Error
              ? err.message
              : (err as { message?: string })?.message ?? "Login failed";
          set({ error: message, isLoading: false });
          throw err;
        }
      },

      logout: () => {
        removeToken();
        set({ user: null, token: null, error: null });
        if (typeof window !== "undefined") {
          window.location.href = "/auth/login";
        }
      },

      fetchMe: async () => {
        const state = getState();
        if (!state.token) return;
        set({ isLoading: true });
        try {
          const user = await import("@/lib/api").then((m) =>
            m.get<User>("/api/auth/me")
          );
          set({ user, isLoading: false });
        } catch {
          set({ isLoading: false });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
    }
  )
);
