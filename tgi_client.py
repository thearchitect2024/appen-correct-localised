"""
TGI Client for AppenCorrect
Replaces vLLM with Text-Generation-Inference (Hugging Face)
"""

import json
import logging
import time
import requests
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class TGIClient:
    """Client for TGI (Text-Generation-Inference) server"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize TGI client
        
        Args:
            base_url: TGI server URL (e.g., http://localhost:8080)
            model: Model name/path (for reference, TGI loads model at startup)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.endpoint = f"{self.base_url}/generate"
        
        logger.info(f"TGIClient initialized - URL: {self.base_url}, Model: {self.model}")
    
    def test_connection(self) -> bool:
        """Test TGI server connection"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✓ TGI server connection successful")
                return True
            else:
                logger.warning(f"TGI server returned status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ TGI server connection failed: {e}")
            return False
    
    def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Generate text using TGI
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate (max_new_tokens in TGI)
            temperature: Sampling temperature (0.0 = deterministic)
            top_p: Nucleus sampling parameter
            stop: Stop sequences
            
        Returns:
            Generated text or None on error
        """
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stop": stop or [],
                "do_sample": temperature > 0,
                "return_full_text": False
            }
        }
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Attempt {attempt} to call TGI API")
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
                    text = result["generated_text"].strip()
                    logger.info(f"✓ TGI response received in {elapsed:.2f}s")
                    return text
                else:
                    logger.error(f"TGI API error {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"TGI request timeout (attempt {attempt}/{self.max_retries})")
                if attempt == self.max_retries:
                    logger.error("Max retries exceeded - timeout")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                logger.error(f"TGI API call failed (attempt {attempt}): {e}")
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
        Correct text using TGI with structured output
        
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
            max_tokens=1024,
            temperature=temperature,
            top_p=0.9,
            stop=["</response>", "\n\n\n"]
        )
        
        if not response:
            logger.error("No response from TGI")
            return None
        
        # Parse JSON response
        try:
            # Extract JSON from response
            result = self._parse_response(response)
            return result
        except Exception as e:
            logger.error(f"Failed to parse TGI response: {e}")
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
        """Parse TGI response and extract JSON"""
        
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


def create_tgi_client(base_url: str = None, model: str = None) -> TGIClient:
    """
    Factory function to create TGI client
    
    Args:
        base_url: TGI server URL (default: http://localhost:8080)
        model: Model name (default: Qwen/Qwen2.5-7B-Instruct)
    """
    import os
    
    base_url = base_url or os.getenv("TGI_URL", "http://localhost:8080")
    model = model or os.getenv("TGI_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    
    return TGIClient(base_url=base_url, model=model)

