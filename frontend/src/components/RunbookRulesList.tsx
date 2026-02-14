import { useState, useEffect, useCallback } from 'react';
import type { RunbookRule } from '../lib/types';
import { api } from '../lib/api';

interface RunbookRulesListProps {
  isAdmin: boolean;
}

export function RunbookRulesList({ isAdmin }: RunbookRulesListProps) {
  const [rules, setRules] = useState<RunbookRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    service_pattern: '',
    name_pattern: '',
    runbook_url_template: '',
    description: '',
    priority: 0,
  });

  const fetchRules = useCallback(async () => {
    try {
      const data = await api.runbooks.listRules();
      setRules(data.rules);
    } catch {
      setError('Failed to load runbook rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const handleCreate = async () => {
    setError(null);
    try {
      await api.runbooks.createRule({
        service_pattern: form.service_pattern,
        name_pattern: form.name_pattern || undefined,
        runbook_url_template: form.runbook_url_template,
        description: form.description || undefined,
        priority: form.priority,
      });
      setShowCreate(false);
      setForm({ service_pattern: '', name_pattern: '', runbook_url_template: '', description: '', priority: 0 });
      fetchRules();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create rule');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this runbook rule?')) return;
    setError(null);
    try {
      await api.runbooks.deleteRule(id);
      fetchRules();
    } catch {
      setError('Failed to delete rule');
    }
  };

  if (loading) {
    return <div className="text-sm text-solace-muted p-4">Loading runbook rules...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-solace-bright">Runbook Rules</h2>
          <p className="text-xs text-solace-muted mt-0.5">
            Auto-attach runbook URLs to incoming alerts based on service and name patterns.
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            {showCreate ? 'Cancel' : 'New Rule'}
          </button>
        )}
      </div>

      {error && (
        <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-400">{error}</div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="bg-solace-bg border border-solace-border rounded-lg p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-solace-muted mb-1">
                Service Pattern <span className="text-red-400">*</span>
              </label>
              <input
                value={form.service_pattern}
                onChange={e => setForm(f => ({ ...f, service_pattern: e.target.value }))}
                placeholder="payment-* or auth-service"
                className="w-full px-2 py-1.5 text-xs font-mono bg-solace-surface border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-solace-muted mb-1">
                Name Pattern <span className="text-solace-muted/50">(optional)</span>
              </label>
              <input
                value={form.name_pattern}
                onChange={e => setForm(f => ({ ...f, name_pattern: e.target.value }))}
                placeholder="CPU* or HighMemory*"
                className="w-full px-2 py-1.5 text-xs font-mono bg-solace-surface border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
              />
            </div>
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-solace-muted mb-1">
              Runbook URL Template <span className="text-red-400">*</span>
            </label>
            <input
              value={form.runbook_url_template}
              onChange={e => setForm(f => ({ ...f, runbook_url_template: e.target.value }))}
              placeholder="https://confluence.com/runbooks#{service}"
              className="w-full px-2 py-1.5 text-xs font-mono bg-solace-surface border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
            />
            <p className="text-[10px] text-solace-muted/70 mt-1">
              Variables: <code className="text-solace-muted">{'{service}'}</code> <code className="text-solace-muted">{'{host}'}</code> <code className="text-solace-muted">{'{name}'}</code> <code className="text-solace-muted">{'{environment}'}</code>
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-solace-muted mb-1">Description</label>
              <input
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="Links payment alerts to runbook"
                className="w-full px-2 py-1.5 text-xs font-mono bg-solace-surface border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-solace-muted mb-1">Priority</label>
              <input
                type="number"
                value={form.priority}
                onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) || 0 }))}
                className="w-full px-2 py-1.5 text-xs font-mono bg-solace-surface border border-solace-border rounded text-solace-bright focus:outline-none focus:border-emerald-500/50"
              />
              <p className="text-[10px] text-solace-muted/70 mt-0.5">Lower = matched first</p>
            </div>
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleCreate}
              disabled={!form.service_pattern.trim() || !form.runbook_url_template.trim()}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Create Rule
            </button>
          </div>
        </div>
      )}

      {/* Rules table */}
      {rules.length === 0 ? (
        <div className="text-center py-8 text-xs text-solace-muted">
          No runbook rules configured. Create one to auto-attach runbook URLs to incoming alerts.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-solace-border">
                <th className="text-left py-2 px-2 text-[10px] uppercase tracking-wider text-solace-muted font-semibold w-12">Pri</th>
                <th className="text-left py-2 px-2 text-[10px] uppercase tracking-wider text-solace-muted font-semibold">Service Pattern</th>
                <th className="text-left py-2 px-2 text-[10px] uppercase tracking-wider text-solace-muted font-semibold">Name Pattern</th>
                <th className="text-left py-2 px-2 text-[10px] uppercase tracking-wider text-solace-muted font-semibold">URL Template</th>
                <th className="text-left py-2 px-2 text-[10px] uppercase tracking-wider text-solace-muted font-semibold">Description</th>
                {isAdmin && (
                  <th className="w-10"></th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-solace-border/30">
              {rules.map(rule => (
                <tr key={rule.id} className="hover:bg-solace-surface/30 transition-colors">
                  <td className="py-2 px-2 font-mono text-solace-bright">{rule.priority}</td>
                  <td className="py-2 px-2 font-mono text-solace-bright">{rule.service_pattern}</td>
                  <td className="py-2 px-2 font-mono text-solace-muted">{rule.name_pattern || '--'}</td>
                  <td className="py-2 px-2 font-mono text-blue-400 truncate max-w-[280px]" title={rule.runbook_url_template}>
                    {rule.runbook_url_template}
                  </td>
                  <td className="py-2 px-2 text-solace-muted">{rule.description || '--'}</td>
                  {isAdmin && (
                    <td className="py-2 px-2 text-right">
                      <button
                        onClick={() => handleDelete(rule.id)}
                        className="text-solace-muted hover:text-red-400 transition-colors"
                        title="Delete rule"
                      >
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M3 3l6 6M9 3l-6 6" />
                        </svg>
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
