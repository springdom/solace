import { useState } from 'react';
import type { SilenceWindow } from '../lib/types';
import { useSilences } from '../hooks/useSilences';
import { formatTimestamp } from '../lib/time';

const STATE_TABS = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'expired', label: 'Expired' },
] as const;

function isActive(w: SilenceWindow): boolean {
  const now = Date.now();
  return w.is_active && new Date(w.starts_at).getTime() <= now && new Date(w.ends_at).getTime() >= now;
}

function toLocalDatetime(isoStr: string): string {
  const d = new Date(isoStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function SilenceList() {
  const [stateFilter, setStateFilter] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const { windows, loading, error, createSilence, updateSilence, deleteSilence } = useSilences({ state: stateFilter });

  // Create form state
  const [formName, setFormName] = useState('');
  const [formServices, setFormServices] = useState('');
  const [formSeverities, setFormSeverities] = useState('');
  const [formStartsAt, setFormStartsAt] = useState('');
  const [formEndsAt, setFormEndsAt] = useState('');
  const [formReason, setFormReason] = useState('');

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editServices, setEditServices] = useState('');
  const [editSeverities, setEditSeverities] = useState('');
  const [editStartsAt, setEditStartsAt] = useState('');
  const [editEndsAt, setEditEndsAt] = useState('');
  const [editReason, setEditReason] = useState('');

  const handleCreate = async () => {
    if (!formName || !formStartsAt || !formEndsAt) return;

    const matchers: Record<string, unknown> = {};
    if (formServices.trim()) {
      matchers.service = formServices.split(',').map(s => s.trim()).filter(Boolean);
    }
    if (formSeverities.trim()) {
      matchers.severity = formSeverities.split(',').map(s => s.trim()).filter(Boolean);
    }

    await createSilence({
      name: formName,
      matchers,
      starts_at: new Date(formStartsAt).toISOString(),
      ends_at: new Date(formEndsAt).toISOString(),
      reason: formReason || undefined,
    });

    setFormName('');
    setFormServices('');
    setFormSeverities('');
    setFormStartsAt('');
    setFormEndsAt('');
    setFormReason('');
    setShowForm(false);
  };

  const startEdit = (w: SilenceWindow) => {
    setEditingId(w.id);
    setEditName(w.name);
    setEditServices(w.matchers.service?.join(', ') || '');
    setEditSeverities(w.matchers.severity?.join(', ') || '');
    setEditStartsAt(toLocalDatetime(w.starts_at));
    setEditEndsAt(toLocalDatetime(w.ends_at));
    setEditReason(w.reason || '');
  };

  const handleUpdate = async () => {
    if (!editingId || !editName || !editStartsAt || !editEndsAt) return;

    const matchers: Record<string, unknown> = {};
    if (editServices.trim()) {
      matchers.service = editServices.split(',').map(s => s.trim()).filter(Boolean);
    }
    if (editSeverities.trim()) {
      matchers.severity = editSeverities.split(',').map(s => s.trim()).filter(Boolean);
    }

    await updateSilence(editingId, {
      name: editName,
      matchers,
      starts_at: new Date(editStartsAt).toISOString(),
      ends_at: new Date(editEndsAt).toISOString(),
      reason: editReason || null,
    });
    setEditingId(null);
  };

  const inputClass = "w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50";
  const labelClass = "block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1";

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center justify-between px-5 py-2 border-b border-solace-border">
        <div className="flex items-center gap-1">
          {STATE_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setStateFilter(tab.key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                stateFilter === tab.key
                  ? 'bg-solace-surface text-solace-bright'
                  : 'text-solace-muted hover:text-solace-text hover:bg-solace-surface/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
        >
          {showForm ? 'Cancel' : '+ New Silence'}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="flex-shrink-0 border-b border-solace-border bg-solace-surface/30 p-4">
          <div className="grid grid-cols-2 gap-3 max-w-2xl">
            <div className="col-span-2">
              <label className={labelClass}>Name</label>
              <input type="text" value={formName} onChange={e => setFormName(e.target.value)} placeholder="Maintenance window name" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Services (comma-separated)</label>
              <input type="text" value={formServices} onChange={e => setFormServices(e.target.value)} placeholder="api, web (empty = all)" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Severities (comma-separated)</label>
              <input type="text" value={formSeverities} onChange={e => setFormSeverities(e.target.value)} placeholder="critical, high (empty = all)" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Starts at</label>
              <input type="datetime-local" value={formStartsAt} onChange={e => setFormStartsAt(e.target.value)} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Ends at</label>
              <input type="datetime-local" value={formEndsAt} onChange={e => setFormEndsAt(e.target.value)} className={inputClass} />
            </div>
            <div className="col-span-2">
              <label className={labelClass}>Reason</label>
              <input type="text" value={formReason} onChange={e => setFormReason(e.target.value)} placeholder="Optional reason for this silence" className={inputClass} />
            </div>
            <div className="col-span-2">
              <button
                onClick={handleCreate}
                disabled={!formName || !formStartsAt || !formEndsAt}
                className="px-4 py-1.5 text-xs font-medium rounded-md bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Create Silence
              </button>
            </div>
          </div>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="m-4 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}
        {loading && windows.length === 0 && (
          <div className="flex items-center justify-center h-40">
            <div className="text-sm text-solace-muted">Loading silences...</div>
          </div>
        )}
        {!loading && windows.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 text-solace-muted">
            <span className="text-sm">No silence windows found</span>
          </div>
        )}
        <div className="divide-y divide-solace-border/50">
          {windows.map(window => (
            <div key={window.id}>
              {editingId === window.id ? (
                /* Inline edit form */
                <div className="bg-solace-surface/30 p-4 border-b border-solace-border">
                  <div className="grid grid-cols-2 gap-3 max-w-2xl">
                    <div className="col-span-2">
                      <label className={labelClass}>Name</label>
                      <input type="text" value={editName} onChange={e => setEditName(e.target.value)} className={inputClass} />
                    </div>
                    <div>
                      <label className={labelClass}>Services</label>
                      <input type="text" value={editServices} onChange={e => setEditServices(e.target.value)} placeholder="api, web (empty = all)" className={inputClass} />
                    </div>
                    <div>
                      <label className={labelClass}>Severities</label>
                      <input type="text" value={editSeverities} onChange={e => setEditSeverities(e.target.value)} placeholder="critical, high (empty = all)" className={inputClass} />
                    </div>
                    <div>
                      <label className={labelClass}>Starts at</label>
                      <input type="datetime-local" value={editStartsAt} onChange={e => setEditStartsAt(e.target.value)} className={inputClass} />
                    </div>
                    <div>
                      <label className={labelClass}>Ends at</label>
                      <input type="datetime-local" value={editEndsAt} onChange={e => setEditEndsAt(e.target.value)} className={inputClass} />
                    </div>
                    <div className="col-span-2">
                      <label className={labelClass}>Reason</label>
                      <input type="text" value={editReason} onChange={e => setEditReason(e.target.value)} className={inputClass} />
                    </div>
                    <div className="col-span-2 flex items-center gap-2">
                      <button
                        onClick={handleUpdate}
                        disabled={!editName || !editStartsAt || !editEndsAt}
                        className="px-4 py-1.5 text-xs font-medium rounded-md bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        Save Changes
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-4 py-1.5 text-xs font-medium text-solace-muted hover:text-solace-text transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* Row display */
                <div className="flex items-center gap-3 px-5 py-3 hover:bg-solace-surface/30 transition-colors">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    isActive(window) ? 'bg-emerald-500' : 'bg-solace-muted/50'
                  }`} />

                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-solace-bright font-medium truncate">{window.name}</div>
                    <div className="flex items-center gap-2 mt-0.5">
                      {window.matchers.service && window.matchers.service.length > 0 && (
                        <span className="text-[10px] font-mono text-solace-muted">
                          services: {window.matchers.service.join(', ')}
                        </span>
                      )}
                      {window.matchers.severity && window.matchers.severity.length > 0 && (
                        <span className="text-[10px] font-mono text-solace-muted">
                          severities: {window.matchers.severity.join(', ')}
                        </span>
                      )}
                      {(!window.matchers.service || window.matchers.service.length === 0) &&
                       (!window.matchers.severity || window.matchers.severity.length === 0) && (
                        <span className="text-[10px] font-mono text-solace-muted">all alerts</span>
                      )}
                    </div>
                  </div>

                  <div className="text-right flex-shrink-0">
                    <div className="text-[10px] font-mono text-solace-muted">
                      {formatTimestamp(window.starts_at)}
                    </div>
                    <div className="text-[10px] font-mono text-solace-muted">
                      to {formatTimestamp(window.ends_at)}
                    </div>
                  </div>

                  {window.reason && (
                    <div className="text-xs text-solace-muted truncate max-w-[120px]" title={window.reason}>
                      {window.reason}
                    </div>
                  )}

                  <button
                    onClick={() => startEdit(window)}
                    className="flex-shrink-0 px-2 py-1 text-[10px] font-mono text-solace-muted hover:text-solace-text hover:bg-solace-surface/50 rounded transition-colors"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => deleteSilence(window.id)}
                    className="flex-shrink-0 px-2 py-1 text-[10px] font-mono text-red-400/60 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                  >
                    Expire
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
