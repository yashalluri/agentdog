import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing';
import Signup from './pages/Signup';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import { authService } from './utils/auth';
import '@/App.css';
// Protected Route wrapper
function ProtectedRoute({ children }) {
  return authService.isAuthenticated() ? children : <Navigate to="/login" />;
}

function App() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runSteps, setRunSteps] = useState([]);
  const [selectedStep, setSelectedStep] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTime, setFilterTime] = useState('all');
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [ingestionUrl, setIngestionUrl] = useState('/api/agentdog/event');
  const [currentView, setCurrentView] = useState('runs'); // 'runs' or 'overview'

  // Fetch runs on mount
  useEffect(() => {
    fetchRuns();
  }, []);

  // Poll for updates when a run is selected and status is running
  useEffect(() => {
    if (selectedRun && selectedRun.status === 'running') {
      const interval = setInterval(() => {
        fetchRunDetails(selectedRun.run_id);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [selectedRun]);

  const fetchRuns = async () => {
    try {
      const response = await axios.get(`${API}/runs`);
      setRuns(response.data);
    } catch (error) {
      console.error('Error fetching runs:', error);
    }
  };

  const fetchRunDetails = async (runId) => {
    try {
      const [runRes, stepsRes] = await Promise.all([
        axios.get(`${API}/run/${runId}`),
        axios.get(`${API}/run/${runId}/steps`)
      ]);
      setSelectedRun(runRes.data);
      setRunSteps(stepsRes.data);
    } catch (error) {
      console.error('Error fetching run details:', error);
    }
  };

  const fetchStepDetail = async (stepId) => {
    try {
      const response = await axios.get(`${API}/step/${stepId}`);
      setSelectedStep(response.data);
    } catch (error) {
      console.error('Error fetching step details:', error);
    }
  };

  const handleRunClick = (run) => {
    setSelectedRun(run);
    setSummary(run.summary || null);
    setCurrentView('runs');
    fetchRunDetails(run.run_id);
  };

  const handleStepClick = (step) => {
    setSelectedStep(step);
    fetchStepDetail(step.id);
  };

  const handleGenerateSummary = async () => {
    if (!selectedRun) return;
    setLoading(true);
    try {
      const response = await axios.post(`${API}/summary/${selectedRun.run_id}`);
      setSummary(response.data.summary);
      toast.success('Summary generated');
    } catch (error) {
      toast.error('Failed to generate summary');
      console.error('Summary error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleIngestSample = async () => {
    try {
      const runId = `sample-${Date.now()}`;
      const sampleSteps = [
        {
          run_id: runId,
          agent_name: 'collector',
          parent_step_id: null,
          status: 'success',
          prompt: 'Collect documents from sources A, B, C',
          output: '3 documents collected successfully',
          latency_ms: 210,
          cost: 0.002,
          tokens: 320,
          claimed_actions: ['used:mcp-docs'],
          actual_actions: ['used:mcp-docs']
        },
        {
          run_id: runId,
          agent_name: 'summarizer-1',
          parent_step_id: 'collector',
          status: 'success',
          prompt: 'Summarize document 1',
          output: 'Summary: Key insights extracted',
          latency_ms: 330,
          cost: 0.003,
          tokens: 280,
          claimed_actions: [],
          actual_actions: []
        },
        {
          run_id: runId,
          agent_name: 'summarizer-2',
          parent_step_id: 'collector',
          status: 'error',
          prompt: 'Summarize document 2',
          output: 'Error occurred during processing',
          latency_ms: 180,
          cost: 0.001,
          tokens: 150,
          claimed_actions: ['used:mcp-tools'],
          actual_actions: [],
          error_message: 'Simulated timeout error'
        },
        {
          run_id: runId,
          agent_name: 'summarizer-2-retry',
          parent_step_id: 'summarizer-2',
          status: 'success',
          prompt: 'Retry summarize document 2 with shorter context',
          output: 'Successfully generated shorter summary',
          latency_ms: 190,
          cost: 0.002,
          tokens: 180,
          claimed_actions: [],
          actual_actions: []
        },
        {
          run_id: runId,
          agent_name: 'synthesizer',
          parent_step_id: 'collector',
          status: 'success',
          prompt: 'Combine all summaries into final report',
          output: 'Final comprehensive report generated',
          latency_ms: 420,
          cost: 0.003,
          tokens: 340,
          claimed_actions: [],
          actual_actions: []
        }
      ];

      const url = ingestionUrl.startsWith('http') ? ingestionUrl : `${BACKEND_URL}${ingestionUrl}`;
      
      for (const step of sampleSteps) {
        await axios.post(url, step);
      }

      toast.success('Sample data ingested');
      await fetchRuns();
    } catch (error) {
      toast.error('Failed to ingest sample data');
      console.error('Ingest error:', error);
    }
  };

  const filteredRuns = runs.filter(run => {
    const matchesSearch = run.run_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const getStatusDot = (status) => {
    switch (status) {
      case 'success': return 'bg-green-500';
      case 'error': return 'bg-red-500';
      case 'running': return 'bg-yellow-500 animate-pulse';
      default: return 'bg-gray-500';
    }
  };

  const getIntegrityBadge = (score) => {
    if (score >= 0.9) return { variant: 'success', text: 'High' };
    if (score >= 0.7) return { variant: 'warning', text: 'Medium' };
    return { variant: 'destructive', text: 'Low' };
  };

  // Build hierarchical tree from flat steps
  const buildTree = (steps) => {
    const stepMap = {};
    const roots = [];

    steps.forEach(step => {
      stepMap[step.agent_name] = { ...step, children: [] };
    });

    steps.forEach(step => {
      if (step.parent_step_id) {
        const parent = stepMap[step.parent_step_id];
        if (parent) {
          parent.children.push(stepMap[step.agent_name]);
        } else {
          roots.push(stepMap[step.agent_name]);
        }
      } else {
        roots.push(stepMap[step.agent_name]);
      }
    });

    return roots;
  };

  const renderTree = (nodes, depth = 0) => {
    return nodes.map((node) => (
      <div key={node.id}>
        <div
          className={`flow-item ${selectedStep?.id === node.id ? 'selected' : ''}`}
          style={{ paddingLeft: `${depth * 16 + 16}px` }}
          onClick={() => handleStepClick(node)}
          data-testid={`flow-item-${node.id}`}
        >
          <div className="flow-item-left">
            <div className={`status-dot ${getStatusDot(node.status)}`} data-testid={`flow-status-${node.status}`}></div>
            <div>
              <div className="flow-item-name" data-testid="flow-item-name">{node.agent_name}</div>
              {node.status === 'error' && node.error_message && (
                <div className="error-text">{node.error_message}</div>
              )}
            </div>
          </div>
          <div className="flow-item-right">
            <span className="flow-metric" data-testid="flow-latency">{node.latency_ms}ms</span>
            <span className="flow-metric" data-testid="flow-cost">${node.cost.toFixed(3)}</span>
          </div>
        </div>
        {node.children && node.children.length > 0 && renderTree(node.children, depth + 1)}
      </div>
    ));
  };

  const OverviewTab = () => {
    // Calculate stats from runs
    const successCount = runs.filter(r => r.status === 'success').length;
    const errorCount = runs.filter(r => r.status === 'error').length;
    const avgDuration = runs.length > 0 
      ? (runs.reduce((sum, r) => sum + r.duration_ms, 0) / runs.length / 1000).toFixed(2)
      : 0;
    const totalCost = runs.reduce((sum, r) => sum + r.cost, 0).toFixed(3);

    const statusData = [
      { name: 'Success', value: successCount, color: '#22C55E' },
      { name: 'Error', value: errorCount, color: '#EF4444' }
    ];

    const runsOverTime = runs.slice(0, 10).reverse().map((r, i) => ({
      name: `Run ${i + 1}`,
      duration: (r.duration_ms / 1000).toFixed(2),
      cost: r.cost
    }));

    return (
      <div className="overview-container" data-testid="overview-tab">
        <h2 className="overview-title">System Overview</h2>
        
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">TOTAL RUNS</div>
            <div className="stat-value">{runs.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">SUCCESS RATE</div>
            <div className="stat-value">
              {runs.length > 0 ? Math.round((successCount / runs.length) * 100) : 0}%
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">AVG DURATION</div>
            <div className="stat-value">{avgDuration}s</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">TOTAL COST</div>
            <div className="stat-value">${totalCost}</div>
          </div>
        </div>

        <div className="charts-grid">
          <div className="chart-card">
            <h3 className="chart-title">Success vs Error</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={statusData} dataKey="value" cx="50%" cy="50%" outerRadius={60}>
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-card">
            <h3 className="chart-title">Recent Run Durations</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={runsOverTime}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="duration" fill="#2563EB" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="app-container" data-testid="agentdog-app">
      <Toaster position="top-right" />
      
      {/* Top Navigation */}
      <div className="top-nav" data-testid="top-nav">
        <div className="nav-logo-container">
          <div className="nav-logo" data-testid="nav-logo">AgentDog</div>
          <div className="nav-tagline" data-testid="nav-tagline">Datadog for AI agents</div>
        </div>
        <div className="nav-actions">
          <Button
            variant="ghost"
            onClick={() => setShowSettings(true)}
            className="nav-button"
            data-testid="settings-btn"
          >
            <Settings className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            onClick={handleGenerateSummary}
            disabled={!selectedRun || loading}
            className="nav-button"
            data-testid="generate-summary-btn"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Generate AI Summary
          </Button>
          <Button
            onClick={handleIngestSample}
            className="nav-button-primary"
            data-testid="ingest-sample-btn"
          >
            Ingest Sample Run
          </Button>
        </div>
      </div>

      {/* Settings Modal */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="settings-modal">
          <DialogHeader>
            <DialogTitle>Agent Ingestion Settings</DialogTitle>
          </DialogHeader>
          <div className="settings-content">
            <Label htmlFor="ingestion-url">Ingestion URL</Label>
            <Input
              id="ingestion-url"
              value={ingestionUrl}
              onChange={(e) => setIngestionUrl(e.target.value)}
              placeholder="/api/agentdog/event"
              data-testid="ingestion-url-input"
            />
            <p className="settings-hint">
              Full URL: <code>{BACKEND_URL}{ingestionUrl}</code>
            </p>
            
            <div className="usage-examples">
              <h4 className="usage-title">Quick Start - LangGraph</h4>
              <pre className="code-example">{`from agentdog_client import AgentDogClient
from agentdog_langgraph import agentdog_node

agentdog = AgentDogClient(
    "${BACKEND_URL}${ingestionUrl}",
    run_id="my-run-1"
)

@agentdog_node(agentdog, "collector")
def collector(state):
    return {"docs": ["doc1", "doc2"]}

# Run your graph - telemetry auto-sent!`}</pre>

              <h4 className="usage-title">Manual Integration</h4>
              <pre className="code-example">{`agentdog.log_step(
    agent_name="my_agent",
    status="success",
    prompt="User query",
    output="Response text",
    latency_ms=150
)`}</pre>
            </div>
            
            <Button onClick={() => setShowSettings(false)} className="mt-4" data-testid="settings-save-btn">
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Main Layout */}
      <div className="main-layout">
        {/* Left Sidebar */}
        <div className="sidebar" data-testid="runs-sidebar">
          <Tabs value={currentView} onValueChange={setCurrentView} className="sidebar-tabs">
            <TabsList className="tabs-list">
              <TabsTrigger value="runs" data-testid="tab-runs">Runs</TabsTrigger>
              <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
            </TabsList>
          </Tabs>

          {currentView === 'runs' && (
            <>
              <div className="sidebar-search">
                <Search className="search-icon" />
                <input
                  type="text"
                  placeholder="Search runs..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="search-input"
                  data-testid="search-runs-input"
                />
              </div>

              <div className="filter-pills">
                <button
                  className={`filter-pill ${filterTime === 'today' ? 'active' : ''}`}
                  onClick={() => setFilterTime('today')}
                  data-testid="filter-today"
                >
                  Today
                </button>
                <button
                  className={`filter-pill ${filterTime === '24h' ? 'active' : ''}`}
                  onClick={() => setFilterTime('24h')}
                  data-testid="filter-24h"
                >
                  24h
                </button>
                <button
                  className={`filter-pill ${filterTime === 'all' ? 'active' : ''}`}
                  onClick={() => setFilterTime('all')}
                  data-testid="filter-all"
                >
                  All
                </button>
              </div>

              <ScrollArea className="runs-list">
                {filteredRuns.length === 0 ? (
                  <div className="empty-state" data-testid="empty-state">
                    <p>No runs yet</p>
                    <p className="empty-subtitle">Ingest sample run to get started</p>
                  </div>
                ) : (
                  filteredRuns.map((run) => (
                    <div
                      key={run.run_id}
                      className={`run-item ${selectedRun?.run_id === run.run_id ? 'active' : ''}`}
                      onClick={() => handleRunClick(run)}
                      data-testid={`run-item-${run.run_id}`}
                    >
                      <div className="run-item-header">
                        <div className={`status-dot ${getStatusDot(run.status)}`} data-testid={`status-dot-${run.status}`}></div>
                        <div className="run-item-title" data-testid="run-item-title">{run.run_id}</div>
                      </div>
                      <div className="run-item-meta" data-testid="run-item-meta">
                        {run.total_steps} steps • {run.failed_steps > 0 ? `${run.failed_steps} error` : 'no errors'}
                      </div>
                    </div>
                  ))
                )}
              </ScrollArea>
            </>
          )}
        </div>

        {/* Main Panel */}
        <div className="main-panel" data-testid="main-panel">
          {currentView === 'overview' ? (
            <OverviewTab />
          ) : !selectedRun ? (
            <div className="empty-main" data-testid="empty-main">
              <p>Select a run to view details</p>
            </div>
          ) : (
            <div className="run-detail" data-testid="run-detail">
              {/* Run Header */}
              <div className="run-header-block">
                <div className="run-header" data-testid="run-header">
                  <div>
                    <h2 className="run-title" data-testid="run-title">Run: {selectedRun.run_id}</h2>
                  </div>
                  <Badge
                    variant={selectedRun.status === 'success' ? 'success' : selectedRun.status === 'error' ? 'destructive' : 'secondary'}
                    className="status-badge"
                    data-testid="run-status-badge"
                  >
                    {selectedRun.status.toUpperCase()}
                  </Badge>
                </div>
                <p className="run-subtitle" data-testid="run-subtitle">
                  Started {new Date(selectedRun.created_at).toLocaleString()} • {selectedRun.total_steps} agents • 
                  {selectedRun.failed_steps > 0 ? ` ${selectedRun.failed_steps} failed • ` : ' '}
                  ${selectedRun.cost.toFixed(3)}
                </p>
              </div>

              {/* Metrics Row */}
              <div className="metrics-row" data-testid="metrics-row">
                <div className="metric-card" data-testid="metric-steps">
                  <div className="metric-label">STEPS</div>
                  <div className="metric-value">{selectedRun.total_steps}</div>
                </div>
                <div className="metric-card" data-testid="metric-succeeded">
                  <div className="metric-label">SUCCEEDED</div>
                  <div className="metric-value">{selectedRun.success_steps}</div>
                </div>
                <div className="metric-card" data-testid="metric-failed">
                  <div className="metric-label">FAILED</div>
                  <div className="metric-value">{selectedRun.failed_steps}</div>
                </div>
                <div className="metric-card" data-testid="metric-duration">
                  <div className="metric-label">DURATION</div>
                  <div className="metric-value">{(selectedRun.duration_ms / 1000).toFixed(2)}s</div>
                </div>
                <div className="metric-card" data-testid="metric-cost">
                  <div className="metric-label">COST</div>
                  <div className="metric-value">${selectedRun.cost.toFixed(3)}</div>
                </div>
                <div className="metric-card" data-testid="metric-integrity">
                  <div className="metric-label">INTEGRITY</div>
                  <div className="metric-value integrity-score">
                    {selectedRun.integrity_score.toFixed(2)}
                    <Badge 
                      variant={getIntegrityBadge(selectedRun.integrity_score).variant}
                      className="integrity-badge"
                    >
                      {getIntegrityBadge(selectedRun.integrity_score).text}
                    </Badge>
                  </div>
                </div>
              </div>

              {/* Agent Flow Tree */}
              <div className="agent-flow" data-testid="agent-flow">
                <h3 className="section-title">AGENT FLOW</h3>
                <div className="flow-tree">
                  {runSteps.length > 0 ? renderTree(buildTree(runSteps)) : <p>No steps yet</p>}
                </div>
              </div>

              {/* AI Summary */}
              {summary && (
                <div className="summary-section" data-testid="summary-section">
                  <h3 className="section-title">AI SUMMARY (CLAUDE SONNET 4)</h3>
                  <div className="summary-content" data-testid="summary-content">
                    {summary}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Drawer */}
        {selectedStep && currentView === 'runs' && (
          <div className="right-drawer" data-testid="right-drawer">
            <div className="drawer-header" data-testid="drawer-header">
              <div>
                <h3 className="drawer-title" data-testid="drawer-title">{selectedStep.agent_name}</h3>
                <p className="drawer-subtitle" data-testid="drawer-subtitle">
                  Step ID: {selectedStep.id.substring(0, 8)}
                </p>
              </div>
              <Badge
                variant={selectedStep.status === 'success' ? 'success' : selectedStep.status === 'error' ? 'destructive' : 'secondary'}
                data-testid="drawer-status-badge"
              >
                {selectedStep.status}
              </Badge>
            </div>

            <div className="drawer-content">
              <div className="drawer-section">
                <div className="drawer-section-label" data-testid="prompt-label">PROMPT</div>
                <div className="code-block" data-testid="prompt-content">
                  {selectedStep.prompt}
                </div>
              </div>

              <div className="drawer-section">
                <div className="drawer-section-label" data-testid="output-label">OUTPUT</div>
                <div className="code-block" data-testid="output-content">
                  {selectedStep.output}
                </div>
              </div>

              {selectedStep.hallucination_flags && selectedStep.hallucination_flags.length > 0 && (
                <div className="drawer-section">
                  <div className="drawer-section-label">HALLUCINATION FLAGS</div>
                  <div className="hallucination-flags">
                    {selectedStep.hallucination_flags.map((flag, i) => (
                      <Badge key={i} variant="destructive" className="hallucination-badge">
                        <AlertTriangle className="w-3 h-3 mr-1" />
                        {flag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <div className="drawer-section">
                <div className="drawer-section-label" data-testid="diagnostics-label">DIAGNOSTICS</div>
                <div className="diagnostics-grid">
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Tokens</div>
                    <div className="diagnostic-value" data-testid="diagnostic-tokens">{selectedStep.tokens}</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Cost</div>
                    <div className="diagnostic-value" data-testid="diagnostic-cost">${selectedStep.cost.toFixed(3)}</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Latency</div>
                    <div className="diagnostic-value" data-testid="diagnostic-latency">{selectedStep.latency_ms}ms</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Step ID</div>
                    <div className="diagnostic-value" data-testid="diagnostic-stepid">{selectedStep.id.substring(0, 12)}...</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
