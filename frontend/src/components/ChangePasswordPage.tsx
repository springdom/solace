import { useState, type FormEvent } from 'react';
import { useAuthStore } from '../stores/authStore';

export function ChangePasswordPage() {
  const changePassword = useAuthStore((s) => s.changePassword);
  const error = useAuthStore((s) => s.error);
  const user = useAuthStore((s) => s.user);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError('');

    if (newPassword.length < 8) {
      setLocalError('New password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setLocalError('Passwords do not match');
      return;
    }

    try {
      await changePassword(currentPassword, newPassword);
    } catch {
      // Error handled in store
    }
  };

  const displayError = localError || error;

  return (
    <div className="min-h-screen flex items-center justify-center bg-solace-bg">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center mb-4">
            <svg width="22" height="22" viewBox="0 0 16 16" fill="white">
              <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2.5a1 1 0 110 2 1 1 0 010-2zM6.5 7h3l-.5 5.5h-2L6.5 7z" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-solace-bright">Change Password</h1>
          <p className="text-sm text-solace-muted mt-1">
            Welcome, {user?.display_name}. Please set a new password to continue.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-solace-surface border border-solace-border rounded-lg p-6 space-y-4">
          {displayError && (
            <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
              {displayError}
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-solace-muted mb-1.5">Current Password</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoFocus
              className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-solace-muted mb-1.5">New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
              placeholder="Minimum 8 characters"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-solace-muted mb-1.5">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
            />
          </div>

          <button
            type="submit"
            disabled={!currentPassword || !newPassword || !confirmPassword}
            className="w-full py-2 text-sm font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Set New Password
          </button>
        </form>
      </div>
    </div>
  );
}
