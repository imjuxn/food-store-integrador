import axios from "axios";
import { useAuthStore } from "../../store/authStore";
import { api } from "./axiosInstance";

const interceptor = api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError<{ detail?: unknown }>(error)) {
      const url = error.config?.url ?? "";
      const disabled = error.response?.status === 400 && error.response.data?.detail === "Cuenta de usuario desactivada";
      const expired = error.response?.status === 401 && !url.includes("/auth/token") && !url.includes("/auth/me");
      if (disabled || expired) useAuthStore.getState().clearSession();
    }
    return Promise.reject(error);
  },
);

if (import.meta.hot) import.meta.hot.dispose(() => api.interceptors.response.eject(interceptor));
