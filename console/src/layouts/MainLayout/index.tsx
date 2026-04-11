import { Suspense } from "react";
import { Layout, Spin, Result } from "antd";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Sidebar from "../Sidebar";
import Header from "../Header";
import ConsoleCronBubble from "../../components/ConsoleCronBubble";
import { ChunkErrorBoundary } from "../../components/ChunkErrorBoundary";
import { lazyWithRetry } from "../../utils/lazyWithRetry";
import styles from "../index.module.less";

// Chat is eagerly loaded (default landing page)
import Chat from "../../pages/Chat";

// All other pages are lazily loaded with automatic retry on chunk failure
const ChannelsPage = lazyWithRetry(
  () => import("../../pages/Control/Channels"),
);
const SessionsPage = lazyWithRetry(
  () => import("../../pages/Control/Sessions"),
);
const CronJobsPage = lazyWithRetry(
  () => import("../../pages/Control/CronJobs"),
);
const HeartbeatPage = lazyWithRetry(
  () => import("../../pages/Control/Heartbeat"),
);
const AgentConfigPage = lazyWithRetry(() => import("../../pages/Agent/Config"));
const SkillsPage = lazyWithRetry(() => import("../../pages/Agent/Skills"));
const SkillPoolPage = lazyWithRetry(
  () => import("../../pages/Settings/SkillPool"),
);
const ToolsPage = lazyWithRetry(() => import("../../pages/Agent/Tools"));
const WorkspacePage = lazyWithRetry(
  () => import("../../pages/Agent/Workspace"),
);
const MCPPage = lazyWithRetry(() => import("../../pages/Agent/MCP"));
const ModelsPage = lazyWithRetry(() => import("../../pages/Settings/Models"));
const EnvironmentsPage = lazyWithRetry(
  () => import("../../pages/Settings/Environments"),
);
const SecurityPage = lazyWithRetry(
  () => import("../../pages/Settings/Security"),
);
const TokenUsagePage = lazyWithRetry(
  () => import("../../pages/Settings/TokenUsage"),
);
const VoiceTranscriptionPage = lazyWithRetry(
  () => import("../../pages/Settings/VoiceTranscription"),
);
const AgentsPage = lazyWithRetry(() => import("../../pages/Settings/Agents"));

const { Content } = Layout;

// Admin-only route guard
function parseRoleFromToken(): string {
  try {
    const token = localStorage.getItem("coco_auth_token");
    if (!token) return "user";
    const payload = JSON.parse(atob(token.split(".")[0]));
    return payload.role || "user";
  } catch {
    return "user";
  }
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const role = parseRoleFromToken();
  if (role !== "admin") {
    return <Result status="403" title="403" subTitle="Access denied. Admin role required." />;
  }
  return <>{children}</>;
}

const pathToKey: Record<string, string> = {
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/heartbeat": "heartbeat",
  "/skills": "skills",
  "/skill-pool": "skill-pool",
  "/tools": "tools",
  "/mcp": "mcp",
  "/workspace": "workspace",
  "/agents": "agents",
  "/models": "models",
  "/environments": "environments",
  "/agent-config": "agent-config",
  "/security": "security",
  "/token-usage": "token-usage",
  "/voice-transcription": "voice-transcription",
};

export default function MainLayout() {
  const { t } = useTranslation();
  const location = useLocation();
  const currentPath = location.pathname;
  const selectedKey = pathToKey[currentPath] || "chat";

  return (
    <Layout className={styles.mainLayout}>
      <Header />
      <Layout>
        <Sidebar selectedKey={selectedKey} />
        <Content className="page-container">
          <ConsoleCronBubble />
          <div className="page-content">
            <ChunkErrorBoundary resetKey={currentPath}>
              <Suspense
                fallback={
                  <Spin
                    tip={t("common.loading")}
                    style={{ display: "block", margin: "20vh auto" }}
                  />
                }
              >
                <Routes>
                  <Route path="/" element={<Navigate to="/chat" replace />} />
                  <Route path="/chat/*" element={<Chat />} />
                  <Route path="/channels" element={<ChannelsPage />} />
                  <Route path="/sessions" element={<SessionsPage />} />
                  <Route path="/cron-jobs" element={<CronJobsPage />} />
                  <Route path="/heartbeat" element={<AdminRoute><HeartbeatPage /></AdminRoute>} />
                  <Route path="/skills" element={<AdminRoute><SkillsPage /></AdminRoute>} />
                  <Route path="/skill-pool" element={<AdminRoute><SkillPoolPage /></AdminRoute>} />
                  <Route path="/tools" element={<AdminRoute><ToolsPage /></AdminRoute>} />
                  <Route path="/mcp" element={<AdminRoute><MCPPage /></AdminRoute>} />
                  <Route path="/workspace" element={<AdminRoute><WorkspacePage /></AdminRoute>} />
                  <Route path="/agents" element={<AdminRoute><AgentsPage /></AdminRoute>} />
                  <Route path="/models" element={<AdminRoute><ModelsPage /></AdminRoute>} />
                  <Route path="/environments" element={<AdminRoute><EnvironmentsPage /></AdminRoute>} />
                  <Route path="/agent-config" element={<AdminRoute><AgentConfigPage /></AdminRoute>} />
                  <Route path="/security" element={<AdminRoute><SecurityPage /></AdminRoute>} />
                  <Route path="/token-usage" element={<AdminRoute><TokenUsagePage /></AdminRoute>} />
                  <Route
                    path="/voice-transcription"
                    element={<AdminRoute><VoiceTranscriptionPage /></AdminRoute>}
                  />
                </Routes>
              </Suspense>
            </ChunkErrorBoundary>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
