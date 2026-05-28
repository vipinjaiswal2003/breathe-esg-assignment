import { useEffect, useState, useCallback } from 'react';
import { ScrollText, Loader2, Filter } from 'lucide-react';
import { auditApi } from '../api/client';
import type { AuditEntry } from '../types';
import { Pagination } from '../components/Pagination';

const ACTION_OPTIONS = [
  { value: '', label: 'All Actions' },
  { value: 'ingestion', label: 'Ingestion' },
  { value: 'normalization', label: 'Normalization' },
  { value: 'review', label: 'Review' },
  { value: 'edit', label: 'Edit' },
  { value: 'lock', label: 'Lock' },
  { value: 'unlock', label: 'Unlock' },
  { value: 'export', label: 'Export' },
];

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

const actionColors: Record<string, string> = {
  ingestion: 'bg-cyan-50 text-cyan-700',
  normalization: 'bg-indigo-50 text-indigo-700',
  review: 'bg-emerald-50 text-emerald-700',
  edit: 'bg-blue-50 text-blue-700',
  lock: 'bg-slate-100 text-slate-600',
  unlock: 'bg-slate-100 text-slate-600',
  export: 'bg-violet-50 text-violet-700',
  login: 'bg-amber-50 text-amber-700',
  config_change: 'bg-orange-50 text-orange-700',
};

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 25;

  // Filters
  const [actionFilter, setActionFilter] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      };
      if (actionFilter) params.action_type = actionFilter;
      if (userFilter) params.performed_by = userFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const res = await auditApi.list(params);
      setEntries(res.results);
      setCount(res.count);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [page, actionFilter, userFilter, dateFrom, dateTo]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  useEffect(() => {
    setPage(1);
  }, [actionFilter, userFilter, dateFrom, dateTo]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Audit Log</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Chronological record of all actions performed on the platform
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-600">Filters</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {ACTION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={userFilter}
            onChange={(e) => setUserFilter(e.target.value)}
            placeholder="Filter by user…"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading audit log…
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <ScrollText className="w-8 h-8 mb-2" />
            <p className="text-sm">No audit entries found</p>
          </div>
        ) : (
          <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4 text-left font-medium text-slate-500">Timestamp</th>
                  <th className="py-3 px-4 text-left font-medium text-slate-500">Action</th>
                  <th className="py-3 px-4 text-left font-medium text-slate-500">User</th>
                  <th className="py-3 px-4 text-left font-medium text-slate-500">Record</th>
                  <th className="py-3 px-4 text-left font-medium text-slate-500">Detail</th>
                  <th className="py-3 px-4 text-left font-medium text-slate-500">Changes</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="py-3 px-4 text-slate-600 whitespace-nowrap">
                      {formatTimestamp(entry.timestamp)}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                          actionColors[entry.action_type] || 'bg-slate-50 text-slate-600'
                        }`}
                      >
                        {entry.action_type_display || entry.action_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-700">{entry.performed_by_username || '—'}</td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-xs">
                      {entry.record_id ? entry.record_id.substring(0, 8) + '…' : '—'}
                    </td>
                    <td className="py-3 px-4 text-slate-600 max-w-48 truncate">
                      {entry.action_detail || '—'}
                    </td>
                    <td className="py-3 px-4">
                      {entry.before_data && entry.after_data ? (
                        <div className="text-xs space-y-0.5">
                          {Object.entries(entry.after_data).map(([key, val]) => {
                            const beforeVal = entry.before_data?.[key];
                            if (beforeVal !== val) {
                              return (
                                <div key={key} className="flex gap-1">
                                  <span className="text-slate-400">{key}:</span>
                                  <span className="text-red-500 line-through">{String(beforeVal)}</span>
                                  <span className="text-emerald-600">{String(val)}</span>
                                </div>
                              );
                            }
                            return null;
                          })}
                        </div>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="px-4 border-t border-slate-100">
          <Pagination count={count} page={page} pageSize={pageSize} onPageChange={setPage} />
        </div>
      </div>
    </div>
  );
}
