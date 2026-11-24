import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authApi } from "../features/auth/api/auth";
import type { Usuario } from "../features/auth/types/usuario";
import { queryClient } from "../shared/api/queryClient";

interface AuthState {
  usuario: Usuario | null;
  cargando: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
  clearSession: () => void;
}

let pendingCheck: Promise<void> | null = null;
let revision = 0;

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      usuario: null,
      cargando: true,
      login: async (username, password) => {
        const currentRevision = ++revision;
        queryClient.clear();
        set({ usuario: null, cargando: false });
        await authApi.login(username, password);
        const usuario = await authApi.me();
        if (currentRevision !== revision) return;
        queryClient.clear();
        set({ usuario, cargando: false });
      },
      logout: async () => {
        ++revision;
        await authApi.logout();
        queryClient.clear();
        set({ usuario: null, cargando: false });
      },
      checkSession: () => {
        if (pendingCheck) return pendingCheck;
        const currentRevision = revision;
        set({ cargando: true });
        pendingCheck = (async () => {
          try {
            const usuario = await authApi.me();
            if (currentRevision === revision) set({ usuario, cargando: false });
          } catch {
            if (currentRevision === revision) {
              queryClient.clear();
              set({ usuario: null, cargando: false });
            }
          } finally {
            pendingCheck = null;
          }
        })();
        return pendingCheck;
      },
      clearSession: () => {
        ++revision;
        queryClient.clear();
        set({ usuario: null, cargando: false });
      },
    }),
    { name: "foodstore-integrador-auth", partialize: (state) => ({ usuario: state.usuario }) },
  ),
);

