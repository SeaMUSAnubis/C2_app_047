import { useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Database, Play, CheckCircle, AlertTriangle } from 'lucide-react';
import { importDemoData, analyzeDemo } from '../lib/apiClient';

export function DataImportPage() {
  const [status, setStatus] = useState<'idle' | 'importing' | 'analyzing' | 'done' | 'error'>('idle');
  const [summary, setSummary] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const runImport = async () => {
    try {
      setStatus('importing');
      setErrorMsg('');
      const data = await importDemoData();
      setSummary(data.summary);
      setStatus('done');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to import data');
      setStatus('error');
    }
  };

  const runAnalysis = async () => {
    try {
      setStatus('analyzing');
      setErrorMsg('');
      // Using an arbitrary demo user for the analysis
      await analyzeDemo({ user_id: 'BDV0168', events: [] }); 
      setStatus('done');
      alert('Analysis completed successfully. Check the Alerts page.');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to run analysis');
      setStatus('error');
    }
  };

  return (
    <section className="data-import-page p-6 max-w-4xl mx-auto animated-bg min-h-[calc(100vh-64px)] rounded-xl">
      <PageHeader
        title="Data Management"
        description="Import CERT dataset and run anomaly detection models."
      />

      <div className="glass-panel hover-glow mt-6">
        <h3 className="text-2xl font-bold mb-4 flex items-center gap-2 glow-text">
          <Database size={24} className="text-blue-600" />
          CERT r4.2 Demo Data
        </h3>
        
        <p className="text-gray-300 mb-6">
          This will inject a predefined set of mock events and alerts simulating the CERT r4.2 dataset to demonstrate the One-Class SVM model capabilities.
        </p>

        <div className="flex gap-4">
          <button
            onClick={runImport}
            disabled={status === 'importing' || status === 'analyzing'}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50 border border-blue-500/50"
          >
            <Play size={18} />
            {status === 'importing' ? 'Importing...' : 'Run Demo Import'}
          </button>
          
          {summary && (
            <button
              onClick={runAnalysis}
              disabled={status === 'importing' || status === 'analyzing'}
              className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 disabled:opacity-50"
            >
              <Play size={18} />
              {status === 'analyzing' ? 'Analyzing...' : 'Run Demo Analysis'}
            </button>
          )}
        </div>

        {status === 'error' && (
          <div className="mt-6 p-4 bg-red-900/30 text-red-400 rounded-md flex items-center gap-2 border border-red-500/50">
            <AlertTriangle size={20} />
            {errorMsg} (Tip: Try logging out and logging back in if you get unauthorized errors)
          </div>
        )}

        {summary && status === 'done' && (
          <div className="mt-6 p-6 border border-green-500/50 bg-green-900/30 rounded-lg">
            <h4 className="font-semibold text-green-400 flex items-center gap-2 mb-4">
              <CheckCircle size={20} />
              Import Successful
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-800/60 p-4 rounded shadow-sm border border-gray-700/50">
                <div className="text-sm text-gray-400">Rows Imported</div>
                <div className="text-xl font-bold text-white">{summary.rows_imported}</div>
              </div>
              <div className="bg-gray-800/60 p-4 rounded shadow-sm border border-gray-700/50">
                <div className="text-sm text-gray-400">Users Found</div>
                <div className="text-xl font-bold text-white">{summary.users_found}</div>
              </div>
              <div className="bg-gray-800/60 p-4 rounded shadow-sm border border-gray-700/50">
                <div className="text-sm text-gray-400">Devices Found</div>
                <div className="text-xl font-bold text-white">{summary.devices_found}</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
