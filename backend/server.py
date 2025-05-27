from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ValidationError, EmailStr
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
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
import logging
import time
from functools import wraps
import jwt
import hashlib

# Load environment variables
load_dotenv()

def anonymize_transcript(transcript: str) -> str:
    """Anonymize personal names in transcript"""
    if not transcript:
        return transcript
    
    # Extended list of Danish names to replace with "anonym"
    danish_names = [
        # Male names
        'lars', 'ole', 'niels', 'erik', 'henrik', 'peter', 'søren', 'jens', 'michael', 'thomas',
        'anders', 'morten', 'martin', 'jan', 'finn', 'bent', 'kurt', 'hans', 'christian', 'jesper',
        'klaus', 'torben', 'bjørn', 'john', 'rene', 'brian', 'leif', 'poul', 'svend', 'preben',
        'ulrik', 'rasmus', 'simon', 'daniel', 'emil', 'gustav', 'oliver', 'victor', 'william',
        
        # Female names  
        'anne', 'kirsten', 'mette', 'lene', 'susanne', 'hanne', 'inge', 'birthe', 'lone', 'pia',
        'karen', 'bente', 'dorthe', 'tina', 'camilla', 'louise', 'charlotte', 'maria', 'emma', 'sofia',
        'ida', 'freja', 'alma', 'clara', 'laura', 'maja', 'caroline', 'mathilde', 'isabella', 'anna',
        'julie', 'sofie', 'liva', 'agnes', 'ellen', 'astrid', 'ingrid', 'malou', 'nanna', 'signe',
        
        # Common surnames
        'nielsen', 'hansen', 'andersen', 'pedersen', 'larsen', 'sørensen', 'rasmussen', 'jørgensen',
        'petersen', 'madsen', 'kristensen', 'olsen', 'thomsen', 'christiansen', 'poulsen', 'johansen',
        'møller', 'mortensen', 'jensen', 'knudsen', 'lind', 'schmidt', 'eriksen', 'holm'
    ]
    
    # Replace names in transcript
    words = transcript.split()
    anonymized_words = []
    
    for word in words:
        # Clean word for comparison (remove punctuation)
        clean_word = ''.join(c for c in word.lower() if c.isalpha())
        
        # Check if it's a Danish name
        if clean_word in danish_names and len(clean_word) > 2:
            # Replace with "anonym" but keep original punctuation
            punctuation = ''.join(c for c in word if not c.isalpha())
            if word[0].isupper():
                anonymized_words.append("Anonym" + punctuation)
            else:
                anonymized_words.append("anonym" + punctuation)
        else:
            anonymized_words.append(word)
    
    return " ".join(anonymized_words)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MindCalls API",
    description="Real-time dashboard for AI interview analysis",
    version="1.0.0"
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure this for production
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting cache
request_cache = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_REQUESTS = 100  # requests per window

def rate_limit(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean old entries
        cutoff_time = current_time - RATE_LIMIT_WINDOW
        request_cache[client_ip] = [
            req_time for req_time in request_cache.get(client_ip, [])
            if req_time > cutoff_time
        ]
        
        # Check rate limit
        if len(request_cache.get(client_ip, [])) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Add current request
        if client_ip not in request_cache:
            request_cache[client_ip] = []
        request_cache[client_ip].append(current_time)
        
        return await func(*args, **kwargs)
    return wrapper

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Der opstod en fejl. Prøv igen senere.",
            "timestamp": datetime.now().isoformat()
        }
    )

# Validation exception handler
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.warning(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "message": "Ugyldig data format",
            "details": exc.errors()
        }
    )

# Environment variables with validation
VAPI_API_KEY = os.environ.get('VAPI_API_KEY')
VAPI_ASSISTANT_ID = os.environ.get('VAPI_ASSISTANT_ID')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ASSISTANT_NAME = os.environ.get('ASSISTANT_NAME', 'Supermarket int. dansk')

# JWT Secret for authentication
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Access codes - In production, store these in database
VALID_ACCESS_CODES = {
    'SUPER2024': 'Supermarket Premium Access',
    'VAPI001': 'Basic Dashboard Access', 
    'DEMO123': 'Demo Access',
    'BETA2024': 'Beta Tester Access'
}

# Store user sessions (in production, use Redis or database)
user_sessions = {}
registered_users = {}

# Pydantic models for authentication
class LoginRequest(BaseModel):
    email: str
    access_code: str

class UserSession(BaseModel):
    email: str
    access_code: str
    access_level: str
    created_at: datetime
    
# Security
security = HTTPBearer(auto_error=False)

def create_access_token(email: str, access_code: str):
    """Create JWT access token"""
    payload = {
        'email': email,
        'access_code': access_code,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_access_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT access token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Adgangskode påkrævet")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get('email')
        access_code = payload.get('access_code')
        
        if not email or not access_code:
            raise HTTPException(status_code=401, detail="Ugyldig adgangstoken")
            
        # Verify access code is still valid
        if access_code not in VALID_ACCESS_CODES:
            raise HTTPException(status_code=401, detail="Adgangskode er ikke længere gyldig")
            
        return {'email': email, 'access_code': access_code, 'access_level': VALID_ACCESS_CODES[access_code]}
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Adgangstoken er udløbet")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Ugyldig adgangstoken")

# Authentication endpoints
@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Authenticate user with email and access code"""
    try:
        # Validate access code
        if request.access_code not in VALID_ACCESS_CODES:
            logger.warning(f"Invalid access code attempted: {request.access_code}")
            raise HTTPException(status_code=401, detail="Ugyldig adgangskode")
        
        # Simple email validation
        if '@' not in request.email or '.' not in request.email.split('@')[1]:
            raise HTTPException(status_code=400, detail="Ugyldig email adresse")
        
        # Create access token
        access_token = create_access_token(request.email, request.access_code)
        
        # Store user session
        user_id = hashlib.md5(request.email.encode()).hexdigest()
        user_sessions[user_id] = UserSession(
            email=request.email,
            access_code=request.access_code,
            access_level=VALID_ACCESS_CODES[request.access_code],
            created_at=datetime.utcnow()
        )
        
        # Store in registered users
        registered_users[request.email] = {
            'access_code': request.access_code,
            'access_level': VALID_ACCESS_CODES[request.access_code],
            'first_login': datetime.utcnow().isoformat(),
            'last_login': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Successful login: {request.email} with code {request.access_code}")
        
        return {
            'access_token': access_token,
            'token_type': 'bearer',
            'email': request.email,
            'access_level': VALID_ACCESS_CODES[request.access_code],
            'expires_in': JWT_EXPIRATION_HOURS * 3600
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Loginproblem - prøv igen")

@app.post("/api/auth/validate")
async def validate_token(user: dict = Depends(verify_access_token)):
    """Validate current access token"""
    return {
        'valid': True,
        'email': user['email'],
        'access_level': user['access_level']
    }

@app.get("/api/auth/logout")
async def logout(user: dict = Depends(verify_access_token)):
    """Logout user"""
    # In a real app, you'd blacklist the token
    return {'message': 'Logget ud succesfuldt'}

@app.get("/api/admin/users")
async def get_users(user: dict = Depends(verify_access_token)):
    """Get registered users (admin only)"""
    # Simple admin check - in production, implement proper role-based access
    if 'Premium' not in user.get('access_level', ''):
        raise HTTPException(status_code=403, detail="Adgang nægtet")
    
    return {
        'total_users': len(registered_users),
        'users': list(registered_users.keys()),
        'access_levels': [info['access_level'] for info in registered_users.values()]
    }

# Simple cache for API responses
api_cache = {}
CACHE_DURATION = 300  # 5 minutes

def get_cached_or_fetch(cache_key: str, fetch_func, cache_duration: int = CACHE_DURATION):
    """Get data from cache or fetch if expired"""
    current_time = time.time()
    
    if cache_key in api_cache:
        cached_data, timestamp = api_cache[cache_key]
        if current_time - timestamp < cache_duration:
            logger.info(f"Cache hit for {cache_key}")
            return cached_data
    
    # Fetch new data
    logger.info(f"Cache miss for {cache_key}, fetching new data")
    new_data = fetch_func()
    api_cache[cache_key] = (new_data, current_time)
    return new_data

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {
            "vapi_api_key": "configured" if VAPI_API_KEY else "missing",
            "openai_api_key": "configured" if OPENAI_API_KEY else "missing",
            "assistant_id": "configured" if VAPI_ASSISTANT_ID else "missing"
        }
    }

# Vapi API functions
async def fetch_vapi_calls():
    """Fetch calls from Vapi API with enhanced error handling"""
    if not VAPI_API_KEY:
        logger.warning("No Vapi API key provided, using mock data")
        return MOCK_INTERVIEWS
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {VAPI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            params = {}
            if VAPI_ASSISTANT_ID:
                params["assistantId"] = VAPI_ASSISTANT_ID
            
            logger.info(f"Fetching calls from Vapi API with assistant ID: {VAPI_ASSISTANT_ID}")
            
            response = await client.get(
                "https://api.vapi.ai/call", 
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                calls_data = response.json()
                logger.info(f"Successfully fetched {len(calls_data)} calls from Vapi")
                
                if not calls_data:
                    logger.info("No calls found, using mock data for demonstration")
                    return MOCK_INTERVIEWS
                
                processed_calls = process_vapi_calls(calls_data)
                logger.info(f"Processed {len(processed_calls)} calls successfully")
                return processed_calls
                
            elif response.status_code == 401:
                logger.error("Vapi API authentication failed - invalid API key")
                return MOCK_INTERVIEWS
            elif response.status_code == 403:
                logger.error("Vapi API access forbidden - check permissions")
                return MOCK_INTERVIEWS
            elif response.status_code == 429:
                logger.warning("Vapi API rate limit exceeded, using cached data")
                return MOCK_INTERVIEWS
            else:
                logger.error(f"Vapi API error: {response.status_code} - {response.text}")
                return MOCK_INTERVIEWS
                
    except httpx.TimeoutException:
        logger.error("Vapi API timeout, using mock data")
        return MOCK_INTERVIEWS
    except httpx.RequestError as e:
        logger.error(f"Vapi API request error: {e}")
        return MOCK_INTERVIEWS
    except Exception as e:
        logger.error(f"Unexpected error fetching Vapi calls: {e}")
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
                "transcript": anonymize_transcript(transcript) if transcript else "Ingen transskription tilgængelig"
            }
            
            processed_calls.append(processed_call)
            
        except Exception as e:
            print(f"Error processing call {call.get('id', 'unknown')}: {e}")
            continue
    
    return processed_calls

# Mock data for development - Enhanced with theme-relevant content
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
        "transcript": "User: Jeg synes butikken har et rigtig godt udvalg af varer, især de friske grøntsager er fantastiske. User: Personalet var meget venligt og hjælpsomt når jeg spurgte om hjælp. User: Priserne er lidt høje sammenlignet med andre steder, men kvaliteten er god. User: Køerne var ikke så lange i dag, så det gik hurtigt.",
        "themes": ["udvalg", "personale", "priser", "kø"]
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
        "transcript": "User: Fantastisk stort udvalg - man kan finde alt her! User: Dog kan det være svært at finde rundt i butikken, den er meget stor og ikke særlig overskuelig. User: Kassedamerne var søde og professionelle. User: Priserne er rimelige for det store udvalg man får.",
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
        "transcript": "User: Butikken er lille men meget overskuelig og let at navigere i. User: Udvalget er begrænset - de har ikke så mange varer, men det mest nødvendige findes. User: Personalet virkede stresset og havde ikke tid til at hjælpe. User: Til gengæld er priserne virkelig gode og økonomiske.",
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
        "transcript": "User: Irma har altid en dejlig atmosfære og stemning. User: Personalet er super venligt og professionelt - de hjælper altid gerne. User: Butikken er flot indrettet og let at navigere i. User: De har gode økologiske varer og friske grøntsager. User: Men priserne er virkelig høje - det er en luksusbetegnelse at handle her.",
        "themes": ["atmosfære", "personale", "indretning", "friskhed", "priser"]
    },
    {
        "id": str(uuid.uuid4()),
        "timestamp": "2024-12-19T18:30:00Z",
        "duration": 190,
        "supermarket": "Kvickly Valby",
        "status": "completed",
        "ratings": {
            "udvalg_af_varer": 7,
            "overskuelighed_indretning": 6,
            "stemning_personal": 7,
            "prisniveau_kvalitet": 6,
            "samlet_karakter": 6
        },
        "transcript": "User: Lange køer ved kasserne - man skal vente alt for længe. User: Udvalget er okay, man kan finde det meste. User: Butikken er lidt rodet og ikke så overskuelig som den kunne være. User: Personalet er okay, men ikke særlig imødekommende. User: Priserne er middel.",
        "themes": ["kø", "udvalg", "indretning", "personale", "priser"]
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
    """Extract and cluster themes from transcripts with relevant quotes"""
    if not transcripts:
        return {}
    
    # Enhanced theme patterns with more specific keywords
    theme_patterns = {
        'udvalg': {
            'keywords': ['udvalg', 'varer', 'sortiment', 'produkter', 'selection', 'mange', 'få', 'alt', 'find'],
            'positive_patterns': ['godt udvalg', 'stort udvalg', 'fantastisk udvalg', 'kan finde alt', 'mange varer'],
            'negative_patterns': ['lille udvalg', 'begrænset udvalg', 'få varer', 'ikke finde', 'mangler']
        },
        'personale': {
            'keywords': ['personale', 'kassedame', 'ekspedient', 'service', 'hjælp', 'venlig', 'professionel', 'stresset'],
            'positive_patterns': ['venligt personale', 'hjælpsomt', 'søde', 'professionelt', 'service'],
            'negative_patterns': ['stresset', 'ikke tid', 'uhøflig', 'ikke hjælpe']
        },
        'priser': {
            'keywords': ['pris', 'billig', 'dyr', 'høj', 'rimelig', 'kostbar', 'luksusbetegnelse', 'økonomisk'],
            'positive_patterns': ['rimelige priser', 'gode priser', 'billig', 'økonomisk'],
            'negative_patterns': ['høje priser', 'dyre', 'kostbar', 'luksusbetegnelse']
        },
        'indretning': {
            'keywords': ['indretning', 'overskuelig', 'navigation', 'stor', 'lille', 'flot', 'let at navigere'],
            'positive_patterns': ['overskuelig', 'let at navigere', 'flot indrettet', 'pæn'],
            'negative_patterns': ['svært at finde', 'ikke overskuelig', 'rodet', 'forvirrende']
        },
        'kø': {
            'keywords': ['kø', 'vente', 'hurtig', 'lang', 'tid', 'kasser'],
            'positive_patterns': ['ikke så lange', 'hurtig', 'ingen kø'],
            'negative_patterns': ['lange køer', 'vente længe', 'meget lang']
        },
        'atmosfære': {
            'keywords': ['atmosfære', 'stemning', 'miljø', 'hyggelig', 'dejlig', 'rart'],
            'positive_patterns': ['dejlig atmosfære', 'hyggelig', 'rart miljø', 'god stemning'],
            'negative_patterns': ['dårlig atmosfære', 'ubehagelig', 'ikke rart']
        },
        'renlighed': {
            'keywords': ['ren', 'pæn', 'beskidt', 'rod', 'ryddet'],
            'positive_patterns': ['ren', 'pæn', 'ryddet'],
            'negative_patterns': ['beskidt', 'rod', 'uryddet']
        },
        'friskhed': {
            'keywords': ['frisk', 'grøntsag', 'kød', 'fisk', 'øko', 'kvalitet', 'dårlig'],
            'positive_patterns': ['friske grøntsager', 'god kvalitet', 'frisk', 'øko'],
            'negative_patterns': ['ikke frisk', 'dårlig kvalitet', 'gammel']
        }
    }
    
    themes = defaultdict(list)
    
    for i, transcript in enumerate(transcripts):
        if i >= len(MOCK_INTERVIEWS):
            break
            
        transcript_lower = transcript.lower()
        
        for theme_name, theme_config in theme_patterns.items():
            # Check if any keywords match
            if any(keyword in transcript_lower for keyword in theme_config['keywords']):
                
                # Determine sentiment based on patterns in the transcript
                sentiment = 'neutral'  # default
                
                # Check for positive patterns
                if any(pattern in transcript_lower for pattern in theme_config['positive_patterns']):
                    sentiment = 'positive'
                # Check for negative patterns
                elif any(pattern in transcript_lower for pattern in theme_config['negative_patterns']):
                    sentiment = 'negative'
                else:
                    # Fallback to general sentiment analysis
                    sentiment = analyze_sentiment_with_openai(transcript)
                
                # Extract relevant quote (the sentence containing the theme keywords)
                sentences = transcript.split('.')
                relevant_quote = transcript  # fallback
                
                # Find the best user quote (not AI)
                user_quotes = []
                
                # Split transcript into parts and look for user responses
                if 'User:' in transcript or 'user:' in transcript:
                    # Handle conversation format with User: labels
                    parts = transcript.split('User:')
                    for part in parts[1:]:  # Skip the first part (before first User:)
                        # Clean the user response
                        user_response = part.split('AI:')[0].strip()  # Remove any AI follow-up
                        if user_response:
                            user_response = user_response.replace('\n', ' ').strip()
                            if any(keyword in user_response.lower() for keyword in theme_config['keywords']):
                                if len(user_response) > 10 and len(user_response) < 200:
                                    user_quotes.append(user_response)
                else:
                    # Handle simple text format - look for sentences with theme keywords
                    sentences = transcript.replace('\n', ' ').split('.')
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if sentence and any(keyword in sentence.lower() for keyword in theme_config['keywords']):
                            # Skip if it looks like an AI question
                            ai_question_indicators = [
                                'hvordan', 'hvad', 'kan du', 'vil du', 'er der', 
                                'fortæl', 'beskriv', 'mener du', 'synes du'
                            ]
                            if not any(indicator in sentence.lower() for indicator in ai_question_indicators):
                                if len(sentence) > 10 and len(sentence) < 200:
                                    user_quotes.append(sentence)
                
                # If no good user quotes found, skip this theme mention
                if not user_quotes:
                    continue
                
                # Use the best user quote
                relevant_quote = user_quotes[0]
                
                themes[theme_name].append({
                    'text': relevant_quote,
                    'sentiment': sentiment,
                    'timestamp': MOCK_INTERVIEWS[i]['timestamp'],
                    'supermarket': MOCK_INTERVIEWS[i]['supermarket']
                })
    
    return dict(themes)

@app.get("/api/overview")
async def get_overview(request: Request, user: dict = Depends(verify_access_token)):
    """Get dashboard overview statistics with caching"""
    try:
        # Use async caching
        cache_key = "vapi_calls"
        current_time = time.time()
        
        # Check cache first
        if cache_key in api_cache:
            cached_data, timestamp = api_cache[cache_key]
            if current_time - timestamp < 180:  # 3 minute cache
                logger.info(f"Cache hit for {cache_key}")
                interviews = cached_data
            else:
                logger.info(f"Cache expired for {cache_key}, fetching new data")
                interviews = await fetch_vapi_calls()
                api_cache[cache_key] = (interviews, current_time)
        else:
            logger.info(f"Cache miss for {cache_key}, fetching new data")
            interviews = await fetch_vapi_calls()
            api_cache[cache_key] = (interviews, current_time)
        
        total_interviews = len(interviews)
        active_interviews = len([i for i in interviews if i['status'] == 'active'])
        
        if total_interviews > 0:
            avg_duration = sum(interview['duration'] for interview in interviews) / total_interviews
        else:
            avg_duration = 0
        
        # Calculate trends
        today = datetime.now().date()
        today_interviews = 0
        yesterday_interviews = 0
        
        for interview in interviews:
            try:
                interview_date = datetime.fromisoformat(interview['timestamp'].replace('Z', '+00:00')).date()
                if interview_date == today:
                    today_interviews += 1
                elif interview_date == today - timedelta(days=1):
                    yesterday_interviews += 1
            except:
                continue
        
        if yesterday_interviews > 0:
            trend = ((today_interviews - yesterday_interviews) / yesterday_interviews * 100)
        else:
            trend = 100 if today_interviews > 0 else 0
        
        logger.info(f"Overview requested by {user['email']}: {total_interviews} total, {active_interviews} active, {avg_duration:.1f}s avg")
        
        return {
            "total_interviews": total_interviews,
            "active_interviews": active_interviews,
            "avg_duration": round(avg_duration),
            "trend_percentage": round(trend, 1),
            "assistant_name": ASSISTANT_NAME,
            "last_updated": datetime.now().isoformat(),
            "user_access_level": user['access_level']
        }
    except Exception as e:
        logger.error(f"Error in get_overview: {e}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente oversigtsdata")

@app.get("/api/themes")
async def get_themes(request: Request, user: dict = Depends(verify_access_token), days: int = Query(7, description="Number of days to look back")):
    """Get theme analysis with sentiment"""
    try:
        # Use same cached data as overview
        cache_key = "vapi_calls"
        current_time = time.time()
        
        if cache_key in api_cache:
            cached_data, timestamp = api_cache[cache_key]
            if current_time - timestamp < 180:  # 3 minute cache
                interviews = cached_data
            else:
                interviews = await fetch_vapi_calls()
                api_cache[cache_key] = (interviews, current_time)
        else:
            interviews = await fetch_vapi_calls()
            api_cache[cache_key] = (interviews, current_time)
        
        transcripts = [interview['transcript'] for interview in interviews if interview['transcript']]
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
                'is_new': False  # You could implement logic to detect new themes
            })
        
        # Sort by total mentions
        processed_themes.sort(key=lambda x: x['total_mentions'], reverse=True)
        
        logger.info(f"Themes: processed {len(processed_themes)} themes")
        return {"themes": processed_themes}
    except Exception as e:
        logger.error(f"Error in get_themes: {e}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente temaer")

@app.get("/api/ratings")
async def get_ratings():
    """Get average ratings for the 5 standard questions"""
    interviews = await fetch_vapi_calls()
    
    rating_sums = defaultdict(float)
    rating_counts = defaultdict(int)
    
    for interview in interviews:
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
        if rating_counts[question] > 0:
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
    interviews = await fetch_vapi_calls()
    
    if supermarket:
        interviews = [i for i in interviews if supermarket.lower() in i['supermarket'].lower()]
    
    # Sort by timestamp (newest first)
    try:
        interviews.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')), reverse=True)
    except:
        # Fallback if timestamp parsing fails
        interviews.reverse()
    
    return {
        "interviews": interviews[:limit],
        "total": len(interviews)
    }

@app.get("/api/interview/{interview_id}")
async def get_full_interview(interview_id: str, user: dict = Depends(verify_access_token)):
    """Get full anonymized transcript for a specific interview"""
    try:
        # Get all interviews
        cache_key = "vapi_calls"
        current_time = time.time()
        
        if cache_key in api_cache:
            cached_data, timestamp = api_cache[cache_key]
            if current_time - timestamp < 180:  # 3 minute cache
                interviews = cached_data
            else:
                interviews = await fetch_vapi_calls()
                api_cache[cache_key] = (interviews, current_time)
        else:
            interviews = await fetch_vapi_calls()
            api_cache[cache_key] = (interviews, current_time)
        
        # Find the specific interview
        target_interview = None
        for interview in interviews:
            if interview['id'] == interview_id:
                target_interview = interview
                break
        
        if not target_interview:
            raise HTTPException(status_code=404, detail="Interview ikke fundet")
        
        logger.info(f"Full interview requested by {user['email']} for interview {interview_id}")
        
        # Return full interview (already anonymized in process_vapi_calls)
        return {
            "id": target_interview['id'],
            "timestamp": target_interview['timestamp'],
            "duration": target_interview['duration'],
            "supermarket": target_interview['supermarket'],
            "status": target_interview['status'],
            "ratings": target_interview['ratings'],
            "transcript": target_interview['transcript'],  # Already anonymized
            "original_length": len(target_interview['transcript']),
            "anonymized": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_full_interview: {e}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente interview")

@app.get("/api/supermarkets")
async def get_supermarkets():
    """Get list of supermarkets from interviews"""
    interviews = await fetch_vapi_calls()
    supermarkets = list(set(interview['supermarket'] for interview in interviews))
    return {"supermarkets": sorted(supermarkets)}

@app.post("/api/chat")
async def chat_query(query: ChatQuery):
    """Answer questions about the dashboard data"""
    question = query.question.lower()
    interviews = await fetch_vapi_calls()
    
    # Simple question answering logic
    if 'hvor mange' in question and 'interview' in question:
        if 'uge' in question or 'week' in question:
            return {"answer": f"Der blev lavet {len(interviews)} interviews i denne periode."}
        else:
            return {"answer": f"Der er i alt {len(interviews)} gennemførte interviews."}
    
    elif 'sentiment' in question or 'stemning' in question:
        if 'kø' in question:
            return {"answer": "Sentimentfordelingen for tema 'kø-oplevelse' bliver beregnet baseret på jeres Vapi data."}
        else:
            return {"answer": "Overordnet sentiment bliver analyseret fra jeres interviews med OpenAI."}
    
    elif 'karakter' in question or 'rating' in question:
        if interviews:
            avg_rating = sum(interview['ratings']['samlet_karakter'] for interview in interviews) / len(interviews)
            return {"answer": f"Gennemsnitlig samlet karakter er {avg_rating:.1f} ud af 10 baseret på {len(interviews)} interviews."}
        else:
            return {"answer": "Ingen ratings data tilgængelig endnu."}
    
    elif 'tema' in question or 'theme' in question:
        return {"answer": f"Temaer bliver automatisk ekstraheret fra jeres {len(interviews)} Vapi interviews og analyseret for sentiment."}
    
    else:
        return {"answer": f"Jeg kan hjælpe dig med spørgsmål om jeres {len(interviews)} interviews, temaer, karakterer og sentiment. Prøv at spørge: 'Hvor mange interviews blev lavet i denne uge?'"}

# Add endpoint to test Vapi connection
@app.get("/api/vapi/test")
async def test_vapi_connection():
    """Test connection to Vapi API"""
    if not VAPI_API_KEY:
        return {"status": "error", "message": "Ingen Vapi API key fundet"}
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {VAPI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            response = await client.get(
                "https://api.vapi.ai/call", 
                headers=headers,
                params={"assistantId": VAPI_ASSISTANT_ID} if VAPI_ASSISTANT_ID else {}
            )
            
            if response.status_code == 200:
                calls_data = response.json()
                return {
                    "status": "success", 
                    "message": f"Vapi forbindelse OK - fandt {len(calls_data)} opkald",
                    "assistant_id": VAPI_ASSISTANT_ID,
                    "calls_count": len(calls_data)
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Vapi API fejl: {response.status_code} - {response.text}",
                    "response_code": response.status_code
                }
                
    except Exception as e:
        return {"status": "error", "message": f"Vapi forbindelsesfejl: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
