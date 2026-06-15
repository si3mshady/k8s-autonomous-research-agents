import os
import time
import json
import sqlite3
import logging
from typing import TypedDict, Any
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch
from langchain_ollama import ChatOllama
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


# --- DATABASE CONNECTION UTILITIES ---
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


# --- PYDANTIC SCHEMAS FOR STRUCTURED OUTPUTS ---
class SearchQueryOutput(BaseModel):
    search_query: str = Field(description="A short, concise search query string with no quotes.")


class StructuredLeadOutput(BaseModel):
    lead_name: str = Field(description="The name of the identified donor, foundation, or grant lead.")
    summary: str = Field(description="A brief summary of the lead and alignment with the company.")
    actionable_plan: str = Field(description="Actionable steps or proposal ideas.")
    estimated_value: str = Field(description="Estimated value or funding size (e.g., '$50,000', 'Unknown').")
    deadline: str = Field(description="Application deadlines or milestones (e.g., '2026-12-31', 'N/A').")


# --- INITIALIZE LANGCHAIN INTEGRATIONS ---
# Robust underlying client with high timeouts to manage slower connections
base_llm = ChatOllama(
    base_url=OLLAMA_BASE_URL,
    model="qwen3.5:0.8b",
    temperature=0.2,
    request_timeout=300.0, 
    num_predict=220
)

# Enforcing structural guarantees using native JSON schemas
structured_query_llm = base_llm.with_structured_output(SearchQueryOutput, method="json_schema")
structured_lead_llm = base_llm.with_structured_output(StructuredLeadOutput, method="json_schema")

# Standardized Tavily tool instantiation
tavily_tool = TavilySearch(
    max_results=TAVILY_MAX_RESULTS,
    search_depth=TAVILY_SEARCH_DEPTH,
    include_answer=TAVILY_INCLUDE_ANSWER,
    include_raw_content="markdown" if TAVILY_INCLUDE_RAW_CONTENT else None,
    include_images=TAVILY_INCLUDE_IMAGES,
    include_favicon=TAVILY_INCLUDE_FAVICON,
    include_usage=TAVILY_INCLUDE_USAGE,
)


# --- PROMPT TEMPLATE CHAINS ---
query_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert search string generator for {company_name}. Respond with a short search query string based on the topic."),
    ("human", "Create a concise search query for: '{research_topic}'. Use the fewest words needed.")
])
query_chain = query_prompt | structured_query_llm

lead_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are the lead agent for {company_name}. {system_prompt}"),
    ("human", "Analyze this compact research payload and keep the response brief: {raw_payload}")
])
lead_chain = lead_prompt | structured_lead_llm


# --- LANGGRAPH NODE STATE & AGENT LOGIC ---
class AgentState(TypedDict):
    search_query: str
    raw_payload: str
    structured_lead: dict[str, Any]


def generate_query_node(state: AgentState):
    try:
        result = query_chain.invoke({
            "company_name": COMPANY_NAME,
            "research_topic": RESEARCH_TOPIC
        })
        query = result.search_query.replace('"', '').replace("'", "").strip()
        return {"search_query": query[:160]}
    except Exception as e:
        logger.error(f"Failed to generate search query safely: {e}")
        return {"search_query": RESEARCH_TOPIC[:160]}


def execute_search_node(state: AgentState):
    query = state["search_query"]
    logger.info(f"[{TENANT_ID}] Querying Tavily Search: '{query}'")
    try:
        search_result = tavily_tool.invoke({"query": query})
        
        # Safely parsing standard dictionary structures returned from TavilySearch
        if isinstance(search_result, str):
            try:
                search_result = json.loads(search_result)
            except Exception:
                return {"raw_payload": search_result[:4000]}

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
                    "content": (r.get("content") or r.get("snippet") or "")[:700],
                    "score": r.get("score")
                })
            return {"raw_payload": json.dumps(pruned, ensure_ascii=False)}
            
        return {"raw_payload": str(search_result)[:4000]}
    except Exception as e:
        logger.error(f"Tavily Search failed: {e}")
        return {"raw_payload": "Search unavailable."}


def synthesize_lead_node(state: AgentState):
    try:
        result = lead_chain.invoke({
            "company_name": COMPANY_NAME,
            "system_prompt": SYSTEM_PROMPT,
            "raw_payload": state["raw_payload"]
        })
        return {"structured_lead": {
            "lead_name": str(result.lead_name)[:120],
            "summary": str(result.summary)[:1000],
            "actionable_plan": str(result.actionable_plan)[:1000],
            "estimated_value": str(result.estimated_value)[:120],
            "deadline": str(result.deadline)[:120],
        }}
    except Exception as e:
        logger.error(f"Structured lead synthesis parsing failed: {e}")
        return {"structured_lead": {
            "lead_name": "Error", 
            "summary": "Parsing failed", 
            "actionable_plan": "N/A", 
            "estimated_value": "Unknown", 
            "deadline": "N/A"
        }}


# --- WORKFLOW COMPILATION ---
workflow = StateGraph(AgentState)
workflow.add_node("query_generator", generate_query_node)
workflow.add_node("search_executor", execute_search_node)
workflow.add_node("lead_synthesizer", synthesize_lead_node)

workflow.add_edge(START, "query_generator")
workflow.add_edge("query_generator", "search_executor")
workflow.add_edge("search_executor", "lead_synthesizer")
workflow.add_edge("lead_synthesizer", END)

agent_platform = workflow.compile()


# --- SERVICE EXECUTION CYCLE ---
def process_research_cycle():
    init_db()
    while True:
        try:
            final_state = agent_platform.invoke({"search_query": "", "raw_payload": "", "structured_lead": {}})
            lead = final_state["structured_lead"]
            
            conn = get_db_connection()
            conn.execute(
                """INSERT INTO tenant_research_leads 
                (tenant_id, company_name, research_topic, lead_name, summary, actionable_plan, estimated_value, deadline_or_milestone, raw_payload) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    TENANT_ID, 
                    COMPANY_NAME, 
                    RESEARCH_TOPIC, 
                    lead.get("lead_name"), 
                    lead.get("summary"), 
                    lead.get("actionable_plan"), 
                    lead.get("estimated_value"), 
                    lead.get("deadline"), 
                    final_state["raw_payload"]
                )
            )
            conn.commit()
            conn.close()
            logger.info("Cycle complete. Database successfully synchronized. Resting for 1 hour...")
            time.sleep(3600)
        except Exception as e:
            logger.error(f"Loop processor error encountered: {e}")
            time.sleep(60)


if __name__ == "__main__":
    process_research_cycle()
