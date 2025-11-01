import json

from optiver_challenge.ai.ai_handlers import request_openrouter, request_gemini, request_anthropic, request_openai
from enum import Enum, auto

from optiver_challenge.ai.ai_handlers import request_cerebras


class LowercaseEnum(str, Enum):
    def _generate_next_value_(self, start, count, last_values):
        return self.lower()

class Providers(LowercaseEnum):
    GOOGLE = auto()
    ANTHROPIC = auto()
    OPENAI = auto()
    CEREBRAS = auto()
    OPENROUTER = auto()

SUPPORTED_MODELS = {
    Providers.GOOGLE: ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemma-3-27b-it"],
    Providers.ANTHROPIC: ['claude-sonnet-4-5-20250929', 'claude-opus-4-1-20250805'],
    Providers.OPENAI: ['gpt-5', 'gpt-4o'],
    Providers.CEREBRAS: ['qwen-3-235b-a22b-instruct-2507', 'gpt-oss-120b', 'qwen-3-coder-480b', 'llama3.1-8b', 'qwen-3-32b'],
    Providers.OPENROUTER: ['google/gemini-2.5-pro', 'google/gemini-2.5-flash', 'anthropic/claude-sonnet-4.5', 'anthropic/claude-opus-4.1'],
}

PROVIDER_FUNCTIONS = {
    Providers.GOOGLE: request_gemini,
    Providers.ANTHROPIC: request_anthropic,
    Providers.OPENAI: request_openai,
    Providers.CEREBRAS: request_cerebras,
    Providers.OPENROUTER: request_openrouter,
}

def request_ai(system_prompt: str, user_text: str=None, provider: str | Providers | None = None, model:str | None=None, temperature: float=0.2) -> dict:
    if provider is None:
        provider = Providers.CEREBRAS
    else:
        provider = Providers(provider)

    if model is None:
        model = "gpt-oss-120b"

    response_text: str = PROVIDER_FUNCTIONS[provider](system_prompt, user_text, model, temperature)

    return parse_ai_response(response_text)


def parse_ai_response(response_text: str) -> dict:
    response_text = response_text.strip()
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start: int = 0
        if "```json" in response_text:
            start = response_text.find("```json") + 7
        elif "```" in response_text:
            start = response_text.find("```") + 3

        if start != 0:
            end: int = response_text.find("```", start)
            if end != -1:
                response_text = response_text[start:end]

    try:
        return json.loads(response_text)
    except json.decoder.JSONDecodeError as e:
        raise Exception(e)