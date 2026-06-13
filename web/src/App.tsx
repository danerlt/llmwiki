import { Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import KbListPage from "./pages/KbListPage";
import KbPagesPage from "./pages/KbPagesPage";
import LoginPage from "./pages/LoginPage";
import PageDetailPage from "./pages/PageDetailPage";
import QueryPage from "./pages/QueryPage";
import SearchPage from "./pages/SearchPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<KbListPage />} />
            <Route path="/kbs/:kbId/pages" element={<KbPagesPage />} />
            <Route path="/pages/:pageId" element={<PageDetailPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/query" element={<QueryPage />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
