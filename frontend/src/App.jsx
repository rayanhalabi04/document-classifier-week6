import { useEffect, useMemo, useState } from "react";
import { fetchCurrentUser, logout as logoutApi } from "./api/auth";
import { fetchAuditEvents } from "./api/audit";
import { listBatches } from "./api/batches";
import { fetchRecentPredictions } from "./api/predictions";
import Layout, { getPrimaryRole } from "./components/Layout";
import { demoAuditEvents, demoPredictions } from "./demoData";
import AdminPage from "./pages/AdminPage";
import AuditorPage from "./pages/AuditorPage";
import BatchesPage from "./pages/BatchesPage";
import LoginPage from "./pages/LoginPage";
import OverviewPage from "./pages/OverviewPage";
import PredictionsPage from "./pages/PredictionsPage";
import ReviewerPage from "./pages/ReviewerPage";
import { getToken, isNetworkError } from "./api/client";

export default function App() {
  const [user, setUser] = useState(null);
  const [activePage, setActivePage] = useState("overview");
  const [loadingUser, setLoadingUser] = useState(Boolean(getToken()));
  const [demoMode, setDemoMode] = useState(false);
  const [data, setData] = useState({
    batches: [],
    predictions: [],
    auditEvents: [],
  });

  useEffect(() => {
    if (!getToken()) return;
    fetchCurrentUser()
      .then((profile) => {
        setUser(profile);
        setActivePage(defaultPageForRole(getPrimaryRole(profile)));
      })
      .catch(() => {
        logoutApi();
        setUser(null);
      })
      .finally(() => setLoadingUser(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.allSettled([listBatches(), fetchRecentPredictions(), fetchAuditEvents({ limit: 20 })]).then(
      (results) => {
        if (cancelled) return;
        const [batchesResult, predictionsResult, auditResult] = results;
        const apiUnavailable = results.some(
          (result) => result.status === "rejected" && isNetworkError(result.reason),
        );
        setDemoMode(apiUnavailable);
        setData({
          batches: valueOrFallback(batchesResult, []),
          predictions: valueOrFallback(predictionsResult, demoPredictions),
          auditEvents: valueOrFallback(auditResult, demoAuditEvents),
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [user]);

  const role = getPrimaryRole(user);
  const canUsePage = useMemo(() => allowedPages(role), [role]);

  useEffect(() => {
    if (user && !canUsePage.includes(activePage)) {
      setActivePage(defaultPageForRole(role));
    }
  }, [activePage, canUsePage, role, user]);

  if (loadingUser) {
    return <div className="centered-page">Checking session...</div>;
  }

  if (!user) {
    return (
      <LoginPage
        onLogin={(profile) => {
          setUser(profile);
          setActivePage(defaultPageForRole(getPrimaryRole(profile)));
        }}
      />
    );
  }

  return (
    <Layout
      user={user}
      activePage={activePage}
      setActivePage={setActivePage}
      demoMode={demoMode}
      onLogout={() => {
        logoutApi();
        setUser(null);
        setData({ batches: [], predictions: [], auditEvents: [] });
        setDemoMode(false);
      }}
    >
      {renderPage(activePage, { user, role, data, demoMode, setDemoMode, refreshData: setData })}
    </Layout>
  );
}

function renderPage(page, props) {
  if (page === "admin") return <AdminPage {...props} />;
  if (page === "reviewer") return <ReviewerPage {...props} />;
  if (page === "auditor" || page === "audit") return <AuditorPage {...props} auditOnly={page === "audit"} />;
  if (page === "batches") return <BatchesPage {...props} />;
  if (page === "predictions") return <PredictionsPage {...props} />;
  return <OverviewPage {...props} />;
}

function valueOrFallback(result, demoValue) {
  if (result.status === "fulfilled") return result.value;
  return isNetworkError(result.reason) ? demoValue : [];
}

function defaultPageForRole(role) {
  return role === "admin" ? "admin" : role === "reviewer" ? "reviewer" : "overview";
}

function allowedPages(role) {
  if (role === "admin") return ["overview", "admin", "batches", "predictions", "audit"];
  if (role === "reviewer") return ["overview", "reviewer", "batches", "predictions"];
  if (role === "auditor") return ["overview", "batches", "predictions", "audit"];
  return ["overview", "predictions"];
}
