import os
import json
import time
import sqlite3
from datetime import datetime
import requests
from langchain_ollama import ChatOllama

# --- CONFIGURATION MATCHES PLATFORM BASES ---
DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://4f1c-67-44-192-47.ngrok-free.app")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "your_tavily_api_key_here")

# Sample Multi-Tenant Portfolio Registry
TENANTS = [
    {
        "id": "stem-drone-org",
        "name": "STEM Drone Youth Program",
        "topic": "Drone STEM education funding and grants"
    },
    {
        "id": "clean-water-fleet",
        "name": "EcoAqua Automation",
        "topic": "Remote sensing water conservation grants"
    }
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenant_research_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT,
            company_name TEXT,
            research_topic TEXT,
            lead_name TEXT,
            estimated_value TEXT,
            deadline_or_milestone TEXT,
            summary TEXT,
            actionable_plan TEXT,
            raw_payload TEXT,
            extracted_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def query_tavily(query: str):
    """Hits Tavily search API natively to grab clean context."""
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 2
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json().get("results", [])
    except Exception as e:
        print(f"Tavily search error: {e}")
    return []

def synthesize_with_llm(tenant_name, topic, raw_payload_str):
    """Uses native Ollama JSON mode to safely guarantee output structure."""
    # Instantiating base runner with strict JSON formatting engine active
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model="qwen3.5:0.8b",
        temperature=0.3,
        format="json" # <--- Forces engine level constraint to output ONLY valid JSON
    )

    system_prompt = f"""
    You are an elite operational intelligence agent evaluating data for the non-profit organization: "{tenant_name}".
    Analyze the provided raw search payloads regarding "{topic}" and compile a structured synthesis.

    You MUST output a valid JSON object matching this exact key structure with NO conversational text outside the JSON:
    {{
        "lead_name": "A clear, concise title of the found opportunity or program",
        "estimated_value": "Provide a projected financial value or resource estimation (e.g., '$45,000' or 'In-Kind Hardware')",
        "deadline_or_milestone": "Provide a review deadline. Explicitly specify either '1 Week Review' or '2 Week Review' based on urgency",
        "summary": "A highly concise summary focusing exactly on how this organization can use this discovery effectively.",
        "actionable_plan": "SCRATCHPAD / ALIGNMENT ANALYSIS: Brainstorm here exactly how this opportunity matches the non-profit's core missions and values."
    }}

    Raw Search Data Stream:
    {raw_payload_str}
    """

    try:
        response = llm.invoke(system_prompt)
        parsed_data = json.loads(response.content.strip())
        return parsed_data
    except Exception as e:
        print(f"LLM Processing Exception, generating safe fallback: {e}")
        # Always return a clean structured dictionary to prevent UI crashes
        return {
            "lead_name": f"Opportunity for {tenant_name}",
            "estimated_value": "Under Evaluation",
            "deadline_or_milestone": "2 Week Review",
            "summary": "Asset successfully synced. Review the raw intelligence payload below for strategic details.",
            "actionable_plan": f"Pending scratchpad alignment analysis for topic: {topic}."
        }

def run_pipeline_cycle():
    print(f"[{datetime.now()}] Initializing dual-search pipeline cycle across portfolio tenants...")
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for tenant in TENANTS:
        print(f"Processing tenant: {tenant['name']}")
        
        # 1. Execute Search Query #1 (General Target)
        q1 = f"Name open grants for {tenant['topic']} 2026"
        res1 = query_tavily(q1)
        
        # 2. Execute Search Query #2 (Foundational/Corporate Target)
        q2 = f"Corporate foundation partnerships for {tenant['topic']}"
        res2 = query_tavily(q2)
        
        # Combine searches into a single concise array
        combined_results = res1 + res2
        if not combined_results:
            print(f"Skipping cycle for {tenant['name']}: No internet data collected.")
            continue
            
        raw_payload_string = json.dumps(combined_results)

        # 3. Process naturally structured data via Ollama
        intelligence = synthesize_with_llm(tenant['name'], tenant['topic'], raw_payload_string)

        # 4. Sync into Multi-Tenant Operational Data Warehouse
        cursor.execute("""
            INSERT INTO tenant_research_leads 
            (tenant_id, company_name, research_topic, lead_name, estimated_value, deadline_or_milestone, summary, actionable_plan, raw_payload, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tenant['id'],
            tenant['name'],
            tenant['topic'],
            intelligence.get("lead_name"),
            intelligence.get("estimated_value"),
            intelligence.get("deadline_or_milestone"),
            intelligence.get("summary"),
            intelligence.get("actionable_plan"),
            raw_payload_string,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        print(f"Successfully committed intelligence pipeline data for {tenant['name']}.")

    conn.close()
    print("Cycle completed. Sleeping for 1 hour...")

if __name__ == "__main__":
    # Run an immediate execution loop on startup
    run_pipeline_cycle()
