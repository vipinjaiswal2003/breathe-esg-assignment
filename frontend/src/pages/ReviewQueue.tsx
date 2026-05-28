import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Filter,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Lock,
  Flag,
  ChevronDown,
  ChevronUp,
  Loader2,
} from 'lucide-react';
import { emissionApi, reviewApi } from '../api/client';
import type { Emission } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { Pagination } from '../components/Pagination';

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'flagged', label: 'Flagged' },
  { value: 'locked', label: 'Locked' },
];

const SCOPE_OPTIONS = [
  { value: '', label: 'All Scopes' },
  { value: '1', label: 'Scope 1' },
  { value: '2', label: 'Scope 2' },
  { value: '3', label: 'Scope 3' },
];

const SOURCE_OPTIONS = [
  { value: '', label: 'All Sources' },
  { value: 'sap', label: 'SAP' },
  { value: 'utility', label: 'Utility' },
  { value: 'travel', label: 'Travel' },
];

type SortField = 'activity_date' | 'co2e_kg' | 'scope' | 'status' | 'created_at';
type SortDir = 'asc' | 'desc';

export function ReviewQueuePage() {
  const navigate = useNavigate();
  const [emissions, setEmissions] = useState<Emission[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 25;

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [anomalyFilter, setAnomalyFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Sort
  const [sortField, setSortField] = useState<SortField>('activity_date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Selection
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchEmissions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      };
      if (statusFilter) params.status = statusFilter;
      if (scopeFilter) params.scope = `scope${scopeFilter}`;
      if (sourceFilter) params.raw_record_type = sourceFilter;
      if (anomalyFilter) params.anomaly_flag = anomalyFilter;
      if (searchQuery) params.search = searchQuery;

      const res = await emissionApi.list(params);
      setEmissions(res.results);
      setCount(res.count);
    } catch {
      setEmissions([]);
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, scopeFilter, sourceFilter, anomalyFilter, searchQuery]);

  useEffect(() => {
    fetchEmissions();
  }, [fetchEmissions]);

  // Reset page on filter change
  useEffect(() => {
    setPage(1);
  }, [statusFilter, scopeFilter, sourceFilter, anomalyFilter, searchQuery]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const sortedEmissions = [...emissions].sort((a, b) => {
    const dir = sortDir === 'asc' ? 1 : -1;
    if (sortField === 'activity_date' || sortField === 'created_at') {
      return dir * (new Date(a[sortField]).getTime() - new Date(b[sortField]).getTime());
    }
    if (sortField === 'co2e_kg' || sortField === 'scope') {
      return dir * ((a[sortField] as number) - (b[sortField] as number));
    }
    if (sortField === 'status') {
      return dir * a.status.localeCompare(b.status);
    }
    return 0;
  });

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === emissions.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(emissions.map((e) => e.id)));
    }
  };

  const handleBulkAction = async (action: 'approve' | 'reject' | 'flag' | 'lock') => {
    if (selected.size === 0) return;
    setActionLoading(true);
    setActionMessage(null);
    try {
      await reviewApi.action({
        action,
        emission_ids: Array.from(selected),
      });
      setActionMessage({ type: 'success', text: `${selected.size} record(s) ${action}d successfully.` });
      setSelected(new Set());
      fetchEmissions();
    } catch {
      setActionMessage({ type: 'error', text: `Failed to ${action} records. Please try again.` });
    } finally {
      setActionLoading(false);
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ChevronDown className="w-3.5 h-3.5 text-slate-300" />;
    return sortDir === 'asc' ? (
      <ChevronUp className="w-3.5 h-3.5 text-emerald-600" />
    ) : (
      <ChevronDown className="w-3.5 h-3.5 text-emerald-600" />
    );
  };

  const formatCO2e = (kg: number) => {
    if (kg >= 1000) return `${(kg / 1000).toFixed(2)} t`;
    return `${kg.toFixed(2)} kg`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Review Queue</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Review and manage normalized emission records
          </p>
        </div>
        <button
          onClick={async () => {
            try {
              const data = await reviewApi.export();
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `audit_export_${new Date().toISOString().slice(0, 10)}.json`;
              a.click();
              URL.revokeObjectURL(url);
            } catch { /* ignore */ }
          }}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          Export Approved
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-medium text-slate-600">Filters</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {SCOPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={anomalyFilter}
            onChange={(e) => setAnomalyFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="">All Anomalies</option>
            <option value="true">Anomalies Only</option>
            <option value="false">No Anomalies</option>
          </select>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search descriptions…"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 lg:col-span-2"
          />
        </div>
      </div>

      {/* Action message */}
      {actionMessage && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            actionMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {actionMessage.text}
        </div>
      )}

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2.5">
          <span className="text-sm font-medium text-blue-700">{selected.size} selected</span>
          <div className="flex gap-2 ml-2">
            <button
              onClick={() => handleBulkAction('approve')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              <CheckCircle className="w-3.5 h-3.5" /> Approve
            </button>
            <button
              onClick={() => handleBulkAction('reject')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              <XCircle className="w-3.5 h-3.5" /> Reject
            </button>
            <button
              onClick={() => handleBulkAction('flag')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-md bg-amber-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-600 disabled:opacity-50"
            >
              <Flag className="w-3.5 h-3.5" /> Flag
            </button>
            <button
              onClick={() => handleBulkAction('lock')}
              disabled={actionLoading}
              className="flex items-center gap-1.5 rounded-md bg-slate-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              <Lock className="w-3.5 h-3.5" /> Lock
            </button>
            {actionLoading && <Loader2 className="w-4 h-4 animate-spin text-blue-600 ml-2" />}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading records…
          </div>
        ) : emissions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <Filter className="w-8 h-8 mb-2" />
            <p className="text-sm">No records found matching your filters</p>
          </div>
        ) : (
          <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="py-3 px-3 w-10">
                    <input
                      type="checkbox"
                      checked={selected.size === emissions.length && emissions.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                    />
                  </th>
                  <th
                    onClick={() => handleSort('activity_date')}
                    className="py-3 px-3 text-left font-medium text-slate-500 cursor-pointer hover:text-slate-700"
                  >
                    <span className="flex items-center gap-1">
                      Date <SortIcon field="activity_date" />
                    </span>
                  </th>
                  <th className="py-3 px-3 text-left font-medium text-slate-500">Description</th>
                  <th className="py-3 px-3 text-left font-medium text-slate-500">Source</th>
                  <th
                    onClick={() => handleSort('scope')}
                    className="py-3 px-3 text-left font-medium text-slate-500 cursor-pointer hover:text-slate-700"
                  >
                    <span className="flex items-center gap-1">
                      Scope <SortIcon field="scope" />
                    </span>
                  </th>
                  <th className="py-3 px-3 text-left font-medium text-slate-500">Category</th>
                  <th
                    onClick={() => handleSort('co2e_kg')}
                    className="py-3 px-3 text-right font-medium text-slate-500 cursor-pointer hover:text-slate-700"
                  >
                    <span className="flex items-center justify-end gap-1">
                      CO₂e <SortIcon field="co2e_kg" />
                    </span>
                  </th>
                  <th
                    onClick={() => handleSort('status')}
                    className="py-3 px-3 text-left font-medium text-slate-500 cursor-pointer hover:text-slate-700"
                  >
                    <span className="flex items-center gap-1">
                      Status <SortIcon field="status" />
                    </span>
                  </th>
                  <th className="py-3 px-3 text-center font-medium text-slate-500">Anomaly</th>
                </tr>
              </thead>
              <tbody>
                {sortedEmissions.map((em) => (
                  <tr
                    key={em.id}
                    onClick={() => navigate(`/review/${em.id}`)}
                    className={`border-b border-slate-100 cursor-pointer transition-colors ${
                      selected.has(em.id) ? 'bg-blue-50/50' : 'hover:bg-slate-50'
                    }`}
                  >
                    <td
                      className="py-3 px-3"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={selected.has(em.id)}
                        onChange={() => toggleSelect(em.id)}
                        className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
                      />
                    </td>
                    <td className="py-3 px-3 text-slate-600">
                      {new Date(em.activity_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </td>
                    <td className="py-3 px-3 text-slate-700 font-medium max-w-xs truncate">
                      {em.activity_description}
                    </td>
                    <td className="py-3 px-3">
                      <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 capitalize">
                        {em.raw_record_type}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-slate-600">Scope {em.scope.replace('scope', '')}</td>
                    <td className="py-3 px-3 text-slate-600 max-w-32 truncate">{em.category}</td>
                    <td className="py-3 px-3 text-right font-mono text-sm text-slate-700">
                      {formatCO2e(em.co2e_kg)}
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={em.status} />
                    </td>
                    <td className="py-3 px-3 text-center">
                      {em.anomaly_flag && em.anomaly_flag !== 'none' ? (
                        <span className="inline-flex items-center gap-1 text-amber-600">
                          <AlertTriangle className="w-4 h-4" />
                          {em.anomaly_notes && (
                            <span className="text-xs max-w-24 truncate">{em.anomaly_notes}</span>
                          )}
                        </span>
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
