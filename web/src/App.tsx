import { Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";
import AdminPage from "./pages/AdminPage";
import AuditPage from "./pages/AuditPage";
import KbListPage from "./pages/KbListPage";
import KbPagesPage from "./pages/KbPagesPage";
import LoginPage from "./pages/LoginPage";
import NotificationsPage from "./pages/NotificationsPage";
import PageDetailPage from "./pages/PageDetailPage";
import PageEditPage from "./pages/PageEditPage";
import PageHistoryPage from "./pages/PageHistoryPage";
import QueryPage from "./pages/QueryPage";
import ReviewsPage from "./pages/ReviewsPage";
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
            <Route path="/kbs/:kbId/pages/new" element={<PageEditPage />} />
            <Route path="/pages/:pageId" element={<PageDetailPage />} />
            <Route path="/pages/:pageId/edit" element={<PageEditPage />} />
            <Route path="/pages/:pageId/history" element={<PageHistoryPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/query" element={<QueryPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/audit" element={<AuditPage />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
