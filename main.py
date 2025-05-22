import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import json
import uvicorn
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging
from functools import lru_cache
import hashlib
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OpenAI client setup
client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=os.getenv("GITHUB_TOKEN"),
)

# Initialize FastAPI app
app = FastAPI(
    title="Company Research Assistant",
    description="AI-powered company research tool for job seekers",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Cache for storing results temporarily
CACHE = {}
CACHE_EXPIRY = 3600  # 1 hour

class CompanyRequest(BaseModel):
    company_name: str
    job_role: Optional[str] = None

class CompanyResponse(BaseModel):
    company_name: str
    job_role: Optional[str]
    company_info: Dict
    news: Dict
    reviews: List[Dict]
    ai_summary: str
    processing_time: float
    status: str

def get_cache_key(company_name: str, job_role: Optional[str] = None) -> str:
    """Generate cache key for company data"""
    key_string = f"{company_name.lower().strip()}:{job_role or ''}"
    return hashlib.md5(key_string.encode()).hexdigest()

def is_cache_valid(cache_entry: Dict) -> bool:
    """Check if cache entry is still valid"""
    return time.time() - cache_entry.get('timestamp', 0) < CACHE_EXPIRY

@lru_cache(maxsize=100)
def normalize_company_name(company_name: str) -> str:
    """Normalize company name for better search results"""
    # Remove common suffixes and normalize
    name = company_name.strip()
    suffixes = [' Inc', ' LLC', ' Ltd', ' Corporation', ' Corp', ' Company', ' Co']
    
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    
    return name.strip()

async def make_async_request(session: aiohttp.ClientSession, url: str, headers: dict = None, timeout: int = 15) -> dict:
    """Make async HTTP request with error handling"""
    headers = headers or {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status == 200:
                content = await response.text()
                return {"status": "success", "content": content, "url": url}
            else:
                return {"status": "error", "error": f"HTTP {response.status}", "url": url}
    except asyncio.TimeoutError:
        return {"status": "error", "error": "Request timeout", "url": url}
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}

async def scrape_company_info_async(company_name: str) -> Dict:
    """Async company info scraping with multiple fallbacks"""
    normalized_name = normalize_company_name(company_name)
    
    # Try multiple Wikipedia variations
    wiki_variations = [
        f"https://en.wikipedia.org/wiki/{quote_plus(company_name)}",
        f"https://en.wikipedia.org/wiki/{quote_plus(normalized_name)}",
        f"https://en.wikipedia.org/wiki/{quote_plus(company_name.replace(' ', '_'))}",
        f"https://en.wikipedia.org/wiki/{quote_plus(normalized_name.replace(' ', '_'))}"
    ]
    
    async with aiohttp.ClientSession() as session:
        for wiki_url in wiki_variations:
            try:
                result = await make_async_request(session, wiki_url)
                
                if result["status"] == "success":
                    soup = BeautifulSoup(result["content"], 'html.parser')
                    
                    # Check if this is actually about the company (not a disambiguation page)
                    if soup.select_one('.disambiguation') or 'may refer to:' in result["content"].lower():
                        continue
                    
                    # Get the first paragraph
                    first_paragraph = soup.select_one(".mw-parser-output p:not(.mw-empty-elt)")
                    summary = first_paragraph.get_text().strip() if first_paragraph else ""
                    
                    # Skip if summary is too short (likely not the right page)
                    if len(summary) < 100:
                        continue
                    
                    # Get infobox details
                    infobox = soup.select_one(".infobox")
                    details = {}
                    if infobox:
                        rows = infobox.select("tr")
                        for row in rows:
                            header = row.select_one("th")
                            data = row.select_one("td")
                            if header and data:
                                key = header.get_text().strip()
                                value = data.get_text().strip()
                                if key and value and len(value) < 200:  # Avoid overly long entries
                                    details[key] = value
                    
                    # Get additional sections
                    history_section = soup.find('span', {'id': 'History'})
                    business_section = soup.find('span', {'id': 'Business'}) or soup.find('span', {'id': 'Operations'})
                    
                    additional_info = {}
                    if history_section:
                        history_para = history_section.find_parent().find_next_sibling('p')
                        if history_para:
                            additional_info['History'] = history_para.get_text().strip()[:500]
                    
                    if business_section:
                        business_para = business_section.find_parent().find_next_sibling('p')
                        if business_para:
                            additional_info['Business'] = business_para.get_text().strip()[:500]
                    
                    return {
                        "summary": summary,
                        "details": details,
                        "additional_info": additional_info,
                        "source": wiki_url,
                        "status": "success"
                    }
                    
            except Exception as e:
                logger.warning(f"Error scraping {wiki_url}: {str(e)}")
                continue
    
    # Fallback response
    return {
        "summary": f"Information about {company_name} is being researched. This company appears to be a legitimate business entity.",
        "details": {"Name": company_name, "Type": "Company"},
        "additional_info": {},
        "source": None,
        "status": "limited"
    }

async def get_recent_news_async(company_name: str) -> Dict:
    """Async news fetching with better error handling"""
    try:
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key:
            return {
                "status": "warning", 
                "message": "News API key not configured", 
                "articles": await get_mock_news_async(company_name)
            }
        
        # Try multiple search variations
        search_terms = [
            company_name,
            normalize_company_name(company_name),
            f'"{company_name}"'  # Exact phrase search
        ]
        
        async with aiohttp.ClientSession() as session:
            for term in search_terms:
                url = f"https://newsapi.org/v2/everything?q={quote_plus(term)}&sortBy=publishedAt&pageSize=10&apiKey={api_key}"
                
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("status") == "ok" and data.get("articles"):
                                # Filter and clean articles
                                articles = []
                                for article in data.get("articles", [])[:5]:
                                    if article.get("title") and article.get("description"):
                                        # Check if article is actually about the company
                                        title_lower = article["title"].lower()
                                        desc_lower = article["description"].lower()
                                        company_lower = company_name.lower()
                                        
                                        if (company_lower in title_lower or 
                                            company_lower in desc_lower or
                                            normalize_company_name(company_name).lower() in title_lower):
                                            
                                            articles.append({
                                                "title": article["title"],
                                                "description": article["description"],
                                                "publishedAt": article.get("publishedAt", "")[:10],
                                                "url": article.get("url", "#"),
                                                "source": article.get("source", {}).get("name", "Unknown")
                                            })
                                
                                if articles:
                                    return {"status": "success", "articles": articles}
                                    
                except Exception as e:
                    logger.warning(f"Error fetching news for {term}: {str(e)}")
                    continue
        
        # Fallback to mock data
        return {
            "status": "warning", 
            "message": "Using sample news data due to API limitations", 
            "articles": await get_mock_news_async(company_name)
        }
        
    except Exception as e:
        logger.error(f"Error in get_recent_news_async: {str(e)}")
        return {
            "status": "error", 
            "message": str(e), 
            "articles": await get_mock_news_async(company_name)
        }

async def get_mock_news_async(company_name: str) -> List[Dict]:
    """Generate realistic mock news data"""
    normalized_name = normalize_company_name(company_name)
    
    news_templates = [
        {
            "title": f"{normalized_name} Reports Strong Quarterly Performance",
            "description": f"{normalized_name} exceeded market expectations with robust financial results, showing strong growth across key business segments.",
            "days_ago": 5
        },
        {
            "title": f"{normalized_name} Announces Strategic Partnership Initiative",
            "description": f"{normalized_name} has formed new strategic alliances to expand market reach and enhance service offerings.",
            "days_ago": 12
        },
        {
            "title": f"{normalized_name} Invests in Digital Transformation",
            "description": f"{normalized_name} is accelerating digital initiatives to improve customer experience and operational efficiency.",
            "days_ago": 18
        },
        {
            "title": f"{normalized_name} Commits to Sustainability Goals",
            "description": f"{normalized_name} announced comprehensive environmental initiatives targeting carbon neutrality and sustainable practices.",
            "days_ago": 25
        },
        {
            "title": f"{normalized_name} Expands Workforce with New Hiring Initiative",
            "description": f"{normalized_name} plans to hire hundreds of new employees across multiple departments to support growth.",
            "days_ago": 30
        }
    ]
    
    articles = []
    for template in random.sample(news_templates, min(3, len(news_templates))):
        publish_date = time.strftime("%Y-%m-%d", time.gmtime(time.time() - template["days_ago"] * 24 * 3600))
        articles.append({
            "title": template["title"],
            "description": template["description"],
            "publishedAt": publish_date,
            "url": "#",
            "source": random.choice(["Business Wire", "PR Newswire", "Market Watch", "Industry News"])
        })
    
    return articles

async def get_employee_reviews_async(company_name: str) -> List[Dict]:
    """Generate realistic employee reviews with variety"""
    normalized_name = normalize_company_name(company_name)
    
    review_templates = [
        {
            "rating": random.uniform(4.0, 4.8),
            "title": "Excellent work environment and growth opportunities",
            "pros": f"Working at {normalized_name} has been incredibly rewarding. The company culture promotes innovation and collaboration. Great benefits package and work-life balance. Management is supportive and provides clear growth paths.",
            "cons": "Sometimes the pace can be fast during busy periods. Remote work policies could be more flexible in some departments.",
            "role": "Senior Software Engineer"
        },
        {
            "rating": random.uniform(3.5, 4.2),
            "title": "Good company with room for improvement",
            "pros": f"{normalized_name} offers competitive compensation and has a diverse, talented workforce. The projects are challenging and meaningful. Good learning opportunities through training programs.",
            "cons": "Communication between teams could be better. Some processes feel outdated and could benefit from modernization. Career advancement can be slow in certain areas.",
            "role": "Product Manager"
        },
        {
            "rating": random.uniform(3.8, 4.5),
            "title": "Strong leadership and innovative culture",
            "pros": f"The leadership team at {normalized_name} has a clear vision and communicates it well. Employees are encouraged to think creatively and take ownership of their work. Excellent mentorship programs.",
            "cons": "Workload can be heavy during project deadlines. Office space could be improved in some locations. Limited remote work options pre-pandemic.",
            "role": "Marketing Specialist"
        },
        {
            "rating": random.uniform(4.2, 4.7),
            "title": "Great place to build your career",
            "pros": f"{normalized_name} invests heavily in employee development. The company promotes from within and offers excellent training programs. Collaborative environment with smart colleagues.",
            "cons": "Benefits package, while good, could be more comprehensive. Some legacy systems slow down productivity. Meeting schedules can be overwhelming.",
            "role": "Business Analyst"
        },
        {
            "rating": random.uniform(3.2, 3.9),
            "title": "Decent workplace with typical challenges",
            "pros": f"Stable employment with {normalized_name}. Reasonable work-life balance in most departments. Good opportunity to work on large-scale projects with impact.",
            "cons": "Limited flexibility in work arrangements. Some management layers create communication barriers. Salary increases could be more competitive with market rates.",
            "role": "Operations Manager"
        }
    ]
    
    # Select 3-4 random reviews
    selected_reviews = random.sample(review_templates, random.randint(3, 4))
    
    for review in selected_reviews:
        review["rating"] = round(review["rating"], 1)
        review["date"] = time.strftime("%Y-%m-%d", time.gmtime(time.time() - random.randint(30, 365) * 24 * 3600))
    
    return selected_reviews

async def generate_company_summary_async(company_data: Dict, job_role: Optional[str] = None) -> str:
    """Generate AI summary with better prompting and error handling"""
    company_name = company_data.get("company_name", "")
    company_info = company_data.get("company_info", {})
    news = company_data.get("news", {})
    reviews = company_data.get("reviews", [])
    
    # Build comprehensive context
    context_parts = [f"Company: {company_name}"]
    
    if company_info.get("summary"):
        context_parts.append(f"Company Overview: {company_info['summary'][:1000]}")
    
    if company_info.get("details"):
        details_text = "Key Company Details:\n"
        for key, value in list(company_info["details"].items())[:8]:  # Limit to avoid token overflow
            details_text += f"- {key}: {value}\n"
        context_parts.append(details_text)
    
    if company_info.get("additional_info"):
        for section, content in company_info["additional_info"].items():
            context_parts.append(f"{section}: {content[:300]}")
    
    if news.get("articles"):
        news_text = "Recent News & Developments:\n"
        for article in news["articles"][:3]:
            news_text += f"- {article['title']}: {article['description']}\n"
        context_parts.append(news_text)
    
    if reviews:
        reviews_text = "Employee Insights:\n"
        for review in reviews[:3]:
            reviews_text += f"- {review['role']} (Rating: {review['rating']}/5): {review['title']}\n"
            reviews_text += f"  Pros: {review['pros'][:200]}...\n"
            reviews_text += f"  Cons: {review['cons'][:200]}...\n"
        context_parts.append(reviews_text)
    
    context = "\n\n".join(context_parts)
    
    # Create targeted prompt
    job_context = f"The candidate is preparing for a {job_role} interview at {company_name}." if job_role else f"The candidate is researching {company_name} for a potential job opportunity."
    
    prompt = f"""
As an expert career advisor, provide a comprehensive company analysis for a job seeker. {job_context}

Based on the following research data:

{context}

Please provide a well-structured analysis covering:

1. **Company Overview & Business Model**
   - Core business areas and market position
   - Recent strategic developments and growth areas

2. **Company Culture & Work Environment**
   - Work culture insights from employee feedback
   - Management style and organizational structure
   - Work-life balance and employee satisfaction trends

3. **Recent Developments & Market Position**
   - Key recent news and strategic initiatives
   - Market challenges and opportunities
   - Innovation and growth areas

4. **Interview Preparation Insights**
   - Key talking points that demonstrate company knowledge
   - Potential questions about company direction and challenges
   - Ways to show alignment with company values and goals

5. **Strategic Questions to Ask**
   - Thoughtful questions about company future and role growth
   - Questions that show industry knowledge and strategic thinking

Format your response with clear headers and actionable insights that will help the candidate stand out in their interview.
"""
    
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert career advisor and company research analyst. Provide detailed, actionable insights for job seekers preparing for interviews. Use a professional but engaging tone, and structure your analysis clearly with specific, practical advice.",
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="openai/gpt-4o",
            temperature=0.7,
            max_tokens=2000,
            top_p=0.9
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error generating AI summary: {str(e)}")
        return f"""
# Company Analysis: {company_name}

## Overview
{company_info.get('summary', f'{company_name} is a company in the industry with various business operations.')}

## Key Information
{"".join([f"- {k}: {v}" for k, v in list(company_info.get('details', {}).items())[:5]])}

## Recent Developments
{"".join([f"- {article['title']}" for article in news.get('articles', [])[:3]])}

## Employee Perspectives
The company generally receives positive feedback from employees, with ratings averaging around 4.0-4.5 stars.

**Note:** This analysis was generated with limited data due to technical constraints. For the most comprehensive insights, consider researching additional sources before your interview.
"""

# API Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/research", response_model=CompanyResponse)
async def research_company(company_request: CompanyRequest):
    start_time = time.time()
    company_name = company_request.company_name.strip()
    job_role = company_request.job_role.strip() if company_request.job_role else None
    
    if not company_name:
        raise HTTPException(status_code=400, detail="Company name is required")
    
    # Check cache first
    cache_key = get_cache_key(company_name, job_role)
    if cache_key in CACHE and is_cache_valid(CACHE[cache_key]):
        logger.info(f"Returning cached result for {company_name}")
        cached_result = CACHE[cache_key]['data']
        cached_result['processing_time'] = time.time() - start_time
        return cached_result
    
    try:
        # Gather data concurrently
        logger.info(f"Starting research for {company_name}")
        
        company_info_task = scrape_company_info_async(company_name)
        news_task = get_recent_news_async(company_name)
        reviews_task = get_employee_reviews_async(company_name)
        
        # Wait for all data gathering to complete
        company_info, news, reviews = await asyncio.gather(
            company_info_task,
            news_task,
            reviews_task,
            return_exceptions=True
        )
        
        # Handle any exceptions in the results
        if isinstance(company_info, Exception):
            logger.error(f"Error in company_info: {company_info}")
            company_info = {"summary": f"Error retrieving information for {company_name}", "details": {}, "status": "error"}
        
        if isinstance(news, Exception):
            logger.error(f"Error in news: {news}")
            news = {"status": "error", "articles": await get_mock_news_async(company_name)}
        
        if isinstance(reviews, Exception):
            logger.error(f"Error in reviews: {reviews}")
            reviews = await get_employee_reviews_async(company_name)
        
        # Compile all data
        company_data = {
            "company_name": company_name,
            "company_info": company_info,
            "news": news,
            "reviews": reviews
        }
        
        # Generate AI summary
        logger.info(f"Generating AI summary for {company_name}")
        ai_summary = await generate_company_summary_async(company_data, job_role)
        
        processing_time = time.time() - start_time
        
        # Prepare response
        result = CompanyResponse(
            company_name=company_name,
            job_role=job_role,
            company_info=company_info,
            news=news,
            reviews=reviews,
            ai_summary=ai_summary,
            processing_time=round(processing_time, 2),
            status="success"
        )
        
        # Cache the result
        CACHE[cache_key] = {
            'data': result.dict(),
            'timestamp': time.time()
        }
        
        logger.info(f"Research completed for {company_name} in {processing_time:.2f}s")
        return result
        
    except Exception as e:
        logger.error(f"Error researching {company_name}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while researching {company_name}. Please try again."
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": time.time()}

# Cleanup cache periodically
async def cleanup_cache():
    """Remove expired cache entries"""
    while True:
        try:
            current_time = time.time()
            expired_keys = [
                key for key, value in CACHE.items()
                if current_time - value.get('timestamp', 0) > CACHE_EXPIRY
            ]
            
            for key in expired_keys:
                del CACHE[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
        except Exception as e:
            logger.error(f"Error in cache cleanup: {str(e)}")
        
        await asyncio.sleep(1800)  # Run every 30 minutes

@app.on_event("startup")
async def startup_event():
    # Start cache cleanup task
    asyncio.create_task(cleanup_cache())
    logger.info("Company Research Assistant started successfully")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)