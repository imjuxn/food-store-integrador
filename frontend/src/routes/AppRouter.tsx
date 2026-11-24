import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout, SiteLayout } from "../shared/components/Layout";
import { Loading } from "../shared/components/Feedback";
import { ProtectedRoute } from "./ProtectedRoute";

const LoginPage = lazy(async () => ({ default: (await import("../features/auth/pages/AuthPages")).LoginPage }));
const RegisterPage = lazy(async () => ({ default: (await import("../features/auth/pages/AuthPages")).RegisterPage }));
const CatalogPage = lazy(async () => ({ default: (await import("../features/productos/pages/CatalogPage")).CatalogPage }));
const CartPage = lazy(async () => ({ default: (await import("../features/pedidos/pages/CheckoutPages")).CartPage }));
const CheckoutPage = lazy(async () => ({ default: (await import("../features/pedidos/pages/CheckoutPages")).CheckoutPage }));
const MyOrdersPage = lazy(async () => ({ default: (await import("../features/pedidos/pages/MyOrdersPage")).MyOrdersPage }));
const AdminDashboardPage = lazy(async () => ({ default: (await import("../features/pedidos/pages/AdminDashboardPage")).AdminDashboardPage }));
const AdminOrdersPage = lazy(async () => ({ default: (await import("../features/pedidos/pages/AdminOrdersPage")).AdminOrdersPage }));
const AdminCategoriesPage = lazy(async () => ({ default: (await import("../features/categorias/pages/AdminCategoriesPage")).AdminCategoriesPage }));
const AdminProductsPage = lazy(async () => ({ default: (await import("../features/productos/pages/AdminProductsPage")).AdminProductsPage }));
const AdminUsersPage = lazy(async () => ({ default: (await import("../features/usuarios/pages/AdminUsersPage")).AdminUsersPage }));

export function AppRouter() {
  return <Suspense fallback={<Loading label="Cargando sección..." />}><Routes>
    <Route element={<SiteLayout />}>
      <Route path="/" element={<CatalogPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/carrito" element={<CartPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/checkout" element={<CheckoutPage />} />
        <Route path="/mis-pedidos" element={<MyOrdersPage />} />
      </Route>
      <Route path="/unauthorized" element={<div className="surface mx-auto max-w-lg text-center"><h1 className="text-3xl font-black">Acceso no autorizado</h1><p className="mt-3 text-stone-600">Tu cuenta no tiene permisos para esta sección.</p><Link to="/" className="btn-primary mt-5">Volver al menú</Link></div>} />
    </Route>
    <Route element={<ProtectedRoute admin />}>
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="resumen" replace />} />
        <Route path="resumen" element={<AdminDashboardPage />} />
        <Route path="categorias" element={<AdminCategoriesPage />} />
        <Route path="productos" element={<AdminProductsPage />} />
        <Route path="pedidos" element={<AdminOrdersPage />} />
        <Route path="usuarios" element={<AdminUsersPage />} />
      </Route>
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Suspense>;
}
