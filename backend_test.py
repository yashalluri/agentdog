import requests
import sys
import json
import time
from datetime import datetime

class AgentDogAPITester:
    def __init__(self, base_url="https://smart-canine.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.sample_run_id = None
        self.sample_step_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout after {timeout}s")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_ingest_sample_data(self):
        """Test sample data ingestion"""
        success, response = self.run_test(
            "Ingest Sample Data",
            "POST",
            "ingest-sample",
            200
        )
        if success and isinstance(response, dict) and 'run_id' in response:
            self.sample_run_id = response['run_id']
            print(f"   Sample run ID: {self.sample_run_id}")
            return True
        return False

    def test_get_runs(self):
        """Test getting all runs"""
        success, response = self.run_test(
            "Get All Runs",
            "GET",
            "runs",
            200
        )
        if success and isinstance(response, list) and len(response) > 0:
            print(f"   Found {len(response)} runs")
            return True
        return False

    def test_get_specific_run(self):
        """Test getting a specific run"""
        if not self.sample_run_id:
            print("❌ No sample run ID available")
            return False
            
        success, response = self.run_test(
            "Get Specific Run",
            "GET",
            f"run/{self.sample_run_id}",
            200
        )
        if success and isinstance(response, dict):
            required_fields = ['id', 'title', 'status', 'num_steps', 'duration', 'cost']
            missing_fields = [field for field in required_fields if field not in response]
            if not missing_fields:
                print(f"   Run: {response.get('title')} - Status: {response.get('status')}")
                return True
            else:
                print(f"   Missing fields: {missing_fields}")
        return False

    def test_get_run_steps(self):
        """Test getting steps for a run"""
        if not self.sample_run_id:
            print("❌ No sample run ID available")
            return False
            
        success, response = self.run_test(
            "Get Run Steps",
            "GET",
            f"run/{self.sample_run_id}/steps",
            200
        )
        if success and isinstance(response, list) and len(response) > 0:
            print(f"   Found {len(response)} steps")
            # Store first step ID for later tests
            self.sample_step_id = response[0]['id']
            print(f"   Sample step ID: {self.sample_step_id}")
            return True
        return False

    def test_get_step_detail(self):
        """Test getting detailed step information"""
        if not self.sample_step_id:
            print("❌ No sample step ID available")
            return False
            
        success, response = self.run_test(
            "Get Step Detail",
            "GET",
            f"step/{self.sample_step_id}",
            200
        )
        if success and isinstance(response, dict):
            required_fields = ['id', 'name', 'status', 'prompt', 'output', 'latency_ms', 'cost']
            missing_fields = [field for field in required_fields if field not in response]
            if not missing_fields:
                print(f"   Step: {response.get('name')} - Status: {response.get('status')}")
                return True
            else:
                print(f"   Missing fields: {missing_fields}")
        return False

    def test_replay_step(self):
        """Test step replay functionality"""
        if not self.sample_step_id:
            print("❌ No sample step ID available")
            return False
            
        success, response = self.run_test(
            "Replay Step",
            "POST",
            f"step/{self.sample_step_id}/replay",
            200
        )
        if success and isinstance(response, dict) and 'message' in response:
            print(f"   Message: {response.get('message')}")
            return True
        return False

    def test_generate_summary(self):
        """Test AI summary generation using Claude Sonnet 4"""
        if not self.sample_run_id:
            print("❌ No sample run ID available")
            return False
            
        print("   Note: This may take 5-10 seconds due to LLM processing...")
        success, response = self.run_test(
            "Generate AI Summary",
            "POST",
            f"summary/{self.sample_run_id}",
            200,
            timeout=60  # Longer timeout for LLM processing
        )
        if success and isinstance(response, dict) and 'summary' in response:
            summary = response.get('summary', '')
            print(f"   Summary length: {len(summary)} characters")
            print(f"   Summary preview: {summary[:100]}...")
            return True
        return False

    def test_event_ingestion_scenarios(self):
        """Test the POST /api/event endpoint with specific scenarios"""
        print("\n🔍 Testing Event Ingestion Scenarios...")
        
        # Generate unique run_id for this test
        import time
        unique_run_id = f"test-workflow-{int(time.time())}"
        
        # Test Scenario 1: Create a new workflow with successful agent
        scenario1_data = {
            "run_id": unique_run_id,
            "agent_name": "data_collector",
            "status": "success",
            "start_time": "2025-11-09T00:55:00Z",
            "end_time": "2025-11-09T00:55:02Z",
            "latency_ms": 2000,
            "prompt": "Collect data from API endpoints",
            "output": "Successfully collected 100 records",
            "tokens": 250,
            "cost_usd": 0.005
        }
        
        success1, response1 = self.run_test(
            "Scenario 1: Create workflow with successful agent",
            "POST",
            "event",
            200,
            scenario1_data
        )
        
        if not success1 or not isinstance(response1, dict) or 'agent_id' not in response1:
            print("❌ Scenario 1 failed - no agent_id returned")
            return False
            
        agent_id_1 = response1['agent_id']
        print(f"   Agent ID from Scenario 1: {agent_id_1}")
        
        # Test Scenario 2: Add agent with parent (success)
        scenario2_data = {
            "run_id": unique_run_id,
            "agent_name": "data_processor",
            "parent_step_id": agent_id_1,
            "status": "success",
            "start_time": "2025-11-09T00:55:03Z",
            "end_time": "2025-11-09T00:55:05Z",
            "latency_ms": 2000,
            "prompt": "Process collected data",
            "output": "Processed 100 records successfully",
            "tokens": 300,
            "cost_usd": 0.007
        }
        
        success2, response2 = self.run_test(
            "Scenario 2: Add agent with parent (success)",
            "POST",
            "event",
            200,
            scenario2_data
        )
        
        if not success2 or not isinstance(response2, dict) or 'agent_id' not in response2:
            print("❌ Scenario 2 failed - no agent_id returned")
            return False
            
        agent_id_2 = response2['agent_id']
        print(f"   Agent ID from Scenario 2: {agent_id_2}")
        
        # Test Scenario 3: Add agent with error and coordination failure detection
        scenario3_data = {
            "run_id": unique_run_id,
            "agent_name": "data_validator",
            "parent_step_id": agent_id_2,
            "status": "error",
            "start_time": "2025-11-09T00:55:06Z",
            "end_time": "2025-11-09T00:55:07Z",
            "latency_ms": 1000,
            "prompt": "Validate processed data",
            "error_message": "KeyError: 'validation_schema' - field not found in parent output",
            "tokens": 50,
            "cost_usd": 0.001
        }
        
        success3, response3 = self.run_test(
            "Scenario 3: Add agent with error and coordination failure",
            "POST",
            "event",
            200,
            scenario3_data
        )
        
        if not success3 or not isinstance(response3, dict) or 'agent_id' not in response3:
            print("❌ Scenario 3 failed - no agent_id returned")
            return False
            
        agent_id_3 = response3['agent_id']
        print(f"   Agent ID from Scenario 3: {agent_id_3}")
        
        # Test Scenario 4: Verify workflow was created and updated
        success4, response4 = self.run_test(
            "Scenario 4: Verify workflow exists",
            "GET",
            "runs",
            200
        )
        
        if not success4 or not isinstance(response4, list):
            print("❌ Scenario 4 failed - could not get runs")
            return False
            
        # Find our test workflow
        test_workflow = None
        for workflow in response4:
            if workflow.get('run_id') == unique_run_id:
                test_workflow = workflow
                break
                
        if not test_workflow:
            print(f"❌ Scenario 4 failed - {unique_run_id} not found")
            return False
            
        print(f"   Found workflow: {test_workflow.get('run_id')} with {test_workflow.get('total_agents', 0)} agents, {test_workflow.get('failed_agents', 0)} failed")
        
        # Verify it has 3 agents, 1 failed
        if test_workflow.get('total_agents') != 3:
            print(f"❌ Expected 3 agents, got {test_workflow.get('total_agents')}")
            return False
            
        if test_workflow.get('failed_agents') != 1:
            print(f"❌ Expected 1 failed agent, got {test_workflow.get('failed_agents')}")
            return False
            
        # Test Scenario 5: Verify agent details
        success5, response5 = self.run_test(
            "Scenario 5: Verify agent details",
            "GET",
            f"run/{unique_run_id}/steps",
            200
        )
        
        if not success5 or not isinstance(response5, list):
            print("❌ Scenario 5 failed - could not get steps")
            return False
            
        if len(response5) != 3:
            print(f"❌ Expected 3 agents, got {len(response5)}")
            return False
            
        # Find the third agent (data_validator) and check coordination status
        validator_agent = None
        for agent in response5:
            if agent.get('agent_name') == 'data_validator':
                validator_agent = agent
                break
                
        if not validator_agent:
            print("❌ Could not find data_validator agent")
            return False
            
        if validator_agent.get('coordination_status') != 'failed':
            print(f"❌ Expected coordination_status='failed', got '{validator_agent.get('coordination_status')}'")
            return False
            
        if not validator_agent.get('coordination_issue'):
            print("❌ Expected coordination_issue to be set")
            return False
            
        print(f"   Coordination issue detected: {validator_agent.get('coordination_issue')}")
        
        print("✅ All event ingestion scenarios passed!")
        return True

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        print("\n🔍 Testing Error Handling...")
        
        # Test invalid run ID
        success, _ = self.run_test(
            "Invalid Run ID",
            "GET",
            "run/invalid-id",
            404
        )
        
        # Test invalid step ID
        success2, _ = self.run_test(
            "Invalid Step ID",
            "GET",
            "step/invalid-id",
            404
        )
        
        return success and success2

def main():
    print("🚀 Starting AgentDog API Testing...")
    print("=" * 50)
    
    tester = AgentDogAPITester()
    
    # Test sequence
    test_results = []
    
    # 1. Test event ingestion scenarios first (as requested)
    test_results.append(("Event Ingestion Scenarios", tester.test_event_ingestion_scenarios()))
    
    # 2. Ingest sample data 
    test_results.append(("Ingest Sample Data", tester.test_ingest_sample_data()))
    
    # 3. Test basic CRUD operations
    test_results.append(("Get All Runs", tester.test_get_runs()))
    test_results.append(("Get Specific Run", tester.test_get_specific_run()))
    test_results.append(("Get Run Steps", tester.test_get_run_steps()))
    test_results.append(("Get Step Detail", tester.test_get_step_detail()))
    
    # 4. Test advanced features
    test_results.append(("Replay Step", tester.test_replay_step()))
    test_results.append(("Generate AI Summary", tester.test_generate_summary()))
    
    # 5. Test error handling
    test_results.append(("Error Handling", tester.test_error_handling()))
    
    # Print results summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Overall: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed! Backend API is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())