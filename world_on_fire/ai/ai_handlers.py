import os

from cerebras.cloud.sdk import Cerebras
from dotenv import load_dotenv
import logging

import google.generativeai as genai
from openai import OpenAI
import anthropic

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("google.generativeai").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("cerebras.cloud.sdk").setLevel(logging.ERROR)

def request_gemini(system_prompt: str, user_text: str=None, model:str=None, temperature: float=0.0) -> str:
    genai.configure(api_key=GEMINI_API_KEY)

    generative_model = genai.GenerativeModel(model, system_instruction=system_prompt)

    response = generative_model.generate_content(
        contents=user_text,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
        ),
    )

    return response.text

def request_anthropic(system_prompt: str, user_text: str=None, model:str=None, temperature: float=0.0):
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    response: str = ""

    with client.messages.stream(
        model=model,
        max_tokens=20000,
        temperature=temperature,
        system=system_prompt,
        messages=[
            {
                'role': 'user',
                'content': user_text,
            }
        ]
    ) as stream:
        for text in stream.text_stream:
            response += text

    return response

def request_openrouter(system_prompt: str, user_text: str=None, model:str=None, temperature: float=0.0) -> str:
    link: str="https://openrouter.ai/api/v1"
    return request_openai(system_prompt, user_text, model, temperature, link)

def request_openai(system_prompt: str, user_text: str=None, model:str=None, temperature: float=0.0, link:str | None=None) -> str:
    client = OpenAI(
        base_url=link,
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text}
        ],
        temperature=temperature
    )

    return completion.choices[0].message.content

def request_cerebras(system_prompt: str, user_text: str, model: str, temperature: float=0.0):
    client = Cerebras(
        api_key=os.environ.get("CEREBRAS_API_KEY")
    )

    response = client.chat.completions.create(
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_text},
        ],
        model=model,
        stream=False,
        max_completion_tokens=20000,
        temperature=temperature,
        top_p=0.8
    )

    return response.choices[0].message.content