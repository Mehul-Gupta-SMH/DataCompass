"""
Module: call_llm_api.py

Description:
    This module defines the CallLLMApi class, which is used to interact with various Language Model (LLM) APIs such as OpenAI, Anthropic, and Google.
    It provides methods to call the LLM service API with a provided prompt and retrieve the generated text.

Classes:
    - CallLLMApi: Class to call Language Model (LLM) APIs.

Attributes:
    - llmService (str): The LLM service to be used (e.g., "OpenAI", "Anthropic").
    - api_temp_dict (dict): The API dictionary containing endpoint, headers, and payload.

Methods:
    - __init__(self, llmService="OpenAI"): Initializes an instance of CallLLMApi class.
    - __set_apidict__(self, llmService): Set up the API dictionary based on the specified LLM service.
    - CallService(self, prompt: str) -> str: Call the LLM service API with the provided prompt and return the generated text.
"""

import json
import logging
import time
import requests
import yaml
from Utilities.base_utils import get_config_val

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0          # seconds; doubles on each attempt
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_REQUEST_TIMEOUT = 60            # seconds before a hung request is aborted


class CallLLMApi:
    """
    Class to call Language Model (LLM) APIs.

    Attributes:
        llmService (str): The LLM service to be used (e.g., "OpenAI", "Anthropic").
        api_temp_dict (dict): The API dictionary containing endpoint, headers, and payload.
    """
    def __init__(self, llmService = "OpenAI"):
        """
        Initializes an instance of CallLLMApi class.

        Args:
            llmService (str, optional): The LLM service to be used. Defaults to "OpenAI".
        """
        self.llmService = llmService
        self.api_temp_dict = None
        self.__set_apidict__(llmService)

    def __set_apidict__(self, llmService):
        """
        Set up the API dictionary based on the specified LLM service.

        Args:
            llmService (str): The LLM service.

        Returns:
            dict: The API dictionary.
        """

        model_config_path = get_config_val("model_config", ["model_config","path"])

        # Get model configuration from the config file
        with open(model_config_path,"r") as model_config_FObj:
            model_config = yaml.load(model_config_FObj,yaml.FullLoader)[str(llmService).upper()]

        # Load API calling template
        with open(model_config["api_template"],"r") as api_temp_fobj:
            api_temp_str = api_temp_fobj.read()
            api_temp_str = api_temp_str.replace("<<api_key>>",model_config["api_key"])
            api_temp_str = api_temp_str.replace("<<model>>",model_config["model_name"])

        # Convert API template string to dictionary
        self.api_temp_dict = json.loads(api_temp_str)


    def CallService(self, prompt: str) -> str:
        """
        Call the LLM service API with the provided prompt.

        Args:
            prompt (str): The prompt text.

        Returns:
            str: Generated text.

        Raises:
            ValueError: If the API call fails.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")

        if self.llmService.lower() in ("open_ai","groq"):
            # Update the payload with the prompt for OpenAI API
            self.api_temp_dict["payload"]["messages"][0]["content"] = prompt

        if self.llmService.lower() == "anthropic":
            # Update the payload with the prompt for Anthropic AI API
            self.api_temp_dict["payload"]["prompt"] = self.api_temp_dict["payload"]["prompt"].replace("<<input_text>>",prompt)

        if self.llmService.lower() == "google":
            # Update the payload with the prompt for Google API
            self.api_temp_dict["payload"]["contents"][0]["parts"][0]["text"] = prompt


        # Make the API call with exponential backoff retry for transient errors
        for attempt in range(1, _MAX_RETRIES + 1):
            response = requests.post(
                self.api_temp_dict["endpoint"],
                headers=self.api_temp_dict["headers"],
                json=self.api_temp_dict["payload"],
                timeout=_REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                if self.llmService.lower() in ("open_ai", "groq"):
                    return data['choices'][0]['message']['content']
                if self.llmService.lower() == "anthropic":
                    return data['completion']
                if self.llmService.lower() == "google":
                    return data['candidates'][0]['content']['parts'][0]['text']

            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM API returned %d (attempt %d/%d) — retrying in %.1fs",
                        response.status_code, attempt, _MAX_RETRIES, delay
                    )
                    time.sleep(delay)
                    continue

            # Non-retryable error or retries exhausted
            raise ValueError(
                f"LLM API call failed after {attempt} attempt(s). "
                f"Status code: {response.status_code} — {response.text[:200]}"
            )

