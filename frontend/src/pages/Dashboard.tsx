import { useEffect, useState } from 'react';
import {
  FileText,
  Cloud,
  Clock,
  AlertTriangle,
  TrendingUp,
  Zap,
  Plane,
  Building2,
  ArrowRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { dashboardApi } from '../api/client';
import type { DashboardStats } from '../types';
import { StatusBadge } from '../components/StatusBadge';

function formatCO2e(kg: number): string {
  if (kg >= 1000) {
    return `${(kg / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })} tCO₂e`;
  }
  return `${kg.toLocaleString(undefined, { maximumFractionDigits: 1 })} kgCO₂e`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    dashboardApi
      .stats()
      .then(setStats)
      .catch(() => setError('Failed to load dashboard data'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold text-slate-800">Dashboard</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 animate-pulse">
              <div className="h-4 bg-slate-200 rounded w-24 mb-3" />
              <div className="h-8 bg-slate-200 rounded w-32" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">{error}</div>
    );
  }

  const scopeEntries = Object.entries(stats.scope_counts);
  const sourceEntries = Object.entries(stats.source_type_counts);
  const anomalyTotal = Object.values(stats.anomaly_counts).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-800">Dashboard</h1>
        <span className="text-sm text-slate-400">
          Last updated: {new Date().toLocaleTimeString()}
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          icon={FileText}
          label="Total Records"
          value={stats.total_records.toLocaleString()}
          color="slate"
        />
        <SummaryCard
          icon={Cloud}
          label="Total CO₂e"
          value={formatCO2e(stats.total_co2e_kg)}
          color="emerald"
        />
        <SummaryCard
          icon={Clock}
          label="Pending Review"
          value={stats.pending_review.toLocaleString()}
          color="blue"
        />
        <SummaryCard
          icon={AlertTriangle}
          label="Flagged"
          value={stats.flagged.toLocaleString()}
          color="amber"
        />
      </div>

      {/* Scope & Source Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Scope Breakdown */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Scope Breakdown</h2>
          <div className="space-y-3">
            {scopeEntries.map(([scope, count]) => {
              const scopeNum = parseInt(scope.replace('scope', ''));
              const ScopeIcon = scopeNum === 1 ? Building2 : scopeNum === 2 ? Zap : Plane;
              const color =
                scopeNum === 1
                  ? 'bg-orange-50 text-orange-600'
                  : scopeNum === 2
                  ? 'bg-yellow-50 text-yellow-600'
                  : 'bg-cyan-50 text-cyan-600';
              const total = scopeEntries.reduce((a, [, c]) => a + c, 0);
              const pct = total > 0 ? Math.round((count / total) * 100) : 0;

              return (
                <div key={scope} className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
                    <ScopeIcon className="w-4.5 h-4.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-slate-700">
                        Scope {scopeNum}
                      </span>
                      <span className="text-sm text-slate-500">
                        {count.toLocaleString()} records
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full ${
                          scopeNum === 1
                            ? 'bg-orange-400'
                            : scopeNum === 2
                            ? 'bg-yellow-400'
                            : 'bg-cyan-400'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
            {scopeEntries.length === 0 && (
              <p className="text-sm text-slate-400 py-4 text-center">No scope data yet</p>
            )}
          </div>
        </div>

        {/* Source Type Breakdown */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Source Types</h2>
          <div className="space-y-3">
            {sourceEntries.map(([source, count]) => {
              const SourceIcon = source === 'sap' ? Building2 : source === 'utility' ? Zap : Plane;
              const label = source === 'sap' ? 'SAP' : source === 'utility' ? 'Utility' : 'Travel';
              const color =
                source === 'sap'
                  ? 'bg-blue-50 text-blue-600'
                  : source === 'utility'
                  ? 'bg-emerald-50 text-emerald-600'
                  : 'bg-violet-50 text-violet-600';
              const total = sourceEntries.reduce((a, [, c]) => a + c, 0);
              const pct = total > 0 ? Math.round((count / total) * 100) : 0;

              return (
                <div key={source} className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
                    <SourceIcon className="w-4.5 h-4.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-slate-700">{label}</span>
                      <span className="text-sm text-slate-500">
                        {count.toLocaleString()} records
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full ${
                          source === 'sap'
                            ? 'bg-blue-400'
                            : source === 'utility'
                            ? 'bg-emerald-400'
                            : 'bg-violet-400'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
            {sourceEntries.length === 0 && (
              <p className="text-sm text-slate-400 py-4 text-center">No source data yet</p>
            )}
          </div>
        </div>
      </div>

      {/* Status Distribution & Anomaly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Status Distribution</h2>
          <div className="grid grid-cols-5 gap-3">
            {Object.entries(stats.status_counts).map(([status, count]) => (
              <div key={status} className="text-center">
                <StatusBadge status={status} size="md" />
                <p className="text-lg font-semibold text-slate-800 mt-2">{count}</p>
              </div>
            ))}
            {Object.keys(stats.status_counts).length === 0 && (
              <p className="col-span-5 text-sm text-slate-400 py-4 text-center">
                No status data yet
              </p>
            )}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Anomaly Summary</h2>
          {anomalyTotal > 0 ? (
            <div className="space-y-2">
              {Object.entries(stats.anomaly_counts).map(([reason, count]) => (
                <div key={reason} className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-amber-50">
                  <span className="text-sm text-amber-800">{reason}</span>
                  <span className="text-sm font-semibold text-amber-700">{count}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <AlertTriangle className="w-5 h-5 mr-2" />
              No anomalies detected
            </div>
          )}
        </div>
      </div>

      {/* Recent Batches */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-700">Recent Ingestion Batches</h2>
          <Link
            to="/ingest"
            className="text-sm text-emerald-600 hover:text-emerald-700 font-medium flex items-center gap-1"
          >
            Upload data
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        {stats.recent_batches && stats.recent_batches.length > 0 ? (
          <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left py-2.5 px-3 font-medium text-slate-500">Source</th>
                  <th className="text-left py-2.5 px-3 font-medium text-slate-500">Status</th>
                  <th className="text-right py-2.5 px-3 font-medium text-slate-500">Total</th>
                  <th className="text-right py-2.5 px-3 font-medium text-slate-500">Success</th>
                  <th className="text-right py-2.5 px-3 font-medium text-slate-500">Failed</th>
                  <th className="text-left py-2.5 px-3 font-medium text-slate-500">Date</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_batches.map((batch) => (
                  <tr key={batch.id} className="border-b border-slate-50 hover:bg-slate-25">
                    <td className="py-2.5 px-3 font-medium text-slate-700">{batch.source_name}</td>
                    <td className="py-2.5 px-3">
                      <StatusBadge status={batch.status} />
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-600">
                      {batch.total_rows}
                    </td>
                    <td className="py-2.5 px-3 text-right text-emerald-600">
                      {batch.successful_rows}
                    </td>
                    <td className="py-2.5 px-3 text-right text-red-600">
                      {batch.total_rows - batch.successful_rows}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">{formatDate(batch.ingested_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <TrendingUp className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-400">No ingestion batches yet</p>
            <Link
              to="/ingest"
              className="text-sm text-emerald-600 hover:text-emerald-700 font-medium mt-2 inline-block"
            >
              Upload your first file →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  color: 'slate' | 'emerald' | 'blue' | 'amber';
}) {
  const colorMap = {
    slate: 'bg-slate-50 text-slate-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    blue: 'bg-blue-50 text-blue-600',
    amber: 'bg-amber-50 text-amber-600',
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colorMap[color]}`}>
          <Icon className="w-4.5 h-4.5" />
        </div>
        <span className="text-sm text-slate-500">{label}</span>
      </div>
      <p className="text-2xl font-semibold text-slate-800">{value}</p>
    </div>
  );
}
