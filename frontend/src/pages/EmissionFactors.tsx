import { useEffect, useState } from 'react';
import { Calculator, Search, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { factorsApi } from '../api/client';
import type { EmissionFactor } from '../types';

const SCOPE_LABELS: Record<string, string> = {
  scope1: 'Scope 1 — Direct Emissions',
  scope2: 'Scope 2 — Indirect Energy',
  scope3: 'Scope 3 — Value Chain',
};

const SCOPE_COLORS: Record<string, string> = {
  scope1: 'border-orange-300 bg-orange-50',
  scope2: 'border-yellow-300 bg-yellow-50',
  scope3: 'border-cyan-300 bg-cyan-50',
};

const SCOPE_ORDER = ['scope1', 'scope2', 'scope3'];

export function EmissionFactorsPage() {
  const [factors, setFactors] = useState<EmissionFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [expandedScopes, setExpandedScopes] = useState<Set<string>>(new Set(['scope1', 'scope2', 'scope3']));

  useEffect(() => {
    factorsApi
      .list()
      .then(setFactors)
      .catch(() => setFactors([]))
      .finally(() => setLoading(false));
  }, []);

  const toggleScope = (scope: string) => {
    setExpandedScopes((prev) => {
      const next = new Set(prev);
      if (next.has(scope)) next.delete(scope);
      else next.add(scope);
      return next;
    });
  };

  const filtered = factors.filter(
    (f) =>
      f.activity_name.toLowerCase().includes(search.toLowerCase()) ||
      f.category_display.toLowerCase().includes(search.toLowerCase()) ||
      f.fuel_or_activity_type.toLowerCase().includes(search.toLowerCase())
  );

  const grouped: Record<string, EmissionFactor[]> = {};
  for (const scope of SCOPE_ORDER) {
    grouped[scope] = filtered.filter((f) => f.scope === scope);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading emission factors…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Emission Factors</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Reference table of emission factors used for CO₂e calculations
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search factors by name, category, or type…"
          className="w-full rounded-lg border border-slate-300 pl-9 pr-4 py-2.5 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
        />
      </div>

      {/* Factor groups by scope */}
      {SCOPE_ORDER.map((scope) => (
        <div key={scope} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <button
            onClick={() => toggleScope(scope)}
            className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-slate-50 transition-colors"
          >
            <div
              className={`w-8 h-8 rounded-lg flex items-center justify-center border ${SCOPE_COLORS[scope]}`}
            >
              <Calculator className="w-4 h-4" />
            </div>
            <span className="text-sm font-semibold text-slate-700 flex-1">
              {SCOPE_LABELS[scope]}
            </span>
            <span className="text-xs text-slate-400 mr-2">
              {grouped[scope]?.length || 0} factors
            </span>
            {expandedScopes.has(scope) ? (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {expandedScopes.has(scope) && (
            <div className="border-t border-slate-200">
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="py-2.5 px-4 text-left font-medium text-slate-500">Category</th>
                      <th className="py-2.5 px-4 text-left font-medium text-slate-500">Activity</th>
                      <th className="py-2.5 px-4 text-right font-medium text-slate-500">CO₂e Factor</th>
                      <th className="py-2.5 px-4 text-left font-medium text-slate-500">Unit</th>
                      <th className="py-2.5 px-4 text-left font-medium text-slate-500">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(grouped[scope] || []).map((f) => (
                      <tr key={f.id} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="py-3 px-4 text-slate-600">{f.category_display}</td>
                        <td className="py-3 px-4 text-slate-700 font-medium">{f.activity_name}</td>
                        <td className="py-3 px-4 text-right font-mono text-slate-700">
                          {f.co2e_factor}
                        </td>
                        <td className="py-3 px-4 text-slate-500 text-xs">{f.unit}</td>
                        <td className="py-3 px-4 text-slate-500 text-xs">{f.source} ({f.year})</td>
                      </tr>
                    ))}
                    {(!grouped[scope] || grouped[scope].length === 0) && (
                      <tr>
                        <td colSpan={5} className="py-6 text-center text-slate-400 text-sm">
                          No matching factors
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ))}

      <p className="text-xs text-slate-400 text-center pb-4">
        Emission factors sourced from DEFRA 2024, EPA eGRID 2022, India CEA 2023, and Cornell CHSB 2023.
        These are default reference values — actual factors may vary by region and methodology.
      </p>
    </div>
  );
}
