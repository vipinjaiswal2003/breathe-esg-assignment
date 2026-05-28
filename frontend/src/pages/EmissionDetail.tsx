import { useEffect, useState, type FormEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Flag,
  Lock,
  Unlock,
  AlertTriangle,
  Send,
  Loader2,

  Edit3,
  X,
} from 'lucide-react';
import { emissionApi, reviewApi } from '../api/client';
import type { Emission, ReviewComment, ReviewActionRecord } from '../types';
import { StatusBadge } from '../components/StatusBadge';

export function EmissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [emission, setEmission] = useState<Emission | null>(null);
  const [comments, setComments] = useState<ReviewComment[]>([]);
  const [auditTrail, setAuditTrail] = useState<ReviewActionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [commentLoading, setCommentLoading] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState<Partial<Emission>>({});
  const [editLoading, setEditLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      emissionApi.get(id),
      // Try loading comments and audit as part of emission detail or separately
    ])
      .then(([em]) => {
        setEmission(em);
        setEditForm({
          activity_description: em.activity_description,
          co2e_kg: em.co2e_kg,
          activity_quantity: em.activity_quantity,
          activity_unit: em.activity_unit,
          category: em.category,
          review_notes: em.review_notes || '',
        });
        setComments([]);
        setAuditTrail([]);
      })
      .catch(() => setMessage({ type: 'error', text: 'Failed to load emission record' }))
      .finally(() => setLoading(false));
  }, [id]);

  const handleAction = async (action: 'approve' | 'reject' | 'flag' | 'lock' | 'unlock') => {
    if (!id) return;
    setActionLoading(true);
    setMessage(null);
    try {
      await reviewApi.action({ action, emission_ids: [id] });
      // Refresh
      const em = await emissionApi.get(id);
      setEmission(em);
      setMessage({ type: 'success', text: `Record ${action}d successfully` });
    } catch {
      setMessage({ type: 'error', text: `Failed to ${action} record` });
    } finally {
      setActionLoading(false);
    }
  };

  const handleComment = async (e: FormEvent) => {
    e.preventDefault();
    if (!id || !commentText.trim()) return;
    setCommentLoading(true);
    try {
      const newComment = await reviewApi.comment(id, commentText);
      setComments((prev) => [...prev, newComment]);
      setCommentText('');
    } catch {
      setMessage({ type: 'error', text: 'Failed to add comment' });
    } finally {
      setCommentLoading(false);
    }
  };

  const handleEditSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setEditLoading(true);
    try {
      const updated = await reviewApi.edit(id, editForm);
      setEmission(updated);
      setEditMode(false);
      setMessage({ type: 'success', text: 'Record updated successfully' });
    } catch {
      setMessage({ type: 'error', text: 'Failed to update record' });
    } finally {
      setEditLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading emission record…
      </div>
    );
  }

  if (!emission) {
    return (
      <div className="text-center py-16">
        <p className="text-slate-500">Emission record not found</p>
        <Link to="/review" className="text-emerald-600 hover:underline text-sm mt-2 inline-block">
          ← Back to Review Queue
        </Link>
      </div>
    );
  }

  const isLocked = emission.status === 'locked';
  const canEdit = !isLocked && emission.status !== 'approved';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/review')}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-slate-800">Emission Record</h1>
            <StatusBadge status={emission.status} size="md" />
            {emission.anomaly_flag && emission.anomaly_flag !== 'none' && (
              <span className="inline-flex items-center gap-1 text-amber-600 text-sm">
                <AlertTriangle className="w-4 h-4" /> Anomaly
              </span>
            )}
          </div>
          <p className="text-sm text-slate-400 mt-0.5 font-mono">{emission.id}</p>
        </div>
        <div className="flex items-center gap-2">
          {actionLoading && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
          {emission.status === 'pending' && (
            <>
              <button
                onClick={() => handleAction('approve')}
                disabled={actionLoading}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                <CheckCircle className="w-4 h-4" /> Approve
              </button>
              <button
                onClick={() => handleAction('reject')}
                disabled={actionLoading}
                className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                <XCircle className="w-4 h-4" /> Reject
              </button>
            </>
          )}
          {(emission.status === 'pending' || emission.status === 'approved') && (
            <button
              onClick={() => handleAction('flag')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3.5 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50"
            >
              <Flag className="w-4 h-4" /> Flag
            </button>
          )}
          {emission.status !== 'locked' ? (
            <button
              onClick={() => handleAction('lock')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              <Lock className="w-4 h-4" /> Lock
            </button>
          ) : (
            <button
              onClick={() => handleAction('unlock')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              <Unlock className="w-4 h-4" /> Unlock
            </button>
          )}
        </div>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            message.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Emission Data */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-700">Emission Data</h2>
              {canEdit && !editMode && (
                <button
                  onClick={() => setEditMode(true)}
                  className="flex items-center gap-1.5 text-sm text-emerald-600 hover:text-emerald-700 font-medium"
                >
                  <Edit3 className="w-3.5 h-3.5" /> Edit
                </button>
              )}
              {editMode && (
                <button
                  onClick={() => setEditMode(false)}
                  className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
                >
                  <X className="w-3.5 h-3.5" /> Cancel
                </button>
              )}
            </div>

            {editMode ? (
              <form onSubmit={handleEditSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Description</label>
                    <input
                      value={editForm.activity_description || ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, activity_description: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Category</label>
                    <input
                      value={editForm.category || ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, category: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">CO₂e (kg)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.co2e_kg || ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, co2e_kg: parseFloat(e.target.value) }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Activity Quantity</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.activity_quantity || ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, activity_quantity: parseFloat(e.target.value) }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Activity Unit</label>
                    <input
                      value={editForm.activity_unit || ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, activity_unit: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-500 mb-1">Notes</label>
                    <input
                      value={editForm.review_notes || ''}
                      onChange={(e) => setEditForm((p) => ({ ...p, review_notes: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditMode(false)}
                    className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={editLoading}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {editLoading ? 'Saving…' : 'Save Changes'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <DetailField label="Description" value={emission.activity_description} />
                <DetailField label="Scope" value={`Scope ${emission.scope.replace('scope', '')}`} />
                <DetailField label="Category" value={emission.category} />
                <DetailField label="Source Date" value={new Date(emission.activity_date).toLocaleDateString()} />
                <DetailField
                  label="CO₂e"
                  value={`${emission.co2e_kg.toLocaleString(undefined, { maximumFractionDigits: 2 })} kg (${(emission.co2e_kg / 1000).toFixed(4)} t)`}
                />
                <DetailField
                  label="Activity"
                  value={`${emission.activity_quantity} ${emission.activity_unit}`}
                />
                <DetailField
                  label="Emission Factor"
                  value={emission.emission_factor_name || '—'}
                />
                <DetailField label="Data Source" value={emission.source_name || `Source #${emission.data_source}`} />
                <DetailField label="Source Type" value={emission.raw_record_type} />
                <DetailField label="Notes" value={emission.review_notes || '—'} />
                {emission.anomaly_flag && emission.anomaly_flag !== 'none' && (
                  <DetailField
                    label="Anomaly Reason"
                    value={emission.anomaly_notes || 'Unspecified'}
                    className="text-amber-600"
                  />
                )}
              </div>
            )}
          </div>

          {/* Raw Source Data — not available in current API */}

          {/* Comments */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Comments</h2>
            {comments.length > 0 ? (
              <div className="space-y-3 mb-4">
                {comments.map((c) => (
                  <div key={c.id} className="bg-slate-50 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-slate-700">{c.author_username || 'Unknown'}</span>
                      <span className="text-xs text-slate-400">
                        {new Date(c.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-sm text-slate-600">{c.comment}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400 mb-4">No comments yet</p>
            )}
            <form onSubmit={handleComment} className="flex gap-2">
              <input
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                placeholder="Add a comment…"
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button
                type="submit"
                disabled={!commentText.trim() || commentLoading}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {commentLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                Send
              </button>
            </form>
          </div>
        </div>

        {/* Sidebar: Audit trail */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Audit Trail</h2>
            {auditTrail.length > 0 ? (
              <div className="space-y-3 max-h-96 overflow-y-auto custom-scrollbar">
                {auditTrail.map((entry) => (
                  <div key={entry.id} className="border-l-2 border-slate-200 pl-3 py-1">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-medium text-slate-700 capitalize">
                        {entry.action}
                      </span>
                      <span className="text-xs text-slate-400">
                        by {entry.performed_by_username || 'Unknown'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">
                      {new Date(entry.performed_at).toLocaleString()}
                    </p>
                    {entry.notes && (
                      <p className="text-xs text-slate-500 mt-1">{entry.notes}</p>
                    )}
                    {entry.field_changes && Object.keys(entry.field_changes).length > 0 && (
                      <div className="mt-1.5 text-xs">
                        {Object.entries(entry.field_changes).map(([key, val]) => (
                          <div key={key} className="flex gap-1">
                            <span className="text-slate-400">{key}:</span>
                            <span className="text-emerald-600">{String(val)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-400">No audit entries yet</p>
            )}
          </div>

          {/* Quick info */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Record Info</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Created</span>
                <span className="text-slate-600">
                  {new Date(emission.created_at).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Updated</span>
                <span className="text-slate-600">
                  {new Date(emission.updated_at).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Raw Record</span>
                <span className="text-slate-600">#{emission.raw_record_id}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailField({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-400 mb-0.5">{label}</p>
      <p className={`text-sm text-slate-700 ${className || ''}`}>{value}</p>
    </div>
  );
}
