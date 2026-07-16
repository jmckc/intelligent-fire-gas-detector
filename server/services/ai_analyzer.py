"""
server/services/ai_analyzer.py
MiniMax false-alarm discrimination pipeline.

Install: pip install openai
.env:    MINIMAX_API_KEY=your_key
         MINIMAX_GROUP_ID=your_group_id
"""

import os, json, logging, time
from openai import OpenAI

logger = logging.getLogger(__name__)

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key  = os.getenv("MINIMAX_API_KEY")
        group_id = os.getenv("MINIMAX_GROUP_ID")
        if not api_key:
            raise ValueError("MINIMAX_API_KEY not set in .env")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.minimax.io/v1",
            default_headers={
                "Authorization": f"Bearer {api_key}",
                "GroupId": group_id or "",
            },
        )
    return _client


_last_call_time = 0
_MIN_INTERVAL   = 20   # 3 calls per minute max

SYSTEM_PROMPT = """\
You are a fire and gas safety classifier for an IoT detection system.
Sensors:
  - MQ-2 gas sensor: ADC value 0-1023 (>400 = alarm threshold)
  - IR flame sensor: bool (true = flame detected)
  - DHT11 temperature: Celsius (>60C = alarm threshold)
  - DHT11 humidity: percentage

Your job: decide if the alarm is a GENUINE_EMERGENCY or a false alarm.
Common false alarms: cooking smoke, steam, brief sensor spike, single reading anomaly.
Genuine emergencies: sustained high gas + rising trend, open flame, rapid temperature rise.

Reply ONLY with a JSON object, no explanation outside JSON:
{"decision":"GENUINE_EMERGENCY|LIKELY_FALSE_ALARM|UNCERTAIN","confidence":0.0-1.0,"reasoning":"one short sentence"}\
"""


def analyze_with_llm(current: dict, history: list) -> dict:
    global _last_call_time

    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < _MIN_INTERVAL:
        wait = int(_MIN_INTERVAL - elapsed)
        logger.info("Rate limit: next AI call in %ds", wait)
        return {"decision": "UNCERTAIN", "confidence": 0.5,
                "reasoning": f"Rate limited, retry in {wait}s."}
    _last_call_time = now

    # Current reading — full context
    curr = {
        "gas_adc":   current.get("gas_adc"),
        "gas_rate":  current.get("gas_rate_pct"),   # % change over last 10s
        "temp_c":    current.get("temperature"),
        "humidity":  current.get("humidity"),
        "flame":     current.get("flame_detected"),
        "gas_alarm": current.get("gas_alarm"),
        "tmp_alarm": current.get("temp_alarm"),
    }

    # Last 10 readings trend summary
    history_summary = _summarize_history(history, n=10)

    user_msg = (
        f"Current reading: {json.dumps(curr)}\n"
        f"Recent trend (last 10 readings): {history_summary}\n"
        f"Classify this alarm."
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="MiniMax-Text-01",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=120,
            temperature=0.1,
            extra_body={"thinking": {"type": "disabled"}},
        )
        raw = response.choices[0].message.content.strip()

        # Strip <think>...</think> reasoning block if present
        if "<think>" in raw:
            raw = raw.split("</think>")[-1].strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        result["confidence"] = float(result.get("confidence", 0.5))
        result.setdefault("reasoning", "No reasoning provided.")
        logger.info("AI: %s (%.0f%%) — %s",
                    result["decision"], result["confidence"] * 100, result["reasoning"])
        return result

    except json.JSONDecodeError as e:
        logger.error("Non-JSON from AI: %s | raw: %s", e, raw[:200])
    except Exception as e:
        logger.error("LLM failed: %s", e)

    return {"decision": "UNCERTAIN", "confidence": 0.5,
            "reasoning": "AI unavailable."}


def _summarize_history(history: list, n: int = 10) -> str:
    if not history:
        return "none"

    recent = history[-n:]
    lines = []
    for r in recent:
        lines.append(
            f"gas={r.get('gas_adc')} temp={r.get('temperature')} "
            f"flame={int(r.get('flame_detected', 0))} rate={r.get('gas_rate_pct', 0):.1f}%"
        )

    gas_vals = [r["gas_adc"] for r in recent if r.get("gas_adc") is not None]
    if gas_vals:
        trend = "rising" if gas_vals[-1] > gas_vals[0] else "falling" if gas_vals[-1] < gas_vals[0] else "stable"
        summary_line = f"gas_trend={trend} max={max(gas_vals)} min={min(gas_vals)}"
    else:
        summary_line = "no gas data"

    return "[" + "; ".join(lines) + f"] | {summary_line}"
