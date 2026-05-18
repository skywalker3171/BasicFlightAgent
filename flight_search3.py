import os
import time
import requests
import re
import json
from openai import OpenAI
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from requests.exceptions import ConnectionError
from http.client import RemoteDisconnected
from dotenv import load_dotenv

# Load environment variables once
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TODAY = date.today().isoformat()

# ── Helper functions ────────────────────────────────────────────────────────

def get_date_range(return_date_str: str) -> list[str]:
    """Generate date range: ±2 days around return_date."""
    return_date = datetime.strptime(return_date_str, '%Y-%m-%d')
    return [(return_date + relativedelta(days=i)).strftime('%Y-%m-%d') for i in [-2, -1, 0, 1, 2]]

def truncate_scratchpad(scratchpad: str, max_chars: int = 24000) -> str:
    """Keep only the last max_chars if scratchpad exceeds limit."""
    return scratchpad if len(scratchpad) <= max_chars else f"...(truncated)...\n{scratchpad[-max_chars:]}"

def search_rapidapi_flights2(origin_code: str, destination_code: str, departure_date: str, 
                             max_offers: int = 2, retries: int = 3, backoff: int = 2) -> dict | str:
    """Search flights via RapidAPI with exponential backoff retry logic."""
    url = f"https://flights-sky.p.rapidapi.com/flights/search-one-way?fromEntityId={origin_code}&toEntityId={destination_code}&departDate={departure_date}"
    headers = {
        "X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY", "XXX"),
        "X-RapidAPI-Host": "flights-sky.p.rapidapi.com",
    }

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except (RemoteDisconnected, ConnectionError) as e:
            if attempt < retries - 1:
                wait = backoff ** attempt
                print(f"Connection dropped, retrying in {wait}s... (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
            else:
                return f"Error: Server dropped connection after {retries} attempts — {e}"
        except requests.exceptions.Timeout:
            return "Error: Request timed out"
        except requests.exceptions.HTTPError as e:
            return f"Error: HTTP {response.status_code} — {e}"

# ── Tool definitions ───────────────────────────────────────────────────────

TOOLS = {
    "searchflights": {
        "fn": search_rapidapi_flights2,
        "description": f"""Searches live flight prices via flights-sky.p.rapidapi.com.
    Required: origin_code, destination_code (IATA codes), departure_date (YYYY-MM-DD, must be today or later; today is {TODAY})
    Optional: return_date, adults, travel_class, currency, max_offers""",
    }
}

REACT_PROMPT = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

def build_prompt(question: str, scratchpad: str = "") -> str:
    tools_desc = "\n".join(
        f"- {name}: {info['description']}" for name, info in TOOLS.items()
    )
    tool_names = ", ".join(TOOLS.keys())
    return REACT_PROMPT.format(
        tools=tools_desc,
        tool_names=tool_names,
        input=question,
        agent_scratchpad=scratchpad,
    )

# ── Parsing helpers ───────────────────────────────────────────────────────

def parse_action(text: str) -> tuple[str | None, dict | str | None]:
    """Extract Action and Action Input from LLM output."""
    action_match = re.search(r"Action:\s*(.+?)$", text, re.MULTILINE)
    input_match = re.search(r"Action Input:\s*(\{.*?\}|[^\n]+)", text)

    if not (action_match and input_match):
        return None, None

    raw = input_match.group(1).strip()
    action = action_match.group(1).strip()

    # Try JSON first
    try:
        return action, json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fall back to key=value format
    try:
        parsed = {k.strip(): v.strip() for pair in re.split(r",\s*", raw) 
                  for k, v in [pair.split("=", 1)]}
        return action, parsed
    except Exception:
        return None, None  # ← Changed from: return action, raw

def parse_final_answer(text: str) -> str | None:
    """Extract Final Answer from LLM output if present."""
    match = re.search(r"Final Answer:\s*(.+?)(?=\n|$)", text)
    return match.group(1).strip() if match else None

# ── Agent loop ────────────────────────────────────────────────────────────

def run_agent(question: str, max_steps: int = 5) -> str:
    """Run ReAct agent loop."""
    scratchpad = ""

    for step in range(max_steps):
        time.sleep(1)
        scratchpad = truncate_scratchpad(scratchpad)
        prompt = build_prompt(question, scratchpad)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
            stop=["Observation:"],
        )

        llm_output = response.choices[0].message.content.strip()
        print(f"\n── Step {step + 1} ──\n{llm_output}")

        if final := parse_final_answer(llm_output):
            return final

        action, tool_input = parse_action(llm_output)
        if action and action in TOOLS:
            fn = TOOLS[action]["fn"]
            observation = fn(**tool_input) if isinstance(tool_input, dict) else fn(tool_input)
            print(f"Observation: {observation}")
            scratchpad += f"{llm_output}\nObservation: {observation}\n"
        else:
            scratchpad += f"{llm_output}\n"

    return "Agent did not reach a final answer within the step limit."

# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    origin = input("Enter origin city or airport code (e.g. JFK): ").strip()
    destination = input("Enter destination city or airport code (e.g. LAX): ").strip()
    travel_date = input("Enter travel date (YYYY-MM-DD): ").strip()

    question = f"Find me 2 cheap flights from {origin} to {destination} on {travel_date}. Use origin_code={origin}, destination_code={destination}, departure_date={travel_date}"
    answer = run_agent(question)
    print(f"\n✅ Final Answer: {answer}")