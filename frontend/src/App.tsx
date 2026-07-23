/**
 * 앱 라우팅 루트 컴포넌트.
 */
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./components/RequireAuth";
import { AdminStoragePage } from "./pages/AdminStoragePage";
import { ExportPage } from "./pages/ExportPage";
import { ImagesPage } from "./pages/ImagesPage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { SummaryPage } from "./pages/SummaryPage";
import { TranslatePage } from "./pages/TranslatePage";
import { UploadPage } from "./pages/UploadPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <UploadPage />
            </RequireAuth>
          }
        />
        <Route
          path="/documents/:id/summary"
          element={
            <RequireAuth>
              <SummaryPage />
            </RequireAuth>
          }
        />
        <Route
          path="/documents/:id/translate"
          element={
            <RequireAuth>
              <TranslatePage />
            </RequireAuth>
          }
        />
        <Route
          path="/documents/:id/images"
          element={
            <RequireAuth>
              <ImagesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/documents/:id/export"
          element={
            <RequireAuth>
              <ExportPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/storage"
          element={
            <RequireAuth>
              <AdminStoragePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
