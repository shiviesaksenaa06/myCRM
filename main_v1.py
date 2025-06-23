import os
import time
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI, OpenAIError
import httpx

from linkedin_bot import connect_with_message

load_dotenv()
SERPAPI_KEY       = os.getenv("SERPAPI_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
LINKEDIN_EMAIL    = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

if not all([SERPAPI_KEY, OPENAI_API_KEY, LINKEDIN_EMAIL, LINKEDIN_PASSWORD]):
    raise RuntimeError("❌ Missing required environment variables.")

# HTTPX client (no proxies)
http_client = httpx.Client()
client = OpenAI(http_client=http_client)

app = FastAPI(
    title="LinkedIn CRM Assistant (DEBUG MODE)",
    description="🔧 Inline send_request with GPT-4 only (no 3.5 fallback)."
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

class SearchRequest(BaseModel):
    name: str
    company: str
    sender_name: str
    context: str

class SendRequest(BaseModel):
    profile_url: str
    message: str

def search_linkedin_profiles(name: str, company: str, max_results: int = 3):
    query = f'"{name}" {company} site:linkedin.com/in/'
    resp = requests.get(
        "https://serpapi.com/search",
        params={"q":query, "api_key":SERPAPI_KEY, "engine":"google", "num":max_results, "filter":0},
        timeout=30
    )
    resp.raise_for_status()
    profiles = []
    for r in resp.json().get("organic_results", []):
        link = r.get("link","")
        if "/in/" not in link: continue
        title = r.get("title","").replace(" | LinkedIn","").strip()
        snippet = (r.get("snippet") or "").lower()
        pos = ""
        if " at " in snippet:
            p = snippet.split(" at ")[0].strip()
            if len(p)<50:
                pos = p.capitalize()
        profiles.append({"name":title,"link":link,"snippet":r.get("snippet",""),"position":pos})
    return profiles

def generate_message(sender_name, recipient_name, recipient_company, position, context):
    pos_line = f"Position: {position}" if position else ""
    prompt = f"""
You are a helpful assistant drafting a LinkedIn connection note.

Sender: {sender_name}
Recipient: {recipient_name}
Company: {recipient_company}
{pos_line}
Context: {context}

Write a short (≤300 chars), conversational, professional invite that:
- Mentions the context
- Shows genuine interest in connecting
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role":"system","content":"You write concise LinkedIn invites."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7,
            max_tokens=200,
        )
        msg = resp.choices[0].message.content.strip()
        return msg if len(msg) <= 300 else msg[:297] + "..."
    except OpenAIError as e:
        # If GPT-4 fails, bubble up an error—no 3.5 fallback
        raise HTTPException(status_code=500, detail=f"GPT-4 error: {e}")

@app.post("/search_and_generate")
def search_and_generate(req: SearchRequest):
    profiles = search_linkedin_profiles(req.name, req.company)
    if not profiles:
        return {"message":"No profiles found.","candidates":[]}

    message = generate_message(
        sender_name=req.sender_name,
        recipient_name=req.name,
        recipient_company=req.company,
        position=profiles[0]["position"],
        context=req.context
    )
    return {"candidates":profiles, "custom_message":message}

@app.post("/send_request")
async def send_request(req: SendRequest):
    """
    🔧 DEBUG endpoint: runs you connect_with_message inline
    so you see the browser opening, clicking Connect → Add a note → filling message.
    """
    profile_url = req.profile_url
    message     = req.message

    result = await connect_with_message(profile_url, message)
    return {"status":"done", "detail":result}

@app.get("/")
def root():
    return {
        "message":"✅ DEBUG mode (GPT-4 only). Use /search_and_generate and /send_request."
    }