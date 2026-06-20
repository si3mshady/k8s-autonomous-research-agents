import os
import json
import sys
import sqlite3
from datetime import datetime
import requests
from langchain_ollama import ChatOllama

# --- CONFIGURATION FROM ENVIRONMENT & HELM ---
DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://4f1c-67-44-192-47.ngrok-free.app")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Safely extract and parse dynamic tenant topology from Helm env injection
TENANTS_JSON_STR = os.getenv("TENANTS_JSON", "[]")
try:
    TENANTS = json.loads(TENANTS_JSON_STR)
    if not TENANTS:
        print("ERROR: Dynamic TENANTS array is empty. Verify your Helm values.yaml structure.")
        sys.exit(1)
except Exception as json_err:
    print(f"FATAL: Failed to parse Helm TENANTS_JSON payload. Raw content: {TENANTS_JSON_STR}. Error: {json_err}")
    sys.exit(1)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Added UNIQUE constraint to prevent duplicate entries per tenant/topic pairing
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
            extracted_at TEXT,
            UNIQUE(tenant_id, research_topic)
        )
    """)
    conn.commit()
    conn.close()

def query_tavily(query: str):
    """Hits Tavily search API natively to grab clean context with verbose logging."""
    print(f"-> Initiating Tavily outbound request: '{query}'")
    if not TAVILY_API_KEY:
        print("CRITICAL: TAVILY_API_KEY environment variable is missing.")
        return []
        
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": 2
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"<- Tavily response received. HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            results = response.json().get("results", [])
            print(f"   Successfully retrieved {len(results)} search documents.")
            return results
        else:
            print(f"   ERROR: Tavily API returned non-200 body: {response.text}")
    except Exception as e:
        print(f"   EXCEPTION: Network failure during Tavily call: {e}")
    return []

def clean_llm_json_output(raw_content: str) -> dict:
    """Strips markdown code blocks from LLM output to prevent JSON parsing errors."""
    cleaned_content = raw_content.strip()
    
    if cleaned_content.startswith("```json"):
        cleaned_content = cleaned_content[7:]
    elif cleaned_content.startswith("```"):
        cleaned_content = cleaned_content[3:]
        
    if cleaned_content.endswith("```"):
        cleaned_content = cleaned_content[:-3]
        
    return json.loads(cleaned_content.strip())

def synthesize_with_llm(tenant_name, topic, raw_payload_str):
    """Uses native Ollama JSON mode to safely guarantee output structure."""
    llm = ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model="qwen3.5:0.8b",
        temperature=0.3,
        format="json"
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
        parsed_data = clean_llm_json_output(response.content)
        return parsed_data
    except Exception as e:
        print(f"LLM Processing Exception, generating safe fallback: {e}")
        return {
            "lead_name": f"Opportunity for {tenant_name}",
            "estimated_value": "Under Evaluation",
            "deadline_or_milestone": "2 Week Review",
            "summary": "Asset successfully synced. Review the raw intelligence payload below for strategic details.",
            "actionable_plan": f"Pending scratchpad alignment analysis for topic: {topic}."
        }

def run_pipeline_cycle():
    print(f"[{datetime.now()}] Initializing dual-search pipeline cycle across {len(TENANTS)} dynamic Helm portfolio tenants...")
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for tenant in TENANTS:
        print(f"Processing Dynamic Tenant: {tenant['name']} [{tenant['id']}]")
        
        q1 = f"Name open grants for {tenant['topic']} 2026"
        res1 = query_tavily(q1)
        
        q2 = f"Corporate foundation partnerships for {tenant['topic']}"
        res2 = query_tavily(q2)
        
        combined_results = res1 + res2
        if not combined_results:
            print(f"❌ Skipping cycle for {tenant['name']}: Combined search payload is empty.")
            continue
            
        raw_payload_string = json.dumps(combined_results)
        intelligence = synthesize_with_llm(tenant['name'], tenant['topic'], raw_payload_string)

        # Implemented UPSERT logic via ON CONFLICT to avoid duplicate row stacking
        cursor.execute("""
            INSERT INTO tenant_research_leads 
            (tenant_id, company_name, research_topic, lead_name, estimated_value, deadline_or_milestone, summary, actionable_plan, raw_payload, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, research_topic) DO UPDATE SET
                company_name=excluded.company_name,
                lead_name=excluded.lead_name,
                estimated_value=excluded.estimated_value,
                deadline_or_milestone=excluded.deadline_or_milestone,
                summary=excluded.summary,
                actionable_plan=excluded.actionable_plan,
                raw_payload=excluded.raw_payload,
                extracted_at=excluded.extracted_at
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
        print(f"Successfully committed dynamic core intelligence payload for {tenant['name']}.")

    conn.close()
    print("Cycle completed. Pipeline in standby...")

if __name__ == "__main__":
    run_pipeline_cycle()
