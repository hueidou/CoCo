import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Spin, Alert } from "antd";
import { useAppMessage } from "../../hooks/useAppMessage";
import { 
  KeyOutlined, 
  GoogleOutlined, 
  GithubOutlined,
} from "@ant-design/icons";
import { authApi, OIDCProvider } from "../../api/modules/auth";
import { useTheme } from "../../contexts/ThemeContext";

interface AuthStatusResponse {
  enabled: boolean;
  has_users: boolean;
  allow_registration: boolean;
}

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isDark } = useTheme();
  const [loadingOIDC, setLoadingOIDC] = useState(false);
  const [oidcProviders, setOidcProviders] = useState<OIDCProvider[]>([]);
  const { message } = useAppMessage();

  useEffect(() => {
    const loadAuthStatus = async () => {
      try {
        const status = await authApi.getStatus() as AuthStatusResponse;
        if (!status.enabled) {
          navigate("/chat", { replace: true });
          return;
        }

        // Load OIDC status
        try {
          const oidcStatusData = await authApi.oidc.getStatus();

          if (oidcStatusData.enabled && oidcStatusData.providers_configured > 0) {
            const providers = await authApi.oidc.getProviders();
            setOidcProviders(providers.providers);
          }
        } catch (oidcError) {
          console.debug("OIDC not configured:", oidcError);
        }

      } catch (error) {
        console.error("Failed to load auth status:", error);
      }
    };

    loadAuthStatus();
  }, [navigate]);

  const handleOIDCLogin = async (providerId: string) => {
    setLoadingOIDC(true);
    try {
      const redirect = searchParams.get("redirect") || "/chat";
      const res = await authApi.oidc.login({
        provider_id: providerId,
        redirect_url: `${window.location.origin}/auth/oidc/callback?redirect=${encodeURIComponent(redirect)}`,
      });

      // Store state for CSRF protection
      localStorage.setItem("oidc_state", res.state);

      // Redirect to OIDC provider for authentication
      window.location.href = res.authorization_url;
    } catch (err) {
      console.error("OIDC login failed:", err);
      message.error(
        err instanceof Error ? err.message : t("login.oidcFailed")
      );
    } finally {
      setLoadingOIDC(false);
    }
  };

  const renderProviderIcon = (provider: OIDCProvider) => {
    const providerName = provider.name.toLowerCase();
    if (providerName.includes("google")) return <GoogleOutlined />;
    if (providerName.includes("github")) return <GithubOutlined />;
    return <KeyOutlined />;
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: isDark
          ? "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)"
          : "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
      }}
    >
      <div
        style={{
          width: 400,
          padding: 32,
          borderRadius: 12,
          background: isDark ? "#1f1f1f" : "#fff",
          boxShadow: isDark
            ? "0 4px 24px rgba(0,0,0,0.4)"
            : "0 4px 24px rgba(0,0,0,0.1)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <img
            src={`${import.meta.env.BASE_URL}${
              isDark ? "dark-logo.png" : "logo.png"
            }`}
            alt="CoCo"
            style={{ height: 48, marginBottom: 12 }}
          />
          <h2 style={{ margin: 0, fontWeight: 600, fontSize: 20 }}>
            {t("login.title")}
          </h2>
          <p
            style={{
              margin: "8px 0 0",
              color: isDark ? "rgba(255,255,255,0.45)" : "#666",
              fontSize: 13,
            }}
          >
            {t("login.oidcHelpMultiUser")}
          </p>
        </div>

        {loadingOIDC ? (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <Spin size="large" />
            <p style={{ marginTop: 16, color: isDark ? "#aaa" : "#666" }}>
              {t("login.oidcLoading")}
            </p>
          </div>
        ) : (
          <div>
            {oidcProviders.length > 0 ? (
              <div style={{ marginBottom: 24 }}>
                {oidcProviders.map((provider) => (
                  <Button
                    key={provider.id}
                    icon={renderProviderIcon(provider)}
                    size="large"
                    onClick={() => handleOIDCLogin(provider.id)}
                    style={{
                      width: "100%",
                      marginBottom: 12,
                      height: 44,
                      borderRadius: 8,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {t("login.continueWith")} {provider.name}
                  </Button>
                ))}
              </div>
            ) : (
              <Alert
                message={t("login.oidcFailed")}
                type="error"
                showIcon
                style={{ marginBottom: 24 }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
