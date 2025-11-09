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
