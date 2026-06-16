import { useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { analyzeDemo } from '../lib/apiClient';
import { ShieldAlert, ShieldCheck, Zap, Activity, Cpu, Play } from 'lucide-react';
import '../styles/demo.css';

const SCENARIOS = [
  {
    id: 1,
    title: 'Hành vi bình thường (Normal)',
    description: 'Nhân viên đăng nhập vào giờ hành chính, gửi email công việc và duyệt web thông thường.',
    payload: {
      user_id: 'MOH0273',
      events: [
        { event_type: 'logon', timestamp: '2010-05-12T08:15:00Z', pc: 'PC-1234' },
        { event_type: 'email', timestamp: '2010-05-12T09:30:00Z', to: 'boss@dtaa.com' },
        { event_type: 'http', timestamp: '2010-05-12T10:00:00Z', url: 'http://news.com' }
      ]
    }
  },
  {
    id: 2,
    title: 'Nghi vấn rò rỉ dữ liệu (Exfiltration)',
    description: 'Đăng nhập ngoài giờ, cắm USB và có lịch sử truy cập trang rò rỉ thông tin (wikileaks).',
    payload: {
      user_id: 'JXD0123',
      events: [
        { event_type: 'logon', timestamp: '2010-05-12T23:15:00Z', pc: 'PC-9999' },
        { event_type: 'device', timestamp: '2010-05-12T23:20:00Z', activity: 'Connect' },
        { event_type: 'http', timestamp: '2010-05-12T23:25:00Z', url: 'http://wikileaks.org/upload' },
        { event_type: 'file', timestamp: '2010-05-12T23:30:00Z', filename: 'confidential.zip' }
      ]
    }
  },
  {
    id: 3,
    title: 'Thực thi mã độc (Suspicious EXE)',
    description: 'Nhân viên sao chép hoặc chạy file thực thi (.exe) không rõ nguồn gốc.',
    payload: {
      user_id: 'HSB0196',
      events: [
        { event_type: 'logon', timestamp: '2010-01-02T09:00:00Z', pc: 'PC-8001' },
        { event_type: 'file', timestamp: '2010-01-02T09:49:30Z', filename: 'RJGC8XX5.exe' }
      ]
    }
  },
  {
    id: 4,
    title: 'Chuẩn bị nhảy việc (Job Hunting)',
    description: 'Truy cập dồn dập các trang tuyển dụng và sao chép lượng lớn file dữ liệu.',
    payload: {
      user_id: 'ABC0999',
      events: [
        { event_type: 'http', timestamp: '2010-08-15T14:00:00Z', url: 'http://indeed.com/jobs' },
        { event_type: 'http', timestamp: '2010-08-15T14:10:00Z', url: 'http://monster.com' },
        { event_type: 'device', timestamp: '2010-08-15T16:00:00Z', activity: 'Connect' },
        { event_type: 'file', timestamp: '2010-08-15T16:05:00Z', filename: 'source_code.zip' }
      ]
    }
  },
  {
    id: 5,
    title: 'Phá hoại hệ thống (Sabotage)',
    description: 'Tải công cụ theo dõi thao tác phím (keylogger) nhắm vào máy tính quản lý.',
    payload: {
      user_id: 'ITAdmin01',
      events: [
        { event_type: 'http', timestamp: '2011-02-10T11:00:00Z', url: 'http://hacker-tools.com/keylog.exe' },
        { event_type: 'file', timestamp: '2011-02-10T11:05:00Z', filename: 'keylogger.exe' },
        { event_type: 'device', timestamp: '2011-02-10T11:10:00Z', activity: 'Connect' }
      ]
    }
  }
];

export function DemoPage() {
  const [activeScenarioId, setActiveScenarioId] = useState(SCENARIOS[0].id);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const activeScenario = SCENARIOS.find(s => s.id === activeScenarioId)!;

  const handleAnalyze = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await analyzeDemo(activeScenario.payload);
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze demo scenario');
    } finally {
      setLoading(false);
    }
  };

  const getRiskClass = (score: number) => {
    if (score < 40) return 'score-low';
    if (score < 75) return 'score-medium';
    return 'score-high';
  };

  return (
    <section>
      <PageHeader
        title="AI Analysis Demo"
        description="Select a scenario to analyze UEBA events using the ML and LLM pipeline."
      />

      <div className="demo-container">
        {/* Sidebar Scenarios */}
        <div className="scenarios-sidebar">
          <h3>Scenarios</h3>
          {SCENARIOS.map(scenario => (
            <div
              key={scenario.id}
              className={`scenario-card ${activeScenarioId === scenario.id ? 'active' : ''}`}
              onClick={() => {
                setActiveScenarioId(scenario.id);
                setResult(null);
                setError('');
              }}
            >
              <h4>
                {scenario.id === 1 ? <ShieldCheck size={18} /> : <ShieldAlert size={18} />}
                {scenario.title}
              </h4>
              <p>{scenario.description}</p>
            </div>
          ))}
        </div>

        {/* Main Content */}
        <div className="demo-main">
          {/* Payload Box */}
          <div className="payload-box">
            <h3>
              <span><Cpu size={20} style={{ marginRight: 8, verticalAlign: 'middle' }} /> Raw Event Payload</span>
              <button
                className="analyze-btn"
                onClick={handleAnalyze}
                disabled={loading}
              >
                {loading ? <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2, marginBottom: 0 }}></span> : <Play size={16} />}
                {loading ? 'Analyzing...' : 'Analyze with AI'}
              </button>
            </h3>
            <pre>
              {JSON.stringify(activeScenario.payload, null, 2)}
            </pre>
          </div>

          {/* Error Message */}
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          {/* Results Box */}
          {result && (
            <div className="result-box">
              <div className="result-header">
                <div className="result-title">
                  {result.is_anomaly ? (
                    <ShieldAlert size={32} color="#ef4444" />
                  ) : (
                    <ShieldCheck size={32} color="#10b981" />
                  )}
                  <div>
                    <h3>{result.is_anomaly ? 'Anomaly Detected' : 'Normal Behavior'}</h3>
                    <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 4 }}>
                      Analyzed by OCSVM Model + LLM
                    </div>
                  </div>
                </div>

                <div className={`score-circle ${getRiskClass(result.risk_score)}`}>
                  <span className="score-val">{result.risk_score}</span>
                  <span className="score-label">Risk</span>
                </div>
              </div>

              {result.top_factors && result.top_factors.length > 0 && (
                <div className="factors-section">
                  <h4>Key Risk Factors</h4>
                  <div className="factors-list">
                    {result.top_factors.map((factor: string, idx: number) => (
                      <span key={idx} className="factor-badge">
                        <Activity size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {result.explanation && (
                <div className="llm-explanation">
                  <h4><Zap size={18} /> LLM Analysis</h4>
                  {result.explanation}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
