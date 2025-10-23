# openai_api.py
# author: rraught@appen.com
# date: 2025-02-06
# version: 0.2
#
import time
import logging
import openai

def call_openai_api(
    messages,
    api_key,
    system_message=None,
    model=None,
    max_retries=1,
    backoff_factor=2,
    max_tokens=300,
    temperature=0.1,
    timeout=30
):
    """
    Calls the OpenAI ChatCompletion API using the new client-based interface.
    Implements retry logic with exponential backoff.
    
    Args:
        messages (list): List of message dicts (each with "role" and "content").
        api_key (str): Your OpenAI API key.
        system_message (str): Optional system message.
        model (str): The model name to use. Defaults to "o1-mini-2024-09-12" if not provided.
        max_retries (int): Maximum retry attempts.
        backoff_factor (int): Exponential backoff factor.
        max_tokens (int): Maximum tokens in the response.
        temperature (float): Sampling temperature.
        
    Returns:
        The API response object.
        
    Raises:
        Exception: If all retries fail.
    """
    logger = logging.getLogger(__name__)
    if model is None:
        model = "o1-mini-2024-09-12"
    
    # Prepend a system message if provided.
    if system_message:
        messages = [{"role": "system", "content": system_message}] + messages

    # Simple retry logic without external circuit breaker dependency
    
    # Instantiate the OpenAI client using the new interface.
    client = openai.OpenAI(api_key=api_key)
    
    def make_openai_call():
        """Make the actual OpenAI API call with timeout protection."""
        return client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,
            timeout=timeout
        )
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempt {attempt} to call OpenAI API.")
            
            # Make the API call directly
            completion = make_openai_call()
            
            logger.info("Received response from OpenAI API.")
            return completion
        except Exception as e:
            logger.error(f"OpenAI API call failed on attempt {attempt}: {e}")
            
            # Log the error and continue with retry logic
                
            if attempt == max_retries:
                logger.error("Max retries exceeded. Raising exception.")
                raise
            wait_time = backoff_factor ** attempt
            logger.info(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    raise Exception("Failed to get a successful response from OpenAI API after multiple retries.")
