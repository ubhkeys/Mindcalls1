def test_ai_quote_filtering(tester):
    """Test that no AI quotes appear in the themes"""
    if not tester.access_token:
        print("❌ Cannot test AI quote filtering without a valid token")
        tester.failures.append("AI Quote Filtering: No token available")
        return False
        
    success, data = tester.run_test(
        "AI Quote Filtering",
        "GET",
        "themes"
    )
    
    if success:
        # Validate response structure
        if "themes" not in data:
            print("❌ Missing 'themes' field in response")
            tester.failures.append("AI Quote Filtering: Missing 'themes' field")
            return False
            
        # Check if themes data is non-empty
        if not data["themes"]:
            print("❌ Themes list is empty")
            tester.failures.append("AI Quote Filtering: Empty themes list")
            return False
        
        # Check all quotes to ensure none start with "AI:" or "ai:"
        all_quotes_filtered = True
        ai_quotes_found = []
        
        for theme in data["themes"]:
            for sentiment in ["positive", "neutral", "negative"]:
                if sentiment in theme["sample_quotes"] and theme["sample_quotes"][sentiment]:
                    for quote in theme["sample_quotes"][sentiment]:
                        quote_text = quote["text"].strip()
                        
                        # Check if quote starts with AI: or ai:
                        if quote_text.lower().startswith("ai:"):
                            print(f"❌ AI quote found in {theme['name']} ({sentiment}): {quote_text[:50]}...")
                            ai_quotes_found.append(quote_text)
                            all_quotes_filtered = False
                        
                        # Check if quote contains AI: or ai: anywhere in the text
                        if " ai:" in quote_text.lower() or "ai:" in quote_text.lower():
                            print(f"❌ AI content found in {theme['name']} ({sentiment}): {quote_text[:50]}...")
                            ai_quotes_found.append(quote_text)
                            all_quotes_filtered = False
                            
                        # Check if quote contains typical AI assistant phrases
                        ai_phrases = [
                            "kan jeg hjælpe", 
                            "hvordan kan jeg hjælpe", 
                            "er der andet",
                            "har du andre spørgsmål",
                            "jeg er din assistent",
                            "jeg er en ai"
                        ]
                        
                        if any(phrase in quote_text.lower() for phrase in ai_phrases):
                            print(f"❌ Potential AI content found in {theme['name']} ({sentiment}): {quote_text[:50]}...")
                            ai_quotes_found.append(quote_text)
                            all_quotes_filtered = False
                            
                        # Check if "User:" prefix was properly removed
                        if quote_text.startswith("User:") or quote_text.startswith("user:"):
                            print(f"❌ 'User:' prefix not removed in {theme['name']} ({sentiment}): {quote_text[:50]}...")
                            tester.failures.append(f"AI Quote Filtering: 'User:' prefix not removed in {theme['name']}")
                            all_quotes_filtered = False
        
        if all_quotes_filtered:
            print("✅ All quotes are properly filtered - no AI content found")
        else:
            print(f"❌ Found {len(ai_quotes_found)} quotes with AI content")
            tester.failures.append(f"AI Quote Filtering: Found {len(ai_quotes_found)} quotes with AI content")
        
        return all_quotes_filtered
    return False

def test_quote_length_and_quality(tester):
    """Test that quotes are meaningful and of appropriate length"""
    if not tester.access_token:
        print("❌ Cannot test quote quality without a valid token")
        tester.failures.append("Quote Quality: No token available")
        return False
        
    success, data = tester.run_test(
        "Quote Quality",
        "GET",
        "themes"
    )
    
    if success:
        # Validate response structure
        if "themes" not in data:
            print("❌ Missing 'themes' field in response")
            tester.failures.append("Quote Quality: Missing 'themes' field")
            return False
            
        # Check if themes data is non-empty
        if not data["themes"]:
            print("❌ Themes list is empty")
            tester.failures.append("Quote Quality: Empty themes list")
            return False
        
        # Check quote quality
        all_quotes_good_quality = True
        for theme in data["themes"]:
            for sentiment in ["positive", "neutral", "negative"]:
                if sentiment in theme["sample_quotes"] and theme["sample_quotes"][sentiment]:
                    for quote in theme["sample_quotes"][sentiment]:
                        quote_text = quote["text"].strip()
                        
                        # Check if quote is too short (less than 10 characters)
                        if len(quote_text) < 10:
                            print(f"❌ Quote in {theme['name']} is too short ({len(quote_text)} chars): {quote_text}")
                            tester.failures.append(f"Quote Quality: Quote in {theme['name']} is too short")
                            all_quotes_good_quality = False
                        
                        # Check if quote is too long (likely a full transcript)
                        if len(quote_text) > 200:
                            print(f"❌ Quote in {theme['name']} is too long ({len(quote_text)} chars): {quote_text[:50]}...")
                            tester.failures.append(f"Quote Quality: Quote in {theme['name']} is too long")
                            all_quotes_good_quality = False
                        
                        # Check if quote contains multiple sentences (should be single sentence)
                        sentences = [s for s in quote_text.split('.') if s.strip()]
                        if len(sentences) > 2:  # Allow for 2 sentences max
                            print(f"❌ Quote in {theme['name']} has too many sentences ({len(sentences)}): {quote_text[:50]}...")
                            tester.failures.append(f"Quote Quality: Quote in {theme['name']} has too many sentences")
                            all_quotes_good_quality = False
        
        if all_quotes_good_quality:
            print("✅ All quotes are of good quality (appropriate length and content)")
        
        return all_quotes_good_quality
    return False

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

def main():
    # Get backend URL from frontend .env
    backend_url = "https://83624c61-ccb9-4125-a85a-5be1f58ae949.preview.emergentagent.com"
    
    # Run tests
    tester = VapiDashboardTester(backend_url)
    
    print("🚀 Starting Theme Collector AI Quote Filtering Tests")
    
    # Login with a valid code for tests
    print("\n=== Logging in for Testing ===")
    login_success = tester.test_login("test@example.com", "SUPER2024")
    
    if not login_success:
        print("❌ Login failed, cannot proceed with tests")
        return 1
    
    # Test the specific improvements
    print("\n=== Testing AI Quote Filtering ===")
    ai_filtering_success = test_ai_quote_filtering(tester)
    
    print("\n=== Testing Quote Quality ===")
    quote_quality_success = test_quote_length_and_quality(tester)
    
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
    return 0 if ai_filtering_success and quote_quality_success else 1

if __name__ == "__main__":
    sys.exit(main())