"""
vLLM Client for AppenCorrect
Replaces Gemini API with local vLLM inference
"""

import json
import logging
import time
import requests
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class VLLMClient:
    """Client for vLLM inference server"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        timeout: int = 60,
        max_retries: int = 3,
        max_model_len: int = 4096
    ):
        """
        Initialize vLLM client
        
        Args:
            base_url: vLLM server URL (e.g., http://localhost:8000)
            model: Model name/path
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            max_model_len: Maximum context length (default: 4096)
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_model_len = max_model_len
        self.endpoint = f"{self.base_url}/v1/chat/completions"
        
        logger.info(f"VLLMClient initialized - URL: {self.base_url}, Model: {self.model}, Max context: {self.max_model_len}")
    
    def test_connection(self) -> bool:
        """Test vLLM server connection"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✓ vLLM server connection successful")
                return True
            else:
                logger.warning(f"vLLM server returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ vLLM server connection failed: {e}")
            return False
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation)
        Rule of thumb: 1 token ≈ 4 characters for English
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)
    
    def calculate_max_tokens(self, prompt: str, system_message: Optional[str] = None, 
                            desired_max_tokens: int = 512, safety_margin: int = 50) -> int:
        """
        Calculate safe max_tokens based on context length
        
        Args:
            prompt: User prompt text
            system_message: Optional system message
            desired_max_tokens: Desired max tokens (will be reduced if needed)
            safety_margin: Safety margin for tokenization differences
            
        Returns:
            Safe max_tokens value
        """
        # Estimate tokens in prompt
        prompt_tokens = self.estimate_tokens(prompt)
        system_tokens = self.estimate_tokens(system_message) if system_message else 0
        
        # Total input tokens
        total_input_tokens = prompt_tokens + system_tokens + safety_margin
        
        # Calculate available tokens for output
        available_tokens = self.max_model_len - total_input_tokens
        
        # Return the minimum of desired and available
        safe_max_tokens = min(desired_max_tokens, max(64, available_tokens))
        
        if safe_max_tokens < desired_max_tokens:
            logger.warning(f"Reduced max_tokens from {desired_max_tokens} to {safe_max_tokens} "
                          f"(prompt uses ~{total_input_tokens} tokens, context limit: {self.max_model_len})")
        
        return safe_max_tokens
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        top_p: float = 1.0,
        stop: Optional[List[str]] = None,
        system_message: Optional[str] = None,
        do_sample: bool = False,
        auto_adjust_tokens: bool = True
    ) -> Optional[str]:
        """
        Generate text using vLLM chat completions
        
        Args:
            prompt: Input prompt (user message)
            max_tokens: Maximum tokens to generate (default: 512, auto-adjusted if needed)
            temperature: Sampling temperature (0.0 = deterministic, greedy decoding)
            top_p: Nucleus sampling parameter (1.0 = disabled)
            stop: Stop sequences (empty for JSON to prevent truncation)
            system_message: Optional system message (extracted from prompt if present)
            do_sample: Enable sampling (False = greedy/deterministic)
            auto_adjust_tokens: Automatically adjust max_tokens to fit context (default: True)
            
        Returns:
            Generated text or None on error
        """
        # Split prompt into system and user if not provided separately
        if system_message is None and "\n\n" in prompt:
            # Try to extract system message from combined prompt
            parts = prompt.split("\n\n", 1)
            if "You are" in parts[0] or "CRITICAL" in parts[0]:
                system_message = parts[0]
                prompt = parts[1]
        
        # Auto-adjust max_tokens to prevent context overflow
        if auto_adjust_tokens:
            max_tokens = self.calculate_max_tokens(prompt, system_message, max_tokens)
        
        # Build messages for chat completions
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": stop if stop is not None else []
        }
        
        # Add do_sample for deterministic output (vLLM OpenAI compatibility)
        if not do_sample and temperature == 0.0:
            payload["temperature"] = 0.0
            payload["top_p"] = 1.0
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Attempt {attempt} to call vLLM API")
                logger.debug(f"vLLM Prompt (first 500 chars):\n{prompt[:500]}...")
                start_time = time.time()
                
                response = requests.post(
                    self.endpoint,
                    json=payload,
                    timeout=self.timeout,
                    headers={"Content-Type": "application/json"}
                )
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    # Chat completions returns message content, not text
                    raw_text = result["choices"][0]["message"]["content"].strip()
                    logger.info(f"✓ vLLM response received in {elapsed:.2f}s ({len(raw_text)} chars)")
                    logger.info(f"vLLM Raw Response:\n{raw_text[:500]}...")  # INFO level, first 500 chars
                    
                    # Robust JSON extraction: find first { and last }
                    start_idx = raw_text.find('{')
                    end_idx = raw_text.rfind('}')
                    
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        # Extract JSON portion only
                        json_text = raw_text[start_idx:end_idx + 1]
                        logger.debug(f"Extracted JSON (length: {len(json_text)})")
                        return json_text
                    else:
                        # No JSON found, return as-is (will be handled by caller)
                        logger.warning("No JSON delimiters found in response")
                        return raw_text
                else:
                    logger.error(f"vLLM API error {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"vLLM request timeout (attempt {attempt}/{self.max_retries})")
                if attempt == self.max_retries:
                    logger.error("Max retries exceeded - timeout")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"vLLM API call failed (attempt {attempt}): {e}")
                if attempt == self.max_retries:
                    return None
                time.sleep(2 ** attempt)
        
        return None
    
    def correct_text(
        self,
        text: str,
        language: str = "english",
        temperature: float = 0.2
    ) -> Optional[Dict[str, Any]]:
        """
        Correct text using vLLM with structured output
        
        Args:
            text: Text to correct
            language: Language of the text
            temperature: Sampling temperature (lower = more deterministic)
            
        Returns:
            Dictionary with corrected_text and errors, or None on error
        """
        # Construct prompt for grammar/spelling correction
        prompt = self._build_correction_prompt(text, language)
        
        # Generate response
        response = self.generate(
            prompt=prompt,
            max_tokens=256,
            temperature=temperature,
            top_p=0.9,
            stop=["\n\n", "```", "</response>", "JSON Response:", "Input text:"]
        )
        
        if not response:
            logger.error("No response from vLLM")
            return None
        
        # Parse JSON response
        try:
            # Extract JSON from response
            result = self._parse_response(response)
            return result
        except Exception as e:
            logger.error(f"Failed to parse vLLM response: {e}")
            logger.debug(f"Raw response: {response}")
            return None
    
    def _build_correction_prompt(self, text: str, language: str) -> str:
        """Build prompt for grammar/spelling correction"""
        
        prompt = f"""You are an expert grammar and spelling checker for {language} text.

Task: Analyze the following text and correct any spelling, grammar, punctuation, or style errors.

Instructions:
1. Return ONLY valid JSON with no additional text
2. Provide the corrected text
3. List all errors found with their corrections and error types
4. If no errors found, return empty errors array and original text

Input text:
{text}

Output format (JSON only):
{{
  "corrected_text": "the fully corrected text",
  "errors": [
    {{
      "original": "incorrect word or phrase",
      "correction": "correct version",
      "type": "spelling|grammar|punctuation|style",
      "position": 0,
      "message": "brief explanation"
    }}
  ]
}}

JSON Response:"""
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse vLLM response and extract JSON"""
        
        # Try to find JSON in response
        response = response.strip()
        
        # Look for JSON block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()
        
        # Find first { and last }
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON found in response")
        
        json_str = response[start_idx:end_idx + 1]
        
        # Parse JSON
        result = json.loads(json_str)
        
        # Validate structure
        if "corrected_text" not in result:
            raise ValueError("Missing 'corrected_text' in response")
        if "errors" not in result:
            result["errors"] = []
        
        return result


def create_vllm_client(base_url: str = None, model: str = None, max_model_len: int = None) -> VLLMClient:
    """
    Factory function to create vLLM client
    
    Args:
        base_url: vLLM server URL (default: http://localhost:8000)
        model: Model name (default: Qwen/Qwen2.5-7B-Instruct)
        max_model_len: Maximum context length (default: 4096, or from VLLM_MAX_MODEL_LEN env var)
    """
    import os
    
    base_url = base_url or os.getenv("VLLM_URL", "http://localhost:8000")
    model = model or os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    max_model_len = max_model_len or int(os.getenv("VLLM_MAX_MODEL_LEN", "4096"))
    
    return VLLMClient(base_url=base_url, model=model, max_model_len=max_model_len)

