
import requests
import sys
import json
from datetime import datetime

class VapiDashboardTester:
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
    
    def test_token_validation(self):
        """Test token validation endpoint"""
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
            # Validate response structure
            if "valid" not in data or "email" not in data or "access_level" not in data:
                print("❌ Missing fields in token validation response")
                self.failures.append("Token Validation: Missing fields in response")
                return False
                
            # Check if validation was successful
            if not data["valid"]:
                print("❌ Token validation failed")
                self.failures.append("Token Validation: Token reported as invalid")
                return False
                
            # Check if email matches
            if data["email"] != self.user_email:
                print(f"❌ Email mismatch: Expected {self.user_email}, got {data['email']}")
                self.failures.append("Token Validation: Email mismatch")
                return False
                
            # Check if access level matches
            if data["access_level"] != self.access_level:
                print(f"❌ Access level mismatch: Expected {self.access_level}, got {data['access_level']}")
                self.failures.append("Token Validation: Access level mismatch")
                return False
                
            return True
        return False
    
    def test_logout(self):
        """Test logout endpoint"""
        if not self.access_token:
            print("❌ Cannot test logout without a valid token")
            self.failures.append("Logout: No token available")
            return False
            
        success, data = self.run_test(
            "Logout",
            "GET",
            "auth/logout"
        )
        
        if success:
            # Validate response structure
            if "message" not in data:
                print("❌ Missing 'message' field in logout response")
                self.failures.append("Logout: Missing 'message' field")
                return False
                
            # Check if logout was successful
            if "succes" not in data["message"].lower():
                print(f"❌ Unexpected logout message: {data['message']}")
                self.failures.append(f"Logout: Unexpected message: {data['message']}")
                return False
                
            # Clear token after successful logout
            self.access_token = None
            self.user_email = None
            self.access_level = None
            
            return True
        return False
    
    def test_protected_endpoint_without_auth(self):
        """Test accessing a protected endpoint without authentication"""
        # Temporarily clear token
        temp_token = self.access_token
        self.access_token = None
        
        success, _ = self.run_test(
            "Protected Endpoint Without Auth",
            "GET",
            "overview",
            expected_status=401
        )
        
        # Restore token
        self.access_token = temp_token
        
        if not success:
            # This test should fail with 401, so if run_test returns False, it's actually good
            self.tests_passed += 1
            print("✅ Protected endpoint correctly rejected unauthenticated request")
            return True
        else:
            print("❌ Protected endpoint allowed access without authentication")
            self.failures.append("Protected Endpoint: Allowed access without authentication")
            return False

    def test_overview_endpoint(self):
        """Test the overview endpoint"""
        if not self.access_token:
            print("❌ Cannot test overview endpoint without a valid token")
            self.failures.append("Overview Endpoint: No token available")
            return False
            
        success, data = self.run_test(
            "Overview Endpoint",
            "GET",
            "overview"
        )
        
        if success:
            # Validate response structure
            required_fields = ["total_interviews", "active_interviews", "avg_duration", "trend_percentage", "assistant_name"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"❌ Missing fields in response: {', '.join(missing_fields)}")
                self.failures.append(f"Overview Endpoint: Missing fields: {', '.join(missing_fields)}")
                return False
                
            # Check if assistant name matches expected value
            if data["assistant_name"] != "Supermarket int. dansk":
                print(f"❌ Assistant name mismatch: Expected 'Supermarket int. dansk', got '{data['assistant_name']}'")
                self.failures.append(f"Overview Endpoint: Assistant name mismatch")
                return False
                
            return True
        return False
        success, data = self.run_test(
            "Themes Endpoint",
            "GET",
            "themes"
        )
        
        if success:
            # Validate response structure
            if "themes" not in data:
                print("❌ Missing 'themes' field in response")
                self.failures.append("Themes Endpoint: Missing 'themes' field")
                return False
                
            # Check if themes data is non-empty
            if not data["themes"]:
                print("❌ Themes list is empty")
                self.failures.append("Themes Endpoint: Empty themes list")
                return False
                
            # Validate theme structure
            sample_theme = data["themes"][0]
            required_fields = ["name", "total_mentions", "sentiment_breakdown", "sample_quotes"]
            missing_fields = [field for field in required_fields if field not in sample_theme]
            
            if missing_fields:
                print(f"❌ Missing fields in theme: {', '.join(missing_fields)}")
                self.failures.append(f"Themes Endpoint: Missing theme fields: {', '.join(missing_fields)}")
                return False
                
            return True
        return False

    def test_ratings_endpoint(self):
        """Test the ratings endpoint"""
        success, data = self.run_test(
            "Ratings Endpoint",
            "GET",
            "ratings"
        )
        
        if success:
            # Validate response structure
            if "ratings" not in data:
                print("❌ Missing 'ratings' field in response")
                self.failures.append("Ratings Endpoint: Missing 'ratings' field")
                return False
                
            # Check if ratings data is non-empty
            if not data["ratings"]:
                print("❌ Ratings data is empty")
                self.failures.append("Ratings Endpoint: Empty ratings data")
                return False
                
            # Check if all 5 standard questions are present
            expected_questions = [
                "udvalg_af_varer", 
                "overskuelighed_indretning", 
                "stemning_personal", 
                "prisniveau_kvalitet", 
                "samlet_karakter"
            ]
            
            missing_questions = [q for q in expected_questions if q not in data["ratings"]]
            
            if missing_questions:
                print(f"❌ Missing questions in ratings: {', '.join(missing_questions)}")
                self.failures.append(f"Ratings Endpoint: Missing questions: {', '.join(missing_questions)}")
                return False
                
            # Validate rating structure
            sample_rating = list(data["ratings"].values())[0]
            required_fields = ["label", "average", "color"]
            missing_fields = [field for field in required_fields if field not in sample_rating]
            
            if missing_fields:
                print(f"❌ Missing fields in rating: {', '.join(missing_fields)}")
                self.failures.append(f"Ratings Endpoint: Missing rating fields: {', '.join(missing_fields)}")
                return False
                
            return True
        return False

    def test_interviews_endpoint(self):
        """Test the interviews endpoint"""
        success, data = self.run_test(
            "Interviews Endpoint",
            "GET",
            "interviews"
        )
        
        if success:
            # Validate response structure
            if "interviews" not in data or "total" not in data:
                print("❌ Missing 'interviews' or 'total' field in response")
                self.failures.append("Interviews Endpoint: Missing required fields")
                return False
                
            # Check if interviews data is non-empty
            if not data["interviews"]:
                print("❌ Interviews list is empty")
                self.failures.append("Interviews Endpoint: Empty interviews list")
                return False
                
            # Validate interview structure
            sample_interview = data["interviews"][0]
            required_fields = ["id", "timestamp", "duration", "supermarket", "status", "ratings", "transcript"]
            missing_fields = [field for field in required_fields if field not in sample_interview]
            
            if missing_fields:
                print(f"❌ Missing fields in interview: {', '.join(missing_fields)}")
                self.failures.append(f"Interviews Endpoint: Missing interview fields: {', '.join(missing_fields)}")
                return False
                
            return True
        return False

    def test_supermarkets_endpoint(self):
        """Test the supermarkets endpoint"""
        success, data = self.run_test(
            "Supermarkets Endpoint",
            "GET",
            "supermarkets"
        )
        
        if success:
            # Validate response structure
            if "supermarkets" not in data:
                print("❌ Missing 'supermarkets' field in response")
                self.failures.append("Supermarkets Endpoint: Missing 'supermarkets' field")
                return False
                
            # Check if supermarkets data is non-empty
            if not data["supermarkets"]:
                print("❌ Supermarkets list is empty")
                self.failures.append("Supermarkets Endpoint: Empty supermarkets list")
                return False
                
            return True
        return False

    def test_chat_endpoint(self):
        """Test the chat endpoint"""
        test_questions = [
            "Hvor mange interviews blev lavet?",
            "Hvad er den gennemsnitlige karakter?",
            "Hvilke temaer er mest nævnt?"
        ]
        
        all_passed = True
        for question in test_questions:
            success, data = self.run_test(
                f"Chat Endpoint ('{question}')",
                "POST",
                "chat",
                data={"question": question}
            )
            
            if success:
                # Validate response structure
                if "answer" not in data:
                    print("❌ Missing 'answer' field in response")
                    self.failures.append(f"Chat Endpoint ('{question}'): Missing 'answer' field")
                    all_passed = False
                    continue
                    
                # Check if answer is non-empty
                if not data["answer"]:
                    print("❌ Answer is empty")
                    self.failures.append(f"Chat Endpoint ('{question}'): Empty answer")
                    all_passed = False
                    continue
            else:
                all_passed = False
                
        return all_passed

    def test_vapi_connection(self):
        """Test the Vapi API connection"""
        success, data = self.run_test(
            "Vapi API Connection",
            "GET",
            "vapi/test"
        )
        
        if success:
            # Validate response structure
            if "status" not in data:
                print("❌ Missing 'status' field in response")
                self.failures.append("Vapi API Connection: Missing 'status' field")
                return False
                
            # Check if connection was successful
            if data["status"] != "success":
                print(f"❌ Vapi API connection failed: {data.get('message', 'No error message')}")
                self.failures.append(f"Vapi API Connection: {data.get('message', 'Connection failed')}")
                return False
                
            # Check if we got real data
            if "calls_count" in data and data["calls_count"] > 0:
                print(f"✅ Successfully connected to Vapi API - Found {data['calls_count']} calls")
            else:
                print("⚠️ Connected to Vapi API but found 0 calls")
                
            return True
        return False
        
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Vapi Dashboard API Tests")
        
        tests = [
            self.test_vapi_connection,
            self.test_overview_endpoint,
            self.test_themes_endpoint,
            self.test_ratings_endpoint,
            self.test_interviews_endpoint,
            self.test_supermarkets_endpoint,
            self.test_chat_endpoint
        ]
        
        for test in tests:
            test()
            
        # Print results
        print("\n📊 Test Results:")
        print(f"Tests passed: {self.tests_passed}/{self.tests_run}")
        
        if self.failures:
            print("\n❌ Failures:")
            for failure in self.failures:
                print(f"  - {failure}")
        else:
            print("\n✅ All tests passed!")
            
        return self.tests_passed == self.tests_run

def main():
    # Get backend URL from frontend .env
    backend_url = "https://83624c61-ccb9-4125-a85a-5be1f58ae949.preview.emergentagent.com"
    
    # Run tests
    tester = VapiDashboardTester(backend_url)
    success = tester.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
