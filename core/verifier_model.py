"""
Verifier Model Module
Uses Grok API (xAI) to verify claims against evidence
Replaces local NLI model for better performance and scalability
"""

import httpx
import os
from typing import List, Dict
import asyncio
from functools import lru_cache
import logging
import json

logger = logging.getLogger(__name__)

# Grok API Configuration
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# Verification prompt template
VERIFICATION_PROMPT = """You are a fact-checking AI assistant. Your task is to determine if the evidence SUPPORTS, REFUTES, or is NEUTRAL towards the given claim.

Claim: {claim}

Evidence: {evidence}

Analyze the relationship between the claim and evidence. Respond with ONLY ONE of these labels:
- SUPPORT: If the evidence clearly supports or confirms the claim
- REFUTE: If the evidence contradicts or disproves the claim  
- NEUTRAL: If the evidence is unrelated or doesn't clearly support/refute the claim

Response format (JSON):
{{"stance": "SUPPORT|REFUTE|NEUTRAL", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}

Respond only with valid JSON, no additional text."""


async def _call_grok_api(claim: str, evidence_text: str, client: httpx.AsyncClient) -> Dict:
    """
    Call Grok API to verify claim against evidence
    
    Args:
        claim: The claim to verify
        evidence_text: Evidence text to check against
        client: httpx AsyncClient instance
        
    Returns:
        Dict with stance, confidence, and reasoning
    """
    if not GROK_API_KEY:
        logger.error("GROK_API_KEY not configured in environment variables")
        return {"stance": "NEUTRAL", "confidence": 0.5, "reasoning": "API key not configured"}
    
    try:
        prompt = VERIFICATION_PROMPT.format(
            claim=claim,
            evidence=evidence_text[:1000]  # Limit evidence length
        )
        
        payload = {
            "model": "grok-beta",  # or "grok-2-latest" depending on your access
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise fact-checking assistant that outputs only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,  # Low temperature for consistent results
            "max_tokens": 150
        }
        
        headers = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = await client.post(
            GROK_API_URL,
            json=payload,
            headers=headers,
            timeout=30.0
        )
        
        response.raise_for_status()
        data = response.json()
        
        # Extract response content
        content = data['choices'][0]['message']['content'].strip()
        
        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            content = content.strip()
            
            result = json.loads(content)
            
            # Validate response
            stance = result.get('stance', 'NEUTRAL').upper()
            if stance not in ['SUPPORT', 'REFUTE', 'NEUTRAL']:
                stance = 'NEUTRAL'
            
            confidence = float(result.get('confidence', 0.7))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
            
            reasoning = result.get('reasoning', 'Analysis completed')
            
            return {
                "stance": stance,
                "confidence": confidence,
                "reasoning": reasoning
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Grok response as JSON: {content}")
            # Fallback: try to extract stance from text
            content_upper = content.upper()
            if 'SUPPORT' in content_upper and 'NOT' not in content_upper:
                stance = 'SUPPORT'
            elif 'REFUTE' in content_upper or 'CONTRADICT' in content_upper:
                stance = 'REFUTE'
            else:
                stance = 'NEUTRAL'
            
            return {
                "stance": stance,
                "confidence": 0.7,
                "reasoning": "Extracted from text analysis"
            }
        
    except httpx.HTTPError as e:
        logger.error(f"Grok API HTTP error: {str(e)}")
        return {
            "stance": "NEUTRAL",
            "confidence": 0.5,
            "reasoning": f"API error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Grok API error: {str(e)}")
        return {
            "stance": "NEUTRAL",
            "confidence": 0.5,
            "reasoning": f"Error: {str(e)}"
        }


@lru_cache(maxsize=100)
def _cache_key(claim: str, evidence: str) -> str:
    """Generate cache key for claim-evidence pair"""
    return f"{claim[:100]}||{evidence[:100]}"


async def verify_single_claim(claim: str, evidence_text: str, client: httpx.AsyncClient) -> Dict:
    """
    Verify a single claim against evidence text using Grok API
    
    Args:
        claim: The claim to verify
        evidence_text: Evidence text to check against
        client: httpx AsyncClient instance
        
    Returns:
        Dict with claim, stance (SUPPORT/REFUTE/NEUTRAL), and confidence
    """
    result = await _call_grok_api(claim, evidence_text, client)
    
    return {
        'claim': claim,
        'stance': result['stance'],
        'confidence': result['confidence']
    }


async def verify_claim(claims: List[str], evidence_list: List[Dict]) -> List[Dict]:
    """
    Verify multiple claims against evidence in parallel using Grok API
    
    Uses Grok to determine:
    - SUPPORT: Evidence supports the claim
    - REFUTE: Evidence contradicts the claim
    - NEUTRAL: Not enough information
    
    Args:
        claims: List of claims to verify
        evidence_list: List of evidence dictionaries
        
    Returns:
        List of verification results with stance and confidence
        
    Example:
        >>> claims = ["Vaccines are safe"]
        >>> evidence = [{"extract": "WHO confirms vaccines are safe..."}]
        >>> results = await verify_claim(claims, evidence)
        >>> print(results[0]['stance'])
        'SUPPORT'
    """
    verification_results = []
    
    async with httpx.AsyncClient() as client:
        # Create tasks for parallel verification
        tasks = []
        for claim in claims:
            for evidence in evidence_list:
                # Get evidence text (from extract, claim_text, or title)
                evidence_text = (
                    evidence.get('extract') or 
                    evidence.get('claim_text') or 
                    evidence.get('title', '')
                )
                
                if evidence_text and len(evidence_text) > 20:
                    tasks.append(verify_single_claim(claim, evidence_text, client))
        
        # Run all verifications in parallel (with rate limiting)
        if tasks:
            # Batch requests to avoid rate limits (5 concurrent max)
            batch_size = 5
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                results = await asyncio.gather(*batch, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, dict):
                        verification_results.append(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Verification error: {str(result)}")
                
                # Small delay between batches to respect rate limits
                if i + batch_size < len(tasks):
                    await asyncio.sleep(0.5)
    
    # If no results, return neutral for each claim
    if not verification_results:
        for claim in claims:
            verification_results.append({
                'claim': claim,
                'stance': 'NEUTRAL',
                'confidence': 0.5
            })
    
    return verification_results


def clear_cache():
    """Clear the verification cache"""
    _cache_key.cache_clear()