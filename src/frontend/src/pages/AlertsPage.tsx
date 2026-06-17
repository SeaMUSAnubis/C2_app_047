import { useState, useEffect } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { ShieldAlert, Activity, ChevronRight, CheckCircle, Clock } from 'lucide-react';
import '../styles/alerts.css';
import { getAlerts } from '../lib/apiClient';

export function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<any>(null);

  useEffect(() => {
    async function fetchAlerts() {
      try {
        const data = await getAlerts();
        setAlerts(data);
        if (data.length > 0) setSelectedAlert(data[0]);
      } catch (err) {
        console.error("Failed to load alerts", err);
      } finally {
        setLoading(false);
      }
    }
    fetchAlerts();
  }, []);

  if (loading) {
    return <div className="loading-spinner">Loading Alerts...</div>;
  }

  return (
    <section className="alerts-page">
      <PageHeader
        title="Security Alerts"
        description="Review and investigate behavioral anomalies detected by OCSVM model."
      />
      
      <div className="alerts-container">
        {/* Sidebar */}
        <div className="alerts-sidebar">
          <h3>Open Alerts ({alerts.length})</h3>
          <div className="alerts-list">
            {alerts.map((alert) => (
              <div 
                key={alert.id} 
                className={`alert-card ${selectedAlert?.id === alert.id ? 'active' : ''} severity-${alert.severity}`}
                onClick={() => setSelectedAlert(alert)}
              >
                <div className="alert-card-header">
                  <ShieldAlert size={16} />
                  <span>{alert.title}</span>
                </div>
                <div className="alert-card-meta">
                  <span className="risk-badge">Risk: {alert.riskScore}</span>
                  <span className="time-badge"><Clock size={12}/> {new Date(alert.detectedAt).toLocaleTimeString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Main Panel */}
        <div className="alert-detail-panel">
          {selectedAlert ? (
            <div className="alert-detail-content">
              <div className="detail-header">
                <h2>{selectedAlert.title}</h2>
                <div className="status-badge status-new">Status: {selectedAlert.status.toUpperCase()}</div>
              </div>
              
              <div className="detail-grid">
                <div className="detail-box">
                  <h4><Activity size={16} /> Risk Analysis</h4>
                  <div className="score-display">
                    <div className="score-circle">
                      <span className="val">{selectedAlert.riskScore}</span>
                      <span className="lbl">Score</span>
                    </div>
                    <div className="factors">
                      <h5>Top Factors:</h5>
                      {selectedAlert.riskFactors?.map((f: string, i: number) => (
                        <span key={i} className="factor-tag">{f}</span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="detail-box">
                  <h4>Entities Involved</h4>
                  <p><strong>User:</strong> {selectedAlert.userName || selectedAlert.user_id}</p>
                  <p><strong>Device:</strong> {selectedAlert.deviceName || selectedAlert.device_id}</p>
                </div>
              </div>

              <div className="llm-explanation-box">
                <h4>AI Explainer (LLM)</h4>
                <p>{selectedAlert.explanation}</p>
              </div>
              
              <div className="action-buttons">
                <button className="btn-primary">Start Investigation</button>
                <button className="btn-secondary"><CheckCircle size={16} /> Mark as False Positive</button>
              </div>
            </div>
          ) : (
            <div className="empty-state">Select an alert to view details.</div>
          )}
        </div>
      </div>
    </section>
  );
}
