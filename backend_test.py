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