import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import './TraceTimeline.css';

const TraceTimeline = ({ runId, api }) => {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedSpans, setExpandedSpans] = useState(new Set());
  const [selectedSpan, setSelectedSpan] = useState(null);
  const [showFullInput, setShowFullInput] = useState(false);
  const [showFullOutput, setShowFullOutput] = useState(false);
  const [coordinationFailures, setCoordinationFailures] = useState(new Map()); // span_id -> failures

  useEffect(() => {
    if (runId) {
      fetchTrace();
      fetchCoordinationFailures();
    }
  }, [runId]);

  const fetchTrace = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${api}/run/${runId}/trace`);
      const data = await response.json();
      
      // Handle new array format (multiple traces) or backward compatible single trace
      if (data.latest_trace) {
        setTrace(data.latest_trace);
        // Auto-expand root span and first level children
        if (data.latest_trace.trace) {
          const expandedSet = new Set([data.latest_trace.trace.span_id]);
          // Auto-expand first level children for better visibility
          if (data.latest_trace.trace.children) {
            data.latest_trace.trace.children.forEach(child => {
              expandedSet.add(child.span_id);
            });
          }
          setExpandedSpans(expandedSet);
        }
      } else if (data.trace) {
        // Backward compatibility - single trace
        setTrace(data);
        const expandedSet = new Set([data.trace.span_id]);
        if (data.trace.children) {
          data.trace.children.forEach(child => expandedSet.add(child.span_id));
        }
        setExpandedSpans(expandedSet);
      } else {
        setTrace(data);
      }
    } catch (error) {
      console.error('Error fetching trace:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCoordinationFailures = async () => {
    try {
      const response = await fetch(`${api}/run/${runId}/coordination-analysis`);
      const data = await response.json();
      
      // Extract failures and map by span_id
      const failuresMap = new Map();
      const analysis = data.latest_analysis || data;
      
      if (analysis && analysis.failures) {
        analysis.failures.forEach(failure => {
          const spanId = failure.span_id;
          if (!failuresMap.has(spanId)) {
            failuresMap.set(spanId, []);
          }
          failuresMap.get(spanId).push(failure);
        });
      }
      
      setCoordinationFailures(failuresMap);
    } catch (error) {
      console.error('Error fetching coordination failures:', error);
    }
  };

  const toggleSpan = (spanId) => {
    const newExpanded = new Set(expandedSpans);
    if (newExpanded.has(spanId)) {
      newExpanded.delete(spanId);
    } else {
      newExpanded.add(spanId);
    }
    setExpandedSpans(newExpanded);
  };

  const getSpanColor = (spanType) => {
    const colors = {
      root: '#8B5CF6',
      agent: '#3B82F6',
      llm_call: '#10B981',
      api_call: '#F59E0B',
      database: '#EF4444',
      tool: '#6366F1',
      retrieval: '#14B8A6'
    };
    return colors[spanType] || '#6B7280';
  };

  const getSpanIcon = (spanType) => {
    const icons = {
      root: '📊',
      agent: '🤖',
      llm_call: '🧠',
      api_call: '🌐',
      database: '💾',
      tool: '🔧',
      retrieval: '🔍'
    };
    return icons[spanType] || '•';
  };

  const formatDuration = (ms) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTokens = (span) => {
    if (span.tokens_total) {
      return `${span.tokens_input || 0}→${span.tokens_output || 0} (${span.tokens_total})`;
    }
    return '-';
  };

  const renderSpan = (span, depth = 0) => {
    const isExpanded = expandedSpans.has(span.span_id);
    const hasChildren = span.children && span.children.length > 0;
    const isSelected = selectedSpan?.span_id === span.span_id;
    const failures = coordinationFailures.get(span.span_id) || [];
    const hasFailures = failures.length > 0;
    const criticalFailures = failures.filter(f => f.severity === 'high').length;

    return (
      <div key={span.span_id} className="trace-span-container">
        <div
          className={`trace-span ${isSelected ? 'selected' : ''} ${hasFailures ? 'has-failures' : ''}`}
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => handleSpanClick(span)}
        >
          {/* Expand/Collapse Icon */}
          {hasChildren && (
            <span
              className="expand-icon"
              onClick={(e) => {
                e.stopPropagation();
                toggleSpan(span.span_id);
              }}
            >
              {isExpanded ? '▼' : '▶'}
            </span>
          )}
          {!hasChildren && <span className="expand-icon-spacer"></span>}

          {/* Span Icon */}
          <span className="span-icon">{getSpanIcon(span.span_type)}</span>

          {/* Span Name */}
          <span className="span-name">{span.name}</span>

          {/* Status Badge */}
          <span className={`span-status ${span.status}`}>
            {span.status === 'success' ? '✓' : span.status === 'error' ? '✗' : '⋯'}
          </span>

          {/* Duration Bar */}
          <div className="span-duration-container">
            <div
              className="span-duration-bar"
              style={{
                width: `${Math.min((span.duration_ms / (trace?.total_duration_ms || 1)) * 100, 100)}%`,
                backgroundColor: getSpanColor(span.span_type)
              }}
            />
            <span className="span-duration-text">{formatDuration(span.duration_ms)}</span>
          </div>

          {/* Tokens */}
          {span.tokens_total && (
            <span className="span-tokens">{formatTokens(span)}</span>
          )}

          {/* Cost */}
          {span.cost_usd && (
            <span className="span-cost">${span.cost_usd.toFixed(4)}</span>
          )}
        </div>

        {/* Children */}
        {hasChildren && isExpanded && (
          <div className="trace-span-children">
            {span.children.map(child => renderSpan(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const handleSpanClick = (span) => {
    setSelectedSpan(span);
    setShowFullInput(false);
    setShowFullOutput(false);
  };

  const formatInputOutput = (data) => {
    if (!data) return '';
    return typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  };

  if (loading) {
    return <div className="trace-loading">Loading trace...</div>;
  }

  if (!trace || !trace.trace) {
    return <div className="trace-empty">No trace data available</div>;
  }

  return (
    <>
      <div className="trace-timeline-container">
        {/* Full Width Timeline Tree */}
        <div className="trace-timeline-tree">
          <div className="trace-timeline-header">
            <h3>Execution Timeline</h3>
            <div className="trace-summary">
              <span>{trace.total_spans} spans</span>
              <span>•</span>
              <span>{formatDuration(trace.total_duration_ms)}</span>
              {trace.total_tokens > 0 && (
                <>
                  <span>•</span>
                  <span>{trace.total_tokens} tokens</span>
                </>
              )}
              {trace.total_cost_usd > 0 && (
                <>
                  <span>•</span>
                  <span>${trace.total_cost_usd.toFixed(4)}</span>
                </>
              )}
            </div>
          </div>
          <div className="trace-spans-list">
            {renderSpan(trace.trace)}
          </div>
        </div>
      </div>

      {/* Right Drawer Modal - Span Detail */}
      {selectedSpan && (
        <>
          <div className="drawer-backdrop" onClick={() => setSelectedSpan(null)}></div>
          <div className="right-drawer-modal" data-testid="trace-drawer">
            <div className="drawer-header">
              <div className="drawer-header-content">
                <div>
                  <h3 className="drawer-title">
                    {getSpanIcon(selectedSpan.span_type)} {selectedSpan.name}
                  </h3>
                  <p className="drawer-subtitle">
                    {selectedSpan.span_type} • {formatDuration(selectedSpan.duration_ms)}
                  </p>
                </div>
                <Badge
                  variant={selectedSpan.status === 'success' ? 'success' : selectedSpan.status === 'error' ? 'destructive' : 'secondary'}
                >
                  {selectedSpan.status.toUpperCase()}
                </Badge>
              </div>
              <button 
                className="drawer-close" 
                onClick={() => setSelectedSpan(null)}
                aria-label="Close drawer"
              >
                ×
              </button>
            </div>

            <div className="drawer-content">
              {/* Input Section */}
              {selectedSpan.input && (
                <div className="drawer-section">
                  <div className="drawer-section-label">Input</div>
                  <div className="code-block">
                    {showFullInput || formatInputOutput(selectedSpan.input).length <= 150
                      ? formatInputOutput(selectedSpan.input)
                      : `${formatInputOutput(selectedSpan.input).substring(0, 150)}...`}
                  </div>
                  {formatInputOutput(selectedSpan.input).length > 150 && (
                    <button 
                      className="show-more-button"
                      onClick={() => setShowFullInput(!showFullInput)}
                    >
                      {showFullInput ? 'Show less' : 'Show more'}
                    </button>
                  )}
                </div>
              )}

              {/* Output Section */}
              {selectedSpan.output && (
                <div className="drawer-section">
                  <div className="drawer-section-label">Output</div>
                  <div className="code-block">
                    {showFullOutput || formatInputOutput(selectedSpan.output).length <= 150
                      ? formatInputOutput(selectedSpan.output)
                      : `${formatInputOutput(selectedSpan.output).substring(0, 150)}...`}
                  </div>
                  {formatInputOutput(selectedSpan.output).length > 150 && (
                    <button 
                      className="show-more-button"
                      onClick={() => setShowFullOutput(!showFullOutput)}
                    >
                      {showFullOutput ? 'Show less' : 'Show more'}
                    </button>
                  )}
                </div>
              )}

              {/* Error Section */}
              {selectedSpan.error && (
                <div className="drawer-section">
                  <div className="drawer-section-label" style={{ color: '#DC2626' }}>Error</div>
                  <div className="code-block" style={{ background: '#FEE2E2', borderColor: '#FCA5A5', color: '#991B1B' }}>
                    {selectedSpan.error}
                  </div>
                </div>
              )}

              {/* Diagnostics */}
              <div className="drawer-section">
                <div className="drawer-section-label">Diagnostics</div>
                <div className="diagnostics-grid">
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Type</div>
                    <div className="diagnostic-value">{selectedSpan.span_type}</div>
                  </div>
                  <div className="diagnostic-item">
                    <div className="diagnostic-label">Duration</div>
                    <div className="diagnostic-value">{formatDuration(selectedSpan.duration_ms)}</div>
                  </div>
                  {selectedSpan.model && (
                    <div className="diagnostic-item">
                      <div className="diagnostic-label">Model</div>
                      <div className="diagnostic-value">{selectedSpan.model}</div>
                    </div>
                  )}
                  {selectedSpan.tokens_total && (
                    <>
                      <div className="diagnostic-item">
                        <div className="diagnostic-label">Tokens In</div>
                        <div className="diagnostic-value">{selectedSpan.tokens_input}</div>
                      </div>
                      <div className="diagnostic-item">
                        <div className="diagnostic-label">Tokens Out</div>
                        <div className="diagnostic-value">{selectedSpan.tokens_output}</div>
                      </div>
                      <div className="diagnostic-item">
                        <div className="diagnostic-label">Total Tokens</div>
                        <div className="diagnostic-value">{selectedSpan.tokens_total}</div>
                      </div>
                    </>
                  )}
                  {selectedSpan.cost_usd && (
                    <div className="diagnostic-item">
                      <div className="diagnostic-label">Cost</div>
                      <div className="diagnostic-value">${selectedSpan.cost_usd.toFixed(4)}</div>
                    </div>
                  )}
                  {selectedSpan.temperature !== null && selectedSpan.temperature !== undefined && (
                    <div className="diagnostic-item">
                      <div className="diagnostic-label">Temperature</div>
                      <div className="diagnostic-value">{selectedSpan.temperature}</div>
                    </div>
                  )}
                  {selectedSpan.http_method && (
                    <>
                      <div className="diagnostic-item">
                        <div className="diagnostic-label">HTTP Method</div>
                        <div className="diagnostic-value">{selectedSpan.http_method}</div>
                      </div>
                      <div className="diagnostic-item">
                        <div className="diagnostic-label">HTTP Status</div>
                        <div className="diagnostic-value">{selectedSpan.http_status}</div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* URL for API calls */}
              {selectedSpan.http_url && (
                <div className="drawer-section">
                  <div className="drawer-section-label">URL</div>
                  <div className="code-block" style={{ wordBreak: 'break-all', color: '#2563EB' }}>
                    {selectedSpan.http_url}
                  </div>
                </div>
              )}

              {/* Metadata */}
              {selectedSpan.metadata && Object.keys(selectedSpan.metadata).length > 0 && (
                <div className="drawer-section">
                  <div className="drawer-section-label">Metadata</div>
                  <div className="code-block">
                    {JSON.stringify(selectedSpan.metadata, null, 2)}
                  </div>
                </div>
              )}

              {/* Span ID */}
              <div className="drawer-section">
                <div className="drawer-section-label">Span ID</div>
                <div className="code-block">
                  {selectedSpan.span_id}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
};

export default TraceTimeline;
