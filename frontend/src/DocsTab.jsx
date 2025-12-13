import React, { useState } from 'react';
import './DocsTab.css';

const DocsTab = () => {
  const [policyText, setPolicyText] = useState('');
  const [chatOutputText, setChatOutputText] = useState('');
  const [isChecking, setIsChecking] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      setPolicyText(e.target.result);
    };
    reader.readAsText(file);
  };

  const runComplianceCheck = async () => {
    if (!policyText.trim() || !chatOutputText.trim()) {
      setError('Please provide both compliance policy and agent output to check.');
      return;
    }

    setIsChecking(true);
    setError(null);
    setResults(null);

    try {
      const response = await fetch('http://localhost:8001/api/docs/check', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          policy_text: policyText,
          target_text: chatOutputText,
          mode: 'good'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      console.error('Compliance check error:', err);
      setError(`Failed to run compliance check: ${err.message}`);
    } finally {
      setIsChecking(false);
    }
  };

  const scoreColor = results ? (results.score >= 80 ? '#10b981' : results.score >= 50 ? '#f59e0b' : '#ef4444') : '#6b7280';

  return (
    <div className="docs-tab-compact">
      <div className="compliance-header-compact">
        <h3>Compliance Checker</h3>
        <p>Check if agent responses follow your compliance policy</p>
      </div>

      <div className="compliance-inputs">
        {/* Policy Upload */}
        <div className="input-group-compact">
          <label><strong>Compliance Policy</strong></label>
          <div className="file-input-wrapper">
            <input
              type="file"
              accept=".txt,.md"
              onChange={handleFileUpload}
              className="file-input"
              id="policy-upload"
            />
            <label htmlFor="policy-upload" className="file-button-compact">
              Choose Policy File
            </label>
          </div>
          <textarea
            className="text-input-compact"
            placeholder="Or paste compliance policy here..."
            value={policyText}
            onChange={(e) => setPolicyText(e.target.value)}
            rows={6}
          />
        </div>

        {/* Agent Output */}
        <div className="input-group-compact">
          <label><strong>Agent Output to Check</strong></label>
          <textarea
            className="text-input-compact"
            placeholder="Copy/paste agent response from chat to check compliance..."
            value={chatOutputText}
            onChange={(e) => setChatOutputText(e.target.value)}
            rows={6}
          />
        </div>

        {/* Check Button */}
        <button
          className="check-button-compact"
          onClick={runComplianceCheck}
          disabled={isChecking || !policyText.trim() || !chatOutputText.trim()}
        >
          {isChecking ? 'Checking...' : 'Check Compliance'}
        </button>

        {error && <div className="error-message-compact">{error}</div>}
      </div>

      {/* Results */}
      {results && (
        <div className="compliance-results-compact">
          <div className="score-display">
            <div className="score-circle-compact" style={{ borderColor: scoreColor }}>
              <span className="score-value-compact" style={{ color: scoreColor }}>
                {results.score}%
              </span>
            </div>
            <div className="score-breakdown">
              <div className="score-stat">
                <span className="stat-label">Total</span>
                <span className="stat-value">{results.total}</span>
              </div>
              <div className="score-stat">
                <span className="stat-label">Met</span>
                <span className="stat-value" style={{ color: '#10b981' }}>{results.met}</span>
              </div>
              <div className="score-stat">
                <span className="stat-label">Missing</span>
                <span className="stat-value" style={{ color: '#ef4444' }}>{results.missing_count}</span>
              </div>
            </div>
          </div>

          {results.missing && results.missing.length > 0 && (
            <div className="missing-requirements">
              <h4>Missing Requirements</h4>
              {results.missing.map((req, idx) => (
                <div key={idx} className="missing-req-item">
                  <div className="req-header">
                    <span className="req-id">{req.requirement_id}</span>
                    <span className="req-category">{req.category}</span>
                  </div>
                  <div className="req-text">{req.requirement_text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!results && !isChecking && (
        <div className="empty-state-compact">
          <p>Upload a policy and paste agent output to check compliance</p>
        </div>
      )}
    </div>
  );
};

export default DocsTab;