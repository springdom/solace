import { useState } from 'react';
import type { NotificationChannel } from '../lib/types';
import { useNotificationChannels, useNotificationLogs } from '../hooks/useNotificationChannels';
import { formatTimestamp } from '../lib/time';

const STATUS_DOT: Record<string, string> = {
  sent: 'bg-emerald-500',
  failed: 'bg-red-500',
  pending: 'bg-yellow-500',
};

export function NotificationChannelList() {
  const { channels, loading, error, createChannel, deleteChannel, testChannel } = useNotificationChannels();
  const [showForm, setShowForm] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; msg: string; ok: boolean } | null>(null);

  // Form state
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState<'slack' | 'email'>('slack');
  const [formWebhookUrl, setFormWebhookUrl] = useState('');
  const [formRecipients, setFormRecipients] = useState('');
  const [formSeverities, setFormSeverities] = useState('');
  const [formServices, setFormServices] = useState('');

  const handleCreate = async () => {
    if (!formName) return;

    const config: Record<string, unknown> = {};
    if (formType === 'slack') {
      if (!formWebhookUrl) return;
      config.webhook_url = formWebhookUrl;
    } else {
      if (!formRecipients) return;
      config.recipients = formRecipients.split(',').map(s => s.trim()).filter(Boolean);
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
    setFormWebhookUrl('');
    setFormRecipients('');
    setFormSeverities('');
    setFormServices('');
    setShowForm(false);
  };

  const handleTest = async (id: string) => {
    try {
      const result = await testChannel(id);
      setTestResult({ id, msg: result.message, ok: result.status === 'ok' });
    } catch (e) {
      setTestResult({ id, msg: e instanceof Error ? e.message : 'Test failed', ok: false });
    }
    setTimeout(() => setTestResult(null), 3000);
  };

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
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1">Name</label>
              <input
                type="text"
                value={formName}
                onChange={e => setFormName(e.target.value)}
                placeholder="Channel name"
                className="w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1">Type</label>
              <select
                value={formType}
                onChange={e => setFormType(e.target.value as 'slack' | 'email')}
                className="w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text focus:outline-none focus:border-emerald-500/50"
              >
                <option value="slack">Slack</option>
                <option value="email">Email</option>
              </select>
            </div>

            {formType === 'slack' ? (
              <div className="col-span-2">
                <label className="block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1">Webhook URL</label>
                <input
                  type="text"
                  value={formWebhookUrl}
                  onChange={e => setFormWebhookUrl(e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  className="w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
                />
              </div>
            ) : (
              <div className="col-span-2">
                <label className="block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1">Recipients (comma-separated emails)</label>
                <input
                  type="text"
                  value={formRecipients}
                  onChange={e => setFormRecipients(e.target.value)}
                  placeholder="team@example.com, oncall@example.com"
                  className="w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
                />
              </div>
            )}

            <div>
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1">Severity filter (comma-separated)</label>
              <input
                type="text"
                value={formSeverities}
                onChange={e => setFormSeverities(e.target.value)}
                placeholder="critical, high (empty = all)"
                className="w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wider font-semibold text-solace-muted mb-1">Service filter (comma-separated)</label>
              <input
                type="text"
                value={formServices}
                onChange={e => setFormServices(e.target.value)}
                placeholder="api, web (empty = all)"
                className="w-full px-3 py-1.5 text-sm bg-solace-bg border border-solace-border rounded-md text-solace-text placeholder:text-solace-muted/50 focus:outline-none focus:border-emerald-500/50"
              />
            </div>

            <div className="col-span-2">
              <button
                onClick={handleCreate}
                disabled={!formName || (formType === 'slack' ? !formWebhookUrl : !formRecipients)}
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
            <span className="text-xs mt-1">Create a channel to start receiving alerts via Slack or email</span>
          </div>
        )}
        <div className="divide-y divide-solace-border/50">
          {channels.map(ch => (
            <ChannelRow
              key={ch.id}
              channel={ch}
              isExpanded={selectedChannel === ch.id}
              onToggle={() => setSelectedChannel(selectedChannel === ch.id ? null : ch.id)}
              onDelete={() => deleteChannel(ch.id)}
              onTest={() => handleTest(ch.id)}
              testResult={testResult?.id === ch.id ? testResult : null}
            />
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
  onDelete,
  onTest,
  testResult,
}: {
  channel: NotificationChannel;
  isExpanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onTest: () => void;
  testResult: { msg: string; ok: boolean } | null;
}) {
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
        <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded ${
          channel.channel_type === 'slack'
            ? 'bg-purple-500/10 text-purple-400'
            : 'bg-blue-500/10 text-blue-400'
        }`}>
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
