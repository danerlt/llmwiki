import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">加载中…</div>;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
