import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type { UserProfile, UserRole } from '../lib/types';

const ROLE_COLORS: Record<UserRole, string> = {
  admin: 'bg-red-500/10 text-red-400 border-red-500/20',
  user: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  viewer: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
};

export function UserManagement() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Create form state — just username, email, password
  const [form, setForm] = useState({ email: '', username: '', password: '' });

  // Reset password state
  const [resetUserId, setResetUserId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');

  // Delete confirm state
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);

  const fetchUsers = async () => {
    try {
      const res = await api.users.list({ page_size: 200 });
      setUsers(res.users);
      setTotal(res.total);
    } catch {
      setError('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const showSuccessMsg = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(null), 3000);
  };

  const handleCreate = async () => {
    setError(null);
    try {
      await api.users.create({ ...form, role: 'user' });
      setShowCreate(false);
      setForm({ email: '', username: '', password: '' });
      showSuccessMsg('User created');
      fetchUsers();
    } catch {
      setError('Failed to create user. Check for duplicate email/username.');
    }
  };

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await api.users.update(userId, { role });
      fetchUsers();
    } catch {
      setError('Failed to update role');
    }
  };

  const handleResetPassword = async () => {
    if (!resetUserId || newPassword.length < 8) return;
    setError(null);
    try {
      await api.users.resetPassword(resetUserId, newPassword);
      setResetUserId(null);
      setNewPassword('');
      showSuccessMsg('Password reset');
    } catch {
      setError('Failed to reset password');
    }
  };

  const handleDelete = async () => {
    if (!deleteUserId) return;
    setError(null);
    try {
      await api.users.delete(deleteUserId);
      setDeleteUserId(null);
      showSuccessMsg('User deleted');
      fetchUsers();
    } catch {
      setError('Failed to delete user');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <span className="text-sm text-solace-muted">Loading users...</span>
      </div>
    );
  }

  const deleteUser = users.find(u => u.id === deleteUserId);
  const resetUser = users.find(u => u.id === resetUserId);

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-solace-bright">
          Users <span className="text-sm font-normal text-solace-muted ml-2">{total}</span>
        </h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
        >
          {showCreate ? 'Cancel' : 'Create User'}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400/50 hover:text-red-400">&times;</button>
        </div>
      )}
      {success && (
        <div className="p-3 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-sm text-emerald-400">
          {success}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="bg-solace-surface border border-solace-border rounded-lg p-5 space-y-3">
          <h2 className="text-sm font-semibold text-solace-bright">New User</h2>
          <div className="grid grid-cols-3 gap-3">
            <input
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
            />
            <input
              placeholder="Email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
            />
            <input
              placeholder="Password (min 8 chars)"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
            />
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-solace-muted">Created as <span className="text-blue-400 font-medium">User</span> role</span>
            <button
              onClick={handleCreate}
              disabled={!form.username || !form.email || !form.password || form.password.length < 8}
              className="px-4 py-2 text-xs font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Create
            </button>
          </div>
        </div>
      )}

      {/* Reset password modal */}
      {resetUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => { setResetUserId(null); setNewPassword(''); }}>
          <div className="bg-solace-surface border border-solace-border rounded-lg p-6 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-sm font-semibold text-solace-bright mb-3">Reset Password</h2>
            <p className="text-xs text-solace-muted mb-3">
              Set a new password for <span className="text-solace-bright font-medium">@{resetUser?.username}</span>
            </p>
            <input
              type="password"
              placeholder="New password (min 8 chars)"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              autoFocus
              className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50 mb-3"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setResetUserId(null); setNewPassword(''); }}
                className="px-3 py-1.5 text-xs text-solace-muted hover:text-solace-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleResetPassword}
                disabled={newPassword.length < 8}
                className="px-4 py-1.5 text-xs font-medium rounded-md bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Reset Password
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirm modal */}
      {deleteUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setDeleteUserId(null)}>
          <div className="bg-solace-surface border border-solace-border rounded-lg p-6 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-sm font-semibold text-red-400 mb-3">Delete User</h2>
            <p className="text-xs text-solace-muted mb-4">
              Permanently delete <span className="text-solace-bright font-medium">@{deleteUser?.username}</span>? This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteUserId(null)}
                className="px-3 py-1.5 text-xs text-solace-muted hover:text-solace-text transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-1.5 text-xs font-medium rounded-md bg-red-600 text-white hover:bg-red-500 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User table */}
      <div className="bg-solace-surface border border-solace-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-solace-border bg-solace-surface/50">
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">User</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Email</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Role</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Status</th>
              <th className="text-right px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-solace-border/50">
            {users.map(u => {
              const isAdminUser = u.role === 'admin' && u.username === 'admin';
              return (
                <tr key={u.id} className="hover:bg-solace-bg/50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-solace-bright">{u.display_name}</div>
                    <div className="text-xs text-solace-muted font-mono">@{u.username}</div>
                  </td>
                  <td className="px-4 py-3 text-solace-text font-mono text-xs">{u.email}</td>
                  <td className="px-4 py-3">
                    {isAdminUser ? (
                      <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded border ${ROLE_COLORS.admin}`}>
                        Admin
                      </span>
                    ) : (
                      <select
                        value={u.role}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded border cursor-pointer bg-transparent ${ROLE_COLORS[u.role]}`}
                      >
                        <option value="user">User</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-[10px] font-medium rounded ${
                      u.is_active
                        ? 'bg-emerald-500/10 text-emerald-400'
                        : 'bg-red-500/10 text-red-400'
                    }`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isAdminUser ? (
                      <span className="text-[10px] text-solace-muted italic">Protected</span>
                    ) : (
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setResetUserId(u.id)}
                          className="px-2 py-1 text-[10px] font-medium rounded text-amber-400 hover:bg-amber-500/10 transition-colors"
                          title="Reset password"
                        >
                          Reset PW
                        </button>
                        <button
                          onClick={() => setDeleteUserId(u.id)}
                          className="px-2 py-1 text-[10px] font-medium rounded text-red-400 hover:bg-red-500/10 transition-colors"
                          title="Delete user"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
