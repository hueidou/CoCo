import { getApiUrl } from "../config";

export interface User {
  id: number;
  username: string;
  email?: string;
  role: string;
  oidc_provider?: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login?: string;
}

export interface UserListResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  email?: string;
  role: string;
}

export interface UpdateUserRequest {
  username?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export interface PasswordResetRequest {
  new_password: string;
}

export const usersApi = {
  // List users
  list: async (
    token: string,
    params?: {
      skip?: number;
      limit?: number;
      active_only?: boolean;
    }
  ): Promise<UserListResponse> => {
    const url = new URL(getApiUrl("/users/"));
    if (params) {
      if (params.skip !== undefined) url.searchParams.append("skip", params.skip.toString());
      if (params.limit !== undefined) url.searchParams.append("limit", params.limit.toString());
      if (params.active_only !== undefined) url.searchParams.append("active_only", params.active_only.toString());
    }

    const res = await fetch(url.toString(), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to list users");
    }
    return res.json();
  },

  // Get user by ID
  get: async (token: string, userId: number): Promise<User> => {
    const res = await fetch(getApiUrl(`/users/${userId}`), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to get user");
    }
    return res.json();
  },

  // Get current user
  getMe: async (token: string): Promise<User> => {
    const res = await fetch(getApiUrl("/users/me"), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to get current user");
    }
    return res.json();
  },

  // Create user
  create: async (token: string, data: CreateUserRequest): Promise<User> => {
    const res = await fetch(getApiUrl("/users/"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to create user");
    }
    return res.json();
  },

  // Update user
  update: async (
    token: string,
    userId: number,
    data: UpdateUserRequest
  ): Promise<User> => {
    const res = await fetch(getApiUrl(`/users/${userId}`), {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to update user");
    }
    return res.json();
  },

  // Delete user (soft delete - deactivate)
  delete: async (token: string, userId: number): Promise<{ message: string }> => {
    const res = await fetch(getApiUrl(`/users/${userId}`), {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to delete user");
    }
    return res.json();
  },

  // Reset user password
  resetPassword: async (
    token: string,
    userId: number,
    data: PasswordResetRequest
  ): Promise<{ message: string }> => {
    const res = await fetch(getApiUrl(`/users/${userId}/reset-password`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to reset password");
    }
    return res.json();
  },

  // Search users
  search: async (
    token: string,
    query: string,
    params?: {
      skip?: number;
      limit?: number;
    }
  ): Promise<User[]> => {
    // Note: Search endpoint might need to be implemented in backend
    // For now, we can filter client-side or wait for backend implementation
    const listResponse = await usersApi.list(token, params);
    
    // Simple client-side search
    const searchTerm = query.toLowerCase();
    return listResponse.users.filter(
      (user) =>
        user.username.toLowerCase().includes(searchTerm) ||
        (user.email && user.email.toLowerCase().includes(searchTerm))
    );
  },

  // Helper: Check if user is admin
  isAdmin: (user: User): boolean => {
    return user.role === "admin";
  },

  // Helper: Format user role for display
  formatRole: (role: string): string => {
    return role.charAt(0).toUpperCase() + role.slice(1);
  },

  // Helper: Format date for display
  formatDate: (dateString?: string): string => {
    if (!dateString) return "Never";
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    } catch {
      return dateString;
    }
  },
};