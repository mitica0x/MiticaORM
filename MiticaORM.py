import os
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
import urllib.parse
from xml.etree import ElementTree as ET
import html
import re

import requests
import anthropic
import tweepy
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

if not ANTHROPIC_API_KEY:
    raise ValueError("Missing ANTHROPIC_API_KEY")

# =========================================================
# CONFIG
# =========================================================

MODEL_NAME = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096
REQUEST_TIMEOUT = 20
DEFAULT_TOOL_BUDGET = 10
MAX_AGENT_LOOPS = 20
MAX_CONSECUTIVE_DUPLICATES = 3

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DRAFTS_FILE = DATA_DIR / "orm_drafts.json"

drafts: List[Dict] = []
if DRAFTS_FILE.exists():
    try:
        drafts = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        drafts = []

def save_drafts():
    DRAFTS_FILE.write_text(
        json.dumps(drafts, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

# =========================================================
# TWITTER
# =========================================================

def get_twitter_client():
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET]):
        raise ValueError("Twitter API keys missing from .env")
    return tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )
def post_tweet(text: str) -> str:
    try:
        client = get_twitter_client()
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        return f"Tweet posted successfully!\nhttps://twitter.com/Mitica0x/status/{tweet_id}"
    except Exception as e:
        return f"Failed to post tweet: {e}"
    
def post_thread(tweets: List[str]) -> str:
    try:
        client = get_twitter_client()
        tweet_ids = []
        reply_to = None

        for i, tweet_text in enumerate(tweets):
            tweet_text = tweet_text.strip()
            if not tweet_text:
                continue

            print(f"\n[DEBUG] Tweet {i+1} ({len(tweet_text)} chars): {tweet_text[:100]}...")

            if i == 0:
                time.sleep(2)

            if reply_to:
                response = client.create_tweet(
                    text=tweet_text,
                    in_reply_to_tweet_id=reply_to
                )
            else:
                response = client.create_tweet(text=tweet_text)

            tweet_id = response.data["id"]
            tweet_ids.append(tweet_id)
            reply_to = tweet_id
            time.sleep(3)

        return (
            f"Thread posted — {len(tweet_ids)} tweets!\n"
            f"https://twitter.com/Mitica0x/status/{tweet_ids[0]}"
        )
    except Exception as e:
        return f"Failed to post thread: {e}"

def parse_thread_from_content(content: str) -> List[str]:
    """Parse a thread from saved draft content"""
    tweets = []
    current_tweet_lines = []
    in_tweet = False

    lines = content.split("\n")

    for line in lines:
        stripped = line.strip()

        # Skip thread header line
        if stripped.upper().startswith("THREAD:"):
            continue

        # Detect tweet markers like "Tweet 1:" or "Tweet 1: text here"
        match = re.match(r"^Tweet \d+:\s*(.*)", stripped)
        if match:
            # Save previous tweet if any
            if current_tweet_lines:
                tweet_text = "\n".join(current_tweet_lines).strip()
                if tweet_text:
                    tweets.append(tweet_text)
            current_tweet_lines = []
            in_tweet = True
            # Capture text on the same line after "Tweet N:"
            remainder = match.group(1).strip().strip('"').strip()
            if remainder:
                current_tweet_lines.append(remainder)
            continue

        if in_tweet and stripped:
            # Strip surrounding quotes if present
            cleaned = stripped.strip('"').strip()
            if cleaned:
                current_tweet_lines.append(cleaned)

    # Add last tweet
    if current_tweet_lines:
        tweet_text = "\n".join(current_tweet_lines).strip()
        if tweet_text:
            tweets.append(tweet_text)

    return tweets

# =========================================================
# PERSONA
# =========================================================

PERSONA = """
WHO HE IS:
Madalin Muraretiu. Alias: Mitica0x. Bucharest, Romania.

Crypto trader and builder since 2016 — this is his primary market now.
Foundation: 15 years in classical markets (FX, CFD, derivatives, commodities) —
gives him an edge most crypto natives don't have.
Not a TradFi guy who discovered crypto. A crypto operator with TradFi depth.

TRADING & MARKETS:
- Crypto trader since 2016 — intraday, dozens to hundreds of trades per day
- Understands price action, market structure, funding rates, liquidation clusters,
  perpetuals, basis, derivatives — at operator level, not theoretical
- Classical markets background (FX, CFD, commodities, indices since 2011) —
  gives him macro context and risk discipline most crypto natives lack
- Bridges both worlds — rare combination that matters at exchange level

BUILDING:
- Co-Founder COINsiglieri — Web3 advisory (mentioned as proof of execution, not identity)
  Turnkey regulatory solutions across multiple jurisdictions (EU/MiCA, UAE, Singapore)
- Founder Sphynx Network — DeFi protocol, Financial NFTs
- Official Bybit Brand Ambassador Romania — first meetup, market opener
- Ecosystem builder — Web3 startup competitions (3 editions), community activation

BYBIT STRATEGY LAYER PROJECT (CONFIDENTIAL):
- Identified a gap: idle capital on CEXs generates zero volume or fees
- Proposed a Strategy Layer between manual trading and Earn/Copy Trading
- V1 Global: Funding Arb, Basis Trading, Smart Grid — native on Bybit infrastructure
- V1 EU (MiCA compliant): Smart Grid, Stat Arb on correlated pairs, Dynamic Accumulation
- V2: Strategy Marketplace (invite-only, curated), Smart Allocation Engine
- V3: DeFi native strategies, MEV, SocialFi layer
- Key argument: Mantle Vault validated demand — $52M AUM in 7 days
- Core insight: "You already have the kitchen. This is the restaurant."
- Already sent pitch to Mazurka Zheng (CEO Bybit EU)

ULTIMATE OBJECTIVE:
- Head of DeFi or Head of Derivatives at Bybit EU
- Or create the position through this project
- Build reputation as the person who understands BOTH real derivatives markets AND DeFi
- Every piece of content should move toward this — without saying it explicitly

SPEAKER CIRCUIT:
- Token2049, Next Block Expo, ETH Bucharest, DISB, Banking 4.0
- Speaks on DeFi architecture, derivatives, AI agents, blockchain infrastructure

BRAND ANCHOR (never say explicitly, build toward it):
"The person you want leading DeFi and Derivatives when you need someone
who has actually traded in real markets AND built in Web3 for 9 years."

IMPORTANT — what COINsiglieri is NOT:
- Not his identity
- Not the center of his brand
- Mentioned only as proof that he executes — not the main story
- His personal brand is bigger than any single company he has built
"""

STRATEGY = """
BRAND STRATEGY — Madalin Muraretiu / Mitica0x

CORE OBJECTIVE:
Build the reputation of a world-class operator at the intersection of
derivatives trading and DeFi/Web3 — someone Bybit or major exchanges
would want at the highest level.

NOT building: influencer status, consultant brand, company PR
BUILDING: personal authority as a crypto market operator and ecosystem thinker

CONTENT PILLARS (in order of priority):

1. MARKETS & TRADING — His sharpest edge
   - Intraday crypto market takes: price action, derivatives, sentiment, funding rates
   - TradFi lens on crypto — what classical traders see that crypto natives miss
   - Honest reads — no hype, no cheerleading
   - Format: punchy Twitter takes, occasional deeper threads

2. DEFI & WEB3 ARCHITECTURE — His builder credibility
   - Protocol design, liquidity, market structure in DeFi
   - Where DeFi is going vs where it is
   - Honest takes on what's broken and what's being built right
   - Format: Twitter threads, LinkedIn thought pieces

3. AI & AUTOMATION IN TRADING — Emerging edge
   - AI agents, trading automation, what's real vs hype
   - His experience building automated systems
   - Format: Twitter, LinkedIn

4. ECOSYSTEM BUILDING — Proof of operator mindset
   - Conference insights, community building
   - Behind the scenes of building — decisions, lessons, failures
   - NOT company PR — personal observations
   - Format: Instagram stories + posts, LinkedIn

5. VISION & PERSPECTIVE — The big picture
   - Where markets and blockchain intersect
   - Regulatory shifts and what they mean for operators
   - Format: LinkedIn long-form, Twitter threads

PLATFORM STRATEGY:

TWITTER/X — Primary platform, trader voice
- 2-3x per day
- Sharp, direct, no corporate speak
- React to market moves with real trader takes
- Dynamic — short when market moves, thread when explaining

LINKEDIN — Authority platform, operator voice
- Every 2-3 days
- Thought leadership on DeFi, derivatives, market structure
- Personal but professional

INSTAGRAM — Human platform, builder voice
- Stories: 2-3x per week
- Posts: 1x per week

VOICE RULES:
- English always
- Never: "thrilled", "honored", "excited to announce"
- Never: excessive hashtags (max 3 Twitter, max 5 LinkedIn)
- Always: add a real take, not just information
- Sounds like a trader who reads — not a marketer who trades
"""

# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = f"""You are MiticaORM — personal brand strategist and content agent for Madalin Muraretiu (Mitica0x).

Your single objective: build the reputation of a world-class operator at the intersection
of derivatives trading and DeFi/Web3. Every piece of content should move toward this.

PERSONA:
{PERSONA}

STRATEGY:
{STRATEGY}

CONTENT DRAFTING RULES:
- Write in his voice — direct, sharp, confident, no fluff
- Twitter: punchy, max 280 chars per tweet unless thread, real trader takes
- LinkedIn: 150-400 words, builds authority, professional but human
- Instagram: visual-first, caption supports image, community-focused
- NEVER: "thrilled", "honored", "excited to announce", "proud to share"
- NEVER center COINsiglieri — mention only as proof of execution if relevant
- NEVER just share information — always add HIS take
- ALWAYS sound like someone who has actually traded and built
- English always, dynamic style

IMPORTANT — conversation memory:
- You have memory of this drafting session
- When user says "variant 2", "make it shorter", "change the tone", "I like the second one"
  you know exactly what they are referring to from earlier in the conversation
- Keep track of what you drafted and iterate based on feedback

When monitoring: be honest about gaps and opportunities.
When drafting: give 3 variants — A (short/punchy), B (medium/balanced), C (long/thread).
When strategizing: think like a trader — clear thesis, entry, stop loss, target.
"""

# =========================================================
# HELPERS
# =========================================================

def safe_get(url: str, params: Optional[dict] = None) -> Any:
    r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()

def normalize_sig(name: str, inp: Dict) -> str:
    return f"{name}:{json.dumps(inp, sort_keys=True)}"

def strip_html_text(raw: str) -> str:
    raw = html.unescape(raw or "")
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()

# =========================================================
# TOOLS
# =========================================================

def web_search(query: str, max_results: int = 5) -> str:
    if not TAVILY_API_KEY:
        return "Web search unavailable — no Tavily key"
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(query=query, max_results=max_results)
        items = results.get("results", [])
        if not items:
            return f"No results for: '{query}'"
        lines = [f"Search: '{query}'"]
        for r in items:
            content = (r.get("content", "") or "").replace("\n", " ").strip()
            lines.append(
                f"- {r.get('title', '')}\n"
                f"  {content[:300]}\n"
                f"  {r.get('url', '')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Search unavailable: {e}"

def get_news(query: str, max_results: int = 5) -> str:
    if NEWS_API_KEY:
        try:
            data = safe_get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": max_results,
                    "apiKey": NEWS_API_KEY
                }
            )
            articles = data.get("articles", [])
            if articles:
                lines = [f"News: '{query}'"]
                for a in articles:
                    lines.append(
                        f"- [{a.get('source', {}).get('name', 'Unknown')} | "
                        f"{a.get('publishedAt', '')[:10]}] {a.get('title', '')}\n"
                        f"  {(a.get('description', '') or '')[:200]}\n"
                        f"  {a.get('url', '')}"
                    )
                return "\n".join(lines)
        except Exception:
            pass

    try:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.text)
        lines = [f"News: '{query}'"]
        for item in root.findall(".//item")[:max_results]:
            raw_title = item.findtext("title", "")
            title = strip_html_text(raw_title)
            source = "Unknown"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip()
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", "")[:16]
            lines.append(f"- [{source} | {pub}] {title}\n  {link}")
        return "\n".join(lines)
    except Exception as e:
        return f"News unavailable: {e}"

def monitor_mentions() -> str:
    queries = [
        '"Madalin Muraretiu" OR "Mitica0x" crypto 2025',
        '"COINsiglieri" Web3 advisory ecosystem',
        '"Madalin Muraretiu" Bybit ambassador speaker',
    ]
    lines = ["**Online presence scan:**\n"]
    for q in queries:
        result = web_search(q, max_results=3)
        lines.append(result)
        lines.append("")
        time.sleep(0.5)
    return "\n".join(lines)

def get_trending_topics() -> str:
    queries = [
        "bitcoin ethereum crypto market today trader perspective",
        "DeFi derivatives protocol news today",
        "AI agents automation trading Web3 latest",
    ]
    lines = ["**Trending topics:**\n"]
    for q in queries:
        result = get_news(q, max_results=3)
        lines.append(result)
        lines.append("")
    return "\n".join(lines)

def save_draft(platform: str, content: str, topic: str = "") -> str:
    draft = {
        "id": len(drafts) + 1,
        "platform": platform,
        "topic": topic,
        "content": content,
        "created": datetime.now().isoformat(),
        "status": "saved"
    }
    drafts.append(draft)
    save_drafts()
    return f"Draft #{draft['id']} saved for {platform}."

def list_drafts() -> str:
    if not drafts:
        return "No saved drafts yet."
    lines = ["**Saved drafts:**"]
    for d in drafts[-10:]:
        preview = d['topic'] if d['topic'] else d['content'][:40]
        lines.append(
            f"#{d['id']} [{d['platform']}] {preview[:50]}... — {d['created'][:10]}"
        )
    return "\n".join(lines)

# =========================================================
# TOOL DISPATCH
# =========================================================

def run_tool(name: str, inp: Dict[str, Any]) -> str:
    try:
        if name == "web_search":
            return web_search(inp["query"], inp.get("max_results", 5))
        if name == "get_news":
            return get_news(inp["query"], inp.get("max_results", 5))
        if name == "monitor_mentions":
            return monitor_mentions()
        if name == "get_trending_topics":
            return get_trending_topics()
        if name == "save_draft":
            return save_draft(inp["platform"], inp["content"], inp.get("topic", ""))
        if name == "list_drafts":
            return list_drafts()
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error in {name}: {e}"

tools = [
    {
        "name": "web_search",
        "description": "Search the web for information, mentions, people, events, trends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_news",
        "description": "Get latest news on any topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "monitor_mentions",
        "description": "Scan online mentions of Madalin Muraretiu, Mitica0x, COINsiglieri.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_trending_topics",
        "description": "Get trending topics across content pillars.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "save_draft",
        "description": "Save an approved draft post.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "content": {"type": "string"},
                "topic": {"type": "string"}
            },
            "required": ["platform", "content"]
        }
    },
    {
        "name": "list_drafts",
        "description": "List saved drafts.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    }
]

# =========================================================
# AGENT ENGINE
# =========================================================

def extract_text(response) -> str:
    return "\n".join(
        b.text for b in response.content
        if getattr(b, "type", None) == "text"
    ).strip()

def make_tool_result(tool_id: str, content: str) -> Dict:
    return {"type": "tool_result", "tool_use_id": tool_id, "content": content}

def execute_agent_turn(
    messages: List[Dict],
    max_tool_calls: int = DEFAULT_TOOL_BUDGET,
    label: str = "ORM"
) -> str:
    used = 0
    dupes = 0
    seen: Set[str] = set()

    for _ in range(MAX_AGENT_LOOPS):
        response = anthropic_client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            results = []

            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue

                sig = normalize_sig(block.name, block.input or {})

                if sig in seen:
                    dupes += 1
                    result = "Duplicate skipped."
                    if dupes >= MAX_CONSECUTIVE_DUPLICATES:
                        result += " Synthesize now."
                elif used >= max_tool_calls:
                    result = "Budget reached. Answer from what you have."
                else:
                    seen.add(sig)
                    dupes = 0
                    preview = list(block.input.values())[:1] if block.input else ""
                    print(f"  [{label}] {block.name} {preview}")
                    result = run_tool(block.name, block.input or {})
                    used += 1
                    time.sleep(0.3)

                results.append(make_tool_result(block.id, result))

            messages.append({"role": "user", "content": results})

        elif response.stop_reason == "end_turn":
            return extract_text(response)

        else:
            messages.append({
                "role": "user",
                "content": "Unexpected stop. Provide best answer now."
            })

    return "Loop limit reached."

# =========================================================
# BUILD DRAFT PROMPT
# =========================================================

def build_draft_prompt(platform: str, topic: str = "") -> str:
    platform_map = {
        "twitter": "Twitter/X",
        "x": "Twitter/X",
        "linkedin": "LinkedIn",
        "instagram": "Instagram"
    }
    platform_name = platform_map.get(platform.lower(), platform)

    return f"""Draft content for {platform_name} for Madalin Muraretiu (Mitica0x).

{"Topic/context: " + topic if topic else "Check trending topics and pick the strongest angle for his brand right now."}

Steps:
1. {"Search for context on: " + topic if topic else "Get trending topics and pick the most relevant"}
2. Draft 3 variants:

**Variant A — Short & Punchy**
{"Max 280 chars, one sharp take" if "Twitter" in platform_name else "2-3 lines, direct"}

**Variant B — Medium & Balanced**
{"2-3 tweets or short thread" if "Twitter" in platform_name else "150-250 words"}

**Variant C — Long & Detailed**
{"Thread 5-7 tweets" if "Twitter" in platform_name else "300-400 words, full thought leadership"}

Platform rules:
{"- Max 280 chars per tweet, punchy, max 3 hashtags" if "Twitter" in platform_name else ""}
{"- 150-400 words, authority builder, max 5 hashtags" if "LinkedIn" in platform_name else ""}
{"- Visual-first, community-focused, max 8 hashtags" if "Instagram" in platform_name else ""}

Voice: Direct, sharp, confident. Never 'thrilled' or 'honored'.
Always add his real take — not just the news.
Sounds like a crypto operator with TradFi depth.
English only."""

# =========================================================
# COMMANDS
# =========================================================

def cmd_monitor() -> str:
    messages = [{
        "role": "user",
        "content": """Monitor Madalin Muraretiu's online presence.

1. Scan mentions (Madalin Muraretiu, Mitica0x, COINsiglieri)
2. Check recent activity on his speaking circuit
3. Look at what top voices in derivatives + DeFi are posting

Report:
## What's Working
## Critical Gaps
## 3 Opportunities This Week (specific and actionable)
## Reputation Risks
## Bottom Line

Brutally honest. He's a trader — clear analysis over comfortable takes.
Objective: build reputation as someone who should lead DeFi/Derivatives
at the highest level in this industry."""
    }]
    return execute_agent_turn(messages, max_tool_calls=8, label="Monitor")

def cmd_calendar() -> str:
    messages = [{
        "role": "user",
        "content": """Create a 7-day content calendar for Madalin Muraretiu.

1. Get trending topics across his pillars right now
2. Check market and ecosystem news

Calendar Monday-Sunday:
- Twitter/X: 2-3 specific post ideas per day with angle
- LinkedIn: 1 post every 2-3 days with angle
- Instagram: story + post idea where relevant

Specific, not generic. Based on what's actually happening now.
Every piece builds toward: crypto operator with TradFi depth
who belongs at the highest level of DeFi/Derivatives."""
    }]
    return execute_agent_turn(messages, max_tool_calls=8, label="Calendar")

def cmd_strategy() -> str:
    messages = [{
        "role": "user",
        "content": """Sharp strategic assessment of Madalin Muraretiu's brand.

1. Search his current online presence
2. Search comparable figures — operators at TradFi + DeFi intersection
3. Look at what Bybit and top DeFi voices talk about

## Current State (honest)
## The Gap (vs where he wants to be)
## Competitive Landscape (who occupies similar space, his edge)
## 30-Day Plan (3 specific moves)
## The Thesis (12-month positioning if executed correctly)

Think like a trader: thesis, entry, target, timeline."""
    }]
    return execute_agent_turn(messages, max_tool_calls=10, label="Strategy")

# =========================================================
# HELP
# =========================================================

def print_help() -> None:
    print("""
MiticaORM v4 — Brand Agent for Mitica0x

Commands:
  /draft twitter [topic]    -> 3 tweet variants (remembers session)
  /draft linkedin [topic]   -> 3 LinkedIn variants
  /draft instagram [topic]  -> 3 Instagram variants
  /cleardraft               -> reset draft conversation
  /monitor                  -> online presence scan
  /calendar                 -> 7-day content calendar
  /strategy                 -> brand strategy assessment
  /drafts                   -> list saved drafts
  /save [platform] [text]   -> save a draft manually
  /post twitter [draft_id]  -> post saved draft to Twitter
  /test twitter             -> post test tweet to verify connection
  /reset                    -> clear all conversations
  /help                     -> show this
  quit                      -> exit

Examples:
  /draft twitter
  /draft twitter BTC funding rate flipped negative
  /draft linkedin DeFi derivatives market structure
  /post twitter 1
  /test twitter

After drafting:
  "give me variant B"
  "make A shorter"
  "change the tone on C"
  "I like B, save it"
""")

# =========================================================
# MAIN
# =========================================================

def main() -> None:
    conversation: List[Dict] = []
    draft_conversation: List[Dict] = []

    twitter_status = "✅ connected" if all([
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
    ]) else "❌ keys missing"

    print(f"MiticaORM v4 online — Brand Agent for Mitica0x")
    print(f"Twitter: {twitter_status}\n")
    print_help()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting MiticaORM.")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "/help":
            print_help()
            continue
        if user_input.lower() == "/reset":
            conversation = []
            draft_conversation = []
            print("\nMiticaORM: All conversations reset.\n")
            continue
        if user_input.lower() == "/cleardraft":
            draft_conversation = []
            print("\nMiticaORM: Draft conversation cleared.\n")
            continue
        if user_input.lower() == "/drafts":
            print(f"\n{list_drafts()}\n")
            continue
        if user_input.lower() == "/monitor":
            try:
                reply = cmd_monitor()
                print(f"\nMiticaORM:\n{reply}\n")
            except Exception as e:
                print(f"\nMiticaORM: Error: {e}\n")
            continue
        if user_input.lower() == "/calendar":
            try:
                reply = cmd_calendar()
                print(f"\nMiticaORM:\n{reply}\n")
            except Exception as e:
                print(f"\nMiticaORM: Error: {e}\n")
            continue
        if user_input.lower() == "/strategy":
            try:
                reply = cmd_strategy()
                print(f"\nMiticaORM:\n{reply}\n")
            except Exception as e:
                print(f"\nMiticaORM: Error: {e}\n")
            continue

        # Test Twitter connection
        if user_input.lower() == "/test twitter":
            try:
                result = post_tweet("MiticaORM is online. 🔥 #Web3 #DeFi")
                print(f"\nMiticaORM: {result}\n")
            except Exception as e:
                print(f"\nMiticaORM: Error: {e}\n")
            continue

        # Post to Twitter
        if user_input.lower().startswith("/post twitter"):
            parts = user_input.strip().split()
            draft_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None

            if not draft_id:
                print("\nMiticaORM: Usage: /post twitter [draft_id]\nUse /drafts to see saved drafts.\n")
                continue

            draft = next((d for d in drafts if d["id"] == draft_id), None)
            if not draft:
                print(f"\nMiticaORM: Draft #{draft_id} not found.\n")
                continue

            content = draft["content"]
            print(f"\n[DEBUG] Content starts with: {content[:200]}")
            print(f"\nMiticaORM: About to post to Twitter:\n\n{content}\n")
            confirm = input("Confirm post? (yes/no): ").strip().lower()

            if confirm == "yes":
                tweets = parse_thread_from_content(content)
                if len(tweets) > 1:
                    print(f"\nMiticaORM: Posting thread ({len(tweets)} tweets)...")
                    result = post_thread(tweets)
                else:
                    result = post_tweet(content)
                print(f"\nMiticaORM: {result}\n")
            else:
                print("\nMiticaORM: Post cancelled.\n")
            continue
        
        # /draft command — persistent draft memory
        if user_input.lower().startswith("/draft "):
            parts = user_input[7:].strip().split(" ", 1)
            platform = parts[0] if parts else "twitter"
            topic = parts[1] if len(parts) > 1 else ""
            try:
                prompt = build_draft_prompt(platform, topic)
                draft_conversation.append({"role": "user", "content": prompt})
                reply = execute_agent_turn(
                    messages=draft_conversation,
                    max_tool_calls=6,
                    label="Draft"
                )
                draft_conversation.append({"role": "assistant", "content": reply})
                print(f"\nMiticaORM:\n{reply}\n")
            except Exception as e:
                print(f"\nMiticaORM: Error: {e}\n")
            continue

        # Save draft manually
        if user_input.lower().startswith("/save "):
            parts = user_input[6:].strip().split(" ", 1)
            if len(parts) >= 2:
                platform = parts[0]
                content = parts[1].strip('"')
                result = save_draft(platform, content, "manual")
                print(f"\nMiticaORM: {result}\n")
            else:
                print('\nMiticaORM: Usage: /save [platform] "content"\n')
            continue

        # Auto-detect draft feedback
        draft_keywords = [
            "variant", "version", "option", "make it", "shorter", "longer",
            "change", "tone", "i like", "use", "tweak", "edit", "rewrite",
            "save this", "save variant", "save version", "save option",
            "tweet 1", "tweet 2", "tweet 3", "variant a", "variant b", "variant c"
        ]
        is_draft_feedback = (
            any(kw in user_input.lower() for kw in draft_keywords)
            and draft_conversation
        )

        if is_draft_feedback:
            draft_conversation.append({"role": "user", "content": user_input})
            try:
                reply = execute_agent_turn(
                    messages=draft_conversation,
                    max_tool_calls=4,
                    label="Draft"
                )
                draft_conversation.append({"role": "assistant", "content": reply})
                print(f"\nMiticaORM:\n{reply}\n")
            except Exception as e:
                print(f"\nMiticaORM: Error: {e}\n")
            continue

        # General chat
        conversation.append({"role": "user", "content": user_input})
        try:
            reply = execute_agent_turn(
                messages=conversation,
                max_tool_calls=DEFAULT_TOOL_BUDGET,
                label="ORM"
            )
            conversation.append({"role": "assistant", "content": reply})
            print(f"\nMiticaORM: {reply}\n")
        except Exception as e:
            print(f"\nMiticaORM: Error: {e}\n")

if __name__ == "__main__":
    main()