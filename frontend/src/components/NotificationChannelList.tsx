import { useState } from 'react';
import type { ChannelType, NotificationChannel } from '../lib/types';
import { useNotificationChannels, useNotificationLogs } from '../hooks/useNotificationChannels';
import { formatTimestamp } from '../lib/time';

const STATUS_DOT: Record<string, string> = {
  sent: 'bg-emerald-500',
  failed: 'bg-red-500',
  pending: 'bg-yellow-500',
};

const CHANNEL_BADGE: Record<string, { bg: string; text: string }> = {
  slack: { bg: 'bg-purple-500/10', text: 'text-purple-400' },
  email: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  teams: { bg: 'bg-indigo-500/10', text: 'text-indigo-400' },
  webhook: { bg: 'bg-amber-500/10', text: 'text-amber-400' },
  pagerduty: { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
};

const CHANNEL_TYPES: { value: ChannelType; label: string }[] = [
  { value: 'slack', label: 'Slack' },
  { value: 'teams', label: 'Microsoft Teams' },
  { value: 'email', label: 'Email' },
  { value: 'webhook', label: 'Webhook (Outbound)' },
  { value: 'pagerduty', label: 'PagerDuty' },
];

/** Returns which config fields each channel type needs */
function getConfigFields(type: ChannelType) {
  switch (type) {
    case 'slack':
      return { primary: 'webhook_url', label: 'Webhook URL', placeholder: 'https://hooks.slack.com/services/...' };
    case 'teams':
      return { primary: 'webhook_url', label: 'Webhook URL', placeholder: 'https://outlook.office.com/webhook/... or Power Automate URL' };
    case 'webhook':
      return { primary: 'webhook_url', label: 'Endpoint URL', placeholder: 'https://your-service.com/webhooks/solace' };
    case 'pagerduty':
      return { primary: 'routing_key', label: 'Integration / Routing Key', placeholder: '32-character PagerDuty Events API v2 key' };
    case 'email':
      return { primary: 'recipients', label: 'Recipients (comma-separated)', placeholder: 'team@example.com, oncall@example.com' };
    default:
      return { primary: 'webhook_url', label: 'URL', placeholder: '' };
  }
}

export function NotificationChannelList() {
  const { channels, loading, error, createChannel, updateChannel, deleteChannel, testChannel } = useNotificationChannels();
  const [showForm, setShowForm] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; msg: string; ok: boolean } | null>(null);

  // Create form state
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState<ChannelType>('slack');
  const [formPrimaryValue, setFormPrimaryValue] = useState('');
  const [formSecret, setFormSecret] = useState('');
  const [formSeverities, setFormSeverities] = useState('');
  const [formServices, setFormServices] = useState('');

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editPrimaryValue, setEditPrimaryValue] = useState('');
  const [editSecret, setEditSecret] = useState('');
  const [editSeverities, setEditSeverities] = useState('');
  const [editServices, setEditServices] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);

  const configFields = getConfigFields(formType);

  const handleCreate = async () => {
    if (!formName || !formPrimaryValue) return;

    const config: Record<string, unknown> = {};
    if (formType === 'email') {
      config.recipients = formPrimaryValue.split(',').map(s => s.trim()).filter(Boolean);
    } else if (formType === 'pagerduty') {
      config.routing_key = formPrimaryValue;
    } else {
      config.webhook_url = formPrimaryValue;
    }
    // Webhook-specific: optional secret and custom headers
    if (formType === 'webhook' && formSecret.trim()) {
      config.secret = formSecret.trim();
    }

    const filters: Record<string, unknown> = {};
    if (formSeverities.trim()) {
      filters.severity = formSeverities.split(',').map(s => s.trim()).filter(Boolean);
    }
    if (formServices.trim()) {
      filters.service = formServices.split(',').map(s => s.trim()).filter(Boolean);
    }

    await createChannel({
      name: formName,
      channel_type: formType,
      config,
      filters: Object.keys(filters).length > 0 ? filters : undefined,
    });

    setFormName('');
    setFormType('slack');
    setFormPrimaryValue('');
    setFormSecret('');
    setFormSeverities('');
    setFormServices('');
    setShowForm(false);
  };

  const startEdit = (ch: NotificationChannel) => {
    setEditingId(ch.id);
    setEditName(ch.name);
    if (ch.channel_type === 'email') {
      setEditPrimaryValue((ch.config.recipients as string[])?.join(', ') || '');
    } else if (ch.channel_type === 'pagerduty') {
      setEditPrimaryValue(ch.config.routing_key as string || '');
    } else {
      setEditPrimaryValue(ch.config.webhook_url as string || '');
    }
    setEditSecret(ch.config.secret as string || '');
    setEditSeverities(ch.filters.severity?.join(', ') || '');
    setEditServices(ch.filters.service?.join(', ') || '');
    setEditIsActive(ch.is_active);
  };

  const handleUpdate = async (ch: NotificationChannel) => {
    if (!editingId || !editName) return;

    const config: Record<string, unknown> = {};
    if (ch.channel_type === 'email') {
      config.recipients = editPrimaryValue.split(',').map(s => s.trim()).filter(Boolean);
    } else if (ch.channel_type === 'pagerduty') {
      config.routing_key = editPrimaryValue;
    } else {
      config.webhook_url = editPrimaryValue;
    }
    if (ch.channel_type === 'webhook' && editSecret.trim()) {
      config.secret = editSecret.trim();
    }

    const filters: Record<string, unknown> = {};
    if (editSeverities.trim()) {
      filters.severity = editSeverities.split(',').map(s => s.trim()).filter(Boolean);
    }
    if (editServices.trim()) {
      filters.service = editServices.split(',').map(s => s.trim()).filter(Boolean);
    }

    await updateChannel(editingId, {
      name: editName,
      config,
      filters,
      is_active: editIsActive,
    });
    setEditingId(null);
  };

  const handleTest = async (id: string) => {
    try {
      const result = await testChannel(id);
      setTestResult({ id, msg: result.message || 'Sent', ok: result.status === 'sent' || result.status === 'ok' });
    } catch (e) {
      setTestResult({ id, msg: e instanceof Error ? e.message : 'Test failed', ok: false });
    }
    setTimeout(() => setTestResult(null), 3000);
  };

  const inputClass = "w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50";
  const labelClass = "block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1";

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex-shrink-0 flex items-center justify-between px-5 py-2 border-b border-solace-border">
        <span className="text-xs font-medium text-solace-muted uppercase tracking-wider">
          Notification Channels
        </span>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
        >
          {showForm ? 'Cancel' : '+ New Channel'}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="flex-shrink-0 border-b border-solace-border bg-solace-surface/30 p-4">
          <div className="grid grid-cols-2 gap-3 max-w-2xl">
            <div>
              <label className={labelClass}>Name</label>
              <input type="text" value={formName} onChange={e => setFormName(e.target.value)} placeholder="Channel name" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Type</label>
              <select value={formType} onChange={e => { setFormType(e.target.value as ChannelType); setFormPrimaryValue(''); setFormSecret(''); }} className={inputClass}>
                {CHANNEL_TYPES.map(ct => (
                  <option key={ct.value} value={ct.value}>{ct.label}</option>
                ))}
              </select>
            </div>

            <div className="col-span-2">
              <label className={labelClass}>{configFields.label}</label>
              <input
                type="text"
                value={formPrimaryValue}
                onChange={e => setFormPrimaryValue(e.target.value)}
                placeholder={configFields.placeholder}
                className={inputClass}
              />
            </div>

            {formType === 'webhook' && (
              <div className="col-span-2">
                <label className={labelClass}>Secret (optional — sent as X-Solace-Secret header)</label>
                <input type="text" value={formSecret} onChange={e => setFormSecret(e.target.value)} placeholder="Optional shared secret for HMAC verification" className={inputClass} />
              </div>
            )}

            <div>
              <label className={labelClass}>Severity filter (comma-separated)</label>
              <input type="text" value={formSeverities} onChange={e => setFormSeverities(e.target.value)} placeholder="critical, high (empty = all)" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Service filter (comma-separated)</label>
              <input type="text" value={formServices} onChange={e => setFormServices(e.target.value)} placeholder="api, web (empty = all)" className={inputClass} />
            </div>

            <div className="col-span-2">
              <button
                onClick={handleCreate}
                disabled={!formName || !formPrimaryValue}
                className="px-4 py-1.5 text-xs font-medium rounded-md bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Create Channel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Channel list */}
      <div className="flex-1 overflow-y-auto">
        {error && (
          <div className="m-4 p-3 rounded-md bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}
        {loading && channels.length === 0 && (
          <div className="flex items-center justify-center h-40">
            <div className="text-sm text-solace-muted">Loading channels...</div>
          </div>
        )}
        {!loading && channels.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 text-solace-muted">
            <span className="text-sm">No notification channels configured</span>
            <span className="text-xs mt-1">Create a channel to receive incident alerts via Slack, Teams, Email, Webhook, or PagerDuty</span>
          </div>
        )}
        <div className="divide-y divide-solace-border/50">
          {channels.map(ch => (
            <div key={ch.id}>
              {editingId === ch.id ? (
                /* Inline edit form */
                <div className="bg-solace-surface/30 p-4 border-b border-solace-border">
                  <div className="grid grid-cols-2 gap-3 max-w-2xl">
                    <div>
                      <label className={labelClass}>Name</label>
                      <input type="text" value={editName} onChange={e => setEditName(e.target.value)} className={inputClass} />
                    </div>
                    <div>
                      <label className={labelClass}>Active</label>
                      <label className="flex items-center gap-2 mt-1">
                        <input
                          type="checkbox"
                          checked={editIsActive}
                          onChange={e => setEditIsActive(e.target.checked)}
                          className="rounded border-solace-border"
                        />
                        <span className="text-sm text-solace-text">{editIsActive ? 'Enabled' : 'Disabled'}</span>
                      </label>
                    </div>

                    <div className="col-span-2">
                      <label className={labelClass}>{getConfigFields(ch.channel_type as ChannelType).label}</label>
                      <input type="text" value={editPrimaryValue} onChange={e => setEditPrimaryValue(e.target.value)} className={inputClass} />
                    </div>

                    {ch.channel_type === 'webhook' && (
                      <div className="col-span-2">
                        <label className={labelClass}>Secret (optional)</label>
                        <input type="text" value={editSecret} onChange={e => setEditSecret(e.target.value)} placeholder="Optional shared secret" className={inputClass} />
                      </div>
                    )}

                    <div>
                      <label className={labelClass}>Severity filter</label>
                      <input type="text" value={editSeverities} onChange={e => setEditSeverities(e.target.value)} placeholder="critical, high (empty = all)" className={inputClass} />
                    </div>
                    <div>
                      <label className={labelClass}>Service filter</label>
                      <input type="text" value={editServices} onChange={e => setEditServices(e.target.value)} placeholder="api, web (empty = all)" className={inputClass} />
                    </div>

                    <div className="col-span-2 flex items-center gap-2">
                      <button
                        onClick={() => handleUpdate(ch)}
                        disabled={!editName}
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
                <ChannelRow
                  channel={ch}
                  isExpanded={selectedChannel === ch.id}
                  onToggle={() => setSelectedChannel(selectedChannel === ch.id ? null : ch.id)}
                  onEdit={() => startEdit(ch)}
                  onDelete={() => deleteChannel(ch.id)}
                  onTest={() => handleTest(ch.id)}
                  testResult={testResult?.id === ch.id ? testResult : null}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChannelRow({
  channel,
  isExpanded,
  onToggle,
  onEdit,
  onDelete,
  onTest,
  testResult,
}: {
  channel: NotificationChannel;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
  testResult: { msg: string; ok: boolean } | null;
}) {
  const badge = CHANNEL_BADGE[channel.channel_type] || { bg: 'bg-gray-500/10', text: 'text-gray-400' };

  return (
    <div>
      <div
        className="flex items-center gap-3 px-5 py-3 hover:bg-solace-surface/30 transition-colors cursor-pointer"
        onClick={onToggle}
      >
        {/* Active dot */}
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
          channel.is_active ? 'bg-emerald-500' : 'bg-solace-muted/50'
        }`} />

        {/* Type badge */}
        <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded ${badge.bg} ${badge.text}`}>
          {channel.channel_type.toUpperCase()}
        </span>

        {/* Name + filters */}
        <div className="flex-1 min-w-0">
          <div className="text-sm text-solace-bright font-medium truncate">{channel.name}</div>
          <div className="flex items-center gap-2 mt-0.5">
            {channel.filters.severity && channel.filters.severity.length > 0 && (
              <span className="text-[10px] font-mono text-solace-muted">
                severity: {channel.filters.severity.join(', ')}
              </span>
            )}
            {channel.filters.service && channel.filters.service.length > 0 && (
              <span className="text-[10px] font-mono text-solace-muted">
                service: {channel.filters.service.join(', ')}
              </span>
            )}
            {(!channel.filters.severity || channel.filters.severity.length === 0) &&
             (!channel.filters.service || channel.filters.service.length === 0) && (
              <span className="text-[10px] font-mono text-solace-muted">all incidents</span>
            )}
          </div>
        </div>

        {/* Test result badge */}
        {testResult && (
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
            testResult.ok ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
          }`}>
            {testResult.msg}
          </span>
        )}

        {/* Actions */}
        <button
          onClick={e => { e.stopPropagation(); onTest(); }}
          className="flex-shrink-0 px-2 py-1 text-[10px] font-mono text-solace-muted hover:text-solace-text hover:bg-solace-surface/50 rounded transition-colors"
        >
          Test
        </button>
        <button
          onClick={e => { e.stopPropagation(); onEdit(); }}
          className="flex-shrink-0 px-2 py-1 text-[10px] font-mono text-solace-muted hover:text-solace-text hover:bg-solace-surface/50 rounded transition-colors"
        >
          Edit
        </button>
        <button
          onClick={e => { e.stopPropagation(); onDelete(); }}
          className="flex-shrink-0 px-2 py-1 text-[10px] font-mono text-red-400/60 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
        >
          Delete
        </button>
      </div>

      {/* Expanded logs */}
      {isExpanded && <ChannelLogs channelId={channel.id} />}
    </div>
  );
}

function ChannelLogs({ channelId }: { channelId: string }) {
  const { logs, loading } = useNotificationLogs(channelId);

  return (
    <div className="bg-solace-surface/20 border-t border-solace-border/50 px-5 py-3">
      <div className="text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-2">Recent Logs</div>
      {loading && <div className="text-xs text-solace-muted">Loading...</div>}
      {!loading && logs.length === 0 && (
        <div className="text-xs text-solace-muted">No notifications sent yet</div>
      )}
      {logs.length > 0 && (
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {logs.map(log => (
            <div key={log.id} className="flex items-center gap-2 text-[11px] font-mono">
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATUS_DOT[log.status] || 'bg-gray-500'}`} />
              <span className="text-solace-muted">{formatTimestamp(log.created_at)}</span>
              <span className="text-solace-text">{log.event_type}</span>
              <span className={`${log.status === 'failed' ? 'text-red-400' : 'text-solace-muted'}`}>
                {log.status}
              </span>
              {log.error_message && (
                <span className="text-red-400 truncate" title={log.error_message}>{log.error_message}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
