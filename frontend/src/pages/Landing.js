import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Activity, BarChart3, Bug } from 'lucide-react';
import '../styles/Landing.css';

function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing-page">
      {/* Top Navigation */}
      <nav className="landing-nav">
        <div className="landing-nav-content">
          <div className="landing-logo">AgentDog</div>
          <div className="landing-nav-actions">
            <button 
              className="landing-nav-link" 
              onClick={() => navigate('/login')}
            >
              Log in
            </button>
            <Button 
              className="landing-nav-button"
              onClick={() => navigate('/signup')}
            >
              Get started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <Badge className="landing-badge">Now in public beta</Badge>
          <h1 className="landing-hero-title">
            Monitor and debug your AI agents
          </h1>
          <p className="landing-hero-subtitle">
            Get complete visibility into your agent execution flows. Track performance, 
            debug errors, and optimize costs in real-time.
          </p>
          <div className="landing-hero-actions">
            <Button 
              size="lg" 
              className="landing-hero-primary"
              onClick={() => navigate('/signup')}
            >
              Start monitoring
            </Button>
            <Button 
              size="lg" 
              variant="outline" 
              className="landing-hero-secondary"
              onClick={() => navigate('/signup')}
            >
              View demo
            </Button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-features">
        <div className="landing-features-grid">
          <div className="landing-feature-card">
            <div className="landing-feature-icon">
              <Activity className="w-6 h-6" />
            </div>
            <h3 className="landing-feature-title">Complete visibility</h3>
            <p className="landing-feature-text">
              View every step of your agent execution with hierarchical flow trees and detailed logs.
            </p>
          </div>

          <div className="landing-feature-card">
            <div className="landing-feature-icon">
              <BarChart3 className="w-6 h-6" />
            </div>
            <h3 className="landing-feature-title">Performance insights</h3>
            <p className="landing-feature-text">
              Track latency, token usage, and costs across all your agents in real-time.
            </p>
          </div>

          <div className="landing-feature-card">
            <div className="landing-feature-icon">
              <Bug className="w-6 h-6" />
            </div>
            <h3 className="landing-feature-title">Debug with ease</h3>
            <p className="landing-feature-text">
              Instantly identify failures, view prompts and outputs, and replay failed steps.
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="landing-cta">
        <h2 className="landing-cta-title">Ready to get started?</h2>
        <p className="landing-cta-subtitle">
          Create your account and start monitoring your agents in minutes.
        </p>
        <Button 
          size="lg" 
          className="landing-cta-button"
          onClick={() => navigate('/signup')}
        >
          Create your account
        </Button>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-footer-content">
          <p className="landing-footer-text">
            © 2025 AgentDog | Documentation | Privacy | Terms
          </p>
        </div>
      </footer>
    </div>
  );
}

export default Landing;
