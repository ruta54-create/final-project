import { Navigate, Route, Routes } from "react-router-dom";
import { BinProvider, useAuth, useBin } from "./context.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { Empty, Loading } from "./components/ui.jsx";
import { useI18n } from "./i18n/index.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Detections from "./pages/Detections.jsx";
import Analytics from "./pages/Analytics.jsx";
import Alerts from "./pages/Alerts.jsx";
import Control from "./pages/Control.jsx";
import Settings from "./pages/Settings.jsx";
import AiLab from "./pages/AiLab.jsx";

function NeedsBin({ children }) {
  const { bins, bin } = useBin();
  const { t } = useI18n();
  if (bins === null) return <Loading />;
  if (!bin) return <Empty title={t("app.noBinTitle")}>{t("app.noBinBody")}</Empty>;
  return children;
}

export default function App() {
  const { user } = useAuth();

  if (user === undefined) return <Loading full />;
  if (!user)
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );

  return (
    <BinProvider>
      <div className="layout">
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/" element={<NeedsBin><Dashboard /></NeedsBin>} />
            <Route path="/detections" element={<NeedsBin><Detections /></NeedsBin>} />
            <Route path="/analytics" element={<NeedsBin><Analytics /></NeedsBin>} />
            <Route path="/alerts" element={<NeedsBin><Alerts /></NeedsBin>} />
            <Route path="/control" element={<NeedsBin><Control /></NeedsBin>} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/ai-lab" element={<NeedsBin><AiLab /></NeedsBin>} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BinProvider>
  );
}
