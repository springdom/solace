import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import type {
  OnCallSchedule, EscalationPolicy, ServiceMapping,
  UserProfile, OnCallCurrentResponse,
} from '../lib/types';

export function OnCallView({ isAdmin }: { isAdmin: boolean }) {
  const [tab, setTab] = useState<'schedules' | 'policies' | 'mappings'>('schedules');
  const [schedules, setSchedules] = useState<OnCallSchedule[]>([]);
  const [policies, setPolicies] = useState<EscalationPolicy[]>([]);
  const [mappings, setMappings] = useState<ServiceMapping[]>([]);
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [currentOnCall, setCurrentOnCall] = useState<Record<string, OnCallCurrentResponse>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sRes, pRes, mRes, uRes] = await Promise.all([
        api.oncall.listSchedules(),
        api.oncall.listPolicies(),
        api.oncall.listMappings(),
        api.users.list({ page_size: 200 }),
      ]);
      setSchedules(sRes.schedules);
      setPolicies(pRes.policies);
      setMappings(mRes);
      setUsers(uRes.users.filter(u => u.is_active));

      // Fetch current on-call for each active schedule
      const oncallMap: Record<string, OnCallCurrentResponse> = {};
      for (const s of sRes.schedules.filter(s => s.is_active)) {
        try {
          oncallMap[s.id] = await api.oncall.getCurrentOnCall(s.id);
        } catch { /* non-critical */ }
      }
      setCurrentOnCall(oncallMap);
    } catch {
      setError('Failed to load on-call data');
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <span className="text-sm text-solace-muted">Loading on-call data...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full space-y-4">
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400/50 hover:text-red-400">&times;</button>
        </div>
      )}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-solace-bright">On-Call</h1>
        <div className="flex items-center bg-solace-surface rounded-lg p-0.5">
          {(['schedules', 'policies', 'mappings'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                tab === t ? 'bg-solace-bg text-solace-bright shadow-sm' : 'text-solace-muted hover:text-solace-text'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Who's On Call Now */}
      {tab === 'schedules' && schedules.filter(s => s.is_active).length > 0 && (
        <div className="bg-solace-surface border border-solace-border rounded-lg p-5">
          <h2 className="text-sm font-semibold text-solace-bright mb-3">Currently On Call</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {schedules.filter(s => s.is_active).map(s => {
              const oc = currentOnCall[s.id];
              return (
                <div key={s.id} className="flex items-center gap-3 p-3 rounded-md bg-solace-bg border border-solace-border">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                    oc?.user ? 'bg-emerald-500/20 text-emerald-400' : 'bg-solace-muted/20 text-solace-muted'
                  }`}>
                    {oc?.user?.display_name?.charAt(0) || '—'}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-solace-bright">
                      {oc?.user?.display_name || 'No members assigned'}
                    </div>
                    <div className="text-[10px] text-solace-muted">{s.name}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {tab === 'schedules' && (
        <SchedulesList schedules={schedules} users={users} isAdmin={isAdmin} onRefresh={fetchData} />
      )}
      {tab === 'policies' && (
        <PoliciesList policies={policies} schedules={schedules} users={users} isAdmin={isAdmin} onRefresh={fetchData} />
      )}
      {tab === 'mappings' && (
        <MappingsList mappings={mappings} policies={policies} isAdmin={isAdmin} onRefresh={fetchData} />
      )}
    </div>
  );
}


/* ─── Schedule List ──────────────────────────────────────── */

function SchedulesList({ schedules, users, isAdmin, onRefresh }: {
  schedules: OnCallSchedule[];
  users: UserProfile[];
  isAdmin: boolean;
  onRefresh: () => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '', description: '', timezone: 'UTC',
    rotation_type: 'weekly' as string,
    handoff_time: '09:00',
    rotation_interval_days: 7,
    rotation_interval_hours: 8,
    members: [] as Array<{ user_id: string; order: number }>,
  });

  const resetForm = () => setForm({
    name: '', description: '', timezone: 'UTC', rotation_type: 'weekly',
    handoff_time: '09:00', rotation_interval_days: 7, rotation_interval_hours: 8,
    members: [],
  });

  const handleCreate = async () => {
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        description: form.description || undefined,
        timezone: form.timezone,
        rotation_type: form.rotation_type,
        handoff_time: form.handoff_time,
        members: form.members,
      };
      if (form.rotation_type === 'hourly') {
        payload.rotation_interval_hours = form.rotation_interval_hours;
      } else {
        payload.rotation_interval_days = form.rotation_interval_days;
      }
      await api.oncall.createSchedule(payload);
      setShowCreate(false);
      resetForm();
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create schedule');
    }
  };

  const handleUpdate = async (id: string) => {
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        description: form.description || undefined,
        timezone: form.timezone,
        rotation_type: form.rotation_type,
        handoff_time: form.handoff_time,
        members: form.members,
      };
      if (form.rotation_type === 'hourly') {
        payload.rotation_interval_hours = form.rotation_interval_hours;
      } else {
        payload.rotation_interval_days = form.rotation_interval_days;
      }
      await api.oncall.updateSchedule(id, payload);
      setEditingId(null);
      resetForm();
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update schedule');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this schedule?')) return;
    setError(null);
    try {
      await api.oncall.deleteSchedule(id);
      onRefresh();
    } catch {
      setError('Failed to delete schedule');
    }
  };

  const startEdit = (s: OnCallSchedule) => {
    setEditingId(s.id);
    setShowCreate(false);
    setForm({
      name: s.name,
      description: s.description || '',
      timezone: s.timezone,
      rotation_type: s.rotation_type,
      handoff_time: s.handoff_time,
      rotation_interval_days: s.rotation_interval_days,
      rotation_interval_hours: s.rotation_interval_hours || 8,
      members: s.members.map((m, i) => ({ user_id: m.user_id, order: m.order ?? i })),
    });
  };

  const addMember = (userId: string) => {
    if (form.members.some(m => m.user_id === userId)) return;
    setForm({
      ...form,
      members: [...form.members, { user_id: userId, order: form.members.length }],
    });
  };

  const removeMember = (userId: string) => {
    setForm({
      ...form,
      members: form.members
        .filter(m => m.user_id !== userId)
        .map((m, i) => ({ ...m, order: i })),
    });
  };

  const getUserName = (userId: string) =>
    users.find(u => u.id === userId)?.display_name ||
    users.find(u => u.id === userId)?.username || userId.slice(0, 8);

  const availableUsers = users.filter(u => !form.members.some(m => m.user_id === u.id));

  const renderForm = (onSubmit: () => void, submitLabel: string) => (
    <div className="bg-solace-surface border border-solace-border rounded-lg p-5 space-y-4">
      <h2 className="text-sm font-semibold text-solace-bright">
        {submitLabel === 'Create' ? 'Create Schedule' : 'Edit Schedule'}
      </h2>
      <div className="grid grid-cols-2 gap-3">
        <input
          placeholder="Name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
        />
        <input
          placeholder="Timezone (e.g. UTC, America/New_York)"
          value={form.timezone}
          onChange={(e) => setForm({ ...form, timezone: e.target.value })}
          className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
        />
        <select
          value={form.rotation_type}
          onChange={(e) => setForm({ ...form, rotation_type: e.target.value })}
          className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
        >
          <option value="hourly">Hourly</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="custom">Custom</option>
        </select>
        <input
          placeholder="Handoff Time (HH:MM)"
          value={form.handoff_time}
          onChange={(e) => setForm({ ...form, handoff_time: e.target.value })}
          className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
        />
      </div>

      {form.rotation_type === 'hourly' ? (
        <div className="flex items-center gap-2">
          <label className="text-xs text-solace-muted">Rotate every</label>
          <input
            type="number"
            min={1} max={720}
            value={form.rotation_interval_hours}
            onChange={(e) => setForm({ ...form, rotation_interval_hours: parseInt(e.target.value) || 1 })}
            className="w-20 px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
          />
          <span className="text-xs text-solace-muted">hours</span>
        </div>
      ) : form.rotation_type === 'custom' ? (
        <div className="flex items-center gap-2">
          <label className="text-xs text-solace-muted">Rotate every</label>
          <input
            type="number"
            min={1} max={365}
            value={form.rotation_interval_days}
            onChange={(e) => setForm({ ...form, rotation_interval_days: parseInt(e.target.value) || 1 })}
            className="w-20 px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
          />
          <span className="text-xs text-solace-muted">days</span>
        </div>
      ) : null}

      <input
        placeholder="Description (optional)"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
        className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
      />

      {/* Member management */}
      <div>
        <label className="block text-xs font-medium text-solace-text mb-2">Rotation Members</label>
        {form.members.length > 0 && (
          <div className="space-y-1 mb-2">
            {form.members.map((m, i) => (
              <div key={m.user_id} className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-solace-bg border border-solace-border">
                <span className="text-[10px] text-solace-muted font-mono w-5">#{i + 1}</span>
                <span className="text-sm text-solace-bright flex-1">{getUserName(m.user_id)}</span>
                <button
                  onClick={() => removeMember(m.user_id)}
                  className="text-xs text-solace-muted hover:text-red-400"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        {availableUsers.length > 0 && (
          <select
            value=""
            onChange={(e) => { if (e.target.value) addMember(e.target.value); }}
            className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
          >
            <option value="">+ Add member...</option>
            {availableUsers.map(u => (
              <option key={u.id} value={u.id}>{u.display_name || u.username}</option>
            ))}
          </select>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onSubmit}
          disabled={!form.name}
          className="px-4 py-2 text-xs font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
        >
          {submitLabel}
        </button>
        <button
          onClick={() => { setShowCreate(false); setEditingId(null); resetForm(); }}
          className="px-4 py-2 text-xs font-medium rounded-md text-solace-muted hover:text-solace-text transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400/50 hover:text-red-400">&times;</button>
        </div>
      )}
      {isAdmin && !editingId && (
        <div className="flex justify-end">
          <button
            onClick={() => { setShowCreate(!showCreate); resetForm(); }}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            {showCreate ? 'Cancel' : 'New Schedule'}
          </button>
        </div>
      )}

      {showCreate && renderForm(handleCreate, 'Create')}

      {schedules.length === 0 && !showCreate ? (
        <div className="text-center py-8 text-sm text-solace-muted">No schedules configured</div>
      ) : (
        <div className="space-y-2">
          {schedules.map(s => (
            <div key={s.id}>
              {editingId === s.id ? (
                renderForm(() => handleUpdate(s.id), 'Save')
              ) : (
                <div className="bg-solace-surface border border-solace-border rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-solace-bright">{s.name}</span>
                        <span className={`px-1.5 py-0.5 text-[9px] font-mono uppercase rounded ${
                          s.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-500/10 text-gray-400'
                        }`}>
                          {s.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      {s.description && <p className="text-xs text-solace-muted mt-0.5">{s.description}</p>}
                    </div>
                    {isAdmin && (
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => startEdit(s)}
                          className="text-xs text-solace-muted hover:text-solace-bright transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(s.id)}
                          className="text-xs text-solace-muted hover:text-red-400 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-4 text-xs text-solace-muted flex-wrap">
                    <span>Rotation: <span className="text-solace-text font-mono">{s.rotation_type}</span></span>
                    {s.rotation_type === 'hourly' ? (
                      <span>Interval: <span className="text-solace-text font-mono">{s.rotation_interval_hours || 1}h</span></span>
                    ) : (
                      <span>Interval: <span className="text-solace-text font-mono">{s.rotation_interval_days}d</span></span>
                    )}
                    <span>Handoff: <span className="text-solace-text font-mono">{s.handoff_time}</span></span>
                    <span>TZ: <span className="text-solace-text font-mono">{s.timezone}</span></span>
                  </div>
                  {s.members.length > 0 && (
                    <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] text-solace-muted uppercase tracking-wider mr-1">Members:</span>
                      {s.members.map((m, i) => {
                        const u = users.find(u => u.id === m.user_id);
                        return (
                          <span key={m.user_id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-solace-bg border border-solace-border text-xs text-solace-text">
                            <span className="text-[10px] text-solace-muted font-mono">#{i + 1}</span>
                            {u?.display_name || u?.username || m.user_id.slice(0, 8)}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  {s.members.length === 0 && (
                    <div className="mt-2 text-xs text-amber-400/80">No members assigned — add members to enable rotation</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ─── Policy List ────────────────────────────────────────── */

function PoliciesList({ policies, schedules, users, isAdmin, onRefresh }: {
  policies: EscalationPolicy[];
  schedules: OnCallSchedule[];
  users: UserProfile[];
  isAdmin: boolean;
  onRefresh: () => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '', description: '', repeat_count: 0,
    levels: [] as Array<{
      level: number;
      targets: Array<{ type: 'user' | 'schedule'; id: string }>;
      timeout_minutes: number;
    }>,
  });

  const resetForm = () => setForm({ name: '', description: '', repeat_count: 0, levels: [] });

  const addLevel = () => {
    setForm({
      ...form,
      levels: [...form.levels, { level: form.levels.length + 1, targets: [], timeout_minutes: 15 }],
    });
  };

  const removeLevel = (idx: number) => {
    setForm({
      ...form,
      levels: form.levels.filter((_, i) => i !== idx).map((l, i) => ({ ...l, level: i + 1 })),
    });
  };

  const updateLevelTimeout = (idx: number, timeout: number) => {
    const levels = [...form.levels];
    levels[idx] = { ...levels[idx], timeout_minutes: timeout };
    setForm({ ...form, levels });
  };

  const addTarget = (levelIdx: number, type: 'user' | 'schedule', id: string) => {
    if (!id) return;
    const levels = [...form.levels];
    if (levels[levelIdx].targets.some(t => t.type === type && t.id === id)) return;
    levels[levelIdx] = {
      ...levels[levelIdx],
      targets: [...levels[levelIdx].targets, { type, id }],
    };
    setForm({ ...form, levels });
  };

  const removeTarget = (levelIdx: number, targetIdx: number) => {
    const levels = [...form.levels];
    levels[levelIdx] = {
      ...levels[levelIdx],
      targets: levels[levelIdx].targets.filter((_, i) => i !== targetIdx),
    };
    setForm({ ...form, levels });
  };

  const getTargetName = (type: string, id: string) => {
    if (type === 'user') {
      const u = users.find(u => u.id === id);
      return u?.display_name || u?.username || id.slice(0, 8);
    }
    if (type === 'schedule') {
      const s = schedules.find(s => s.id === id);
      return s?.name || id.slice(0, 8);
    }
    return id.slice(0, 8);
  };

  const handleCreate = async () => {
    setError(null);
    try {
      await api.oncall.createPolicy({
        name: form.name,
        description: form.description || undefined,
        repeat_count: form.repeat_count,
        levels: form.levels,
      });
      setShowCreate(false);
      resetForm();
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create policy');
    }
  };

  const handleUpdate = async (id: string) => {
    setError(null);
    try {
      await api.oncall.updatePolicy(id, {
        name: form.name,
        description: form.description || undefined,
        repeat_count: form.repeat_count,
        levels: form.levels,
      });
      setEditingId(null);
      resetForm();
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update policy');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this escalation policy?')) return;
    setError(null);
    try {
      await api.oncall.deletePolicy(id);
      onRefresh();
    } catch {
      setError('Failed to delete policy');
    }
  };

  const startEdit = (p: EscalationPolicy) => {
    setEditingId(p.id);
    setShowCreate(false);
    setForm({
      name: p.name,
      description: p.description || '',
      repeat_count: p.repeat_count,
      levels: p.levels.map(l => ({
        level: l.level,
        targets: l.targets.map(t => ({ type: t.type as 'user' | 'schedule', id: t.id })),
        timeout_minutes: l.timeout_minutes,
      })),
    });
  };

  const renderForm = (onSubmit: () => void, submitLabel: string) => (
    <div className="bg-solace-surface border border-solace-border rounded-lg p-5 space-y-4">
      <h2 className="text-sm font-semibold text-solace-bright">
        {submitLabel === 'Create' ? 'Create Escalation Policy' : 'Edit Escalation Policy'}
      </h2>
      <input
        placeholder="Policy Name"
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
        className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
      />
      <input
        placeholder="Description (optional)"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
        className="w-full px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
      />
      <div className="flex items-center gap-2">
        <label className="text-xs text-solace-muted">Repeat count:</label>
        <input
          type="number"
          min={0} max={10}
          value={form.repeat_count}
          onChange={(e) => setForm({ ...form, repeat_count: parseInt(e.target.value) || 0 })}
          className="w-16 px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
        />
        <span className="text-[10px] text-solace-muted">0 = no repeat, 1+ = re-escalate N times</span>
      </div>

      {/* Levels */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-medium text-solace-text">Escalation Levels</label>
          <button
            onClick={addLevel}
            className="text-[10px] px-2 py-1 rounded bg-solace-bg text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          >
            + Add Level
          </button>
        </div>
        {form.levels.length === 0 && (
          <p className="text-xs text-solace-muted">No levels — add at least one level with targets.</p>
        )}
        <div className="space-y-3">
          {form.levels.map((lvl, li) => (
            <div key={li} className="p-3 rounded-md bg-solace-bg border border-solace-border space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-semibold text-solace-bright">Level {lvl.level}</span>
                <button onClick={() => removeLevel(li)} className="text-[10px] text-solace-muted hover:text-red-400">Remove</button>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-[10px] text-solace-muted">Timeout:</label>
                <input
                  type="number"
                  min={1} max={1440}
                  value={lvl.timeout_minutes}
                  onChange={(e) => updateLevelTimeout(li, parseInt(e.target.value) || 15)}
                  className="w-16 px-2 py-1 text-xs bg-solace-surface border border-solace-border rounded text-solace-bright focus:outline-none"
                />
                <span className="text-[10px] text-solace-muted">min</span>
              </div>
              {/* Targets */}
              {lvl.targets.length > 0 && (
                <div className="space-y-1">
                  {lvl.targets.map((t, ti) => (
                    <div key={ti} className="flex items-center gap-2 text-xs">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-mono ${
                        t.type === 'schedule' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'
                      }`}>
                        {t.type}
                      </span>
                      <span className="text-solace-text flex-1">{getTargetName(t.type, t.id)}</span>
                      <button onClick={() => removeTarget(li, ti)} className="text-solace-muted hover:text-red-400">×</button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2">
                <select
                  value=""
                  onChange={(e) => { if (e.target.value) addTarget(li, 'user', e.target.value); }}
                  className="px-2 py-1 text-xs bg-solace-surface border border-solace-border rounded text-solace-bright focus:outline-none"
                >
                  <option value="">+ Add user...</option>
                  {users.map(u => (
                    <option key={u.id} value={u.id}>{u.display_name || u.username}</option>
                  ))}
                </select>
                <select
                  value=""
                  onChange={(e) => { if (e.target.value) addTarget(li, 'schedule', e.target.value); }}
                  className="px-2 py-1 text-xs bg-solace-surface border border-solace-border rounded text-solace-bright focus:outline-none"
                >
                  <option value="">+ Add schedule...</option>
                  {schedules.filter(s => s.is_active).map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onSubmit}
          disabled={!form.name}
          className="px-4 py-2 text-xs font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
        >
          {submitLabel}
        </button>
        <button
          onClick={() => { setShowCreate(false); setEditingId(null); resetForm(); }}
          className="px-4 py-2 text-xs font-medium rounded-md text-solace-muted hover:text-solace-text transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400/50 hover:text-red-400">&times;</button>
        </div>
      )}
      {isAdmin && !editingId && (
        <div className="flex justify-end">
          <button
            onClick={() => { setShowCreate(!showCreate); resetForm(); }}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            {showCreate ? 'Cancel' : 'New Policy'}
          </button>
        </div>
      )}

      {showCreate && renderForm(handleCreate, 'Create')}

      {policies.length === 0 && !showCreate ? (
        <div className="text-center py-8 text-sm text-solace-muted">No escalation policies configured</div>
      ) : (
        <div className="space-y-2">
          {policies.map(p => (
            <div key={p.id}>
              {editingId === p.id ? (
                renderForm(() => handleUpdate(p.id), 'Save')
              ) : (
                <div className="bg-solace-surface border border-solace-border rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-solace-bright">{p.name}</span>
                        {p.repeat_count > 0 && (
                          <span className="px-1.5 py-0.5 text-[9px] font-mono uppercase rounded bg-amber-500/10 text-amber-400">
                            Repeat ×{p.repeat_count}
                          </span>
                        )}
                      </div>
                      {p.description && <p className="text-xs text-solace-muted mt-0.5">{p.description}</p>}
                    </div>
                    {isAdmin && (
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => startEdit(p)}
                          className="text-xs text-solace-muted hover:text-solace-bright transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDelete(p.id)}
                          className="text-xs text-solace-muted hover:text-red-400 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                  {p.levels.length === 0 ? (
                    <div className="mt-2 text-xs text-amber-400/80">No levels configured</div>
                  ) : (
                    <div className="mt-2 space-y-1">
                      {p.levels.map((lvl, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className="px-1.5 py-0.5 rounded bg-solace-bg text-solace-muted font-mono">L{lvl.level}</span>
                          <span className="text-solace-text">
                            {lvl.targets.map(t => (
                              <span key={`${t.type}-${t.id}`} className="inline-flex items-center gap-1 mr-2">
                                <span className={`px-1 py-0.5 rounded text-[8px] uppercase font-mono ${
                                  t.type === 'schedule' ? 'bg-blue-500/10 text-blue-400' : 'bg-purple-500/10 text-purple-400'
                                }`}>{t.type === 'schedule' ? 'SCH' : 'USR'}</span>
                                {getTargetName(t.type, t.id)}
                              </span>
                            ))}
                          </span>
                          <span className="text-solace-muted ml-auto">timeout: {lvl.timeout_minutes}m</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ─── Mapping List ───────────────────────────────────────── */

function MappingsList({ mappings, policies, isAdmin, onRefresh }: {
  mappings: ServiceMapping[];
  policies: EscalationPolicy[];
  isAdmin: boolean;
  onRefresh: () => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    service_pattern: '', escalation_policy_id: '', priority: 0,
    severity_filter: '' as string,
  });

  const handleCreate = async () => {
    setError(null);
    try {
      const sevFilter = form.severity_filter.trim()
        ? form.severity_filter.split(',').map(s => s.trim()).filter(Boolean)
        : undefined;
      await api.oncall.createMapping({
        service_pattern: form.service_pattern,
        escalation_policy_id: form.escalation_policy_id,
        priority: form.priority,
        severity_filter: sevFilter,
      });
      setShowCreate(false);
      setForm({ service_pattern: '', escalation_policy_id: '', priority: 0, severity_filter: '' });
      onRefresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create mapping');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this mapping?')) return;
    setError(null);
    try {
      await api.oncall.deleteMapping(id);
      onRefresh();
    } catch {
      setError('Failed to delete mapping');
    }
  };

  const getPolicyName = (id: string) => policies.find(p => p.id === id)?.name || 'Unknown';

  return (
    <div className="space-y-3">
      {error && (
        <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400/50 hover:text-red-400">&times;</button>
        </div>
      )}
      {isAdmin && (
        <div className="flex justify-end">
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
          >
            {showCreate ? 'Cancel' : 'New Mapping'}
          </button>
        </div>
      )}

      {showCreate && (
        <div className="bg-solace-surface border border-solace-border rounded-lg p-5 space-y-3">
          <h2 className="text-sm font-semibold text-solace-bright">Map Service to Escalation Policy</h2>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Service pattern (e.g. billing-*, prod-*)"
              value={form.service_pattern}
              onChange={(e) => setForm({ ...form, service_pattern: e.target.value })}
              className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
            />
            <select
              value={form.escalation_policy_id}
              onChange={(e) => setForm({ ...form, escalation_policy_id: e.target.value })}
              className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
            >
              <option value="">Select policy...</option>
              {policies.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs text-solace-muted whitespace-nowrap">Priority:</label>
              <input
                type="number"
                min={0} max={1000}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
                className="w-20 px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright focus:outline-none focus:border-emerald-500/50"
              />
              <span className="text-[10px] text-solace-muted">lower = first</span>
            </div>
            <input
              placeholder="Severity filter (e.g. critical,high)"
              value={form.severity_filter}
              onChange={(e) => setForm({ ...form, severity_filter: e.target.value })}
              className="px-3 py-2 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={!form.service_pattern || !form.escalation_policy_id}
            className="px-4 py-2 text-xs font-medium rounded-md bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
          >
            Create
          </button>
        </div>
      )}

      {mappings.length === 0 ? (
        <div className="text-center py-8 text-sm text-solace-muted">No service mappings configured</div>
      ) : (
        <div className="bg-solace-surface border border-solace-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-solace-border bg-solace-surface/50">
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted w-12">Pri</th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Service Pattern</th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Escalation Policy</th>
                <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-wider font-semibold text-solace-muted">Severity Filter</th>
                {isAdmin && <th className="w-16" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-solace-border/50">
              {mappings.map(m => (
                <tr key={m.id} className="hover:bg-solace-bg/50">
                  <td className="px-4 py-3 font-mono text-solace-muted text-xs">{m.priority}</td>
                  <td className="px-4 py-3 font-mono text-solace-bright">{m.service_pattern}</td>
                  <td className="px-4 py-3 text-solace-text">{getPolicyName(m.escalation_policy_id)}</td>
                  <td className="px-4 py-3 text-solace-muted text-xs">
                    {m.severity_filter ? m.severity_filter.join(', ') : 'All'}
                  </td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(m.id)}
                        className="text-xs text-solace-muted hover:text-red-400 transition-colors"
                      >
                        Delete
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
