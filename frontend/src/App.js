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
  const [liveExecution, setLiveExecution] = useState(null);
  const [executionLog, setExecutionLog] = useState([]);
  
  // Chat interface state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatPanelWidth, setChatPanelWidth] = useState(40); // percentage
  const [isResizing, setIsResizing] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('debate');
  const [currentRunId, setCurrentRunId] = useState(null); // Track active chat run
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [debateProgress, setDebateProgress] = useState('Thinking...');
  
  // Available agents
  const availableAgents = [
    { id: 'debate', name: 'Debate Agent (Multi-Agent)' }
  ];

  // Fetch runs on mount and setup WebSocket
  useEffect(() => {
    fetchRuns();
    
    // Setup WebSocket for real-time updates
    const wsUrl = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');
    const ws = new WebSocket(`${wsUrl}/api/ws`);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'agent_update') {
          // If this is for the currently selected run, update it live
          if (selectedRun && data.run_id === selectedRun.id) {
            // Add/update the agent in runSteps
            setRunSteps(prevSteps => {
              // Check if agent already exists
              const existingIndex = prevSteps.findIndex(s => s.id === data.agent_id);
              const newAgent = {
                id: data.agent_id,
                run_id: data.run_id,
                name: data.agent_name,
                agent_name: data.agent_name,
                status: data.status,
                latency_ms: data.latency_ms || 0,
                cost: data.cost_usd || 0,
                cost_usd: data.cost_usd || 0,
                parent_step_id: data.parent_step_id,
                coordination_status: data.coordination_status,
                coordination_issue: data.coordination_issue,
                error_message: data.error_message,
                prompt: '',
                output: '',
                tokens: 0
              };
              
              if (existingIndex >= 0) {
                // Update existing agent
                const updated = [...prevSteps];
                updated[existingIndex] = newAgent;
                return updated;
              } else {
                // Add new agent
                return [...prevSteps, newAgent];
              }
            });
            
            // Fetch updated run details to get accurate metrics
            fetchRunDetails(selectedRun.id);
          }
          
          // Refresh runs list in sidebar
          fetchRuns();
        } else if (data.type === 'debate_progress') {
          // Update debate progress status
          setDebateProgress(data.status);
        }
      } catch (e) {
        console.error('WebSocket parse error:', e);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };
    
    return () => {
      ws.close();
    };
  }, [liveExecution]);

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

  const handleRunClick = async (run) => {
    setSelectedRun(run);
    setLiveExecution(null); // Clear live execution view
    setExecutionLog([]); // Clear execution log
    setSummary(null);
    setCurrentRunId(run.id);
    
    // Fetch run details for observability
    fetchRunDetails(run.id);
    
    // Load chat messages for this run
    try {
      const response = await axios.get(`${API}/run/${run.id}/messages`);
      setChatMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error loading chat messages:', error);
      // If no messages endpoint, clear chat
      setChatMessages([]);
    }
    
    // Close sidebar on mobile after selection
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  // Handle panel resize
  const handleMouseDown = (e) => {
    setIsResizing(true);
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      
      const containerWidth = window.innerWidth - (sidebarOpen ? 280 : 0);
      const newWidth = ((e.clientX - (sidebarOpen ? 280 : 0)) / containerWidth) * 100;
      
      // Keep between 20% and 80%
      if (newWidth > 20 && newWidth < 80) {
        setChatPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, sidebarOpen]);

  const handleStartNewRun = () => {
    // Clear current chat and reset session
    setChatMessages([]);
    setCurrentRunId(null);
    setSelectedRun(null);
    setRunSteps([]);
    setSummary(null);
    toast.success('Ready to start new conversation');
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isSendingMessage) return;
    
    const userMessage = chatInput.trim();
    setChatInput(''); // Clear input immediately
    
    // Add user message to chat
    const userMsg = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setChatMessages(prev => [...prev, userMsg]);
    
    setIsSendingMessage(true);
    
    try {
      // Send to backend chat API
      const response = await axios.post(`${API}/chat`, {
        run_id: currentRunId,
        message: userMessage,
        agent_type: selectedAgent
      });
      
      const { run_id, response: agentResponse, agent_name } = response.data;
      
      // If this is a new run, set it as current and fetch runs list
      if (!currentRunId) {
        setCurrentRunId(run_id);
        fetchRuns(); // Refresh sidebar to show new run
        
        // Set this run as selected to show observability
        setTimeout(() => {
          fetchRunDetails(run_id);
        }, 500);
      }
      
      // Add assistant response to chat
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: agentResponse,
        timestamp: new Date().toISOString(),
        agent_name: agent_name
      }]);
      
    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Failed to send message');
      
      // Add error message to chat
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your message.',
        timestamp: new Date().toISOString(),
        error: true
      }]);
    } finally {
      setIsSendingMessage(false);
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

  const handleRunMultiAgentDemo = async () => {
    try {
      toast.info('🚀 Starting multi-agent workflow...');
      const response = await axios.post(`${API}/run-multiagent-demo`);
      const runId = response.data.run_id;
      
      // Create a placeholder run object to show immediately
      const placeholderRun = {
        id: runId,
        run_id: runId,
        title: runId,
        start_time: new Date().toISOString(),
        status: 'running',
        num_steps: 0,
        num_success: 0,
        num_failed: 0,
        duration: 0,
        cost: 0
      };
      
      // Select this run immediately
      setSelectedRun(placeholderRun);
      setRunSteps([]); // Clear steps initially
      setLiveExecution({ run_id: runId, started: Date.now() });
      
      toast.success('✨ Watch agents execute in real-time!');
      
      // Refresh runs list to show new run
      setTimeout(() => fetchRuns(), 500);
      
    } catch (error) {
      toast.error('Failed to start multi-agent demo');
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
        <div className="nav-left">
          <button 
            className="mobile-menu-button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label="Toggle menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="nav-logo-container">
            <div className="nav-logo" data-testid="nav-logo">AgentLens</div>
            <div className="nav-tagline" data-testid="nav-tagline">Datadog for AI agents</div>
          </div>
        </div>
        <div className="nav-actions">
          <Button
            variant="ghost"
            onClick={handleGenerateSummary}
            disabled={!selectedRun || loading}
            className="nav-button nav-button-hide-mobile"
            data-testid="generate-summary-btn"
          >
            <Sparkles className="w-4 h-4 mr-2" />
            <span className="nav-button-text">Generate AI Summary</span>
          </Button>
          <Button
            onClick={handleIngestSample}
            className="nav-button-secondary"
            data-testid="ingest-sample-btn"
            style={{ background: '#6B7280' }}
          >
            <span className="nav-button-text-full">Ingest Sample</span>
            <span className="nav-button-text-short">Sample</span>
          </Button>
        </div>
      </div>

      {/* Main Layout */}
      <div className="main-layout">
        {/* Mobile Overlay */}
        {sidebarOpen && <div className="mobile-overlay" onClick={() => setSidebarOpen(false)}></div>}
        
        {/* Left Sidebar - Runs List */}
        <div className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`} data-testid="runs-sidebar">
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

        {/* Split Panel Layout */}
        <div className="split-panel-container">
          {/* Left Panel - Chat */}
          <div className="chat-panel-split" style={{ width: `${chatPanelWidth}%` }}>
            <div className="chat-panel-header">
              <h3 className="chat-panel-title">Agent Chat</h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Button
                  onClick={handleStartNewRun}
                  className="start-new-run-btn-header"
                  variant="outline"
                  size="sm"
                >
                  Start New Run
                </Button>
                <span className="panel-size-hint">{Math.round(chatPanelWidth)}%</span>
              </div>
            </div>
            
            <div className="chat-messages-area">
              {chatMessages.length === 0 ? (
                <div className="chat-empty">
                  <p>No messages yet</p>
                  <p className="chat-empty-sub">Start chatting with your agent</p>
                </div>
              ) : (
                chatMessages.map((msg, idx) => (
                  <div key={idx} className={`chat-msg ${msg.role}`}>
                    <div className="chat-msg-avatar">
                      {msg.role === 'user' ? (
                        <img 
                          src="https://customer-assets.emergentagent.com/job_smart-canine/artifacts/gmjgkpri_Screenshot%202568-11-09%20at%2000.27.06.png" 
                          alt="User" 
                          className="chat-avatar-img"
                        />
                      ) : (
                        '✨'
                      )}
                    </div>
                    <div className="chat-msg-content">
                      <div className="chat-msg-text">
                        {renderMessageWithCitations(msg.content)}
                      </div>
                      <div className="chat-msg-time">
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))
              )}
              {isSendingMessage && (
                <div className="chat-msg assistant">
                  <div className="chat-msg-avatar">✨</div>
                  <div className="chat-msg-content">
                    <div className="chat-msg-text">
                      <span className="typing-indicator">{debateProgress}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            <div className="chat-input-container-new">
              <div className="chat-input-wrapper">
                <select 
                  className="agent-selector-inline"
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  title="Select Agent"
                >
                  {availableAgents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
                <div className="input-divider"></div>
                <input
                  type="text"
                  className="chat-input-new"
                  placeholder="Type your message..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                  disabled={isSendingMessage}
                />
                <button 
                  className="chat-send-btn-new"
                  onClick={handleSendMessage}
                  disabled={!chatInput.trim() || isSendingMessage}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          
          {/* Resize Divider */}
          <div 
            className="panel-divider"
            onMouseDown={handleMouseDown}
          >
            <div className="divider-handle">⋮</div>
          </div>
          
          {/* Right Panel - Observability */}
          <div className="observability-panel-split" style={{ width: `${100 - chatPanelWidth}%` }}>
            <div className="observability-panel-header">
              <h3 className="observability-panel-title">Agent Observability</h3>
              <div className="panel-size-hint">{Math.round(100 - chatPanelWidth)}%</div>
            </div>
            
            <div className="observability-content">
            {!selectedRun ? (
              <div className="empty-main" data-testid="empty-main">
                <p>Select a run to view details or click "Run Multi-Agent Demo" to watch live execution</p>
              </div>
            ) : (
            <div className="run-detail" data-testid="run-detail">
              {/* Run Header */}
              <div className="run-header" data-testid="run-header">
                <div>
                  <h2 className="run-title" data-testid="run-title">
                    {liveExecution && selectedRun.id === liveExecution.run_id && (
                      <span className="live-indicator">🔴 LIVE</span>
                    )}
                    Run: {selectedRun.title}
                  </h2>
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

        {/* Right Drawer Modal - Agent Detail */}
        {selectedStep && (
          <>
            <div className="drawer-backdrop" onClick={() => setSelectedStep(null)}></div>
            <div className="right-drawer-modal" data-testid="right-drawer">
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
          </>
        )}
        </div>
      </div>
      </div>
    </div>
  );
}

export default App;