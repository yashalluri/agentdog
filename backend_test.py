import requests
import sys
import json
import time
from datetime import datetime

class AgentDogAPITester:
    def __init__(self, base_url="https://visual-preview-15.preview.emergentagent.com"):
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
    
    # 1. Ingest sample data first
    test_results.append(("Ingest Sample Data", tester.test_ingest_sample_data()))
    
    # 2. Test basic CRUD operations
    test_results.append(("Get All Runs", tester.test_get_runs()))
    test_results.append(("Get Specific Run", tester.test_get_specific_run()))
    test_results.append(("Get Run Steps", tester.test_get_run_steps()))
    test_results.append(("Get Step Detail", tester.test_get_step_detail()))
    
    # 3. Test advanced features
    test_results.append(("Replay Step", tester.test_replay_step()))
    test_results.append(("Generate AI Summary", tester.test_generate_summary()))
    
    # 4. Test error handling
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