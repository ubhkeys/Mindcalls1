
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
    def test_themes_endpoint(self):
        """Test the themes endpoint"""
        if not self.access_token:
            print("❌ Cannot test themes endpoint without a valid token")
            self.failures.append("Themes Endpoint: No token available")
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
        if not self.access_token:
            print("❌ Cannot test ratings endpoint without a valid token")
            self.failures.append("Ratings Endpoint: No token available")
            return False
            
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
        if not self.access_token:
            print("❌ Cannot test interviews endpoint without a valid token")
            self.failures.append("Interviews Endpoint: No token available")
            return False
            
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
        if not self.access_token:
            print("❌ Cannot test supermarkets endpoint without a valid token")
            self.failures.append("Supermarkets Endpoint: No token available")
            return False
            
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
        if not self.access_token:
            print("❌ Cannot test chat endpoint without a valid token")
            self.failures.append("Chat Endpoint: No token available")
            return False
            
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
        if not self.access_token:
            print("❌ Cannot test Vapi API connection without a valid token")
            self.failures.append("Vapi API Connection: No token available")
            return False
            
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
        
    def test_access_levels(self):
        """Test different access levels"""
        access_codes = {
            "DEMO123": "Demo Access",
            "SUPER2024": "Supermarket Premium Access",
            "VAPI001": "Basic Dashboard Access",
            "BETA2024": "Beta Tester Access"
        }
        
        results = {}
        
        for code, expected_level in access_codes.items():
            # Use a test email with the code to make it unique
            test_email = f"test_{code.lower()}@example.com"
            
            # Try to login with this code
            print(f"\n🔑 Testing access level for code: {code}")
            success = self.test_login(test_email, code)
            
            if success:
                # Store the access level we got
                results[code] = {
                    "expected": expected_level,
                    "actual": self.access_level,
                    "success": expected_level.lower() in self.access_level.lower()
                }
                
                # Test a protected endpoint to verify access
                self.test_overview_endpoint()
                
                # Logout to prepare for next code
                self.test_logout()
            else:
                results[code] = {
                    "expected": expected_level,
                    "actual": "Login failed",
                    "success": False
                }
        
        # Print results
        print("\n📊 Access Level Test Results:")
        all_passed = True
        
        for code, result in results.items():
            if result["success"]:
                print(f"✅ {code}: Expected '{result['expected']}', got '{result['actual']}'")
            else:
                print(f"❌ {code}: Expected '{result['expected']}', got '{result['actual']}'")
                self.failures.append(f"Access Level Test: {code} - Expected '{result['expected']}', got '{result['actual']}'")
                all_passed = False
        
        return all_passed
        
    def test_invalid_login(self):
        """Test login with invalid credentials"""
        # Test with invalid access code
        invalid_code_success = self.test_login("test@example.com", "INVALID_CODE", expected_status=401)
        
        # Test with invalid email format
        invalid_email_success = self.test_login("not_an_email", "DEMO123", expected_status=422)
        
        return invalid_code_success and invalid_email_success
        
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Vapi Dashboard API Tests")
        
        # First test authentication and access levels
        print("\n=== Testing Authentication and Access Levels ===")
        self.test_invalid_login()
        self.test_access_levels()
        
        # Login with a valid code for further tests
        print("\n=== Logging in for Protected Endpoint Tests ===")
        self.test_login("test@example.com", "DEMO123")
        
        # Test protected endpoints
        print("\n=== Testing Protected Endpoints ===")
        self.test_protected_endpoint_without_auth()
        self.test_token_validation()
        
        # Test data endpoints
        print("\n=== Testing Data Endpoints ===")
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
        
        # Test logout
        print("\n=== Testing Logout ===")
        self.test_logout()
            
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

def test_theme_specific_quotes(tester):
    """Test that theme quotes are specific to each theme"""
    if not tester.access_token:
        print("❌ Cannot test theme-specific quotes without a valid token")
        tester.failures.append("Theme-Specific Quotes: No token available")
        return False
        
    success, data = tester.run_test(
        "Theme-Specific Quotes",
        "GET",
        "themes"
    )
    
    if success:
        # Validate response structure
        if "themes" not in data:
            print("❌ Missing 'themes' field in response")
            tester.failures.append("Theme-Specific Quotes: Missing 'themes' field")
            return False
            
        # Check if themes data is non-empty
        if not data["themes"]:
            print("❌ Themes list is empty")
            tester.failures.append("Theme-Specific Quotes: Empty themes list")
            return False
        
        # Check specific themes
        theme_keywords = {
            "udvalg": ["udvalg", "varer", "sortiment", "produkter", "selection"],
            "personale": ["personale", "kassedame", "ekspedient", "service", "hjælp"],
            "priser": ["pris", "billig", "dyr", "høj", "rimelig"],
            "indretning": ["indretning", "overskuelig", "navigation", "stor", "lille"]
        }
        
        found_themes = {}
        for theme in data["themes"]:
            theme_name = theme["name"].lower()
            for key, keywords in theme_keywords.items():
                if any(keyword in theme_name for keyword in keywords):
                    found_themes[key] = theme
                    break
        
        # Check if we found all the required themes
        missing_themes = [key for key in theme_keywords.keys() if key not in found_themes]
        if missing_themes:
            print(f"❌ Missing required themes: {', '.join(missing_themes)}")
            tester.failures.append(f"Theme-Specific Quotes: Missing themes: {', '.join(missing_themes)}")
            return False
        
        # Check if each theme has relevant quotes
        all_quotes_relevant = True
        for theme_key, theme_data in found_themes.items():
            keywords = theme_keywords[theme_key]
            
            # Check quotes for each sentiment
            for sentiment in ["positive", "neutral", "negative"]:
                if sentiment in theme_data["sample_quotes"] and theme_data["sample_quotes"][sentiment]:
                    relevant_quotes = 0
                    total_quotes = len(theme_data["sample_quotes"][sentiment])
                    
                    for quote in theme_data["sample_quotes"][sentiment]:
                        quote_text = quote["text"].lower()
                        if any(keyword in quote_text for keyword in keywords):
                            relevant_quotes += 1
                    
                    relevance_percentage = (relevant_quotes / total_quotes) * 100 if total_quotes > 0 else 0
                    if relevance_percentage < 50:  # At least half the quotes should be relevant
                        print(f"❌ {theme_key.capitalize()} theme has low relevance ({relevance_percentage:.1f}%) for {sentiment} quotes")
                        tester.failures.append(f"Theme-Specific Quotes: {theme_key} has low relevance for {sentiment} quotes")
                        all_quotes_relevant = False
                    else:
                        print(f"✅ {theme_key.capitalize()} theme has {relevance_percentage:.1f}% relevant {sentiment} quotes")
        
        return all_quotes_relevant
    return False

def test_sentiment_accuracy(tester):
    """Test that sentiment analysis matches quote content"""
    if not tester.access_token:
        print("❌ Cannot test sentiment accuracy without a valid token")
        tester.failures.append("Sentiment Accuracy: No token available")
        return False
        
    success, data = tester.run_test(
        "Sentiment Accuracy",
        "GET",
        "themes"
    )
    
    if success:
        # Validate response structure
        if "themes" not in data:
            print("❌ Missing 'themes' field in response")
            tester.failures.append("Sentiment Accuracy: Missing 'themes' field")
            return False
            
        # Check if themes data is non-empty
        if not data["themes"]:
            print("❌ Themes list is empty")
            tester.failures.append("Sentiment Accuracy: Empty themes list")
            return False
        
        # Sentiment keywords
        sentiment_keywords = {
            "positive": ["godt", "fantastisk", "dejlig", "venligt", "søde", "professionelt", "gode", "overskuelig", "let", "hurtig"],
            "negative": ["dårligt", "stresset", "høje", "begrænset", "svært", "ikke", "dyre", "lang", "rodet"]
        }
        
        # Check sentiment accuracy for each theme
        sentiment_accuracy = True
        for theme in data["themes"]:
            for sentiment in ["positive", "negative"]:
                if sentiment in theme["sample_quotes"] and theme["sample_quotes"][sentiment]:
                    matching_quotes = 0
                    total_quotes = len(theme["sample_quotes"][sentiment])
                    
                    for quote in theme["sample_quotes"][sentiment]:
                        quote_text = quote["text"].lower()
                        # Check if quote contains keywords matching its sentiment
                        if any(keyword in quote_text for keyword in sentiment_keywords[sentiment]):
                            matching_quotes += 1
                    
                    accuracy_percentage = (matching_quotes / total_quotes) * 100 if total_quotes > 0 else 0
                    if accuracy_percentage < 50:  # At least half should match
                        print(f"❌ {theme['name']} theme has low sentiment accuracy ({accuracy_percentage:.1f}%) for {sentiment} quotes")
                        tester.failures.append(f"Sentiment Accuracy: {theme['name']} has low accuracy for {sentiment} quotes")
                        sentiment_accuracy = False
                    else:
                        print(f"✅ {theme['name']} theme has {accuracy_percentage:.1f}% accurate {sentiment} quotes")
        
        return sentiment_accuracy
    return False

def test_quote_length(tester):
    """Test that quotes are sentence-based, not full transcripts"""
    if not tester.access_token:
        print("❌ Cannot test quote length without a valid token")
        tester.failures.append("Quote Length: No token available")
        return False
        
    success, data = tester.run_test(
        "Quote Length",
        "GET",
        "themes"
    )
    
    if success:
        # Validate response structure
        if "themes" not in data:
            print("❌ Missing 'themes' field in response")
            tester.failures.append("Quote Length: Missing 'themes' field")
            return False
            
        # Check if themes data is non-empty
        if not data["themes"]:
            print("❌ Themes list is empty")
            tester.failures.append("Quote Length: Empty themes list")
            return False
        
        # Check quote lengths
        all_quotes_appropriate = True
        for theme in data["themes"]:
            for sentiment in ["positive", "neutral", "negative"]:
                if sentiment in theme["sample_quotes"] and theme["sample_quotes"][sentiment]:
                    for quote in theme["sample_quotes"][sentiment]:
                        quote_text = quote["text"]
                        
                        # Check if quote is too long (likely a full transcript)
                        if len(quote_text) > 200:
                            print(f"❌ Quote in {theme['name']} is too long ({len(quote_text)} chars): {quote_text[:50]}...")
                            tester.failures.append(f"Quote Length: Quote in {theme['name']} is too long")
                            all_quotes_appropriate = False
                        
                        # Check if quote contains multiple sentences (should be single sentence)
                        sentences = [s for s in quote_text.split('.') if s.strip()]
                        if len(sentences) > 2:  # Allow for 2 sentences max
                            print(f"❌ Quote in {theme['name']} has too many sentences ({len(sentences)}): {quote_text[:50]}...")
                            tester.failures.append(f"Quote Length: Quote in {theme['name']} has too many sentences")
                            all_quotes_appropriate = False
        
        if all_quotes_appropriate:
            print("✅ All quotes are appropriately sized (sentence-based, not full transcripts)")
        
        return all_quotes_appropriate
    return False

def main():
    # Get backend URL from frontend .env
    backend_url = "https://83624c61-ccb9-4125-a85a-5be1f58ae949.preview.emergentagent.com"
    
    # Run tests
    tester = VapiDashboardTester(backend_url)
    
    print("🚀 Starting Vapi Dashboard API Tests for Improved Features")
    
    # Login with a valid code for tests
    print("\n=== Logging in for Testing ===")
    login_success = tester.test_login("test@example.com", "SUPER2024")
    
    if not login_success:
        print("❌ Login failed, cannot proceed with tests")
        return 1
    
    # Test the specific improvements
    print("\n=== Testing Theme-Specific Quotes ===")
    theme_quotes_success = test_theme_specific_quotes(tester)
    
    print("\n=== Testing Sentiment Analysis Accuracy ===")
    sentiment_success = test_sentiment_accuracy(tester)
    
    print("\n=== Testing Quote Length (Sentence-based vs Full Transcript) ===")
    quote_length_success = test_quote_length(tester)
    
    # Test logout
    print("\n=== Testing Logout ===")
    tester.test_logout()
    
    # Print results
    print("\n📊 Test Results:")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    
    if tester.failures:
        print("\n❌ Failures:")
        for failure in tester.failures:
            print(f"  - {failure}")
    else:
        print("\n✅ All tests passed!")
    
    # Return success if all specific tests passed
    return 0 if theme_quotes_success and sentiment_success and quote_length_success else 1

if __name__ == "__main__":
    sys.exit(main())
