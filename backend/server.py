from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import asyncio
import httpx
import openai
from datetime import datetime, timedelta
import uuid
import json
from collections import defaultdict, Counter
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
VAPI_API_KEY = os.environ.get('VAPI_API_KEY')
VAPI_ASSISTANT_ID = os.environ.get('VAPI_ASSISTANT_ID')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ASSISTANT_NAME = os.environ.get('ASSISTANT_NAME', 'Supermarket int. dansk')

# Set OpenAI API key
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Vapi API functions
async def fetch_vapi_calls():
    """Fetch calls from Vapi API"""
    if not VAPI_API_KEY:
        print("Warning: No Vapi API key provided, using mock data")
        return MOCK_INTERVIEWS
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {VAPI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Fetch calls from Vapi
            response = await client.get(
                "https://api.vapi.ai/call", 
                headers=headers,
                params={"assistantId": VAPI_ASSISTANT_ID} if VAPI_ASSISTANT_ID else {}
            )
            
            if response.status_code == 200:
                calls_data = response.json()
                print(f"Successfully fetched {len(calls_data)} calls from Vapi")
                return process_vapi_calls(calls_data)
            else:
                print(f"Vapi API error: {response.status_code} - {response.text}")
                return MOCK_INTERVIEWS
                
    except Exception as e:
        print(f"Error fetching Vapi calls: {e}")
        return MOCK_INTERVIEWS

def process_vapi_calls(vapi_calls):
    """Process Vapi call data into our format"""
    processed_calls = []
    
    for call in vapi_calls:
        try:
            # Extract basic call info
            call_id = call.get('id', str(uuid.uuid4()))
            status = call.get('status', 'unknown')
            created_at = call.get('createdAt', datetime.now().isoformat())
            ended_at = call.get('endedAt')
            duration = call.get('duration', 0) or 0
            
            # Extract transcript
            transcript = ""
            if call.get('transcript'):
                # Vapi transcript is usually an object or array
                transcript_data = call['transcript']
                if isinstance(transcript_data, list):
                    transcript = " ".join([msg.get('content', '') for msg in transcript_data if msg.get('role') == 'user'])
                elif isinstance(transcript_data, str):
                    transcript = transcript_data
                else:
                    transcript = str(transcript_data)
            
            # Extract or generate supermarket name
            supermarket = "Ukendt supermarked"
            if call.get('metadata') and call['metadata'].get('supermarket'):
                supermarket = call['metadata']['supermarket']
            elif transcript:
                # Try to extract supermarket name from transcript
                supermarket_keywords = {
                    'netto': 'Netto',
                    'bilka': 'Bilka', 
                    'rema': 'Rema 1000',
                    'irma': 'Irma',
                    'kvickly': 'Kvickly',
                    'fakta': 'Fakta',
                    'lidl': 'Lidl',
                    'aldi': 'Aldi'
                }
                transcript_lower = transcript.lower()
                for keyword, name in supermarket_keywords.items():
                    if keyword in transcript_lower:
                        supermarket = name
                        break
            
            # Generate mock ratings if not available
            ratings = {
                "udvalg_af_varer": 7,
                "overskuelighed_indretning": 7,
                "stemning_personal": 8,
                "prisniveau_kvalitet": 6,
                "samlet_karakter": 7
            }
            
            # Try to extract ratings from call data or transcript
            if call.get('analysis') or call.get('summary'):
                # You could implement rating extraction logic here
                pass
            
            processed_call = {
                "id": call_id,
                "timestamp": created_at,
                "duration": int(duration),
                "supermarket": supermarket,
                "status": "completed" if status == "ended" else status,
                "ratings": ratings,
                "transcript": transcript or "Ingen transskription tilgængelig",
                "themes": extract_simple_themes(transcript) if transcript else []
            }
            
            processed_calls.append(processed_call)
            
        except Exception as e:
            print(f"Error processing call {call.get('id', 'unknown')}: {e}")
            continue
    
    return processed_calls

def extract_simple_themes(transcript):
    """Extract simple themes from transcript"""
    if not transcript:
        return []
    
    theme_keywords = {
        'udvalg': ['udvalg', 'varer', 'sortiment', 'produkter'],
        'personale': ['personale', 'kassedame', 'ekspedient', 'service', 'hjælp'],
        'priser': ['pris', 'billig', 'dyr', 'høj', 'rimelig'],
        'indretning': ['indretning', 'overskuelig', 'navigation', 'stor', 'lille'],
        'kø': ['kø', 'vente', 'hurtig', 'lang', 'tid'],
        'atmosfære': ['atmosfære', 'stemning', 'miljø', 'hyggelig'],
        'renlighed': ['ren', 'pæn', 'beskidt', 'rod']
    }
    
    found_themes = []
    transcript_lower = transcript.lower()
    
    for theme, keywords in theme_keywords.items():
        if any(keyword in transcript_lower for keyword in keywords):
            found_themes.append(theme)
    
    return found_themes

# Mock data for development
MOCK_INTERVIEWS = [
    {
        "id": str(uuid.uuid4()),
        "timestamp": "2024-12-19T10:30:00Z",
        "duration": 245,
        "supermarket": "Netto Østerbro",
        "status": "completed",
        "ratings": {
            "udvalg_af_varer": 8,
            "overskuelighed_indretning": 7,
            "stemning_personal": 9,
            "prisniveau_kvalitet": 6,
            "samlet_karakter": 7
        },
        "transcript": "Jeg synes butikken har et rigtig godt udvalg af varer, især de friske grøntsager. Personalet var meget venligt og hjælpsomt. Priserne er lidt høje, men kvaliteten er god. Køerne var ikke så lange i dag.",
        "themes": ["udvalg", "personale", "priser", "kø-oplevelse"]
    },
    {
        "id": str(uuid.uuid4()),
        "timestamp": "2024-12-19T11:15:00Z",
        "duration": 180,
        "supermarket": "Bilka Hundige",
        "status": "completed",
        "ratings": {
            "udvalg_af_varer": 9,
            "overskuelighed_indretning": 6,
            "stemning_personal": 8,
            "prisniveau_kvalitet": 7,
            "samlet_karakter": 8
        },
        "transcript": "Fantastisk stort udvalg! Man kan finde alt her. Dog kan det være svært at finde rundt - butikken er meget stor og ikke særlig overskuelig. Kassedamerne var søde. Priserne er rimelige.",
        "themes": ["udvalg", "indretning", "personale", "priser"]
    },
    {
        "id": str(uuid.uuid4()),
        "timestamp": "2024-12-19T14:20:00Z",
        "duration": 205,
        "supermarket": "Rema 1000 Amager",
        "status": "completed",
        "ratings": {
            "udvalg_af_varer": 6,
            "overskuelighed_indretning": 8,
            "stemning_personal": 5,
            "prisniveau_kvalitet": 8,
            "samlet_karakter": 7
        },
        "transcript": "Butikken er lille men overskuelig. Udvalget er begrænset, men de har det mest nødvendige. Personalet virkede stresset og havde ikke tid til at hjælpe. Til gengæld er priserne virkelig gode.",
        "themes": ["udvalg", "indretning", "personale", "priser"]
    },
    {
        "id": str(uuid.uuid4()),
        "timestamp": "2024-12-19T16:45:00Z",
        "duration": 320,
        "supermarket": "Irma Frederiksberg",
        "status": "completed",
        "ratings": {
            "udvalg_af_varer": 8,
            "overskuelighed_indretning": 9,
            "stemning_personal": 9,
            "prisniveau_kvalitet": 5,
            "samlet_karakter": 8
        },
        "transcript": "Irma har altid en dejlig atmosfære og personalet er super venligt og professionelt. Butikken er flot indrettet og let at navigere i. De har gode økologiske varer. Dog er priserne virkelig høje - det er en luksusbetegnelse at handle her.",
        "themes": ["atmosfære", "personale", "indretning", "økologi", "priser"]
    }
]

class ChatQuery(BaseModel):
    question: str

class DateRange(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None

def analyze_sentiment_with_openai(text: str) -> str:
    """Analyze sentiment using OpenAI"""
    if not OPENAI_API_KEY:
        # Simple fallback sentiment analysis
        positive_words = ['godt', 'fantastisk', 'dejlig', 'venligt', 'søde', 'professionelt', 'gode']
        negative_words = ['dårligt', 'stresset', 'høje', 'begrænset', 'svært', 'ikke']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        return 'neutral'
    
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Analyze the sentiment of Danish customer feedback. Respond with only: positive, negative, or neutral"},
                {"role": "user", "content": text}
            ],
            max_tokens=10,
            temperature=0
        )
        return response.choices[0].message.content.strip().lower()
    except:
        return 'neutral'

def extract_themes_with_clustering(transcripts: List[str]) -> Dict[str, List[Dict]]:
    """Extract and cluster themes from transcripts"""
    if not transcripts:
        return {}
    
    # Simple theme extraction for demo
    theme_patterns = {
        'udvalg': ['udvalg', 'varer', 'sortiment', 'produkter'],
        'personale': ['personale', 'kassedame', 'ekspedient', 'service', 'hjælp'],
        'priser': ['pris', 'billig', 'dyr', 'høj', 'rimelig'],
        'indretning': ['indretning', 'overskuelig', 'navigation', 'stor', 'lille'],
        'kø-oplevelse': ['kø', 'vente', 'hurtig', 'lang', 'tid'],
        'atmosfære': ['atmosfære', 'stemning', 'miljø', 'hyggelig'],
        'renlighed': ['ren', 'pæn', 'beskidt', 'rod'],
        'friskhed': ['frisk', 'grøntsag', 'kød', 'fisk', 'øko']
    }
    
    themes = defaultdict(list)
    
    for i, transcript in enumerate(transcripts):
        transcript_lower = transcript.lower()
        for theme, keywords in theme_patterns.items():
            if any(keyword in transcript_lower for keyword in keywords):
                sentiment = analyze_sentiment_with_openai(transcript)
                themes[theme].append({
                    'text': transcript,
                    'sentiment': sentiment,
                    'timestamp': MOCK_INTERVIEWS[i]['timestamp'],
                    'supermarket': MOCK_INTERVIEWS[i]['supermarket']
                })
    
    return dict(themes)

@app.get("/api/overview")
async def get_overview():
    """Get dashboard overview statistics"""
    total_interviews = len(MOCK_INTERVIEWS)
    active_interviews = 2  # Mock active count
    avg_duration = sum(interview['duration'] for interview in MOCK_INTERVIEWS) / total_interviews
    
    # Calculate trends (mock data)
    today_interviews = total_interviews // 3
    yesterday_interviews = total_interviews // 4
    trend = ((today_interviews - yesterday_interviews) / yesterday_interviews * 100) if yesterday_interviews > 0 else 0
    
    return {
        "total_interviews": total_interviews,
        "active_interviews": active_interviews,
        "avg_duration": round(avg_duration),
        "trend_percentage": round(trend, 1),
        "assistant_name": ASSISTANT_NAME
    }

@app.get("/api/themes")
async def get_themes(days: int = Query(7, description="Number of days to look back")):
    """Get theme analysis with sentiment"""
    transcripts = [interview['transcript'] for interview in MOCK_INTERVIEWS]
    themes_data = extract_themes_with_clustering(transcripts)
    
    # Process themes for frontend
    processed_themes = []
    for theme_name, mentions in themes_data.items():
        sentiment_counts = Counter(mention['sentiment'] for mention in mentions)
        
        # Get sample quotes for each sentiment
        quotes_by_sentiment = defaultdict(list)
        for mention in mentions:
            if len(quotes_by_sentiment[mention['sentiment']]) < 3:
                quotes_by_sentiment[mention['sentiment']].append({
                    'text': mention['text'][:100] + '...' if len(mention['text']) > 100 else mention['text'],
                    'timestamp': mention['timestamp'],
                    'supermarket': mention['supermarket']
                })
        
        processed_themes.append({
            'name': theme_name.replace('_', ' ').title(),
            'total_mentions': len(mentions),
            'sentiment_breakdown': {
                'positive': sentiment_counts.get('positive', 0),
                'neutral': sentiment_counts.get('neutral', 0),
                'negative': sentiment_counts.get('negative', 0)
            },
            'sample_quotes': dict(quotes_by_sentiment),
            'is_new': theme_name in ['atmosfære', 'økologi']  # Mock new themes
        })
    
    # Sort by total mentions
    processed_themes.sort(key=lambda x: x['total_mentions'], reverse=True)
    
    return {"themes": processed_themes}

@app.get("/api/ratings")
async def get_ratings():
    """Get average ratings for the 5 standard questions"""
    rating_sums = defaultdict(float)
    rating_counts = defaultdict(int)
    
    for interview in MOCK_INTERVIEWS:
        for question, rating in interview['ratings'].items():
            rating_sums[question] += rating
            rating_counts[question] += 1
    
    averages = {}
    question_labels = {
        'udvalg_af_varer': 'Udvalget af varer',
        'overskuelighed_indretning': 'Overskuelighed og indretning',
        'stemning_personal': 'Stemning og personale',
        'prisniveau_kvalitet': 'Prisniveau i forhold til kvalitet',
        'samlet_karakter': 'Samlet karakter'
    }
    
    for question, total in rating_sums.items():
        avg = total / rating_counts[question]
        averages[question] = {
            'label': question_labels.get(question, question),
            'average': round(avg, 1),
            'color': 'green' if avg >= 8 else 'yellow' if avg >= 6 else 'red'
        }
    
    return {"ratings": averages}

@app.get("/api/interviews")
async def get_interviews(
    limit: int = Query(50, description="Number of interviews to return"),
    supermarket: Optional[str] = Query(None, description="Filter by supermarket"),
    days: int = Query(7, description="Number of days to look back")
):
    """Get detailed interview responses"""
    interviews = MOCK_INTERVIEWS.copy()
    
    if supermarket:
        interviews = [i for i in interviews if supermarket.lower() in i['supermarket'].lower()]
    
    # Sort by timestamp (newest first)
    interviews.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return {
        "interviews": interviews[:limit],
        "total": len(interviews)
    }

@app.get("/api/supermarkets")
async def get_supermarkets():
    """Get list of supermarkets from interviews"""
    supermarkets = list(set(interview['supermarket'] for interview in MOCK_INTERVIEWS))
    return {"supermarkets": sorted(supermarkets)}

@app.post("/api/chat")
async def chat_query(query: ChatQuery):
    """Answer questions about the dashboard data"""
    question = query.question.lower()
    
    # Simple question answering logic
    if 'hvor mange' in question and 'interview' in question:
        if 'uge' in question or 'week' in question:
            return {"answer": f"Der blev lavet {len(MOCK_INTERVIEWS)} interviews i sidste uge."}
        else:
            return {"answer": f"Der er i alt {len(MOCK_INTERVIEWS)} gennemførte interviews."}
    
    elif 'sentiment' in question or 'stemning' in question:
        if 'kø' in question:
            return {"answer": "Sentimentfordelingen for tema 'kø-oplevelse': 40% positive, 30% neutral, 30% negative"}
        else:
            return {"answer": "Overordnet sentiment: 45% positive, 35% neutral, 20% negative"}
    
    elif 'karakter' in question or 'rating' in question:
        avg_rating = sum(interview['ratings']['samlet_karakter'] for interview in MOCK_INTERVIEWS) / len(MOCK_INTERVIEWS)
        return {"answer": f"Gennemsnitlig samlet karakter er {avg_rating:.1f} ud af 10."}
    
    elif 'tema' in question or 'theme' in question:
        themes = ['Udvalg', 'Personale', 'Priser', 'Indretning', 'Atmosfære']
        return {"answer": f"De mest nævnte temaer er: {', '.join(themes[:3])}"}
    
    else:
        return {"answer": "Jeg kan hjælpe dig med spørgsmål om interviews, temaer, karakterer og sentiment. Prøv at spørge: 'Hvor mange interviews blev lavet i denne uge?'"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
