import os
import time
import json
import sqlite3
import logging
import requests
from typing import TypedDict, Any
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

# --- Tavily output minimization knobs ---
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "1"))
TAVILY_SEARCH_DEPTH = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
TAVILY_INCLUDE_ANSWER = os.getenv("TAVILY_INCLUDE_ANSWER", "false").lower() == "true"
TAVILY_INCLUDE_RAW_CONTENT = os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "false").lower() == "true"
TAVILY_INCLUDE_IMAGES = os.getenv("TAVILY_INCLUDE_IMAGES", "false").lower() == "true"
TAVILY_INCLUDE_FAVICON = os.getenv("TAVILY_INCLUDE_FAVICON", "false").lower() == "true"
TAVILY_INCLUDE_USAGE = os.getenv("TAVILY_INCLUDE_USAGE", "false").lower() == "true"

if not TAVILY_API_KEY:
    logger.warning("TAVILY_API_KEY is not set! Search operations will fail.")
else:
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY


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


def call_ollama_api(system_msg: str, user_msg: str) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": "qwen3.5:0.8b",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "stream": False,
        "options": {"num_predict": 220, "temperature": 0.2}
    }
    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Ollama API error: {e}")
        raise e


class AgentState(TypedDict):
    search_query: str
    raw_payload: str
    structured_lead: dict[str, Any]


def _build_tavily_tool():
    try:
        return TavilyAnswer(
            max_results=TAVILY_MAX_RESULTS,
            search_depth=TAVILY_SEARCH_DEPTH,
            include_answer=TAVILY_INCLUDE_ANSWER,
            include_raw_content=TAVILY_INCLUDE_RAW_CONTENT,
            include_images=TAVILY_INCLUDE_IMAGES,
            include_favicon=TAVILY_INCLUDE_FAVICON,
            include_usage=TAVILY_INCLUDE_USAGE,
        )
    except TypeError:
        tool = TavilyAnswer(max_results=TAVILY_MAX_RESULTS)
        for attr, value in {
            "search_depth": TAVILY_SEARCH_DEPTH,
            "include_answer": TAVILY_INCLUDE_ANSWER,
            "include_raw_content": TAVILY_INCLUDE_RAW_CONTENT,
            "include_images": TAVILY_INCLUDE_IMAGES,
            "include_favicon": TAVILY_INCLUDE_FAVICON,
            "include_usage": TAVILY_INCLUDE_USAGE,
        }.items():
            if hasattr(tool, attr):
                try:
                    setattr(tool, attr, value)
                except Exception:
                    pass
        return tool


tavily_tool = _build_tavily_tool()


def generate_query_node(state: AgentState):
    sys_instruction = f"You are an expert search string generator for {COMPANY_NAME}. Respond with ONLY a short search query string with no quotes."
    user_instruction = f"Create a concise search query for: '{RESEARCH_TOPIC}'. Use the fewest words needed."
    query = call_ollama_api(sys_instruction, user_instruction).replace('"', '').replace("'", "").strip()
    return {"search_query": query[:160]}


def execute_search_node(state: AgentState):
    query = state["search_query"]
    logger.info(f"[{TENANT_ID}] Querying Tavily: '{query}'")
    try:
        search_result = tavily_tool.invoke({"query": query})
        if isinstance(search_result, dict):
            pruned = {
                "query": search_result.get("query", query),
                "answer": search_result.get("answer") if TAVILY_INCLUDE_ANSWER else None,
                "results": []
            }
            for r in (search_result.get("results") or [])[:TAVILY_MAX_RESULTS]:
                pruned["results"].append({
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "content": (r.get("content") or "")[:700],
                    "score": r.get("score")
                })
            return {"raw_payload": json.dumps(pruned, ensure_ascii=False)}
        return {"raw_payload": str(search_result)[:4000]}
    except Exception as e:
        logger.error(f"Tavily Search failed: {e}")
        return {"raw_payload": "Search unavailable."}


def synthesize_lead_node(state: AgentState):
    sys_instruction = (
        f"You are the lead agent for {COMPANY_NAME}. {SYSTEM_PROMPT} "
        'Output valid JSON with exactly these keys: '
        '{"lead_name":"Name","summary":"...","actionable_plan":"...","estimated_value":"...","deadline":"..."}'
    )
    user_instruction = f"Analyze this compact research payload and keep the response brief: {state['raw_payload']}"
    response = call_ollama_api(sys_instruction, user_instruction)
    clean_json = response.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(clean_json)
        return {"structured_lead": {
            "lead_name": str(parsed.get("lead_name", "Unknown"))[:120],
            "summary": str(parsed.get("summary", ""))[:1000],
            "actionable_plan": str(parsed.get("actionable_plan", ""))[:1000],
            "estimated_value": str(parsed.get("estimated_value", "Unknown"))[:120],
            "deadline": str(parsed.get("deadline", "N/A"))[:120],
        }}
    except Exception:
        return {"structured_lead": {"lead_name": "Error", "summary": "Parsing failed", "actionable_plan": "N/A", "estimated_value": "Unknown", "deadline": "N/A"}}


workflow = StateGraph(AgentState)
workflow.add_node("query_generator", generate_query_node)
workflow.add_node("search_executor", execute_search_node)
workflow.add_node("lead_synthesizer", synthesize_lead_node)
workflow.add_edge(START, "query_generator")
workflow.add_edge("query_generator", "search_executor")
workflow.add_edge("search_executor", "lead_synthesizer")
workflow.add_edge("lead_synthesizer", END)
agent_platform = workflow.compile()


def process_research_cycle():
    init_db()
    while True:
        try:
            final_state = agent_platform.invoke({"search_query": "", "raw_payload": "", "structured_lead": {}})
            lead = final_state["structured_lead"]
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO tenant_research_leads (tenant_id, company_name, research_topic, lead_name, summary, actionable_plan, estimated_value, deadline_or_milestone, raw_payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (TENANT_ID, COMPANY_NAME, RESEARCH_TOPIC, lead.get("lead_name"), lead.get("summary"), lead.get("actionable_plan"), lead.get("estimated_value"), lead.get("deadline"), final_state["raw_payload"])
            )
            conn.commit()
            conn.close()
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    process_research_cycle()
