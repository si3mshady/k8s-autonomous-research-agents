import os
import time
import json
import sqlite3
import logging
import requests
from typing import TypedDict
from langchain_community.tools.tavily_search import TavilyAnswer
from langgraph.graph import StateGraph, START, END

# --- SEVERE HARDWARE CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Helm & Environment Value Injections
TENANT_ID = os.getenv("TENANT_ID", "default-tenant")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Default Non-Profit")
RESEARCH_TOPIC = os.getenv("RESEARCH_TOPIC", "general fundraising opportunities")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Identify high-value leads and grants.")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://172.28.240.1:11434")
DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")
# --- NEW: Explicit API Key Injection ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    logger.warning("TAVILY_API_KEY is not set! Search operations will fail.")

# Set the environment variable so LangChain/Tavily automatically picks it up
os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

# Thread-safe database connection helpers
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    logger.info("Initializing multi-tenant database schema...")
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_research_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            company_name TEXT NOT NULL,
            research_topic TEXT NOT NULL,
            lead_name TEXT NOT NULL,
            summary TEXT,
            actionable_plan TEXT,
            estimated_value TEXT DEFAULT 'Unknown',
            deadline_or_milestone TEXT DEFAULT 'N/A',
            raw_payload TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# --- CHAT OLLAMA DIRECT REQUEST SHAPER ---
def call_ollama_api(system_msg: str, user_msg: str) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": "qwen3.5:0.8b",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "stream": False,
        "options": {"num_predict": 350, "temperature": 0.3}
    }
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        raise e

# --- LANGGRAPH STATE & WORKFLOW ---
class AgentState(TypedDict):
    search_query: str
    raw_payload: str
    structured_lead: dict

# Initialize tool (it will now automatically look for os.environ["TAVILY_API_KEY"])
tavily_tool = TavilyAnswer(max_results=3)

def generate_query_node(state: AgentState):
    sys_instruction = f"You are an expert search string generator for {COMPANY_NAME}. Respond with ONLY a search query string."
    user_instruction = f"Create a search query for: '{RESEARCH_TOPIC}'."
    query = call_ollama_api(sys_instruction, user_instruction).replace('"', '').replace("'", "")
    return {"search_query": query}

def execute_search_node(state: AgentState):
    query = state["search_query"]
    logger.info(f"[{TENANT_ID}] Querying Tavily: '{query}'")
    try:
        search_result = tavily_tool.invoke({"query": query})
        return {"raw_payload": str(search_result)}
    except Exception as e:
        logger.error(f"Tavily Search failed: {e}")
        return {"raw_payload": "Search unavailable."}

def synthesize_lead_node(state: AgentState):
    sys_instruction = f"You are the lead agent for {COMPANY_NAME}. {SYSTEM_PROMPT} Output valid JSON: " + \
                      '{"lead_name": "Name", "summary": "...", "actionable_plan": "...", "estimated_value": "...", "deadline": "..."}'
    user_instruction = f"Analyze: {state['raw_payload']}"
    
    response = call_ollama_api(sys_instruction, user_instruction)
    clean_json = response.replace("```json", "").replace("```", "").strip()
    try:
        return {"structured_lead": json.loads(clean_json)}
    except:
        return {"structured_lead": {"lead_name": "Error", "summary": "Parsing failed", "actionable_plan": "N/A", "estimated_value": "Unknown", "deadline": "N/A"}}

# Workflow setup
workflow = StateGraph(AgentState)
workflow.add_node("query_generator", generate_query_node)
workflow.add_node("search_executor", execute_search_node)
workflow.add_node("lead_synthesizer", synthesize_lead_node)
workflow.add_edge(START, "query_generator")
workflow.add_edge("query_generator", "search_executor")
workflow.add_edge("search_executor", "lead_synthesizer")
workflow.add_edge("lead_synthesizer", END)
agent_platform = workflow.compile()

# Process loop remains the same...
def process_research_cycle():
    init_db()
    while True:
        try:
            final_state = agent_platform.invoke({"search_query": "", "raw_payload": "", "structured_lead": {}})
            lead = final_state["structured_lead"]
            conn = get_db_connection()
            conn.execute("INSERT INTO tenant_research_leads (tenant_id, company_name, research_topic, lead_name, summary, actionable_plan, estimated_value, deadline_or_milestone, raw_payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                         (TENANT_ID, COMPANY_NAME, RESEARCH_TOPIC, lead.get("lead_name"), lead.get("summary"), lead.get("actionable_plan"), lead.get("estimated_value"), lead.get("deadline"), final_state["raw_payload"]))
            conn.commit()
            conn.close()
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    process_research_cycle()
