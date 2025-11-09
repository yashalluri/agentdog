import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Search, Play, Sparkles, Settings, LogOut, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Toaster, toast } from 'sonner';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { authService } from '../utils/auth';
import '../App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runSteps, setRunSteps] = useState([]);
  const [selectedStep, setSelectedStep] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTime, setFilterTime] = useState('all');
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [currentView, setCurrentView] = useState('runs');

  // Load current user
  useEffect(() => {
    loadUser();
  }, []);

  // Fetch runs on mount
  useEffect(() => {
    if (user) {
      fetchRuns();
    }
  }, [user]);

  // Poll for updates
  useEffect(() => {
    if (selectedRun && selectedRun.status === 'running') {
      const interval = setInterval(() => {
        fetchRunDetails(selectedRun.run_id);
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [selectedRun]);

  const loadUser = async () => {
    const currentUser = await authService.getCurrentUser();
    if (!currentUser) {
      navigate('/login');
      return;
    }
    setUser(currentUser);
  };

  const handleLogout = () => {
    authService.logout();
    navigate('/');
  };

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
    } finally {
      setLoading(false);
    }
  };

  const handleIngestSample = async () => {
    if (!user) return;
    
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
          output: 'Error occurred. I have completed the task successfully.',
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
          prompt: 'Retry summarize document 2',
          output: 'Successfully generated summary',
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
          prompt: 'Combine all summaries',
          output: 'Final report generated',
          latency_ms: 420,
          cost: 0.003,
          tokens: 340,
          claimed_actions: [],
          actual_actions: []
        }
      ];

      const url = `${BACKEND_URL}/api/agentdog/event?key=${user.ingestion_key}`;
      
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
        >
          <div className="flow-item-left">
            <div className={`status-dot ${getStatusDot(node.status)}`}></div>
            <div>
              <div className="flow-item-name">{node.agent_name}</div>
              {node.status === 'error' && node.error_message && (
                <div className="error-text">{node.error_message}</div>
              )}
            </div>
          </div>
          <div className="flow-item-right">
            <span className="flow-metric">{node.latency_ms}ms</span>
            <span className="flow-metric">${node.cost.toFixed(3)}</span>
          </div>
        </div>
        {node.children && node.children.length > 0 && renderTree(node.children, depth + 1)}
      </div>
    ));
  };

  if (!user) {
    return <div>Loading...</div>;
  }

  const ingestionUrl = `${window.location.origin}/api/agentdog/event?key=${user.ingestion_key}`;

  return (
    <div className="app-container">
      <Toaster position="top-right" />
      
      {/* Top Navigation */}
      <div className="top-nav">
        <div className="nav-logo-container">
          <div className="nav-logo">AgentDog</div>
          <div className="nav-tagline">Datadog for AI agents</div>
        </div>
        <div className="nav-actions">
          <Button
            variant="ghost"
            onClick={() => setShowSettings(true)}
            className="nav-button"
          >
            <Settings className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            onClick={handleGenerateSummary}
            disabled={!selectedRun || loading}
            className="nav-button"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Generate AI Summary
          </Button>
          <Button
            onClick={handleIngestSample}
            className="nav-button-primary"
          >
            Ingest Sample Run
          </Button>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="user-avatar">
                <User className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <div className="user-info">
                <div className="user-name">{user.name}</div>
                <div className="user-email">{user.email}</div>
              </div>
              <DropdownMenuItem onClick={() => setShowSettings(true)}>
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-2" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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
              readOnly
              onClick={(e) => e.target.select()}
            />
            <p className="settings-hint">
              Point your multi-agent system to this URL
            </p>
            
            <div className="usage-examples">
              <h4 className="usage-title">Quick Start - LangGraph</h4>
              <pre className="code-example">{`from agentdog_client import AgentDogClient
from agentdog_langgraph import agentdog_node

agentdog = AgentDogClient(
    "${ingestionUrl}",
    run_id="my-run-1"
)

@agentdog_node(agentdog, "collector")
def collector(state):
    return {"docs": ["doc1", "doc2"]}`}</pre>

              <h4 className="usage-title">Manual Integration</h4>
              <pre className="code-example">{`import requests

requests.post("${ingestionUrl}", json={
    "run_id": "support-run-1",
    "agent_name": "retriever",
    "status": "success",
    "prompt": "Retrieve tickets",
    "output": "Found 5 tickets",
    "latency_ms": 210,
    "cost": 0.001
})`}</pre>
            </div>
            
            <Button onClick={() => setShowSettings(false)} className="mt-4">
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Main Layout - Rest of dashboard code same as before */}
      <div className="main-layout">
        <div className="sidebar">
          <Tabs value={currentView} onValueChange={setCurrentView} className="sidebar-tabs">
            <TabsList className="tabs-list">
              <TabsTrigger value="runs">Runs</TabsTrigger>
              <TabsTrigger value="overview">Overview</TabsTrigger>
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
                />
              </div>

              <ScrollArea className="runs-list">
                {filteredRuns.length === 0 ? (
                  <div className="empty-state">
                    <p>No runs yet</p>
                    <p className="empty-subtitle">Ingest sample run to get started</p>
                  </div>
                ) : (
                  filteredRuns.map((run) => (
                    <div
                      key={run.run_id}
                      className={`run-item ${selectedRun?.run_id === run.run_id ? 'active' : ''}`}
                      onClick={() => handleRunClick(run)}
                    >
                      <div className="run-item-header">
                        <div className={`status-dot ${getStatusDot(run.status)}`}></div>
                        <div className="run-item-title">{run.run_id}</div>
                      </div>
                      <div className="run-item-meta">
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
        <div className="main-panel">
          {!selectedRun ? (
            <div className="empty-main">
              <p>Select a run to view details</p>
            </div>
          ) : (
            <div className="run-detail">
              <div className="run-header-block">
                <div className="run-header">
                  <div>
                    <h2 className="run-title">Run: {selectedRun.run_id}</h2>
                  </div>
                  <Badge
                    variant={selectedRun.status === 'success' ? 'success' : selectedRun.status === 'error' ? 'destructive' : 'secondary'}
                    className="status-badge"
                  >
                    {selectedRun.status.toUpperCase()}
                  </Badge>
                </div>
                <p className="run-subtitle">
                  Started {new Date(selectedRun.created_at).toLocaleString()} • {selectedRun.total_steps} agents • 
                  {selectedRun.failed_steps > 0 ? ` ${selectedRun.failed_steps} failed • ` : ' '}
                  ${selectedRun.cost.toFixed(3)}
                </p>
              </div>

              {/* Metrics Row */}
              <div className="metrics-row">
                <div className="metric-card">
                  <div className="metric-label">STEPS</div>
                  <div className="metric-value">{selectedRun.total_steps}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">SUCCEEDED</div>
                  <div className="metric-value">{selectedRun.success_steps}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">FAILED</div>
                  <div className="metric-value">{selectedRun.failed_steps}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">DURATION</div>
                  <div className="metric-value">{(selectedRun.duration_ms / 1000).toFixed(2)}s</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">COST</div>
                  <div className="metric-value">${selectedRun.cost.toFixed(3)}</div>
                </div>
                <div className="metric-card">
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

              {/* Agent Flow */}
              <div className="agent-flow">
                <h3 className="section-title">AGENT FLOW</h3>
                <div className="flow-tree">
                  {runSteps.length > 0 ? renderTree(buildTree(runSteps)) : <p>No steps yet</p>}
                </div>
              </div>

              {/* AI Summary */}
              {summary && (
                <div className="summary-section">
                  <h3 className="section-title">AI SUMMARY (CLAUDE SONNET 4)</h3>
                  <div className="summary-content">{summary}</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Drawer */}
        {selectedStep && currentView === 'runs' && (
          <div className="right-drawer">
            <div className="drawer-header">
              <div>
                <h3 className="drawer-title">{selectedStep.agent_name}</h3>
                <p className="drawer-subtitle">Step ID: {selectedStep.id.substring(0, 8)}</p>
              </div>
              <Badge variant={selectedStep.status === 'success' ? 'success' : 'destructive'}>
                {selectedStep.status}
              </Badge>
            </div>

            <div className="drawer-content">
              <div className="drawer-section">
                <div className="drawer-section-label">PROMPT</div>
                <div className="code-block">{selectedStep.prompt}</div>
              </div>

              <div className="drawer-section">
                <div className="drawer-section-label">OUTPUT</div>
                <div className="code-block">{selectedStep.output}</div>
              </div>

              <div className="drawer-section">
                <div className="drawer-section-label">DIAGNOSTICS</div>
                <div className="diagnostics-grid">
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Tokens</div>
                    <div className="diagnostic-value">{selectedStep.tokens}</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Cost</div>
                    <div className="diagnostic-value">${selectedStep.cost.toFixed(3)}</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Latency</div>
                    <div className="diagnostic-value">{selectedStep.latency_ms}ms</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Step ID</div>
                    <div className="diagnostic-value">{selectedStep.id.substring(0, 12)}...</div>
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

export default Dashboard;
