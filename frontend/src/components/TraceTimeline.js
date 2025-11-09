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

  useEffect(() => {
    if (runId) {
      fetchTrace();
    }
  }, [runId]);

  const fetchTrace = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${api}/run/${runId}/trace`);
      const data = await response.json();
      setTrace(data);
      
      // Auto-expand root span
      if (data.trace) {
        setExpandedSpans(new Set([data.trace.span_id]));
      }
    } catch (error) {
      console.error('Error fetching trace:', error);
    } finally {
      setLoading(false);
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

    return (
      <div key={span.span_id} className="trace-span-container">
        <div
          className={`trace-span ${isSelected ? 'selected' : ''}`}
          style={{ paddingLeft: `${depth * 20 + 8}px` }}
          onClick={() => setSelectedSpan(span)}
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

  const renderSpanDetails = () => {
    if (!selectedSpan) {
      return (
        <div className="span-details-empty">
          <p>Select a span to view details</p>
        </div>
      );
    }

    return (
      <div className="span-details">
        <div className="span-details-header">
          <h3>
            {getSpanIcon(selectedSpan.span_type)} {selectedSpan.name}
          </h3>
          <span className={`span-status-badge ${selectedSpan.status}`}>
            {selectedSpan.status}
          </span>
        </div>

        {/* Metadata Grid */}
        <div className="span-details-grid">
          <div className="detail-item">
            <label>Type</label>
            <value>{selectedSpan.span_type}</value>
          </div>
          <div className="detail-item">
            <label>Duration</label>
            <value>{formatDuration(selectedSpan.duration_ms)}</value>
          </div>
          {selectedSpan.model && (
            <div className="detail-item">
              <label>Model</label>
              <value>{selectedSpan.model}</value>
            </div>
          )}
          {selectedSpan.tokens_total && (
            <>
              <div className="detail-item">
                <label>Tokens In</label>
                <value>{selectedSpan.tokens_input}</value>
              </div>
              <div className="detail-item">
                <label>Tokens Out</label>
                <value>{selectedSpan.tokens_output}</value>
              </div>
              <div className="detail-item">
                <label>Total Tokens</label>
                <value>{selectedSpan.tokens_total}</value>
              </div>
            </>
          )}
          {selectedSpan.cost_usd && (
            <div className="detail-item">
              <label>Cost</label>
              <value>${selectedSpan.cost_usd.toFixed(4)}</value>
            </div>
          )}
          {selectedSpan.http_method && (
            <>
              <div className="detail-item">
                <label>HTTP Method</label>
                <value>{selectedSpan.http_method}</value>
              </div>
              <div className="detail-item">
                <label>HTTP Status</label>
                <value>{selectedSpan.http_status}</value>
              </div>
            </>
          )}
          {selectedSpan.temperature !== null && selectedSpan.temperature !== undefined && (
            <div className="detail-item">
              <label>Temperature</label>
              <value>{selectedSpan.temperature}</value>
            </div>
          )}
        </div>

        {/* Metadata */}
        {selectedSpan.metadata && Object.keys(selectedSpan.metadata).length > 0 && (
          <div className="span-details-section">
            <h4>Metadata</h4>
            <pre className="span-details-code">
              {JSON.stringify(selectedSpan.metadata, null, 2)}
            </pre>
          </div>
        )}

        {/* Input */}
        {selectedSpan.input && (
          <div className="span-details-section">
            <h4>Input</h4>
            <pre className="span-details-code">
              {typeof selectedSpan.input === 'string' 
                ? selectedSpan.input 
                : JSON.stringify(selectedSpan.input, null, 2)}
            </pre>
          </div>
        )}

        {/* Output */}
        {selectedSpan.output && (
          <div className="span-details-section">
            <h4>Output</h4>
            <pre className="span-details-code">
              {typeof selectedSpan.output === 'string'
                ? selectedSpan.output
                : JSON.stringify(selectedSpan.output, null, 2)}
            </pre>
          </div>
        )}

        {/* Error */}
        {selectedSpan.error && (
          <div className="span-details-section error">
            <h4>Error</h4>
            <pre className="span-details-code">{selectedSpan.error}</pre>
          </div>
        )}

        {/* URL for API calls */}
        {selectedSpan.http_url && (
          <div className="span-details-section">
            <h4>URL</h4>
            <code className="span-url">{selectedSpan.http_url}</code>
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return <div className="trace-loading">Loading trace...</div>;
  }

  if (!trace || !trace.trace) {
    return <div className="trace-empty">No trace data available</div>;
  }

  return (
    <div className="trace-timeline-container">
      {/* Timeline Tree */}
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

      {/* Span Details Panel */}
      <div className="trace-details-panel">
        {renderSpanDetails()}
      </div>
    </div>
  );
};

export default TraceTimeline;
