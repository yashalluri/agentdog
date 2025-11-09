import React, { useState, useEffect } from 'react';
import '@/App.css';
import axios from 'axios';
import { Search, Play, Sparkles, Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Toaster, toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runSteps, setRunSteps] = useState([]);
  const [selectedStep, setSelectedStep] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTime, setFilterTime] = useState('all');
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showFullPrompt, setShowFullPrompt] = useState(false);
  const [showFullOutput, setShowFullOutput] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Fetch runs on mount
  useEffect(() => {
    fetchRuns();
  }, []);

  // Poll for updates when a run is selected and status is running
  useEffect(() => {
    if (selectedRun && selectedRun.status === 'running') {
      const interval = setInterval(() => {
        fetchRunDetails(selectedRun.id);
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
    setSummary(null);
    fetchRunDetails(run.id);
    // Close sidebar on mobile after selection
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  const handleStepClick = (step) => {
    setSelectedStep(step);
    setShowFullPrompt(false);
    setShowFullOutput(false);
    fetchStepDetail(step.id);
  };

  const handleReplayStep = async (stepId) => {
    try {
      await axios.post(`${API}/step/${stepId}/replay`);
      toast.success('Step replay initiated');
      setTimeout(() => fetchRunDetails(selectedRun.id), 1500);
    } catch (error) {
      toast.error('Failed to replay step');
    }
  };

  const handleGenerateSummary = async () => {
    if (!selectedRun) return;
    setLoading(true);
    try {
      const response = await axios.post(`${API}/summary/${selectedRun.id}`);
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
      await axios.post(`${API}/ingest-sample`);
      toast.success('Sample data ingested');
      fetchRuns();
    } catch (error) {
      toast.error('Failed to ingest sample data');
    }
  };

  const filteredRuns = runs.filter(run => {
    const matchesSearch = run.title.toLowerCase().includes(searchQuery.toLowerCase());
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

  return (
    <div className="app-container" data-testid="agentlens-app">
      <Toaster position="top-right" />
      
      {/* Top Navigation */}
      <div className="top-nav" data-testid="top-nav">
        <div className="nav-logo-container">
          <div className="nav-logo" data-testid="nav-logo">AgentLens</div>
          <div className="nav-tagline" data-testid="nav-tagline">Datadog for AI agents</div>
        </div>
        <div className="nav-actions">
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

      {/* Main Layout */}
      <div className="main-layout">
        {/* Left Sidebar - Runs List */}
        <div className="sidebar" data-testid="runs-sidebar">
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
                  key={run.id}
                  className={`run-item ${selectedRun?.id === run.id ? 'active' : ''}`}
                  onClick={() => handleRunClick(run)}
                  data-testid={`run-item-${run.id}`}
                >
                  <div className="run-item-header">
                    <div className={`status-dot ${getStatusDot(run.status)}`} data-testid={`status-dot-${run.status}`}></div>
                    <div className="run-item-title" data-testid="run-item-title">{run.title}</div>
                  </div>
                  <div className="run-item-meta" data-testid="run-item-meta">
                    {run.num_steps} steps • {run.num_failed > 0 ? `${run.num_failed} error` : 'no errors'}
                  </div>
                </div>
              ))
            )}
          </ScrollArea>
        </div>

        {/* Main Panel - Run Detail */}
        <div className="main-panel" data-testid="main-panel">
          {!selectedRun ? (
            <div className="empty-main" data-testid="empty-main">
              <p>Select a run to view details</p>
            </div>
          ) : (
            <div className="run-detail" data-testid="run-detail">
              {/* Run Header */}
              <div className="run-header" data-testid="run-header">
                <div>
                  <h2 className="run-title" data-testid="run-title">Run: {selectedRun.title}</h2>
                  <p className="run-subtitle" data-testid="run-subtitle">
                    Started {new Date(selectedRun.start_time).toLocaleTimeString()} • {selectedRun.num_steps} agents • 
                    {selectedRun.num_failed > 0 ? ` ${selectedRun.num_failed} failed • ` : ' '}
                    ${selectedRun.cost.toFixed(3)}
                  </p>
                </div>
                <Badge
                  variant={selectedRun.status === 'success' ? 'success' : selectedRun.status === 'error' ? 'destructive' : 'secondary'}
                  className="status-badge"
                  data-testid="run-status-badge"
                >
                  {selectedRun.status.toUpperCase()}
                </Badge>
              </div>

              {/* Metrics Row */}
              <div className="metrics-row" data-testid="metrics-row">
                <div className="metric-card" data-testid="metric-steps">
                  <div className="metric-label">STEPS</div>
                  <div className="metric-value">{selectedRun.num_steps}</div>
                </div>
                <div className="metric-card" data-testid="metric-succeeded">
                  <div className="metric-label">SUCCEEDED</div>
                  <div className="metric-value">{selectedRun.num_success}</div>
                </div>
                <div className="metric-card" data-testid="metric-failed">
                  <div className="metric-label">FAILED</div>
                  <div className="metric-value">{selectedRun.num_failed}</div>
                </div>
                <div className="metric-card" data-testid="metric-duration">
                  <div className="metric-label">DURATION</div>
                  <div className="metric-value">{selectedRun.duration}s</div>
                </div>
                <div className="metric-card" data-testid="metric-cost">
                  <div className="metric-label">COST</div>
                  <div className="metric-value">${selectedRun.cost.toFixed(3)}</div>
                </div>
              </div>

              {/* Agent Flow Tree */}
              <div className="agent-flow" data-testid="agent-flow">
                <h3 className="section-title">Agent Flow</h3>
                <div className="flow-tree">
                  {runSteps.map((step) => (
                    <div
                      key={step.id}
                      className={`flow-item ${selectedStep?.id === step.id ? 'selected' : ''}`}
                      onClick={() => handleStepClick(step)}
                      data-testid={`flow-item-${step.id}`}
                    >
                      <div className="flow-item-left">
                        <div className={`status-dot ${getStatusDot(step.status)}`} data-testid={`flow-status-${step.status}`}></div>
                        <div>
                          <div className="flow-item-name" data-testid="flow-item-name">{step.name}</div>
                          {step.status === 'error' && (
                            <button className="view-error-link" data-testid="view-error-link">View error</button>
                          )}
                        </div>
                      </div>
                      <div className="flow-item-right">
                        <span className="flow-metric" data-testid="flow-latency">{step.latency_ms}ms</span>
                        <span className="flow-metric" data-testid="flow-cost">${step.cost.toFixed(3)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* AI Summary Section */}
              {summary && (
                <div className="summary-section" data-testid="summary-section">
                  <h3 className="section-title">AI Summary (Claude Sonnet 4)</h3>
                  <div className="summary-content" data-testid="summary-content">
                    {summary}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Drawer - Agent Detail */}
        {selectedStep && (
          <div className="right-drawer" data-testid="right-drawer">
            <div className="drawer-header" data-testid="drawer-header">
              <div className="drawer-header-content">
                <div>
                  <h3 className="drawer-title" data-testid="drawer-title">{selectedStep.name}</h3>
                  <p className="drawer-subtitle" data-testid="drawer-subtitle">
                    {selectedStep.start_time || `Step ID: ${selectedStep.id.substring(0, 8)}`}
                  </p>
                </div>
                <Badge
                  variant={selectedStep.status === 'success' ? 'success' : selectedStep.status === 'error' ? 'destructive' : 'secondary'}
                  data-testid="drawer-status-badge"
                >
                  {selectedStep.status}
                </Badge>
              </div>
              <button 
                className="drawer-close" 
                onClick={() => setSelectedStep(null)}
                aria-label="Close drawer"
              >
                ×
              </button>
            </div>

            <div className="drawer-content">
              <div className="drawer-section">
                <div className="drawer-section-label" data-testid="prompt-label">Prompt</div>
                <div className="code-block" data-testid="prompt-content">
                  {showFullPrompt || (selectedStep.prompt && selectedStep.prompt.length <= 150)
                    ? selectedStep.prompt
                    : `${selectedStep.prompt?.substring(0, 150)}...`}
                </div>
                {selectedStep.prompt && selectedStep.prompt.length > 150 && (
                  <button 
                    className="show-more-button"
                    onClick={() => setShowFullPrompt(!showFullPrompt)}
                  >
                    {showFullPrompt ? 'Show less' : 'Show more'}
                  </button>
                )}
              </div>

              <div className="drawer-section">
                <div className="drawer-section-label" data-testid="output-label">Output</div>
                <div className="code-block" data-testid="output-content">
                  {showFullOutput || (selectedStep.output && selectedStep.output.length <= 150)
                    ? selectedStep.output
                    : `${selectedStep.output?.substring(0, 150)}...`}
                </div>
                {selectedStep.output && selectedStep.output.length > 150 && (
                  <button 
                    className="show-more-button"
                    onClick={() => setShowFullOutput(!showFullOutput)}
                  >
                    {showFullOutput ? 'Show less' : 'Show more'}
                  </button>
                )}
              </div>

              <div className="drawer-section">
                <div className="drawer-section-label" data-testid="diagnostics-label">Diagnostics</div>
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
                    <div className="diagnostic-value" data-testid="diagnostic-stepid">{selectedStep.id.substring(0, 10)}...</div>
                  </div>
                  {selectedStep.parent_step_id && (
                    <div className="diagnostic-item">
                      <div className="diagnostic-label">Parent</div>
                      <div className="diagnostic-value" data-testid="diagnostic-parent">
                        {runSteps.find(s => s.id === selectedStep.parent_step_id)?.name || 'N/A'}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="drawer-actions">
                <Button
                  onClick={() => handleReplayStep(selectedStep.id)}
                  className="replay-button"
                  data-testid="replay-step-btn"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Replay step
                </Button>
                <Button
                  variant="ghost"
                  className="insight-button"
                  data-testid="generate-insight-btn"
                >
                  Generate insight
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;