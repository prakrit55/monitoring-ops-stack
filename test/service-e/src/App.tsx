import { useState, useEffect } from 'react';
import './App.css';

interface Endpoints {
  serviceA: string;
  serviceB: string;
  serviceC: string;
  serviceD: string;
}

interface ServiceStatus {
  name: string;
  url: string;
  status: 'UP' | 'DOWN';
  checking: boolean;
  port: string;
  lang: string;
}

interface LogEntry {
  timestamp: string;
  type: 'info' | 'success' | 'error';
  service: string;
  method: string;
  url: string;
  elapsedMs: number;
  statusCode?: number;
  correlationId?: string;
  body: string;
}

export default function App() {
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const [endpoints, setEndpoints] = useState<Endpoints>({
    serviceA: (isLocal ? localStorage.getItem('url_service_a') : null) || (isLocal ? 'http://localhost:8080' : `${window.location.origin}/api/service-a`),
    serviceB: (isLocal ? localStorage.getItem('url_service_b') : null) || (isLocal ? 'http://localhost:8081' : `${window.location.origin}/api/service-b`),
    serviceC: (isLocal ? localStorage.getItem('url_service_c') : null) || (isLocal ? 'http://localhost:8082' : `${window.location.origin}/api/service-c`),
    serviceD: (isLocal ? localStorage.getItem('url_service_d') : null) || (isLocal ? 'http://localhost:8083' : `${window.location.origin}/api/service-d`),
  });

  const [statuses, setStatuses] = useState<Record<string, ServiceStatus>>({
    serviceA: { name: 'Service A', url: endpoints.serviceA, status: 'DOWN', checking: false, port: '8080', lang: 'Go (gRPC/HTTP)' },
    serviceB: { name: 'Service B', url: endpoints.serviceB, status: 'DOWN', checking: false, port: '8081', lang: 'Go (gRPC/HTTP)' },
    serviceC: { name: 'Service C', url: endpoints.serviceC, status: 'DOWN', checking: false, port: '8082', lang: 'TS / Express' },
    serviceD: { name: 'Service D', url: endpoints.serviceD, status: 'DOWN', checking: false, port: '8083', lang: 'Python / Flask' },
  });

  const [showSettings, setShowSettings] = useState(false);
  const [nameInput, setNameInput] = useState('Frontend Client');
  const [customCorrelationId, setCustomCorrelationId] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeFlow, setActiveFlow] = useState<string | null>(null);
  const [latestCorrelationId, setLatestCorrelationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Ping services helper
  const checkHealth = async (key: string, url: string) => {
    setStatuses(prev => ({
      ...prev,
      [key]: { ...prev[key], checking: true }
    }));
    
    try {
      const res = await fetch(url, { method: 'GET', mode: 'cors', cache: 'no-store' });
      if (res.ok) {
        setStatuses(prev => ({
          ...prev,
          [key]: { ...prev[key], status: 'UP', checking: false }
        }));
        return;
      }
    } catch (e) {
      // Ignore error
    }
    
    setStatuses(prev => ({
      ...prev,
      [key]: { ...prev[key], status: 'DOWN', checking: false }
    }));
  };

  // Check health on load and every 5 seconds
  useEffect(() => {
    const runChecks = () => {
      checkHealth('serviceA', endpoints.serviceA);
      checkHealth('serviceB', endpoints.serviceB);
      checkHealth('serviceC', endpoints.serviceC);
      checkHealth('serviceD', endpoints.serviceD);
    };

    runChecks();
    const interval = setInterval(runChecks, 5000);
    return () => clearInterval(interval);
  }, [endpoints]);

  // Save settings handler
  const saveSettings = (newUrls: typeof endpoints) => {
    setEndpoints(newUrls);
    localStorage.setItem('url_service_a', newUrls.serviceA);
    localStorage.setItem('url_service_b', newUrls.serviceB);
    localStorage.setItem('url_service_c', newUrls.serviceC);
    localStorage.setItem('url_service_d', newUrls.serviceD);
    
    setStatuses(prev => ({
      serviceA: { ...prev.serviceA, url: newUrls.serviceA },
      serviceB: { ...prev.serviceB, url: newUrls.serviceB },
      serviceC: { ...prev.serviceC, url: newUrls.serviceC },
      serviceD: { ...prev.serviceD, url: newUrls.serviceD },
    }));
    setShowSettings(false);
  };

  // Generate a mock log record
  const addLog = (entry: LogEntry) => {
    setLogs(prev => [entry, ...prev].slice(0, 50));
    if (entry.correlationId) {
      setLatestCorrelationId(entry.correlationId);
    }
  };

  // Trigger service call
  const handleServiceCall = async (serviceKey: 'serviceA' | 'serviceC' | 'serviceD', route: string, method: string = 'GET') => {
    setLoading(true);
    const flowName = serviceKey === 'serviceA' ? 'flow-a' : serviceKey === 'serviceC' ? 'flow-c' : 'flow-d';
    setActiveFlow(flowName);
    
    const startTime = Date.now();
    const correlationId = customCorrelationId.trim() || Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    
    // Construct request details
    let url = `${endpoints[serviceKey]}${route}`;
    if (serviceKey !== 'serviceA') {
      url += `?name=${encodeURIComponent(nameInput)}`;
    }
    
    addLog({
      timestamp: new Date().toLocaleTimeString(),
      type: 'info',
      service: statuses[serviceKey].name,
      method,
      url,
      elapsedMs: 0,
      correlationId,
      body: `Initiating HTTP ${method} call...`
    });

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (serviceKey === 'serviceA') {
        headers['X-Correlation-Id'] = correlationId;
      }

      const res = await fetch(url, {
        method,
        headers,
        mode: 'cors',
      });
      
      const text = await res.text();
      const elapsed = Date.now() - startTime;
      
      let parsedBody = text;
      try {
        parsedBody = JSON.stringify(JSON.parse(text), null, 2);
      } catch (e) {}

      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: res.ok ? 'success' : 'error',
        service: statuses[serviceKey].name,
        method,
        url,
        elapsedMs: elapsed,
        statusCode: res.status,
        correlationId,
        body: parsedBody
      });
    } catch (err: any) {
      const elapsed = Date.now() - startTime;
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: 'error',
        service: statuses[serviceKey].name,
        method,
        url,
        elapsedMs: elapsed,
        body: `Network Error: ${err.message}`
      });
    } finally {
      setLoading(false);
      // Let the animation run a bit longer to look cool
      setTimeout(() => {
        setActiveFlow(null);
      }, 2500);
    }
  };

  const handlePokeService = async (serviceKey: 'serviceA' | 'serviceB' | 'serviceC' | 'serviceD') => {
    setLoading(true);
    const svc = statuses[serviceKey];
    const url = endpoints[serviceKey];
    const startTime = Date.now();
    const correlationId = customCorrelationId.trim() || Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    
    addLog({
      timestamp: new Date().toLocaleTimeString(),
      type: 'info',
      service: svc.name,
      method: 'GET',
      url: url,
      elapsedMs: 0,
      correlationId,
      body: `Poking service root endpoint...`
    });

    try {
      const res = await fetch(url, {
        method: 'GET',
        headers: {
          'X-Correlation-Id': correlationId
        },
        mode: 'cors'
      });
      const elapsed = Date.now() - startTime;
      const text = await res.text();
      let parsedBody = text;
      try {
        parsedBody = JSON.stringify(JSON.parse(text), null, 2);
      } catch (e) {}

      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: res.ok ? 'success' : 'error',
        service: svc.name,
        method: 'GET',
        url: url,
        elapsedMs: elapsed,
        statusCode: res.status,
        correlationId,
        body: parsedBody
      });
    } catch (err: any) {
      const elapsed = Date.now() - startTime;
      addLog({
        timestamp: new Date().toLocaleTimeString(),
        type: 'error',
        service: svc.name,
        method: 'GET',
        url: url,
        elapsedMs: elapsed,
        body: `Poke failed: ${err.message}`
      });
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert('Correlation ID copied to clipboard!');
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-title">
          <h1>Service Linkage Analyzer</h1>
          <p>Microservices Inter-connectivity, Log Correlation, and Metrics Dashboard</p>
        </div>
        <div className="header-actions">
          <button className="icon-btn" title="Settings" onClick={() => setShowSettings(true)}>
            ⚙️
          </button>
        </div>
      </header>

      {/* Grid */}
      <div className="dashboard-grid">
        
        {/* Left Side: System Diagram & Health */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Health Check Widget */}
          <section className="glass-card">
            <h2 className="card-title">
              <span>🩺</span> System Health Status
            </h2>
            <div className="status-list">
              {Object.entries(statuses).map(([key, svc]) => (
                <div key={key} className="status-card">
                  <div className="status-card-header">
                    <span className="service-name">{svc.name}</span>
                    <span className={`service-lang-badge ${key}`}>
                      {svc.lang.split(' ')[0]}
                    </span>
                  </div>
                  
                  <div className="status-card-body">
                    <div className="port-info">
                      Port: <code>{svc.port}</code>
                    </div>
                    <div className="status-badge">
                      <span className={`ping-circle ${svc.status.toLowerCase()}`}></span>
                      <span className={`ping-label ${svc.status.toLowerCase()}`}>{svc.status}</span>
                    </div>
                  </div>
                  
                  <button 
                    className="poke-btn-full" 
                    onClick={() => handlePokeService(key as 'serviceA' | 'serviceB' | 'serviceC' | 'serviceD')}
                    disabled={loading || svc.checking}
                    title={`Poke ${svc.name} directly`}
                  >
                    <span>⚡ Poke</span>
                  </button>
                </div>
              ))}
            </div>
          </section>

          {/* Topology Diagram */}
          <section className="glass-card" style={{ flexGrow: 1 }}>
            <h2 className="card-title">
              <span>🕸️</span> Flow Topology Map
            </h2>
            <div className="diagram-container">
              <svg className="flow-svg" viewBox="0 0 500 350">
                {/* Flow Paths Definition */}
                <defs>
                  <path id="svg-path-a" d="M 50 175 L 310 175" />
                  <path id="svg-path-c" d="M 50 175 L 180 80 L 310 175" />
                  <path id="svg-path-d" d="M 50 175 L 180 270 L 310 175" />
                  <path id="svg-path-ab" d="M 310 175 L 440 175" />
                </defs>

                {/* Background Connecting Lines */}
                <path d="M 50 175 L 310 175" className={`flow-line ${activeFlow === 'flow-a' ? 'active' : ''}`} />
                <path d="M 50 175 L 180 80 L 310 175" className={`flow-line ${activeFlow === 'flow-c' ? 'active' : ''}`} />
                <path d="M 50 175 L 180 270 L 310 175" className={`flow-line ${activeFlow === 'flow-d' ? 'active' : ''}`} />
                <path d="M 310 175 L 440 175" className={`flow-line ${activeFlow ? 'active' : ''}`} />

                {/* Animated Particles */}
                {activeFlow === 'flow-a' && (
                  <>
                    <circle className="flow-dot active" style={{ offsetPath: "path('M 50 175 L 310 175')" }} />
                    <circle className="flow-dot active" style={{ offsetPath: "path('M 310 175 L 440 175')", animationDelay: '1.25s' }} />
                  </>
                )}
                {activeFlow === 'flow-c' && (
                  <>
                    <circle className="flow-dot active" style={{ offsetPath: "path('M 50 175 L 180 80 L 310 175')" }} />
                    <circle className="flow-dot active" style={{ offsetPath: "path('M 310 175 L 440 175')", animationDelay: '1.5s' }} />
                  </>
                )}
                {activeFlow === 'flow-d' && (
                  <>
                    <circle className="flow-dot active" style={{ offsetPath: "path('M 50 175 L 180 270 L 310 175')" }} />
                    <circle className="flow-dot active" style={{ offsetPath: "path('M 310 175 L 440 175')", animationDelay: '1.5s' }} />
                  </>
                )}

                {/* Nodes */}
                {/* Client / Browser */}
                <g className="svg-node" transform="translate(50, 175)">
                  <circle r="22" fill="#12131a" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" />
                  <text className="node-text" y="4">Browser</text>
                  <text className="node-subtext" y="32">Dashboard</text>
                </g>

                {/* Service C */}
                <g className="svg-node" transform="translate(180, 80)">
                  <circle r="25" fill="#12131a" stroke={statuses.serviceC.status === 'UP' ? 'var(--status-up)' : 'rgba(255,255,255,0.1)'} strokeWidth="2" />
                  <text className="node-text" y="-2">Service C</text>
                  <text className="node-text" y="10" style={{ fontSize: '9px', fill: 'var(--accent-purple)' }}>Port 8082</text>
                  <text className="node-subtext" y="36">TS / Express</text>
                </g>

                {/* Service D */}
                <g className="svg-node" transform="translate(180, 270)">
                  <circle r="25" fill="#12131a" stroke={statuses.serviceD.status === 'UP' ? 'var(--status-up)' : 'rgba(255,255,255,0.1)'} strokeWidth="2" />
                  <text className="node-text" y="-2">Service D</text>
                  <text className="node-text" y="10" style={{ fontSize: '9px', fill: 'var(--accent-purple)' }}>Port 8083</text>
                  <text className="node-subtext" y="36">Python / Flask</text>
                </g>

                {/* Service A */}
                <g className="svg-node" transform="translate(310, 175)">
                  <circle r="28" fill="#12131a" stroke={statuses.serviceA.status === 'UP' ? 'var(--status-up)' : 'rgba(255,255,255,0.1)'} strokeWidth="2" />
                  <text className="node-text" y="-2">Service A</text>
                  <text className="node-text" y="12" style={{ fontSize: '9px', fill: 'var(--accent-blue)' }}>Port 8080</text>
                  <text className="node-subtext" y="40">Go / gRPC</text>
                </g>

                {/* Service B */}
                <g className="svg-node" transform="translate(440, 175)">
                  <circle r="28" fill="#12131a" stroke={statuses.serviceB.status === 'UP' ? 'var(--status-up)' : 'rgba(255,255,255,0.1)'} strokeWidth="2" />
                  <text className="node-text" y="-2">Service B</text>
                  <text className="node-text" y="12" style={{ fontSize: '9px', fill: 'var(--accent-blue)' }}>Port 8081</text>
                  <text className="node-subtext" y="40">Go Core</text>
                </g>
              </svg>
            </div>
          </section>
        </div>

        {/* Right Side: Interactive Actions & Logs Terminal */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Action Panel */}
          <section className="glass-card">
            <h2 className="card-title">
              <span>🚀</span> Dispatch Flow Request
            </h2>
            <div className="action-cards">
              
              {/* Inputs */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.5rem' }}>
                <div className="form-group">
                  <label>Client Payload Name</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    value={nameInput} 
                    onChange={(e) => setNameInput(e.target.value)} 
                  />
                </div>
                <div className="form-group">
                  <label>Custom Correlation ID (Optional)</label>
                  <input 
                    type="text" 
                    placeholder="Auto-generated if blank" 
                    className="form-control" 
                    value={customCorrelationId} 
                    onChange={(e) => setCustomCorrelationId(e.target.value)} 
                  />
                </div>
              </div>

              {/* Grid of Action Buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                
                {/* Service A flow */}
                <div className="action-card">
                  <div className="action-card-header">
                    <h3>HTTP Pipeline: Service A ➔ Service B</h3>
                    <span className="badge http">HTTP</span>
                  </div>
                  <button 
                    className="btn-primary" 
                    disabled={loading || statuses.serviceA.status === 'DOWN'}
                    onClick={() => handleServiceCall('serviceA', '/api/hello')}
                  >
                    {loading ? 'Processing...' : 'Send HTTP Request to Service A'}
                  </button>
                </div>

                {/* Service C flow */}
                <div className="action-card">
                  <div className="action-card-header">
                    <h3>gRPC Pipeline: Service C ➔ Service A ➔ Service B</h3>
                    <span className="badge grpc">gRPC Link</span>
                  </div>
                  <button 
                    className="btn-primary" 
                    disabled={loading || statuses.serviceC.status === 'DOWN'}
                    onClick={() => handleServiceCall('serviceC', '/call-grpc')}
                  >
                    {loading ? 'Processing...' : 'Send gRPC Flow via Service C'}
                  </button>
                </div>

                {/* Service D flow */}
                <div className="action-card">
                  <div className="action-card-header">
                    <h3>gRPC Pipeline: Service D ➔ Service A ➔ Service B</h3>
                    <span className="badge grpc">gRPC Link</span>
                  </div>
                  <button 
                    className="btn-primary" 
                    disabled={loading || statuses.serviceD.status === 'DOWN'}
                    onClick={() => handleServiceCall('serviceD', '/call-grpc')}
                  >
                    {loading ? 'Processing...' : 'Send gRPC Flow via Service D'}
                  </button>
                </div>

              </div>

            </div>
          </section>

          {/* Real-time terminal console */}
          <section className="terminal-container">
            <div className="terminal-header">
              <div className="terminal-dots">
                <span className="dot red"></span>
                <span className="dot yellow"></span>
                <span className="dot green"></span>
              </div>
              <span className="terminal-title">trace-output.log</span>
              <div style={{ width: '40px' }}></div>
            </div>
            
            <div className="terminal-body">
              {logs.length === 0 ? (
                <div className="console-placeholder">
                  <span style={{ fontSize: '2rem' }}>📟</span>
                  <p>Awaiting execution dispatches...</p>
                  <p style={{ fontSize: '0.75rem', opacity: 0.7 }}>Trigger any request card above to log runtime details</p>
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="log-entry">
                    <div className="log-meta">
                      [{log.timestamp}] {log.service} ➔ {log.method} {log.statusCode ? `(${log.statusCode})` : ''} - {log.elapsedMs > 0 ? `${log.elapsedMs}ms` : 'pending'}
                    </div>
                    <pre className={`log-body ${log.type}`}>
                      {log.body}
                    </pre>
                  </div>
                ))
              )}
            </div>

            {latestCorrelationId && (
              <div className="correlation-box">
                <div className="correlation-header">
                  <span>Track Logs in Grafana Loki</span>
                  <span>Correlation ID</span>
                </div>
                <div className="correlation-val-row">
                  <span className="correlation-val">{latestCorrelationId}</span>
                  <button className="copy-btn" onClick={() => copyToClipboard(latestCorrelationId)}>
                    Copy ID
                  </button>
                </div>
                <span className="correlation-desc">
                  Use query `{`{container=~"service-.*"} | json | correlation_id="${latestCorrelationId}"`}` in Loki to trace the logs across all containers.
                </span>
              </div>
            )}
          </section>

        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Connection Endpoint Configuration</h2>
              <button className="close-btn" onClick={() => setShowSettings(false)}>×</button>
            </div>
            <SettingsForm endpoints={endpoints} onSave={saveSettings} onClose={() => setShowSettings(false)} />
          </div>
        </div>
      )}
    </div>
  );
}

interface SettingsFormProps {
  endpoints: Endpoints;
  onSave: (urls: Endpoints) => void;
  onClose: () => void;
}

function SettingsForm({ endpoints, onSave, onClose }: SettingsFormProps) {
  const [urls, setUrls] = useState<Endpoints>({ ...endpoints });

  const handleChange = (key: keyof Endpoints, val: string) => {
    setUrls(prev => ({ ...prev, [key]: val }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
      <div className="form-group">
        <label>Service A Base URL (Go API)</label>
        <input 
          type="text" 
          className="form-control" 
          value={urls.serviceA} 
          onChange={(e) => handleChange('serviceA', e.target.value)} 
        />
      </div>
      <div className="form-group">
        <label>Service B Base URL (Go Core)</label>
        <input 
          type="text" 
          className="form-control" 
          value={urls.serviceB} 
          onChange={(e) => handleChange('serviceB', e.target.value)} 
        />
      </div>
      <div className="form-group">
        <label>Service C Base URL (TS / Express)</label>
        <input 
          type="text" 
          className="form-control" 
          value={urls.serviceC} 
          onChange={(e) => handleChange('serviceC', e.target.value)} 
        />
      </div>
      <div className="form-group">
        <label>Service D Base URL (Python / Flask)</label>
        <input 
          type="text" 
          className="form-control" 
          value={urls.serviceD} 
          onChange={(e) => handleChange('serviceD', e.target.value)} 
        />
      </div>
      
      <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
        <button className="btn-primary" onClick={() => onSave(urls)}>
          Save Endpoints
        </button>
        <button 
          className="btn-primary" 
          style={{ background: 'transparent', border: '1px solid var(--card-border)', color: 'var(--text-primary)', boxShadow: 'none' }}
          onClick={onClose}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
