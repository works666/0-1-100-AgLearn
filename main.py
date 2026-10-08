# Please install OpenAI SDK first: `pip3 install openai`
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.environ.get("DEEPSEEK_KEY")
if not api_key:
    raise ValueError("DEEPSEEK_KEY is missing. Add it to the project .env file.")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-flash",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ],
    stream=False,
    reasoning_effort="low",
    #extra_body={"thinking": {"type": "enabled"}}
)

print(response)
#print(response.choices[0])
print(response.choices[0].message.content)
