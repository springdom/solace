import { create } from 'zustand';
import type { UserProfile, UserRole } from '../lib/types';
import { api, getToken, setToken, clearToken } from '../lib/api';

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  mustChangePassword: boolean;
  loading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  loadFromStorage: () => Promise<void>;
  isRole: (...roles: UserRole[]) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  mustChangePassword: false,
  loading: true,
  error: null,

  login: async (username, password) => {
    set({ loading: true, error: null });
    try {
      const res = await api.auth.login(username, password);
      setToken(res.access_token);
      set({
        token: res.access_token,
        user: res.user,
        isAuthenticated: true,
        mustChangePassword: res.must_change_password,
        loading: false,
        error: null,
      });
    } catch (e) {
      set({ loading: false, error: 'Invalid username or password' });
      throw e;
    }
  },

  logout: () => {
    clearToken();
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      mustChangePassword: false,
      loading: false,
      error: null,
    });
  },

  changePassword: async (currentPassword, newPassword) => {
    set({ error: null });
    try {
      await api.auth.changePassword(currentPassword, newPassword);
      set({ mustChangePassword: false });
    } catch {
      set({ error: 'Failed to change password. Check your current password.' });
      throw new Error('Password change failed');
    }
  },

  loadFromStorage: async () => {
    const token = getToken();
    if (!token) {
      set({ loading: false });
      return;
    }

    try {
      const user = await api.auth.me();
      set({
        token,
        user,
        isAuthenticated: true,
        mustChangePassword: user.must_change_password,
        loading: false,
      });
    } catch {
      clearToken();
      set({ loading: false });
    }
  },

  isRole: (...roles) => {
    const { user } = get();
    if (!user) return false;
    return roles.includes(user.role);
  },
}));
