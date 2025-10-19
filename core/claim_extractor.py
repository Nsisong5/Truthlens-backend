
import spacy
from typing import List
import re
import asyncio
from functools import lru_cache

# Load spaCy model (use en_core_web_sm for MVP)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If model not found, download it
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


@lru_cache(maxsize=100)
def _extract_claims_cached(text: str) -> tuple:
    """
    Cached synchronous claim extraction
    Returns tuple for hashability (required by lru_cache)
    """
    doc = nlp(text)
    claims = []
    
    for sent in doc.sents:
        sent_text = sent.text.strip()
        
        # Skip very short sentences
        if len(sent_text.split()) < 5:
            continue
        
        # Check if sentence contains entities or numbers (likely factual)
        has_entities = any(ent.label_ in ['PERSON', 'ORG', 'GPE', 'DATE', 'CARDINAL'] 
                          for ent in sent.ents)
        has_numbers = bool(re.search(r'\d', sent_text))
        
        # Check for factual indicators
        factual_patterns = [
            r'\b(is|are|was|were|has|have|had)\b',
            r'\b(according to|reported|stated|confirmed|announced)\b',
            r'\b(study|research|report|survey|data)\b',
            r'\b(shows|reveals|indicates|suggests|demonstrates)\b'
        ]
        has_factual_language = any(re.search(pattern, sent_text, re.I) 
                                   for pattern in factual_patterns)
        
        # Include sentence if it has entities/numbers or factual language
        if (has_entities or has_numbers) and has_factual_language:
            claims.append(sent_text)
        elif has_entities and len(sent_text.split()) >= 8:
            # Include longer sentences with entities even without factual language
            claims.append(sent_text)
    
    # Limit to top 5 most substantial claims
    claims = sorted(claims, key=len, reverse=True)[:5]
    
    return tuple(claims)


async def extract_claims(text: str) -> List[str]:
    """
    Extract verifiable factual claims from text asynchronously
    
    Uses spaCy for:
    - Sentence segmentation
    - Named Entity Recognition (NER)
    - Part-of-speech tagging
    
    Args:
        text: Input text to analyze
        
    Returns:
        List of extracted factual claims (sentences)
        
    Example:
        >>> text = "The WHO confirmed that vaccines are safe. Studies show 95% efficacy."
        >>> claims = await extract_claims(text)
        >>> print(claims)
        ['The WHO confirmed that vaccines are safe.', 'Studies show 95% efficacy.']
    """
    # Run in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    claims_tuple = await loop.run_in_executor(
        None, 
        _extract_claims_cached, 
        text
    )
    
    return list(claims_tuple)


def clear_cache():
    """Clear the claim extraction cache"""
    _extract_claims_cached.cache_clear()