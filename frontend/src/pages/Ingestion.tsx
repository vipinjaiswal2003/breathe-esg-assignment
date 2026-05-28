import { useEffect, useState, useCallback, type ChangeEvent } from 'react';
import { Upload, FileSpreadsheet, Zap, Plane, CheckCircle, Loader2, Info } from 'lucide-react';
import { sourceApi, ingestApi } from '../api/client';
import type { DataSource, IngestionBatch } from '../types';

type UploadTab = 'sap' | 'utility' | 'travel';

interface UploadState {
  file: File | null;
  dataSourceId: string;
  uploading: boolean;
  result: IngestionBatch | null;
  error: string;
}

const initialUploadState: UploadState = {
  file: null,
  dataSourceId: '',
  uploading: false,
  result: null,
  error: '',
};

const tabConfig: {
  key: UploadTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  accept: string;
  description: string;
  formatInfo: string[];
}[] = [
  {
    key: 'sap',
    label: 'SAP',
    icon: FileSpreadsheet,
    accept: '.txt,.csv,.tsv',
    description: 'Upload SAP SE16N flat-file export with material document data.',
    formatInfo: [
      'Tab-delimited text file (SAP SE16N export)',
      'Required columns: Mat_Doc, MvT, Material, Plant, Quantity, UoM, Pstng_Date',
      'Supports German headers: Materialbeleg, Bewegungsart, Werk, Menge, etc.',
      'Movement types 201 (fuel to cost center) and 261 (fuel to prod order)',
      'Dates: DD.MM.YYYY, YYYY-MM-DD, or MM/DD/YYYY',
      'Decimals: German (1.234,56) or English (1,234.56) format',
    ],
  },
  {
    key: 'utility',
    label: 'Utility',
    icon: Zap,
    accept: '.csv',
    description: 'Upload utility portal CSV export for electricity billing data.',
    formatInfo: [
      'CSV format with headers (comma, tab, or semicolon delimited)',
      'Required columns: meter_number, bill_start_date, bill_end_date, consumption_kwh',
      'Optional: demand_kw, meter_multiplier, reading_type, rate_schedule',
      'Column names auto-detected (e.g., "kWh", "Usage (kWh)", "consumption_kwh")',
      'Billing periods need not align with calendar months',
      'Dates: YYYY-MM-DD, MM/DD/YYYY, or other common formats',
    ],
  },
  {
    key: 'travel',
    label: 'Travel',
    icon: Plane,
    accept: '.json',
    description: 'Upload Concur-style travel itinerary JSON for business trips.',
    formatInfo: [
      'JSON array of trip objects with Segments (Air, Hotel, Car, Rail)',
      'Air: StartCityCode, EndCityCode, Cabin, CarrierCode, StartDate, Miles',
      'Hotel: CityName, CountryCode, Nights, StartDate, EndDate',
      'Car: CarClass, FuelType, DistanceDriven, StartDate',
      'Rail: StartCityCode, EndCityCode, Distance, StartDate',
      'Distance calculated from IATA airport codes when not provided',
    ],
  },
];

export function IngestionPage() {
  const [activeTab, setActiveTab] = useState<UploadTab>('sap');
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [uploadStates, setUploadStates] = useState<Record<UploadTab, UploadState>>({
    sap: { ...initialUploadState },
    utility: { ...initialUploadState },
    travel: { ...initialUploadState },
  });

  useEffect(() => {
    sourceApi.list().then(setDataSources).catch(() => {});
  }, []);

  const sourcesForTab = useCallback(
    (tab: UploadTab) => dataSources.filter((ds) => ds.source_type === tab),
    [dataSources]
  );

  const currentConfig = tabConfig.find((t) => t.key === activeTab)!;
  const state = uploadStates[activeTab];

  const updateState = (updates: Partial<UploadState>) => {
    setUploadStates((prev) => ({
      ...prev,
      [activeTab]: { ...prev[activeTab], ...updates },
    }));
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    updateState({ file, result: null, error: '' });
  };

  const handleUpload = async () => {
    if (!state.file || !state.dataSourceId) return;

    updateState({ uploading: true, error: '', result: null });

    try {
      let result: IngestionBatch;
      const dsId = state.dataSourceId;
      if (activeTab === 'sap') {
        result = await ingestApi.uploadSap(state.file, dsId);
      } else if (activeTab === 'utility') {
        result = await ingestApi.uploadUtility(state.file, dsId);
      } else {
        result = await ingestApi.uploadTravel(state.file, dsId);
      }
      updateState({ result, uploading: false });
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string; error?: string } } };
      updateState({
        error:
          error?.response?.data?.detail ||
          error?.response?.data?.error ||
          'Upload failed. Please check your file and try again.',
        uploading: false,
      });
    }
  };

  const handleReset = () => {
    updateState({ ...initialUploadState });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Ingest Data</h1>
        <p className="text-slate-500 mt-1">
          Upload emission data files from SAP, utility bills, or travel records.
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-6">
          {tabConfig.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 pb-3 border-b-2 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'border-emerald-500 text-emerald-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Upload Form */}
        <div className="lg:col-span-3">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-800 mb-1">{currentConfig.label} Upload</h2>
            <p className="text-sm text-slate-500 mb-5">{currentConfig.description}</p>

            {/* Data source selector */}
            <div className="mb-5">
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Data Source <span className="text-red-500">*</span>
              </label>
              <select
                value={state.dataSourceId}
                onChange={(e) => updateState({ dataSourceId: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              >
                <option value="">Select a data source…</option>
                {sourcesForTab(activeTab).map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.name}
                  </option>
                ))}
              </select>
              {sourcesForTab(activeTab).length === 0 && (
                <p className="text-xs text-amber-600 mt-1.5">
                  No {activeTab} data sources configured. Please create one in the admin panel first.
                </p>
              )}
            </div>

            {/* File upload */}
            <div className="mb-5">
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                File <span className="text-red-500">*</span>
              </label>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  state.file ? 'border-emerald-300 bg-emerald-50/30' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                {state.file ? (
                  <div className="flex items-center justify-center gap-3">
                    <FileSpreadsheet className="w-8 h-8 text-emerald-500" />
                    <div className="text-left">
                      <p className="text-sm font-medium text-slate-700">{state.file.name}</p>
                      <p className="text-xs text-slate-400">
                        {(state.file.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      onClick={handleReset}
                      className="ml-4 text-sm text-slate-500 hover:text-red-500 underline"
                    >
                      Remove
                    </button>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-600 mb-1">
                      Drag & drop or click to select a file
                    </p>
                    <p className="text-xs text-slate-400">
                      Accepted: {currentConfig.accept}
                    </p>
                  </div>
                )}
                <input
                  type="file"
                  accept={currentConfig.accept}
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  style={{ position: 'relative', marginTop: '1rem' }}
                />
              </div>
            </div>

            {/* Upload button */}
            <div className="flex gap-3">
              <button
                onClick={handleUpload}
                disabled={!state.file || !state.dataSourceId || state.uploading}
                className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {state.uploading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading…
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload & Ingest
                  </>
                )}
              </button>
              {(state.result || state.error) && (
                <button
                  onClick={handleReset}
                  className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  Reset
                </button>
              )}
            </div>

            {/* Error */}
            {state.error && (
              <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
                {state.error}
              </div>
            )}

            {/* Success Result */}
            {state.result && (
              <div className="mt-4 rounded-lg bg-emerald-50 border border-emerald-200 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle className="w-5 h-5 text-emerald-600" />
                  <span className="font-semibold text-emerald-800">
                    Ingestion Complete
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Total Records</p>
                    <p className="text-lg font-semibold text-slate-800">
                      {state.result.total_rows}
                    </p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Successfully Processed</p>
                    <p className="text-lg font-semibold text-emerald-600">
                      {state.result.successful_rows}
                    </p>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-100">
                    <p className="text-xs text-slate-500">Failed</p>
                    <p className="text-lg font-semibold text-red-600">
                      {state.result.failed_rows}
                    </p>
                  </div>
                </div>
                {state.result.error_summary && Object.keys(state.result.error_summary).length > 0 && (
                  <p className="mt-3 text-sm text-red-600">{JSON.stringify(state.result.error_summary)}</p>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Format Guide */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl border border-slate-200 p-5 sticky top-6">
            <div className="flex items-center gap-2 mb-3">
              <Info className="w-4 h-4 text-blue-500" />
              <h3 className="text-sm font-semibold text-slate-700">
                Expected Format — {currentConfig.label}
              </h3>
            </div>
            <ul className="space-y-2">
              {currentConfig.formatInfo.map((info, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 shrink-0" />
                  {info}
                </li>
              ))}
            </ul>

            {/* Example for the active tab */}
            <div className="mt-4">
              <p className="text-xs font-medium text-slate-500 mb-2">Example:</p>
              {activeTab === 'sap' && (
                <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600 overflow-x-auto custom-scrollbar">
{`Mat_Doc\tDoc_Yr\tItem\tMvT\tMaterial\tMatl_Group\tPlant\tQuantity\tUoM\tPstng_Date\tCost_Center
4900000200\t2024\t1\t201\t0000000000FUEL001\tFUEL01\t1000\t5000\tL\t15.07.2024\tCC-MFG-01
4900000201\t2024\t1\t201\t0000000000FUEL002\tFUEL02\t2000\t2.500,00\tKG\t20.07.2024\tCC-MFG-02`}
                </pre>
              )}
              {activeTab === 'utility' && (
                <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600 overflow-x-auto custom-scrollbar">
{`meter_number,bill_start_date,bill_end_date,consumption_kwh,demand_kw,meter_multiplier,reading_type
MTR-001,01/07/2024,31/07/2024,45600,120,1.0,actual
MTR-002,2024-06-28,2024-07-27,32100,85,1.0,actual
MTR-003,2024-07-01,2024-07-31,68000,200,40,actual`}
                </pre>
              )}
              {activeTab === 'travel' && (
                <pre className="bg-slate-50 rounded-lg p-3 text-xs text-slate-600 overflow-x-auto custom-scrollbar">
{`[{
  "id": "TRIP-001",
  "BookedBy": "EMP-1001",
  "Segments": {
    "Air": [{
      "StartCityCode": "BOM",
      "EndCityCode": "DEL",
      "Cabin": "E",
      "CarrierCode": "6E",
      "StartDate": "2024-07-10",
      "Miles": 705
    }],
    "Hotel": [{
      "CityName": "New Delhi",
      "CountryCode": "IND",
      "StartDate": "2024-07-10",
      "EndDate": "2024-07-12",
      "Nights": 2
    }]
  }
}]`}
                </pre>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
