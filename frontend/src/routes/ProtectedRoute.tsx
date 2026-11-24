import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Loading } from "../shared/components/Feedback";
import { useAuthStore } from "../store/authStore";

export function ProtectedRoute({ admin = false }: { admin?: boolean }) {
  const usuario = useAuthStore((state) => state.usuario);
  const cargando = useAuthStore((state) => state.cargando);
  const location = useLocation();
  if (cargando) return <Loading label="Comprobando sesión..." />;
  if (!usuario) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (admin && usuario.role !== "admin") return <Navigate to="/unauthorized" replace />;
  return <Outlet />;
}
