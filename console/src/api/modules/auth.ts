import { getApiUrl } from "../config";

export interface LoginResponse {
  token: string;
  username: string;
  user_id?: number;
  role: string;
  message?: string;
}

export interface AuthStatusResponse {
  enabled: boolean;
  has_users: boolean;
  allow_registration: boolean;
}

export interface VerifyResponse {
  valid: boolean;
  username: string;
  role: string;
  user_id?: number;
}

export interface OIDCProvider {
  id: string;
  name: string;
  enabled: boolean;
  issuer_url?: string;
  authorization_endpoint?: string;
  discovery_url?: string;
}

export interface OIDCProvidersResponse {
  providers: OIDCProvider[];
}

export interface OIDCLoginRequest {
  provider_id: string;
  redirect_url?: string;
}

export interface OIDCLoginResponse {
  authorization_url: string;
  state: string;
}

export interface OIDCCallbackResponse {
  token: string;
  username: string;
  user_id?: number;
  role: string;
  provider: string;
}

export interface OIDCStatusResponse {
  enabled: boolean;
  providers_configured: number;
  providers_enabled: number;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
}

export interface UpdateProfileRequest {
  current_password: string;
  new_username?: string;
  new_password?: string;
  email?: string;
}

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const res = await fetch(getApiUrl("/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    return res.json();
  },

  register: async (
    data: RegisterRequest
  ): Promise<LoginResponse> => {
    const res = await fetch(getApiUrl("/auth/register"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    return res.json();
  },

  getStatus: async (): Promise<AuthStatusResponse> => {
    const res = await fetch(getApiUrl("/auth/status"));
    if (!res.ok) throw new Error("Failed to check auth status");
    return res.json();
  },

  verify: async (token: string): Promise<VerifyResponse> => {
    const res = await fetch(getApiUrl("/auth/verify"), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Token verification failed");
    }
    return res.json();
  },

  updateProfile: async (
    data: UpdateProfileRequest,
    token: string
  ): Promise<LoginResponse> => {
    const res = await fetch(getApiUrl("/auth/update-profile"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Update failed");
    }
    return res.json();
  },

  // OIDC API
  oidc: {
    getProviders: async (): Promise<OIDCProvidersResponse> => {
      const res = await fetch(getApiUrl("/auth/oidc/providers"));
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to get OIDC providers");
      }
      return res.json();
    },

    login: async (data: OIDCLoginRequest): Promise<OIDCLoginResponse> => {
      const res = await fetch(getApiUrl("/auth/oidc/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "OIDC login initiation failed");
      }
      return res.json();
    },

    getStatus: async (): Promise<OIDCStatusResponse> => {
      const res = await fetch(getApiUrl("/auth/oidc/status"));
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to get OIDC status");
      }
      return res.json();
    },

    // Callback is handled by redirect, not direct API call
  },
};
