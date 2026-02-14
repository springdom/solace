import { useState, useEffect, useCallback } from 'react';
import type { Alert, AlertNote, AlertOccurrence } from '../lib/types';
import { api } from '../lib/api';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';
import { ExpandableText } from './ExpandableText';
import { formatTimestamp, duration, timeAgo } from '../lib/time';

interface AlertDetailProps {
  alert: Alert;
  onAcknowledge?: (id: string) => void;
  onResolve?: (id: string) => void;
  onClose: () => void;
  onTagAdd?: (alertId: string, tag: string) => Promise<Alert | undefined>;
  onTagRemove?: (alertId: string, tag: string) => Promise<Alert | undefined>;
  onTagClick?: (tag: string) => void;
  onBackToIncident?: () => void;
}

export function AlertDetail({ alert, onAcknowledge, onResolve, onClose, onTagAdd, onTagRemove, onTagClick, onBackToIncident }: AlertDetailProps) {
  const isFiring = alert.status === 'firing';
  const isActive = isFiring || alert.status === 'acknowledged';

  // Notes state
  const [notes, setNotes] = useState<AlertNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editNoteText, setEditNoteText] = useState('');

  // Tag input state
  const [tagInput, setTagInput] = useState('');

  // Raw payload toggle
  const [showRawPayload, setShowRawPayload] = useState(false);

  // Ticket URL state
  const [ticketInput, setTicketInput] = useState('');
  const [editingTicket, setEditingTicket] = useState(false);

  // Occurrence history
  const [occurrences, setOccurrences] = useState<AlertOccurrence[]>([]);
  const [showOccurrences, setShowOccurrences] = useState(false);

  // Fetch notes when alert changes
  useEffect(() => {
    setNotesLoading(true);
    api.alerts.listNotes(alert.id)
      .then(data => setNotes(data.notes))
      .catch(() => {})
      .finally(() => setNotesLoading(false));
  }, [alert.id]);

  // Fetch occurrences when expanded
  useEffect(() => {
    if (showOccurrences) {
      api.alerts.getHistory(alert.id)
        .then(data => setOccurrences(data.occurrences))
        .catch(() => setOccurrences([]));
    }
  }, [alert.id, showOccurrences]);

  const handleAddNote = useCallback(async () => {
    if (!noteText.trim()) return;
    try {
      const note = await api.alerts.addNote(alert.id, noteText.trim());
      setNotes(prev => [note, ...prev]);
      setNoteText('');
    } catch {}
  }, [alert.id, noteText]);

  const handleDeleteNote = useCallback(async (noteId: string) => {
    await api.alerts.deleteNote(noteId);
    setNotes(prev => prev.filter(n => n.id !== noteId));
  }, []);

  const handleEditNote = useCallback(async (noteId: string) => {
    if (!editNoteText.trim()) return;
    try {
      const updated = await api.alerts.updateNote(noteId, editNoteText.trim());
      setNotes(prev => prev.map(n => n.id === noteId ? updated : n));
      setEditingNoteId(null);
      setEditNoteText('');
    } catch {}
  }, [editNoteText]);

  const startEditNote = (note: AlertNote) => {
    setEditingNoteId(note.id);
    setEditNoteText(note.text);
  };

  const handleAddTag = useCallback(async () => {
    const tag = tagInput.trim();
    if (!tag || !onTagAdd) return;
    const updated = await onTagAdd(alert.id, tag);
    if (updated) setTagInput('');
  }, [alert.id, tagInput, onTagAdd]);

  const handleRemoveTag = useCallback(async (tag: string) => {
    if (!onTagRemove) return;
    await onTagRemove(alert.id, tag);
  }, [alert.id, onTagRemove]);

  const handleTagKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); handleAddTag(); }
  };

  const handleSetTicket = useCallback(async () => {
    if (!ticketInput.trim()) return;
    // Ensure URL has a protocol
    let url = ticketInput.trim();
    if (!/^https?:\/\//i.test(url)) {
      url = 'https://' + url;
    }
    try {
      const updated = await api.alerts.setTicketUrl(alert.id, url);
      // Update local state so link appears immediately
      alert.ticket_url = updated.ticket_url ?? url;
      setEditingTicket(false);
      setTicketInput('');
    } catch {}
  }, [alert, ticketInput]);

  // Build attributes table rows
  const attributes = [
    ['Source', alert.source],
    ['Service', alert.service],
    ['Host', alert.host],
    ['Environment', alert.environment],
    ['Fingerprint', alert.fingerprint],
    ['Duplicates', String(alert.duplicate_count)],
    ['ID', alert.id.slice(0, 8) + '...'],
  ].filter(([, v]) => v) as [string, string][];

  return (
    <div className="h-full flex flex-col bg-solace-surface border-l border-solace-border animate-slide-in">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-solace-border">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <SeverityBadge severity={alert.severity} pulse={isFiring} />
            <StatusBadge status={alert.status} />
          </div>
          <h2 className="font-mono text-base font-semibold text-solace-bright break-words">
            {alert.name}
          </h2>
          {alert.description && (
            <ExpandableText text={alert.description} maxLines={2} className="mt-1" />
          )}
        </div>
        <button
          onClick={onClose}
          className="flex-shrink-0 ml-3 p-1 rounded text-solace-muted hover:text-solace-bright hover:bg-solace-border/50 transition-colors"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>

      {/* Back to incident */}
      {onBackToIncident && (
        <button
          onClick={onBackToIncident}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-blue-400 hover:bg-blue-500/10 border-b border-solace-border transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M10 4l-4 4 4 4" />
          </svg>
          Back to Incident
        </button>
      )}

      {/* Actions */}
      {isActive && (onAcknowledge || onResolve) && (
        <div className="flex items-center gap-2 px-4 py-3 border-b border-solace-border">
          {isFiring && onAcknowledge && (
            <button
              onClick={() => onAcknowledge(alert.id)}
              className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
            >
              Acknowledge
            </button>
          )}
          {onResolve && (
            <button
              onClick={() => onResolve(alert.id)}
              className="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
            >
              Resolve
            </button>
          )}
        </div>
      )}

      {/* Details */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Tags */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Tags</h3>
          {alert.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {alert.tags.map(tag => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 text-xs font-mono border border-teal-500/20"
                >
                  <button
                    onClick={() => onTagClick?.(tag)}
                    className="hover:underline"
                  >
                    {tag}
                  </button>
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="ml-0.5 text-teal-400/50 hover:text-teal-400 transition-colors"
                  >
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M2.5 2.5l5 5M7.5 2.5l-5 5" />
                    </svg>
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-1.5">
            <input
              value={tagInput}
              onChange={e => setTagInput(e.target.value)}
              onKeyDown={handleTagKeyDown}
              placeholder="Add tag..."
              className="flex-1 px-2 py-1 text-xs font-mono bg-solace-bg border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-teal-500/50"
            />
            <button
              onClick={handleAddTag}
              disabled={!tagInput.trim()}
              className="px-2 py-1 text-xs font-medium rounded bg-teal-500/10 text-teal-400 border border-teal-500/20 hover:bg-teal-500/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              +
            </button>
          </div>
        </section>

        {/* Timing */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Timing</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Started" value={formatTimestamp(alert.starts_at)} />
            <Field label="Duration" value={duration(alert.starts_at, alert.ends_at)} mono />
            {alert.acknowledged_at && (
              <Field label="Acknowledged" value={formatTimestamp(alert.acknowledged_at)} />
            )}
            {alert.resolved_at && (
              <Field label="Resolved" value={formatTimestamp(alert.resolved_at)} />
            )}
          </div>
        </section>

        {/* Attributes */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Attributes</h3>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-solace-border/30">
              {attributes.map(([label, value]) => (
                <tr key={label}>
                  <td className="py-1.5 pr-3 text-solace-muted text-xs w-28">{label}</td>
                  <td className="py-1.5 font-mono text-solace-bright text-xs break-all">{value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* Links (generator, runbook, ticket) */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Links</h3>
          <div className="space-y-2">
            {alert.generator_url && (
              <div>
                <a
                  href={ensureProtocol(alert.generator_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline"
                >
                  <ExternalLinkIcon />
                  View in source
                </a>
              </div>
            )}
            {alert.runbook_url && (
              <div>
                <a
                  href={ensureProtocol(alert.runbook_url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline"
                >
                  <ExternalLinkIcon />
                  Runbook
                </a>
              </div>
            )}

            {/* Ticket URL */}
            <div>
              {alert.ticket_url && !editingTicket ? (
                <div className="flex items-center gap-2">
                  <a
                    href={ensureProtocol(alert.ticket_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:underline truncate"
                  >
                    <ExternalLinkIcon />
                    External Ticket
                  </a>
                  <button
                    onClick={() => { setTicketInput(alert.ticket_url || ''); setEditingTicket(true); }}
                    className="text-[10px] text-solace-muted hover:text-solace-text transition-colors"
                  >
                    Edit
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <input
                    value={ticketInput}
                    onChange={e => setTicketInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleSetTicket(); }}
                    placeholder="Paste ticket URL (Jira, GitHub...)"
                    className="flex-1 px-2 py-1 text-xs font-mono bg-solace-bg border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-blue-500/50"
                  />
                  <button
                    onClick={handleSetTicket}
                    disabled={!ticketInput.trim()}
                    className="px-2 py-1 text-xs font-medium rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    Link
                  </button>
                  {editingTicket && (
                    <button
                      onClick={() => setEditingTicket(false)}
                      className="px-2 py-1 text-xs text-solace-muted hover:text-solace-text transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              )}
            </div>

            {!alert.generator_url && !alert.runbook_url && !alert.ticket_url && !editingTicket && (
              <div className="text-xs text-solace-muted italic">No links</div>
            )}
          </div>
        </section>

        {/* Labels */}
        {Object.keys(alert.labels).length > 0 && (
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Labels</h3>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(alert.labels).map(([key, value]) => (
                <span
                  key={key}
                  className="inline-flex items-center px-2 py-0.5 rounded bg-solace-border/50 text-xs font-mono"
                >
                  <span className="text-solace-muted">{key}=</span>
                  <span className="text-solace-bright">{value}</span>
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Annotations */}
        {Object.keys(alert.annotations).length > 0 && (
          <section>
            <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">Annotations</h3>
            <div className="space-y-2">
              {Object.entries(alert.annotations).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-[10px] uppercase tracking-wider text-solace-muted">{key}</dt>
                  <dd className="text-sm text-solace-text mt-0.5">
                    {key.includes('url') ? (
                      <a href={value} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                        {value}
                      </a>
                    ) : value}
                  </dd>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Occurrence History */}
        <section>
          <button
            onClick={() => setShowOccurrences(!showOccurrences)}
            className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2 flex items-center gap-1 hover:text-solace-text transition-colors"
          >
            <svg
              width="8" height="8" viewBox="0 0 8 8" fill="currentColor"
              className={`transition-transform ${showOccurrences ? 'rotate-90' : ''}`}
            >
              <path d="M2 1l4 3-4 3V1z" />
            </svg>
            Occurrence History ({alert.duplicate_count})
          </button>
          {showOccurrences && (
            <div className="relative pl-5 space-y-0 max-h-48 overflow-y-auto">
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-solace-border" />
              {occurrences.length === 0 ? (
                <div className="text-xs text-solace-muted py-1 pl-2">No occurrence records</div>
              ) : (
                occurrences.map((occ) => (
                  <div key={occ.id} className="relative flex items-center gap-3 py-1.5">
                    <div className="absolute left-[-13px] top-[9px] w-2 h-2 rounded-full bg-solace-muted border-2 border-solace-surface" />
                    <span className="text-[11px] font-mono text-solace-muted">
                      {formatTimestamp(occ.received_at)}
                    </span>
                    <span className="text-[10px] text-solace-muted">
                      {timeAgo(occ.received_at)}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </section>

        {/* Raw Payload */}
        {alert.raw_payload && Object.keys(alert.raw_payload).length > 0 && (
          <section>
            <button
              onClick={() => setShowRawPayload(!showRawPayload)}
              className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2 flex items-center gap-1 hover:text-solace-text transition-colors"
            >
              <svg
                width="8" height="8" viewBox="0 0 8 8" fill="currentColor"
                className={`transition-transform ${showRawPayload ? 'rotate-90' : ''}`}
              >
                <path d="M2 1l4 3-4 3V1z" />
              </svg>
              Raw Payload
            </button>
            {showRawPayload && (
              <pre className="text-[11px] font-mono text-solace-text bg-solace-bg p-3 rounded border border-solace-border overflow-x-auto max-h-64 overflow-y-auto">
                {JSON.stringify(alert.raw_payload, null, 2)}
              </pre>
            )}
          </section>
        )}

        {/* Notes */}
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-solace-muted font-semibold mb-2">
            Notes{notes.length > 0 && <span className="text-solace-muted/60 ml-1">({notes.length})</span>}
          </h3>

          {/* Add note form */}
          <div className="mb-3">
            <textarea
              value={noteText}
              onChange={e => setNoteText(e.target.value)}
              placeholder="Add a note..."
              rows={2}
              className="w-full px-3 py-2 text-sm font-mono bg-solace-bg border border-solace-border rounded text-solace-bright placeholder:text-solace-muted/50 focus:outline-none focus:border-blue-500/50 resize-none"
            />
            <div className="flex justify-end mt-1">
              <button
                onClick={handleAddNote}
                disabled={!noteText.trim()}
                className="px-3 py-1.5 text-xs font-medium rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Add Note
              </button>
            </div>
          </div>

          {/* Notes list */}
          {notesLoading ? (
            <div className="text-xs text-solace-muted">Loading notes...</div>
          ) : notes.length === 0 ? (
            <div className="text-xs text-solace-muted italic">No notes yet</div>
          ) : (
            <div className="space-y-2">
              {notes.map(note => (
                <div key={note.id} className="px-3 py-2 rounded bg-solace-bg/60 border border-solace-border/50">
                  {editingNoteId === note.id ? (
                    <div>
                      <textarea
                        value={editNoteText}
                        onChange={e => setEditNoteText(e.target.value)}
                        rows={2}
                        className="w-full px-2 py-1 text-sm font-mono bg-solace-bg border border-solace-border rounded text-solace-bright focus:outline-none focus:border-blue-500/50 resize-none"
                      />
                      <div className="flex items-center gap-2 mt-1.5">
                        <button
                          onClick={() => handleEditNote(note.id)}
                          disabled={!editNoteText.trim()}
                          className="px-2 py-1 text-[10px] font-medium rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 disabled:opacity-30 transition-colors"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => { setEditingNoteId(null); setEditNoteText(''); }}
                          className="px-2 py-1 text-[10px] text-solace-muted hover:text-solace-text transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm text-solace-text font-mono whitespace-pre-wrap break-words flex-1">
                          {note.text}
                        </p>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <button
                            onClick={() => startEditNote(note)}
                            className="text-solace-muted hover:text-blue-400 transition-colors"
                            title="Edit note"
                          >
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M7 1l2 2-6 6H1V7l6-6z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleDeleteNote(note.id)}
                            className="text-solace-muted hover:text-red-400 transition-colors"
                            title="Delete note"
                          >
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M2.5 2.5l5 5M7.5 2.5l-5 5" />
                            </svg>
                          </button>
                        </div>
                      </div>
                      <div className="mt-1.5 text-[10px] text-solace-muted font-mono">
                        {timeAgo(note.created_at)}
                        {note.author && ` \u00b7 ${note.author}`}
                        {note.updated_at !== note.created_at && ' (edited)'}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function ExternalLinkIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 2H2v12h12v-4M10 2h4v4M7 9l7-7" />
    </svg>
  );
}

/** Ensure a URL has a protocol so <a href> doesn't treat it as relative */
function ensureProtocol(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  return 'https://' + url;
}

function Field({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wider text-solace-muted font-medium mb-0.5">{label}</dt>
      <dd className={`text-sm text-solace-bright ${mono ? 'font-mono' : ''}`}>{value}</dd>
    </div>
  );
}
