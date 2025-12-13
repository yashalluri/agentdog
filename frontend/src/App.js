import React, { useState, useEffect } from 'react';
import '@/App.css';
import axios from 'axios';
import { Search, Play, Sparkles, Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Toaster, toast } from 'sonner';
import TraceTimeline from './components/TraceTimeline';
import CoordinationAnalysis from './components/CoordinationAnalysis';

const API =
  process.env.NODE_ENV === "development"
    ? "/api"
    : `${process.env.REACT_APP_BACKEND_URL}/api`;


// Compliance View Component
const ComplianceView = ({ compliancePolicyText, chatMessages, selectedAgent }) => {
  const [results, setResults] = useState(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState(null);

  const checkCompliance = async () => {
    if (!compliancePolicyText) {
      setError('Please upload a compliance policy first');
      return;
    }

    if (chatMessages.length === 0) {
      setError('No agent messages to check');
      return;
    }

    setIsChecking(true);
    setError(null);

    try {
      const agentResponses = chatMessages
        .filter(msg => msg.role === 'assistant')
        .map(msg => msg.content)
        .join('\n\n');

      const response = await fetch(`${API}/docs/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          policy_text: compliancePolicyText,
          target_text: agentResponses,
          mode: 'good'
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(`Failed to check compliance: ${err.message}`);
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    if (compliancePolicyText && chatMessages.length > 0) {
      checkCompliance();
    }
  }, [compliancePolicyText, chatMessages]);

  const scoreColor = results ? 
    (results.score >= 80 ? '#10b981' : results.score >= 50 ? '#f59e0b' : '#ef4444') : 
    '#6b7280';

  if (!compliancePolicyText) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>
        <p>Upload a compliance policy to check agent responses</p>
      </div>
    );
  }

  if (isChecking) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ 
          width: '40px', 
          height: '40px', 
          border: '4px solid #e5e7eb',
          borderTopColor: '#3b82f6',
          borderRadius: '50%',
          margin: '0 auto 16px',
          animation: 'spin 0.8s linear infinite'
        }}></div>
        <p style={{ color: '#6b7280' }}>Analyzing compliance...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px' }}>
        <div style={{ 
          background: '#fef2f2', 
          border: '1px solid #fecaca', 
          borderRadius: '8px',
          padding: '16px',
          color: '#dc2626'
        }}>
          {error}
        </div>
      </div>
    );
  }

  if (!results) return null;

  return (
    <div style={{ padding: '20px' }}>
      <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '20px' }}>
        Compliance Analysis: {selectedAgent}
      </h3>

      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '24px',
        padding: '20px',
        background: '#f9fafb',
        borderRadius: '8px',
        marginBottom: '20px'
      }}>
        <div style={{
          width: '100px',
          height: '100px',
          border: `5px solid ${scoreColor}`,
          borderRadius: '50%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'white'
        }}>
          <span style={{ fontSize: '28px', fontWeight: '700', color: scoreColor }}>
            {results.score}%
          </span>
        </div>

        <div style={{ display: 'flex', gap: '20px', flex: 1 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: '700' }}>{results.total}</div>
            <div style={{ fontSize: '11px', color: '#6b7280', textTransform: 'uppercase' }}>Total</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#10b981' }}>{results.met}</div>
            <div style={{ fontSize: '11px', color: '#6b7280', textTransform: 'uppercase' }}>Met</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#ef4444' }}>{results.missing_count}</div>
            <div style={{ fontSize: '11px', color: '#6b7280', textTransform: 'uppercase' }}>Missing</div>
          </div>
        </div>
      </div>

      {results.missing && results.missing.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px' }}>
            Missing Requirements
          </h4>
          {results.missing.map((req, idx) => (
            <div key={idx} style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderLeft: '3px solid #ef4444',
              borderRadius: '6px',
              padding: '12px',
              marginBottom: '8px'
            }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                marginBottom: '6px'
              }}>
                <span style={{ fontWeight: '600', fontSize: '12px', color: '#dc2626' }}>
                  {req.requirement_id}
                </span>
                <span style={{
                  fontSize: '10px',
                  textTransform: 'uppercase',
                  color: '#6b7280',
                  background: 'white',
                  padding: '2px 6px',
                  borderRadius: '3px'
                }}>
                  {req.category}
                </span>
              </div>
              <div style={{ fontSize: '13px', color: '#374151' }}>
                {req.requirement_text}
              </div>
            </div>
          ))}
        </div>
      )}

      <div>
        <h4 style={{ fontSize: '15px', fontWeight: '600', marginBottom: '12px' }}>
          All Requirements
        </h4>
        <div style={{ 
          border: '1px solid #e5e7eb', 
          borderRadius: '8px',
          overflow: 'hidden'
        }}>
          <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
            <thead style={{ background: '#f9fafb' }}>
              <tr>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>ID</th>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Requirement</th>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Category</th>
                <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.results && results.results.map((req, idx) => (
                <tr key={idx} style={{ 
                  background: req.status === 'met' ? '#f0fdf4' : '#fef2f2',
                  borderTop: '1px solid #e5e7eb'
                }}>
                  <td style={{ padding: '12px' }}>{req.requirement_id}</td>
                  <td style={{ padding: '12px' }}>{req.requirement_text}</td>
                  <td style={{ padding: '12px' }}>
                    <span style={{
                      background: '#e5e7eb',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      textTransform: 'uppercase',
                      fontWeight: '600'
                    }}>
                      {req.category}
                    </span>
                  </td>
                  <td style={{ padding: '12px' }}>
                    <span style={{
                      padding: '4px 12px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: '600',
                      background: req.status === 'met' ? '#d1fae5' : '#fee2e2',
                      color: req.status === 'met' ? '#065f46' : '#991b1b'
                    }}>
                      {req.status === 'met' ? '✓ Met' : '✗ Missing'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

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
  const [chatPanelWidth, setChatPanelWidth] = useState(40);
  const [isResizing, setIsResizing] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [currentRunId, setCurrentRunId] = useState(null);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [debateProgress, setDebateProgress] = useState('Thinking...');
  const [observabilityView, setObservabilityView] = useState('overview');
  const [showPerformanceModal, setShowPerformanceModal] = useState(false);
  const [performanceStats, setPerformanceStats] = useState(null);
  
  // Compliance state
  const [compliancePolicy, setCompliancePolicy] = useState(null);
  const [compliancePolicyText, setCompliancePolicyText] = useState('');
  
  // Available agents - UPDATED with 2 new compliance agents
  const availableAgents = [
    { id: 'debate', name: 'Debate Agent (Multi-Agent)' },
    { id: 'social_media', name: 'Social Media Creator (7 Agents)' },
    { id: 'compliance_agent_1', name: 'Compliance Agent 1' },
    { id: 'compliance_agent_2', name: 'Compliance Agent 2' },
    { id: 'test_buggy', name: 'Test: Buggy Single Agent', description: 'Single agent with 7 intentional bugs' },
    { id: 'test_faulty', name: 'Test: Faulty Multi-Agent', description: '3 agents with 8 coordination failures' }
  ];

  const calculatePerformanceStats = () => {
    if (!runs || runs.length === 0) {
      setPerformanceStats({
        total: 0,
        success: 0,
        error: 0,
        running: 0,
        successRate: 0,
        errorRate: 0,
        avgSteps: 0
      });
      return;
    }

    const total = runs.length;
    const success = runs.filter(r => r.status === 'success').length;
    const error = runs.filter(r => r.status === 'error').length;
    const running = runs.filter(r => r.status === 'running').length;
    const totalSteps = runs.reduce((sum, r) => sum + (r.num_steps || 0), 0);

    setPerformanceStats({
      total,
      success,
      error,
      running,
      successRate: total > 0 ? ((success / total) * 100).toFixed(1) : 0,
      errorRate: total > 0 ? ((error / total) * 100).toFixed(1) : 0,
      avgSteps: total > 0 ? (totalSteps / total).toFixed(1) : 0
    });
  };

  useEffect(() => {
    calculatePerformanceStats();
  }, [runs]);

  useEffect(() => {
    fetchRuns();
    
    const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${wsProto}://${window.location.host}/api/ws`);

    
    ws.onopen = () => {
      console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'agent_update') {
          if (selectedRun && data.run_id === selectedRun.id) {
            setRunSteps(prevSteps => {
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
                const updated = [...prevSteps];
                updated[existingIndex] = newAgent;
                return updated;
              } else {
                return [...prevSteps, newAgent];
              }
            });
            
            fetchRunDetails(selectedRun.id);
          }
          
          fetchRuns();
        } else if (data.type === 'debate_progress') {
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
    setLiveExecution(null);
    setExecutionLog([]);
    setSummary(null);
    setCurrentRunId(run.id);
    
    fetchRunDetails(run.id);
    
    try {
      const response = await axios.get(`${API}/run/${run.id}/messages`);
      setChatMessages(response.data.messages || []);
    } catch (error) {
      console.error('Error loading chat messages:', error);
      setChatMessages([]);
    }
    
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  const handleMouseDown = (e) => {
    setIsResizing(true);
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      
      const containerWidth = window.innerWidth - (sidebarOpen ? 280 : 0);
      const newWidth = ((e.clientX - (sidebarOpen ? 280 : 0)) / containerWidth) * 100;
      
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
    setChatMessages([]);
    setCurrentRunId(null);
    setSelectedRun(null);
    setRunSteps([]);
    setSummary(null);
    setDebateProgress('Thinking...');
    toast.success('Ready to start new conversation');
  };

  const renderMessageWithCitations = (content) => {
    if (!content) return '';
    
    const parts = content.split('---');
    
    if (parts.length === 1) {
      return <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>;
    }
    
    let mainContent = parts[0];
    const sourcesSection = parts[1];
    
    const sourceLines = sourcesSection.split('\n').filter(line => line.trim().startsWith('['));
    const citationMap = {};
    
    sourceLines.forEach((line) => {
      const match = line.match(/\[(\d+)\]\s+(.+)/);
      if (match) {
        const [, num, url] = match;
        citationMap[num] = url.trim();
      }
    });
    
    const renderContentWithInlineCitations = () => {
      const citationRegex = /\[(\d+)\]/g;
      const parts = [];
      let lastIndex = 0;
      let match;
      
      while ((match = citationRegex.exec(mainContent)) !== null) {
        if (match.index > lastIndex) {
          parts.push(mainContent.substring(lastIndex, match.index));
        }
        
        const citNum = match[1];
        const citUrl = citationMap[citNum];
        
        if (citUrl) {
          parts.push(
            <a
              key={`cit-${match.index}`}
              href={citUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: '#2563EB',
                textDecoration: 'none',
                fontSize: '0.8em',
                verticalAlign: 'super',
                fontWeight: '600',
                marginLeft: '1px',
                marginRight: '1px'
              }}
              title={`Source ${citNum}: ${citUrl}`}
            >
              [{citNum}]
            </a>
          );
        } else {
          parts.push(`[${citNum}]`);
        }
        
        lastIndex = match.index + match[0].length;
      }
      
      if (lastIndex < mainContent.length) {
        parts.push(mainContent.substring(lastIndex));
      }
      
      return parts;
    };
    
    return (
      <div>
        <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
          {renderContentWithInlineCitations()}
        </div>
        {sourceLines.length > 0 && (
          <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #E5E7EB' }}>
            <div style={{ fontSize: '12px', fontWeight: '600', color: '#6B7280', marginBottom: '8px' }}>
              SOURCES:
            </div>
            {sourceLines.map((line, idx) => {
              const match = line.match(/\[(\d+)\]\s+(.+)/);
              if (match) {
                const [, num, url] = match;
                return (
                  <div key={idx} style={{ fontSize: '12px', marginBottom: '4px' }} id={`source-${num}`}>
                    <span style={{ color: '#6B7280', marginRight: '4px', fontWeight: '600' }}>[{num}]</span>
                    <a 
                      href={url.trim()} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      style={{ color: '#2563EB', textDecoration: 'underline' }}
                    >
                      {url.trim().substring(0, 70)}{url.trim().length > 70 ? '...' : ''}
                    </a>
                  </div>
                );
              }
              return null;
            })}
          </div>
        )}
      </div>
    );
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isSendingMessage) return;
    
    const userMessage = chatInput.trim();
    setChatInput('');
    
    const userMsg = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setChatMessages(prev => [...prev, userMsg]);
    
    setIsSendingMessage(true);
    
    try {
      const response = await axios.post(`${API}/chat`, {
        run_id: currentRunId,
        message: userMessage,
        agent_type: selectedAgent
      });
      
      const { run_id, response: agentResponse, agent_name } = response.data;
      
      if (!currentRunId) {
        setCurrentRunId(run_id);
        fetchRuns();
        
        setTimeout(() => {
          fetchRunDetails(run_id);
        }, 1000);
      }
      
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        content: agentResponse,
        timestamp: new Date().toISOString(),
        agent_name: agent_name
      }]);
      
    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Failed to send message');
      
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
      
      setSelectedRun(placeholderRun);
      setRunSteps([]);
      setLiveExecution({ run_id: runId, started: Date.now() });
      
      toast.success('✨ Watch agents execute in real-time!');
      
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
            variant="ghost"
            onClick={() => {
              calculatePerformanceStats();
              setShowPerformanceModal(true);
            }}
            className="nav-button nav-button-hide-mobile"
            data-testid="performance-btn"
          >
            <span className="nav-button-text">📊 Performance</span>
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

      <div className="main-layout">
        {sidebarOpen && <div className="mobile-overlay" onClick={() => setSidebarOpen(false)}></div>}
        
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

        <div className="split-panel-container">
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
              {/* COMPLIANCE POLICY UPLOAD - moved outside wrapper */}
              <div style={{ padding: '8px 12px', borderBottom: '1px solid #e5e7eb', background: '#f9fafb' }}>
                <input
                  type="file"
                  accept=".txt,.md,.pdf"
                  onChange={async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;
                    const reader = new FileReader();
                    reader.onload = (event) => {
                      setCompliancePolicyText(event.target.result);
                      setCompliancePolicy(file.name);
                    };
                    reader.readAsText(file);
                  }}
                  style={{ display: 'none' }}
                  id="policy-upload-input"
                />
                <label 
                  htmlFor="policy-upload-input" 
                  style={{ 
                    fontSize: '12px', 
                    color: '#6b7280',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  {compliancePolicy || 'Upload Compliance Policy'}
                </label>
              </div>
              
              <div className="chat-input-wrapper" style={{ display: 'flex', alignItems: 'center', padding: '12px' }}>
                <select 
                  className="agent-selector-inline"
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  title="Select Agent"
                  style={{ 
                    minWidth: '180px',
                    maxWidth: '200px',
                    flexShrink: 0,
                    marginRight: '8px'
                  }}
                >
                  <option value="">Select Agent</option>
                  {availableAgents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
                
                <input
                  type="text"
                  className="chat-input-new"
                  placeholder="Type your message..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
                  disabled={isSendingMessage}
                  style={{ 
                    flex: 1, 
                    minWidth: 0,
                    border: 'none',
                    outline: 'none',
                    padding: '8px 12px',
                    fontSize: '14px'
                  }}
                />
                
                <button 
                  className="chat-send-btn-new"
                  onClick={handleSendMessage}
                  disabled={!chatInput.trim() || isSendingMessage || !selectedAgent}
                  style={{ marginLeft: '8px', flexShrink: 0 }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          
          <div 
            className="panel-divider"
            onMouseDown={handleMouseDown}
          >
            <div className="divider-handle">⋮</div>
          </div>
          
          <div className="observability-panel-split" style={{ width: `${100 - chatPanelWidth}%` }}>
            <div className="observability-panel-header">
              <h3 className="observability-panel-title">Agent Observability</h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div className="view-toggle">
                  <button
                    className={`view-toggle-btn ${observabilityView === 'overview' ? 'active' : ''}`}
                    onClick={() => setObservabilityView('overview')}
                  >
                    Overview
                  </button>
                  <button
                    className={`view-toggle-btn ${observabilityView === 'trace' ? 'active' : ''}`}
                    onClick={() => setObservabilityView('trace')}
                    disabled={!selectedRun}
                  >
                    Trace
                  </button>
                  <button
                    className={`view-toggle-btn ${observabilityView === 'coordination' ? 'active' : ''}`}
                    onClick={() => setObservabilityView('coordination')}
                    disabled={!selectedRun}
                  >
                    Coordination
                  </button>
                  {/* NEW COMPLIANCE BUTTON */}
                  <button
                    className={`view-toggle-btn ${observabilityView === 'compliance' ? 'active' : ''}`}
                    onClick={() => setObservabilityView('compliance')}
                    disabled={!selectedRun || !compliancePolicyText}
                  >
                    Compliance
                  </button>
                </div>
                <div className="panel-size-hint">{Math.round(100 - chatPanelWidth)}%</div>
              </div>
            </div>
            
            <div className="observability-content">
            {!selectedRun ? (
              <div className="empty-main" data-testid="empty-main">
                <p>Select a run to view details or click "Run Multi-Agent Demo" to watch live execution</p>
              </div>
            ) : observabilityView === 'trace' ? (
              <TraceTimeline runId={selectedRun.id} api={API} />
            ) : observabilityView === 'coordination' ? (
              <CoordinationAnalysis runId={selectedRun.id} api={API} />
            ) : observabilityView === 'compliance' ? (
              <ComplianceView 
                compliancePolicyText={compliancePolicyText}
                chatMessages={chatMessages}
                selectedAgent={selectedAgent}
              />
            ) : (
            <div className="run-detail" data-testid="run-detail">
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

      {showPerformanceModal && performanceStats && (
      <>
        <div className="drawer-backdrop" onClick={() => setShowPerformanceModal(false)}></div>
        <div className="right-drawer-modal performance-modal">
          <div className="drawer-header">
            <div className="drawer-header-content">
              <div>
                <h3 className="drawer-title">System Performance</h3>
                <p className="drawer-subtitle">Real-time metrics across all runs</p>
              </div>
            </div>
            <button 
              className="drawer-close" 
              onClick={() => setShowPerformanceModal(false)}
            >
              ×
            </button>
          </div>

          <div className="drawer-content">
            <div className="performance-stats-grid">
              <div className="perf-stat-card">
                <div className="perf-stat-label">Total Runs</div>
                <div className="perf-stat-value">{performanceStats.total}</div>
              </div>
              <div className="perf-stat-card success">
                <div className="perf-stat-label">Success Rate</div>
                <div className="perf-stat-value">{performanceStats.successRate}%</div>
                <div className="perf-stat-sublabel">{performanceStats.success} successful</div>
              </div>
              <div className="perf-stat-card error">
                <div className="perf-stat-label">Error Rate</div>
                <div className="perf-stat-value">{performanceStats.errorRate}%</div>
                <div className="perf-stat-sublabel">{performanceStats.error} failed</div>
              </div>
              <div className="perf-stat-card">
                <div className="perf-stat-label">Avg Steps</div>
                <div className="perf-stat-value">{performanceStats.avgSteps}</div>
              </div>
            </div>

            <div className="performance-section">
              <h4 className="performance-section-title">Run Status Breakdown</h4>
              <div className="status-breakdown">
                <div className="status-bar-container">
                  <div className="status-bar-labels">
                    <span>Success</span>
                    <span>{performanceStats.success}</span>
                  </div>
                  <div className="status-bar">
                    <div 
                      className="status-bar-fill success" 
                      style={{ width: `${performanceStats.successRate}%` }}
                    ></div>
                  </div>
                </div>
                <div className="status-bar-container">
                  <div className="status-bar-labels">
                    <span>Errors</span>
                    <span>{performanceStats.error}</span>
                  </div>
                  <div className="status-bar">
                    <div 
                      className="status-bar-fill error" 
                      style={{ width: `${performanceStats.errorRate}%` }}
                    ></div>
                  </div>
                </div>
                {performanceStats.running > 0 && (
                  <div className="status-bar-container">
                    <div className="status-bar-labels">
                      <span>Running</span>
                      <span>{performanceStats.running}</span>
                    </div>
                    <div className="status-bar">
                      <div 
                        className="status-bar-fill running" 
                        style={{ width: `${(performanceStats.running / performanceStats.total * 100).toFixed(1)}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="performance-section">
              <h4 className="performance-section-title">System Health</h4>
              <div className="health-indicator">
                {performanceStats.errorRate < 5 ? (
                  <div className="health-status excellent">
                    <span className="health-icon">✓</span>
                    <div>
                      <div className="health-label">Excellent</div>
                      <div className="health-description">System running smoothly</div>
                    </div>
                  </div>
                ) : performanceStats.errorRate < 15 ? (
                  <div className="health-status good">
                    <span className="health-icon">⚠</span>
                    <div>
                      <div className="health-label">Good</div>
                      <div className="health-description">Some errors detected</div>
                    </div>
                  </div>
                ) : (
                  <div className="health-status poor">
                    <span className="health-icon">✗</span>
                    <div>
                      <div className="health-label">Needs Attention</div>
                      <div className="health-description">High error rate detected</div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="performance-footer">
              <p className="performance-note">Updates automatically as new runs complete</p>
            </div>
          </div>
        </div>
      </>
    )}
    </div>
  ); 
}

export default App;