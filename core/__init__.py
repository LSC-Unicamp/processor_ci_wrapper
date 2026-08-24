import os
from core.bus_defines import PROTOCOLS
from ollama import Client

SERVER_URL = "http://enqii.lsc.ic.unicamp.br:11434"
#SERVER_URL = 'http://127.0.0.1:11434'
#SERVER_URL = os.getenv('SERVER_URL', 'http://127.0.0.1:11434')
client = Client(host=SERVER_URL)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURRENT_DIR = os.getcwd()
BUILD_DIR = os.path.join(CURRENT_DIR, 'build')
TEMPLATES_DIR: str = os.path.normpath(
    os.path.join(BASE_DIR, '..', 'templates')
)
INTERNAL_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', 'internal'))


def send_prompt(prompt: str, model: str = 'qwen2.5:14b') -> tuple[bool, str]:
    """
    Sends a prompt to the specified server and receives the model's response.

    Args:
        prompt (str): The prompt to be sent to the model.
        model (str, optional): The model to use. Default is 'qwen2.5:32b'.

    Returns:
        tuple: A tuple containing a boolean value (indicating success)
               and the model's response as a string.
    """
    response = client.generate(prompt=prompt, model=model)

    # print("Full response:", response)  # Debug: show the full response

    if not response or 'response' not in response:
        return 0, ''

    return 1, response['response']
