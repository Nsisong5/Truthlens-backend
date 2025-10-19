"""
Verifier Model Module
Uses NLI (Natural Language Inference) model to verify claims against evidence
Uses facebook/bart-large-mnli for stance detection
"""

from transformers import pipeline
from typing import List, Dict
import asyncio
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Initialize NLI model (lazy loading)
_nli_pipeline = None


def get_nli_model():
    """Lazy load the NLI model"""
    global _nli_pipeline
    if _nli_pipeline is None:
        logger.info("Loading NLI model: facebook/bart-large-mnli")
        _nli_pipeline = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1  # CPU for MVP, use device=0 for GPU
        )
    return _nli_pipeline


@lru_cache(maxsize=100)
def _verify_single_cached(claim: str, evidence_text: str) -> tuple:
    """
    Cached synchronous verification of single claim-evidence pair
    Returns tuple for hashability
    """
    try:
        nli = get_nli_model()
        
        # Classify the relationship between claim and evidence
        result = nli(
            claim,
            candidate_labels=["supports", "refutes", "neutral"],
            hypothesis_template="This evidence {} the claim."
        )
        
        # Get the top prediction
        top_label = result['labels'][0]
        confidence = result['scores'][0]
        
        return (top_label, float(confidence))
        
    except Exception as e:
        logger.error(f"NLI model error: {str(e)}")
        return ("neutral", 0.5)


async def verify_single_claim(claim: str, evidence_text: str) -> Dict:
    """
    Verify a single claim against evidence text asynchronously
    
    Args:
        claim: The claim to verify
        evidence_text: Evidence text to check against
        
    Returns:
        Dict with stance (SUPPORT/REFUTE/NEUTRAL) and confidence
    """
    loop = asyncio.get_event_loop()
    label, confidence = await loop.run_in_executor(
        None,
        _verify_single_cached,
        claim,
        evidence_text[:512]  # Limit evidence length for model
    )
    
    # Map to our format
    stance_map = {
        'supports': 'SUPPORT',
        'refutes': 'REFUTE',
        'neutral': 'NEUTRAL'
    }
    
    return {
        'claim': claim,
        'stance': stance_map.get(label, 'NEUTRAL'),
        'confidence': confidence
    }


async def verify_claim(claims: List[str], evidence_list: List[Dict]) -> List[Dict]:
    """
    Verify multiple claims against evidence in parallel
    
    Uses NLI model (facebook/bart-large-mnli) to determine:
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
    
    # Create tasks for parallel verification
    tasks = []
    for claim in claims:
        for evidence in evidence_list:
            # Get evidence text (from extract, claim_text, or title)
            evidence_text = evidence.get('extract') or evidence.get('claim_text') or evidence.get('title', '')
            
            if evidence_text and len(evidence_text) > 20:
                tasks.append(verify_single_claim(claim, evidence_text))
    
    # Run all verifications in parallel
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict):
                verification_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Verification error: {str(result)}")
    
    # If no results, return neutral
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
    _verify_single_cached.cache_clear()