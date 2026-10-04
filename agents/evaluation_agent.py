import os, json
from langchain_cohere import ChatCohere
from langchain_core.messages import SystemMessage, HumanMessage

MODEL = "command-r-plus-08-2024"   # if this model name errors, try "command-r-08-2024"

SYSTEM_PROMPT = """You are a procurement analyst evaluating ONE supplier's RFP response.
Rules:
1. Use ONLY evidence present in the supplier document. Do not use outside knowledge or assumptions.
2. Return exactly one result for EVERY criterion listed below. Do not skip or add criteria.
3. Each score must be a number between 0 and the criterion's max_score.
4. If the document lacks information for a criterion, give a low score and say what is missing.
5. "evidence" must be a short, direct quote or close paraphrase from the document.
6. Output valid JSON ONLY. No markdown, no code fences, no text outside the JSON.

Required JSON format:
{
  "supplier_name": "<name>",
  "criteria": [
    {"criterion_id": <int>, "score": <number>, "max_score": <number>,
     "justification": "<why this score>", "evidence": "<supporting text from the document>"}
  ],
  "risks": ["<risk 1>", "<risk 2>"],
  "overall_summary": "<2-3 sentences>"
}"""


def build_prompt(supplier_name, document_text, criteria):
    lines = [
        f"- criterion_id {c['criterion_id']}: {c['name']} (max_score {c['max_score']}). Inspect: {c['description']}"
        for c in criteria
    ]
    return (
        f"Supplier: {supplier_name}\n\n"
        f"CRITERIA TO SCORE:\n" + "\n".join(lines) + "\n\n"
        f"SUPPLIER DOCUMENT:\n\"\"\"\n{document_text}\n\"\"\"\n\n"
        "Return the JSON now."
    )


def get_llm(api_key=None):
    key = api_key or os.environ.get("COHERE_API_KEY")
    if not key:
        raise RuntimeError("COHERE_API_KEY is not set.")
    # temperature 0 keeps scoring as repeatable as the LLM allows
    return ChatCohere(model=MODEL, cohere_api_key=key, temperature=0)


def evaluate_supplier(supplier_name, document_text, criteria, api_key=None):
    """Returns the RAW LLM text. The validation tool cleans it afterwards."""
    llm = get_llm(api_key)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=build_prompt(supplier_name, document_text, criteria)),
    ]
    try:
        # Cohere supports forcing JSON output
        response = llm.bind(response_format={"type": "json_object"}).invoke(messages)
    except Exception:
        response = llm.invoke(messages)   # fallback: plain call, validator handles fences
    return response.content
