"""
Coordination Failure Detection System

Analyzes multi-agent execution traces to detect:
1. Hallucination Detection - AI invents non-existent APIs, tools, fields, models
2. Logical Consistency - AI's reasoning doesn't make sense or contradicts itself
3. Missing Context - AI makes unverifiable claims
4. Contract Violations - Agent breaks predefined coordination rules
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


class CoordinationFailureDetector:
    """Detects coordination failures in multi-agent traces"""
    
    # Known valid models, APIs, tools in our system
    # Base models used across all workflows
    BASE_VALID_MODELS = {
        "claude-4-sonnet-20250514",
        "claude-sonnet-4", 
        "gpt-4",
        "gpt-3.5-turbo"
    }
    
    # Workflow-specific models
    DEBATE_WORKFLOW_MODELS = {
        "sonar",  # Perplexity search model for research agent
        "sonar-small-chat",
        "sonar-medium-chat",
        "sonar-pro"
    }
    
    SOCIAL_MEDIA_WORKFLOW_MODELS = set()  # Only uses base models
    
    VALID_AGENT_TYPES = {
        "content_strategist",
        "twitter_writer",
        "linkedin_writer", 
        "instagram_writer",
        "facebook_writer",
        "hashtag_generator",
        "engagement_optimizer"
    }
    
    VALID_SPAN_TYPES = {
        "root",
        "agent",
        "llm_call",
        "api_call",
        "database",
        "tool",
        "retrieval"
    }
    
    def __init__(self, trace_data: Dict, workflow_data: Dict):
        """
        Initialize detector with trace and workflow data
        
        Args:
            trace_data: The detailed_trace from workflow
            workflow_data: The workflow document from MongoDB
        """
        self.trace = trace_data
        self.workflow = workflow_data
        self.all_spans = []
        self.detection_results = {
            "run_id": workflow_data.get("run_id"),
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "has_failures": False,
            "failure_count": 0,
            "failures": [],
            "summary": {}
        }
        
        # Determine workflow type and valid models
        self.workflow_type = self._detect_workflow_type()
        self.valid_models = self._get_valid_models_for_workflow()
        
        # Flatten trace for easier analysis
        self._flatten_spans(self.trace.get("trace"))
        
    def _detect_workflow_type(self) -> str:
        """Detect the type of workflow from trace data"""
        root_span = self.trace.get("trace", {})
        root_name = root_span.get("name", "")
        root_metadata = root_span.get("metadata", {})
        
        # Check root span name
        if "social_media" in root_name.lower():
            return "social_media"
        if "debate" in root_name.lower():
            return "debate"
            
        # Check metadata
        workflow_type = root_metadata.get("workflow_type", "")
        if workflow_type:
            return workflow_type
            
        # Check children span names
        children = root_span.get("children", [])
        for child in children:
            child_name = child.get("name", "").lower()
            if "research_agent" in child_name or "debate_agent" in child_name:
                return "debate"
            if any(platform in child_name for platform in ["twitter", "linkedin", "instagram", "facebook", "hashtag"]):
                return "social_media"
        
        return "unknown"
    
    def _get_valid_models_for_workflow(self) -> set:
        """Get valid models based on workflow type"""
        valid_models = self.BASE_VALID_MODELS.copy()
        
        if self.workflow_type == "debate":
            valid_models.update(self.DEBATE_WORKFLOW_MODELS)
        elif self.workflow_type == "social_media":
            valid_models.update(self.SOCIAL_MEDIA_WORKFLOW_MODELS)
        
        return valid_models
    
    def _flatten_spans(self, span: Optional[Dict], parent_span: Optional[Dict] = None):
        """Recursively flatten trace tree into list with parent references"""
        if not span:
            return
            
        span_with_parent = {**span, "parent_span": parent_span}
        self.all_spans.append(span_with_parent)
        
        for child in span.get("children", []):
            self._flatten_spans(child, span_with_parent)
    
    def detect_all(self) -> Dict:
        """Run all detection checks and return results"""
        self._detect_hallucinations()
        self._detect_logical_inconsistencies()
        self._detect_missing_context()
        self._detect_contract_violations()
        
        # Generate summary
        self.detection_results["summary"] = self._generate_summary()
        
        return self.detection_results
    
    def _detect_hallucinations(self):
        """Detect if AI invented non-existent APIs, tools, models, fields"""
        hallucinations = []
        
        # Track what we've already detected to avoid duplicates
        detected_apis = set()
        detected_fields = set()
        
        for span in self.all_spans:
            span_name = span.get("name", "")
            span_type = span.get("span_type", "")
            model = span.get("model")
            output_data = str(span.get("output", ""))
            
            # Check 1: Invalid model claims (context-aware)
            if model and model not in self.valid_models:
                hallucinations.append({
                    "type": "hallucination",
                    "subtype": "invalid_model",
                    "severity": "high",
                    "span_id": span.get("span_id"),
                    "span_name": span_name,
                    "message": f"Agent claims to use model '{model}' which is not valid for {self.workflow_type} workflow",
                    "evidence": {
                        "claimed_model": model,
                        "workflow_type": self.workflow_type,
                        "valid_models_for_workflow": list(self.valid_models)
                    }
                })
            
            # Check 2: Invalid span type
            if span_type and span_type not in self.VALID_SPAN_TYPES:
                hallucinations.append({
                    "type": "hallucination",
                    "subtype": "invalid_span_type",
                    "severity": "medium",
                    "span_id": span.get("span_id"),
                    "span_name": span_name,
                    "message": f"Span uses invalid type '{span_type}'",
                    "evidence": {
                        "claimed_type": span_type,
                        "valid_types": list(self.VALID_SPAN_TYPES)
                    }
                })
            
            # Check 3: References to non-existent APIs in output (deduplicated)
            api_references = re.findall(r'/api/[a-zA-Z0-9_/-]+', output_data)
            for api_ref in api_references:
                if not self._is_valid_api(api_ref) and api_ref not in detected_apis:
                    detected_apis.add(api_ref)  # Mark as detected
                    hallucinations.append({
                        "type": "hallucination",
                        "subtype": "invented_api",
                        "severity": "high",
                        "span_id": span.get("span_id"),
                        "span_name": span_name,
                        "message": f"Agent references non-existent API endpoint '{api_ref}'",
                        "evidence": {
                            "claimed_api": api_ref,
                            "found_in": "output",
                            "first_detected_in_span": span_name
                        }
                    })
            
            # Check 4: Claims about non-existent fields (deduplicated, only check agent spans)
            if span_type == "agent":
                claimed_fields = self._extract_field_references(output_data)
                for field in claimed_fields:
                    if not self._field_exists_in_trace(field) and field not in detected_fields:
                        detected_fields.add(field)  # Mark as detected
                        hallucinations.append({
                            "type": "hallucination",
                            "subtype": "invented_field",
                            "severity": "medium",
                            "span_id": span.get("span_id"),
                            "span_name": span_name,
                            "message": f"Agent references field '{field}' that doesn't exist in trace",
                            "evidence": {
                                "claimed_field": field
                            }
                        })
        
        self.detection_results["failures"].extend(hallucinations)
        self.detection_results["failure_count"] += len(hallucinations)
        if hallucinations:
            self.detection_results["has_failures"] = True
    
    def _detect_logical_inconsistencies(self):
        """Detect logical contradictions and inconsistencies"""
        inconsistencies = []
        
        for span in self.all_spans:
            span_name = span.get("name", "")
            status = span.get("status")
            error = span.get("error")
            
            # Check 1: Success status but has error message
            if status == "success" and error:
                inconsistencies.append({
                    "type": "logical_inconsistency",
                    "subtype": "status_error_mismatch",
                    "severity": "high",
                    "span_id": span.get("span_id"),
                    "span_name": span_name,
                    "message": "Span marked as success but contains error message",
                    "evidence": {
                        "status": status,
                        "error": error
                    }
                })
            
            # Check 2: Error status but no error message
            if status == "error" and not error:
                inconsistencies.append({
                    "type": "logical_inconsistency",
                    "subtype": "missing_error_details",
                    "severity": "medium",
                    "span_id": span.get("span_id"),
                    "span_name": span_name,
                    "message": "Span marked as error but missing error details",
                    "evidence": {
                        "status": status
                    }
                })
            
            # Check 3: Token counts don't match
            tokens_in = span.get("tokens_input", 0)
            tokens_out = span.get("tokens_output", 0)
            tokens_total = span.get("tokens_total", 0)
            
            if tokens_total and (tokens_in + tokens_out) != tokens_total:
                inconsistencies.append({
                    "type": "logical_inconsistency",
                    "subtype": "token_count_mismatch",
                    "severity": "low",
                    "span_id": span.get("span_id"),
                    "span_name": span_name,
                    "message": "Token counts don't add up correctly",
                    "evidence": {
                        "tokens_input": tokens_in,
                        "tokens_output": tokens_out,
                        "tokens_total": tokens_total,
                        "expected_total": tokens_in + tokens_out
                    }
                })
            
            # Check 4: Duration inconsistencies (child longer than parent)
            parent = span.get("parent_span")
            if parent:
                child_duration = span.get("duration_ms", 0)
                parent_duration = parent.get("duration_ms", 0)
                
                if child_duration > parent_duration:
                    inconsistencies.append({
                        "type": "logical_inconsistency",
                        "subtype": "duration_inconsistency",
                        "severity": "medium",
                        "span_id": span.get("span_id"),
                        "span_name": span_name,
                        "message": "Child span duration exceeds parent span duration",
                        "evidence": {
                            "child_duration_ms": child_duration,
                            "parent_duration_ms": parent_duration,
                            "parent_span": parent.get("span_id")
                        }
                    })
        
        self.detection_results["failures"].extend(inconsistencies)
        self.detection_results["failure_count"] += len(inconsistencies)
        if inconsistencies:
            self.detection_results["has_failures"] = True
    
    def _detect_missing_context(self):
        """Detect claims that can't be verified from available data"""
        missing_context = []
        
        # Track detected references to avoid duplicates
        detected_references = set()
        
        for span in self.all_spans:
            span_name = span.get("name", "")
            span_type = span.get("span_type")
            input_data = str(span.get("input", ""))
            output_data = str(span.get("output", ""))
            parent = span.get("parent_span")
            
            # Check 1: Agent makes claims not present in parent output (only for agent spans)
            if span_type == "agent" and parent:
                parent_output = str(parent.get("output", ""))
                
                # Extract key claims from output
                claims = self._extract_claims(output_data)
                for claim in claims:
                    if not self._claim_verifiable(claim, parent_output, input_data):
                        missing_context.append({
                            "type": "missing_context",
                            "subtype": "unverifiable_claim",
                            "severity": "medium",
                            "span_id": span.get("span_id"),
                            "span_name": span_name,
                            "message": "Agent makes claim that can't be verified from parent context",
                            "evidence": {
                                "claim": claim,
                                "parent_span": parent.get("span_id")
                            }
                        })
            
            # Check 2: References to data not in trace (deduplicated, only check agent spans)
            if span_type == "agent" and ("based on" in output_data.lower() or "according to" in output_data.lower()):
                # Agent claiming to use data - verify it exists
                references = re.findall(r'based on ([^.]+)', output_data, re.IGNORECASE)
                for ref in references:
                    ref_clean = ref.strip().lower()
                    if not self._reference_exists_in_trace(ref) and ref_clean not in detected_references:
                        detected_references.add(ref_clean)
                        missing_context.append({
                            "type": "missing_context",
                            "subtype": "missing_reference",
                            "severity": "high",
                            "span_id": span.get("span_id"),
                            "span_name": span_name,
                            "message": "Agent references data not found in trace",
                            "evidence": {
                                "reference": ref
                            }
                        })
        
        self.detection_results["failures"].extend(missing_context)
        self.detection_results["failure_count"] += len(missing_context)
        if missing_context:
            self.detection_results["has_failures"] = True
    
    def _detect_contract_violations(self):
        """Detect violations of coordination contracts"""
        violations = []
        
        # Define coordination contracts per workflow type
        social_media_contracts = {
            "content_strategist": {
                "must_run_first": True,
                "required_output_fields": ["strategy", "target_audience", "tone"],
                "max_duration_ms": 30000
            },
            "platform_writers": {
                "agent_names": ["twitter_writer", "linkedin_writer", "instagram_writer", "facebook_writer"],
                "must_have_parent": "social_media_workflow",
                "required_input_from": "content_strategist"
            },
            "hashtag_generator": {
                "must_run_after": ["twitter_writer", "linkedin_writer", "instagram_writer", "facebook_writer"],
                "max_duration_ms": 15000
            }
        }
        
        test_faulty_contracts = {
            "analyzer": {
                "must_run_first": True,  # Should run first but doesn't
                "must_have_parent": "faulty_analysis_workflow",
                "max_duration_ms": 5000
            },
            "data_collector": {
                "must_have_parent": "faulty_analysis_workflow",
                "max_duration_ms": 10000
            },
            "reporter": {
                "must_have_parent": "faulty_analysis_workflow",
                "must_run_after": ["analyzer", "data_collector"],
                "max_duration_ms": 3000
            }
        }
        
        # Select contracts based on workflow type
        if self.workflow_type == "social_media":
            contracts = social_media_contracts
        elif self.workflow_type == "test_faulty_multiagent":
            contracts = test_faulty_contracts
        else:
            contracts = {}
        
        # Check Contract 1: Content Strategist runs first
        strategist_span = next((s for s in self.all_spans if s.get("name") == "content_strategist"), None)
        if strategist_span:
            # Find all agent spans (exclude LLM calls)
            agent_spans = [s for s in self.all_spans if s.get("span_type") == "agent"]
            if agent_spans:
                first_agent = min(agent_spans, key=lambda s: s.get("start_time", ""))
                if first_agent.get("name") != "content_strategist":
                    violations.append({
                        "type": "contract_violation",
                        "subtype": "execution_order",
                        "severity": "high",
                        "span_id": strategist_span.get("span_id"),
                        "span_name": "content_strategist",
                        "message": "Content Strategist must run first but didn't",
                        "evidence": {
                            "first_agent": first_agent.get("name"),
                            "contract": "content_strategist.must_run_first"
                        }
                    })
        
        # Check Contract 2: Platform writers have correct parent
        for writer_name in contracts["platform_writers"]["agent_names"]:
            writer_span = next((s for s in self.all_spans if s.get("name") == writer_name), None)
            if writer_span:
                parent = writer_span.get("parent_span")
                if not parent or parent.get("name") != "social_media_workflow":
                    violations.append({
                        "type": "contract_violation",
                        "subtype": "wrong_parent",
                        "severity": "high",
                        "span_id": writer_span.get("span_id"),
                        "span_name": writer_name,
                        "message": "Platform writer must be child of social_media_workflow",
                        "evidence": {
                            "actual_parent": parent.get("name") if parent else "none",
                            "expected_parent": "social_media_workflow"
                        }
                    })
        
        # Check Contract 3: Duration limits
        for span in self.all_spans:
            span_name = span.get("name", "")
            duration = span.get("duration_ms", 0)
            
            if span_name == "content_strategist" and duration > contracts["content_strategist"]["max_duration_ms"]:
                violations.append({
                    "type": "contract_violation",
                    "subtype": "duration_exceeded",
                    "severity": "low",
                    "span_id": span.get("span_id"),
                    "span_name": span_name,
                    "message": "Agent exceeded maximum allowed duration",
                    "evidence": {
                        "duration_ms": duration,
                        "max_allowed_ms": contracts["content_strategist"]["max_duration_ms"]
                    }
                })
        
        self.detection_results["failures"].extend(violations)
        self.detection_results["failure_count"] += len(violations)
        if violations:
            self.detection_results["has_failures"] = True
    
    # Helper methods
    
    def _is_valid_api(self, api_path: str) -> bool:
        """Check if API endpoint actually exists"""
        valid_apis = [
            "/api/chat", "/api/runs", "/api/run/", "/api/event",
            "/api/step/", "/api/summary/", "/api/ingest-sample"
        ]
        return any(api_path.startswith(valid) for valid in valid_apis)
    
    def _extract_field_references(self, text: str) -> List[str]:
        """Extract field references from text (e.g., user_id, session_id)"""
        # Find patterns like field_name, field.name, or "field"
        pattern = r'\b([a-z_]+_[a-z_]+)\b'
        return list(set(re.findall(pattern, text.lower())))
    
    def _field_exists_in_trace(self, field: str) -> bool:
        """Check if field exists anywhere in the trace"""
        for span in self.all_spans:
            metadata = span.get("metadata", {})
            if field in str(metadata).lower():
                return True
            if field in str(span.get("input", "")).lower():
                return True
        return False
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract factual claims from text"""
        # Simple extraction - look for definitive statements
        sentences = text.split('.')
        claims = []
        for sentence in sentences[:5]:  # Check first 5 sentences
            if len(sentence) > 20 and ('is ' in sentence or 'will ' in sentence or 'should ' in sentence):
                claims.append(sentence.strip())
        return claims
    
    def _claim_verifiable(self, claim: str, parent_output: str, input_data: str) -> bool:
        """Check if claim can be verified from parent output or input"""
        # Extract key terms from claim
        words = claim.lower().split()
        key_terms = [w for w in words if len(w) > 4][:3]
        
        # Check if key terms exist in parent output or input
        combined_context = (parent_output + " " + input_data).lower()
        matches = sum(1 for term in key_terms if term in combined_context)
        
        # If at least half the key terms are found, consider it verifiable
        return matches >= len(key_terms) / 2 if key_terms else True
    
    def _reference_exists_in_trace(self, reference: str) -> bool:
        """Check if reference exists in trace (strict matching)"""
        ref_lower = reference.lower().strip()
        
        # Extract key nouns/phrases (at least 2 significant words)
        words = [w for w in ref_lower.split() if len(w) > 3 and w not in ['the', 'this', 'that', 'with', 'from', 'data']]
        
        # Need at least 2 significant words to check
        if len(words) < 2:
            return True  # Too generic to check
        
        # Check if the specific reference (or key parts) exists in trace
        for span in self.all_spans:
            span_output = str(span.get("output", "")).lower()
            span_input = str(span.get("input", "")).lower()
            
            # Check if at least 2 key words from reference appear together
            matches_in_output = sum(1 for word in words if word in span_output)
            matches_in_input = sum(1 for word in words if word in span_input)
            
            # If at least 2 key words found, consider it exists
            if matches_in_output >= 2 or matches_in_input >= 2:
                return True
        
        return False
    
    def _generate_summary(self) -> Dict:
        """Generate summary of detection results"""
        failures_by_type = {}
        failures_by_severity = {"high": 0, "medium": 0, "low": 0}
        
        for failure in self.detection_results["failures"]:
            ftype = failure["type"]
            severity = failure["severity"]
            
            failures_by_type[ftype] = failures_by_type.get(ftype, 0) + 1
            failures_by_severity[severity] = failures_by_severity.get(severity, 0) + 1
        
        return {
            "total_failures": self.detection_results["failure_count"],
            "by_type": failures_by_type,
            "by_severity": failures_by_severity,
            "critical_issues": failures_by_severity["high"],
            "health_score": self._calculate_health_score(failures_by_severity)
        }
    
    def _calculate_health_score(self, severity_counts: Dict) -> float:
        """Calculate overall coordination health score (0-100)"""
        # Start at 100, deduct points for failures
        score = 100.0
        score -= severity_counts.get("high", 0) * 15  # -15 per high severity
        score -= severity_counts.get("medium", 0) * 5  # -5 per medium severity
        score -= severity_counts.get("low", 0) * 1  # -1 per low severity
        
        return max(0.0, min(100.0, score))


def analyze_workflow_coordination(workflow_doc: Dict) -> Optional[Dict]:
    """
    Analyze a workflow's coordination and detect failures
    
    Args:
        workflow_doc: MongoDB workflow document with detailed_trace
        
    Returns:
        Detection results dictionary or None if no trace available
    """
    detailed_trace = workflow_doc.get("detailed_trace")
    if not detailed_trace:
        return None
    
    detector = CoordinationFailureDetector(detailed_trace, workflow_doc)
    return detector.detect_all()
