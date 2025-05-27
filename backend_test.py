import requests
import sys
import json
from datetime import datetime

class MindCallsAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []
        self.access_token = None
        self.user_email = None
        self.access_level = None
        
    def run_test(self, name, method, endpoint, expected_status=200, data=None, params=None, auth=True):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        # Add authorization header if token exists and auth is required
        if auth and self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_json = response.json()
                    print(f"Response: {json.dumps(response_json, indent=2)[:500]}...")
                    return True, response_json
                except:
                    print(f"Response: {response.text[:500]}...")
                    return True, {}
            else:
                error_msg = f"❌ Failed - Expected {expected_status}, got {response.status_code}"
                print(error_msg)
                try:
                    print(f"Error response: {response.text[:500]}")
                except:
                    pass
                self.failures.append(f"{name}: {error_msg}")
                return False, {}

        except Exception as e:
            error_msg = f"❌ Failed - Error: {str(e)}"
            print(error_msg)
            self.failures.append(f"{name}: {error_msg}")
            return False, {}
    
    def test_login(self, email, access_code, expected_status=200):
        """Test login with email and access code"""
        print(f"\n🔑 Testing login with email: {email}, access code: {access_code}")
        
        success, data = self.run_test(
            f"Login with {access_code}",
            "POST",
            "auth/login",
            expected_status=expected_status,
            data={"email": email, "access_code": access_code},
            auth=False
        )
        
        if success and expected_status == 200:
            # Store token for subsequent requests
            self.access_token = data.get('access_token')
            self.user_email = data.get('email')
            self.access_level = data.get('access_level')
            
            print(f"✅ Successfully logged in as {self.user_email} with access level: {self.access_level}")
            return True
        elif expected_status != 200 and not success:
            # This is a negative test that's supposed to fail
            self.tests_passed += 1
            print(f"✅ Login correctly rejected with status {expected_status}")
            return True
        
        return False

    def test_health_check(self):
        """Test the health check endpoint"""
        success, data = self.run_test(
            "Health Check",
            "GET",
            "health",
            auth=False
        )
        
        if success:
            # Verify the API title is "MindCalls API"
            if data.get("version") == "1.0.0" and "healthy" in data.get("status", ""):
                print("✅ Health check confirms API is healthy")
                return True
            else:
                print("❌ Health check response does not indicate healthy status")
                self.failures.append("Health Check: API not healthy")
                return False
        return False

    def test_validate_token(self):
        """Test token validation"""
        if not self.access_token:
            print("❌ Cannot test token validation without a valid token")
            self.failures.append("Token Validation: No token available")
            return False
            
        success, data = self.run_test(
            "Token Validation",
            "POST",
            "auth/validate"
        )
        
        if success:
            if data.get("valid") and data.get("email") == self.user_email:
                print("✅ Token validation successful")
                return True
            else:
                print("❌ Token validation failed")
                self.failures.append("Token Validation: Invalid response")
                return False
        return False

    def test_overview(self):
        """Test the overview endpoint"""
        if not self.access_token:
            print("❌ Cannot test overview without a valid token")
            self.failures.append("Overview: No token available")
            return False
            
        success, data = self.run_test(
            "Overview",
            "GET",
            "overview"
        )
        
        if success:
            # Check for MindCalls branding in assistant_name
            assistant_name = data.get("assistant_name", "")
            if "Vapi" in assistant_name:
                print("❌ Overview contains 'Vapi' reference in assistant_name")
                self.failures.append("Overview: Contains 'Vapi' reference")
                return False
            
            print("✅ Overview endpoint working correctly with proper branding")
            return True
        return False

    def test_themes(self):
        """Test the themes endpoint"""
        if not self.access_token:
            print("❌ Cannot test themes without a valid token")
            self.failures.append("Themes: No token available")
            return False
            
        success, data = self.run_test(
            "Themes",
            "GET",
            "themes"
        )
        
        if success:
            # Check if themes data is present
            if "themes" in data and isinstance(data["themes"], list):
                print(f"✅ Themes endpoint returned {len(data['themes'])} themes")
                return True
            else:
                print("❌ Themes endpoint did not return expected data structure")
                self.failures.append("Themes: Invalid response structure")
                return False
        return False

    def test_ratings(self):
        """Test the ratings endpoint"""
        success, data = self.run_test(
            "Ratings",
            "GET",
            "ratings",
            auth=False  # This endpoint doesn't require auth
        )
        
        if success:
            # Check if ratings data is present
            if "ratings" in data and isinstance(data["ratings"], dict):
                print(f"✅ Ratings endpoint returned data for {len(data['ratings'])} questions")
                return True
            else:
                print("❌ Ratings endpoint did not return expected data structure")
                self.failures.append("Ratings: Invalid response structure")
                return False
        return False

    def test_interviews(self):
        """Test the interviews endpoint"""
        success, data = self.run_test(
            "Interviews",
            "GET",
            "interviews",
            auth=False,  # This endpoint doesn't require auth
            params={"limit": 5}
        )
        
        if success:
            # Check if interviews data is present
            if "interviews" in data and isinstance(data["interviews"], list):
                print(f"✅ Interviews endpoint returned {len(data['interviews'])} interviews")
                
                # Store interview IDs for later use in single interview test
                if data["interviews"]:
                    self.interview_ids = [interview.get("id") for interview in data["interviews"] if interview.get("id")]
                    print(f"Found {len(self.interview_ids)} interview IDs for further testing")
                
                return True
            else:
                print("❌ Interviews endpoint did not return expected data structure")
                self.failures.append("Interviews: Invalid response structure")
                return False
        return False
        
    def test_single_interview(self):
        """Test the single interview endpoint with anonymization"""
        if not hasattr(self, 'interview_ids') or not self.interview_ids:
            print("❌ Cannot test single interview without interview IDs")
            self.failures.append("Single Interview: No interview IDs available")
            return False
            
        interview_id = self.interview_ids[0]
        print(f"Testing single interview with ID: {interview_id}")
        
        success, data = self.run_test(
            "Single Interview",
            "GET",
            f"interview/{interview_id}",
            auth=False  # Check if this endpoint requires auth
        )
        
        if success:
            # Check if interview data is present with full transcript
            if "transcript" in data and isinstance(data["transcript"], str):
                transcript = data["transcript"]
                print(f"✅ Single interview endpoint returned transcript of length: {len(transcript)}")
                
                # Test anonymization of Danish names
                danish_names = ["Anders", "Mette", "Søren", "Lars", "Jens", "Niels", "Hans", "Peter", "Jørgen", "Henrik"]
                
                # Check if any Danish names appear in the transcript
                found_names = [name for name in danish_names if name in transcript]
                
                if found_names:
                    print(f"❌ Found non-anonymized Danish names in transcript: {', '.join(found_names)}")
                    self.failures.append(f"Anonymization: Found non-anonymized names: {', '.join(found_names)}")
                    return False
                
                # Check for "anonym" in the transcript (case-insensitive)
                if "anonym" in transcript.lower():
                    print("✅ Found anonymized content in transcript")
                    
                    # Check for capitalization preservation
                    if "Anonym" in transcript and "anonym" in transcript:
                        print("✅ Anonymization preserves capitalization")
                    else:
                        print("⚠️ Could not verify if anonymization preserves capitalization")
                    
                    return True
                else:
                    print("⚠️ Could not find 'anonym' in transcript - either no names were present or anonymization is not working")
                    
                return True
            else:
                print("❌ Single interview endpoint did not return expected transcript")
                self.failures.append("Single Interview: Invalid response structure")
                return False
        return False

    def test_supermarkets(self):
        """Test the supermarkets endpoint"""
        success, data = self.run_test(
            "Supermarkets",
            "GET",
            "supermarkets",
            auth=False  # This endpoint doesn't require auth
        )
        
        if success:
            # Check if supermarkets data is present
            if "supermarkets" in data and isinstance(data["supermarkets"], list):
                print(f"✅ Supermarkets endpoint returned {len(data['supermarkets'])} supermarkets")
                return True
            else:
                print("❌ Supermarkets endpoint did not return expected data structure")
                self.failures.append("Supermarkets: Invalid response structure")
                return False
        return False

    def test_chat(self):
        """Test the chat endpoint"""
        success, data = self.run_test(
            "Chat",
            "POST",
            "chat",
            data={"question": "Hvor mange interviews er der?"},
            auth=False  # This endpoint doesn't require auth
        )
        
        if success:
            # Check if answer is present
            if "answer" in data and isinstance(data["answer"], str):
                # Check for Vapi references in the answer
                if "Vapi" in data["answer"]:
                    print("❌ Chat response contains 'Vapi' reference")
                    self.failures.append("Chat: Contains 'Vapi' reference")
                    return False
                
                print("✅ Chat endpoint returned a valid answer")
                return True
            else:
                print("❌ Chat endpoint did not return expected data structure")
                self.failures.append("Chat: Invalid response structure")
                return False
        return False

    def test_vapi_connection(self):
        """Test the Vapi connection endpoint"""
        success, data = self.run_test(
            "Vapi Connection",
            "GET",
            "vapi/test",
            auth=False  # This endpoint doesn't require auth
        )
        
        # This endpoint might still use "Vapi" in its name since it's connecting to the Vapi API
        # We're just checking if it works, not checking for branding here
        if success:
            print("✅ Vapi connection test endpoint is working")
            return True
        return False

def main():
    # Get backend URL from frontend .env
    backend_url = "https://83624c61-ccb9-4125-a85a-5be1f58ae949.preview.emergentagent.com"
    
    # Run tests
    tester = MindCallsAPITester(backend_url)
    
    print("🚀 Starting MindCalls API Tests")
    print(f"Testing against API URL: {backend_url}")
    
    # Test health check (no auth required)
    print("\n=== Testing Health Check ===")
    health_check_success = tester.test_health_check()
    
    # Login with a valid code for tests
    print("\n=== Logging in for Testing ===")
    login_success = tester.test_login("test@example.com", "SUPER2024")
    
    if not login_success:
        print("❌ Login failed, cannot proceed with authenticated tests")
    else:
        # Test token validation
        print("\n=== Testing Token Validation ===")
        token_validation_success = tester.test_validate_token()
        
        # Test overview endpoint
        print("\n=== Testing Overview Endpoint ===")
        overview_success = tester.test_overview()
        
        # Test themes endpoint
        print("\n=== Testing Themes Endpoint ===")
        themes_success = tester.test_themes()
    
    # Test endpoints that don't require authentication
    print("\n=== Testing Ratings Endpoint ===")
    ratings_success = tester.test_ratings()
    
    print("\n=== Testing Interviews Endpoint ===")
    interviews_success = tester.test_interviews()
    
    print("\n=== Testing Single Interview Endpoint with Anonymization ===")
    single_interview_success = tester.test_single_interview()
    
    print("\n=== Testing Supermarkets Endpoint ===")
    supermarkets_success = tester.test_supermarkets()
    
    print("\n=== Testing Chat Endpoint ===")
    chat_success = tester.test_chat()
    
    print("\n=== Testing Vapi Connection Endpoint ===")
    vapi_connection_success = tester.test_vapi_connection()
    
    # Print results
    print("\n📊 Test Results:")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    if tester.failures:
        print("\n❌ Failures:")
        for failure in tester.failures:
            print(f"  - {failure}")
    else:
        print("\n✅ All tests passed!")
    
    # Return success if all tests passed
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
