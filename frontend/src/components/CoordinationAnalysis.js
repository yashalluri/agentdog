import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import './CoordinationAnalysis.css';

const CoordinationAnalysis = ({ runId, api }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedFailure, setExpandedFailure] = useState(null);

  useEffect(() => {
    if (runId) {
      fetchAnalysis();
    }
  }, [runId]);

  const fetchAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${api}/run/${runId}/coordination-analysis`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch coordination analysis');
      }
      
      const data = await response.json();
      setAnalysis(data);
    } catch (err) {
      console.error('Error fetching coordination analysis:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getHealthScoreColor = (score) => {
    if (score >= 90) return '#10B981'; // Green
    if (score >= 70) return '#F59E0B'; // Orange
    if (score >= 50) return '#EF4444'; // Red
    return '#DC2626'; // Dark Red
  };

  const getHealthScoreLabel = (score) => {
    if (score >= 90) return 'Excellent';
    if (score >= 70) return 'Good';
    if (score >= 50) return 'Fair';
    return 'Poor';
  };

  const getSeverityBadgeVariant = (severity) => {
    if (severity === 'high') return 'destructive';
    if (severity === 'medium') return 'default';
    return 'secondary';
  };

  const getTypeIcon = (type) => {
    const icons = {
      hallucination: 'H',
      logical_inconsistency: 'L',
      missing_context: 'M',
      contract_violation: 'C'
    };
    return icons[type] || '!';
  };

  const getTypeLabel = (type) => {
    const labels = {
      hallucination: 'Hallucination',
      logical_inconsistency: 'Logical Inconsistency',
      missing_context: 'Missing Context',
      contract_violation: 'Contract Violation'
    };
    return labels[type] || type;
  };

  const toggleFailure = (failureIndex) => {
    setExpandedFailure(expandedFailure === failureIndex ? null : failureIndex);
  };

  if (loading) {
    return <div className="coordination-loading">Analyzing coordination...</div>;
  }

  if (error) {
    return (
      <div className="coordination-error">
        <p>Failed to load coordination analysis</p>
        <button onClick={fetchAnalysis} className="retry-button">Retry</button>
      </div>
    );
  }

  if (!analysis || analysis.error) {
    return (
      <div className="coordination-empty">
        <p>No coordination analysis available for this run</p>
        {analysis?.error && <p className="error-detail">{analysis.error}</p>}
      </div>
    );
  }

  const { summary, failures, has_failures } = analysis;
  const healthScore = summary?.health_score || 100;

  return (
    <div className="coordination-analysis-container">
      {/* Health Score Card */}
      <div className="health-score-card">
        <div className="health-score-header">
          <h3>Coordination Health Score</h3>
          <Badge variant={healthScore >= 70 ? 'success' : healthScore >= 50 ? 'default' : 'destructive'}>
            {getHealthScoreLabel(healthScore)}
          </Badge>
        </div>
        
        <div className="health-score-display">
          <div className="health-score-circle" style={{ borderColor: getHealthScoreColor(healthScore) }}>
            <span className="health-score-value" style={{ color: getHealthScoreColor(healthScore) }}>
              {Math.round(healthScore)}
            </span>
            <span className="health-score-max">/100</span>
          </div>
          
          <div className="health-score-details">
            <div className="health-detail-item">
              <span className="health-detail-label">Total Issues</span>
              <span className="health-detail-value">{summary?.total_failures || 0}</span>
            </div>
            <div className="health-detail-item critical">
              <span className="health-detail-label">Critical</span>
              <span className="health-detail-value">{summary?.critical_issues || 0}</span>
            </div>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="summary-stats">
          <div className="stat-item">
            <span className="stat-label">High Severity</span>
            <span className="stat-value severity-high">{summary?.by_severity?.high || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Medium Severity</span>
            <span className="stat-value severity-medium">{summary?.by_severity?.medium || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Low Severity</span>
            <span className="stat-value severity-low">{summary?.by_severity?.low || 0}</span>
          </div>
        </div>
      </div>

      {/* Failures by Type */}
      {summary?.by_type && Object.keys(summary.by_type).length > 0 && (
        <div className="failures-by-type">
          <h3>Issues by Type</h3>
          <div className="type-cards">
            {Object.entries(summary.by_type).map(([type, count]) => (
              <div key={type} className="type-card">
                <div className="type-icon">{getTypeIcon(type)}</div>
                <div className="type-info">
                  <div className="type-name">{getTypeLabel(type)}</div>
                  <div className="type-count">{count} issue{count !== 1 ? 's' : ''}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Failures List */}
      {has_failures && failures && failures.length > 0 ? (
        <div className="failures-list">
          <h3>Detected Issues ({failures.length})</h3>
          {failures.map((failure, index) => (
            <div 
              key={index} 
              className={`failure-item ${expandedFailure === index ? 'expanded' : ''}`}
            >
              <div className="failure-header" onClick={() => toggleFailure(index)}>
                <div className="failure-header-left">
                  <span className="failure-icon">{getTypeIcon(failure.type)}</span>
                  <div className="failure-title-group">
                    <div className="failure-title">{failure.message}</div>
                    <div className="failure-meta">
                      <span className="failure-span">{failure.span_name}</span>
                      <span className="failure-subtype">{failure.subtype}</span>
                    </div>
                  </div>
                </div>
                <div className="failure-header-right">
                  <Badge variant={getSeverityBadgeVariant(failure.severity)}>
                    {failure.severity}
                  </Badge>
                  <span className="expand-icon">
                    {expandedFailure === index ? '▼' : '▶'}
                  </span>
                </div>
              </div>

              {expandedFailure === index && (
                <div className="failure-details">
                  <div className="failure-section">
                    <div className="failure-section-label">Type</div>
                    <div className="failure-section-value">{getTypeLabel(failure.type)}</div>
                  </div>

                  <div className="failure-section">
                    <div className="failure-section-label">Span ID</div>
                    <div className="failure-section-value code">{failure.span_id}</div>
                  </div>

                  {failure.evidence && (
                    <div className="failure-section">
                      <div className="failure-section-label">Evidence</div>
                      <div className="evidence-box">
                        <pre>{JSON.stringify(failure.evidence, null, 2)}</pre>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="no-failures">
          <div className="success-icon">✅</div>
          <h3>No Coordination Issues Detected</h3>
          <p>All agents executed correctly with proper coordination</p>
        </div>
      )}

      {/* Refresh Button */}
      <div className="coordination-footer">
        <button onClick={fetchAnalysis} className="refresh-button">
          Refresh Analysis
        </button>
        <span className="analysis-timestamp">
          Analyzed: {analysis.detected_at ? new Date(analysis.detected_at).toLocaleString() : 'Unknown'}
        </span>
      </div>
    </div>
  );
};

export default CoordinationAnalysis;
