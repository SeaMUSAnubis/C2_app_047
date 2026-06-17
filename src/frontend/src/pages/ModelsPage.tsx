import { PageHeader } from '../components/layout/PageHeader';
import { Cpu, CheckCircle } from 'lucide-react';

export function ModelsPage() {
  return (
    <section className="models-page p-6 max-w-4xl mx-auto animated-bg min-h-[calc(100vh-64px)] rounded-xl">
      <PageHeader
        title="ML Models"
        description="Manage and monitor anomaly detection models."
      />

      <div className="glass-panel hover-glow mt-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="p-4 bg-blue-500/20 text-blue-400 rounded-full shadow-[0_0_15px_rgba(59,130,246,0.5)]">
            <Cpu size={32} />
          </div>
          <div>
            <h3 className="text-2xl font-bold glow-text">One-Class SVM (ocsvm-v1.0-cert)</h3>
            <p className="text-gray-400 text-sm mt-1">Active Model for Anomaly Detection</p>
          </div>
          <div className="ml-auto flex items-center gap-2 text-green-400 bg-green-900/30 px-4 py-2 rounded-full text-sm font-semibold border border-green-500/50 shadow-[0_0_10px_rgba(16,185,129,0.2)]">
            <span className="pulse-dot"></span> Active
          </div>
        </div>

        <div className="border-t border-gray-700/50 pt-6 grid grid-cols-2 gap-6">
          <div className="bg-gray-800/40 p-5 rounded-xl border border-gray-700/50">
            <h4 className="text-sm text-gray-400 font-medium mb-4 uppercase tracking-wider">Metrics</h4>
            <ul className="space-y-3 text-sm">
              <li className="flex justify-between items-center bg-gray-900/50 p-2 rounded-lg">
                <span className="text-gray-300">Precision@K:</span>
                <span className="font-bold text-blue-400 text-lg">0.86</span>
              </li>
              <li className="flex justify-between items-center bg-gray-900/50 p-2 rounded-lg">
                <span className="text-gray-300">ROC AUC:</span>
                <span className="font-bold text-purple-400 text-lg">0.93</span>
              </li>
            </ul>
          </div>
          <div className="bg-gray-800/40 p-5 rounded-xl border border-gray-700/50">
            <h4 className="text-sm text-gray-400 font-medium mb-4 uppercase tracking-wider">Configuration</h4>
            <ul className="space-y-3 text-sm">
              <li className="flex justify-between items-center bg-gray-900/50 p-2 rounded-lg">
                <span className="text-gray-300">Algorithm:</span>
                <span className="font-semibold text-white">OneClassSVM</span>
              </li>
              <li className="flex justify-between items-center bg-gray-900/50 p-2 rounded-lg">
                <span className="text-gray-300">Source Data:</span>
                <span className="font-semibold text-white">CERT r4.2 chunked</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 border-t border-gray-700/50 pt-6">
          <h4 className="text-sm text-gray-400 font-medium mb-4 uppercase tracking-wider">Training History</h4>
          <div className="bg-gray-900/60 rounded-xl border border-gray-700/50 p-5 text-sm text-gray-300 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.8)]"></div>
            <p className="mb-3 flex items-center gap-2"><strong className="text-white w-20">Version:</strong> <span className="bg-blue-900/40 text-blue-300 px-2 py-1 rounded">ocsvm-v1.0-cert</span></p>
            <p className="mb-3 flex items-center gap-2"><strong className="text-white w-20">Status:</strong> <span className="text-green-400 flex items-center gap-1"><CheckCircle size={14}/> Completed successfully</span></p>
            <p className="flex items-center gap-2"><strong className="text-white w-20">Artifact:</strong> <span className="font-mono text-xs text-gray-400 bg-black/40 px-2 py-1 rounded">Weight/ocsvm_cert_r42_chunked.joblib</span></p>
          </div>
        </div>
      </div>
    </section>
  );
}
