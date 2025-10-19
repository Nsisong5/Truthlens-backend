"""
Evidence Retriever Module
Queries trusted sources (Google Fact Check API, Wikipedia) for evidence
Uses httpx for async HTTP requests
"""

import httpx
import asyncio
from typing import List, Dict, Optional
from functools import lru_cache
import os
import logging

logger = logging.getLogger(__name__)

# API Configuration
GOOGLE_FACT_CHECK_API_KEY = os.getenv("GOOGLE_FACT_CHECK_API_KEY", "")
FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"

# Trusted source domains for reputation scoring
TRUSTED_SOURCES = {
    'who.int': 'WHO',
    'cdc.gov': 'CDC',
    'reuters.com': 'Reuters',
    'bbc.com': 'BBC',
    'apnews.com': 'AP News',
    'factcheck.org': 'FactCheck.org',
    'snopes.com': 'Snopes',
    'politifact.com': 'PolitiFact'
}


async def _search_google_fact_check(claim: str, client: httpx.AsyncClient) -> List[Dict]:
    """
    Search Google Fact Check API for claim reviews
    
    Args:
        claim: The claim to search for
        client: httpx AsyncClient instance
        
    Returns:
        List of fact check results
    """
    if not GOOGLE_FACT_CHECK_API_KEY:
        logger.warning("Google Fact Check API key not configured")
        return []
    
    try:
        params = {
            'query': claim,
            'key': GOOGLE_FACT_CHECK_API_KEY,
            'languageCode': 'en'
        }
        
        response = await client.get(FACT_CHECK_API_URL, params=params, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        claims = data.get('claims', [])
        
        results = []
        for item in claims[:3]:  # Top 3 results
            claim_review = item.get('claimReview', [{}])[0]
            results.append({
                'title': claim_review.get('title', 'Fact Check'),
                'url': claim_review.get('url', ''),
                'publisher': claim_review.get('publisher', {}).get('name', 'Unknown'),
                'text_rating': claim_review.get('textualRating', 'Unknown'),
                'claim_text': item.get('text', ''),
                'source': 'google_fact_check'
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Google Fact Check API error: {str(e)}")
        return []


async def _search_wikipedia(claim: str, client: httpx.AsyncClient) -> List[Dict]:
    """
    Search Wikipedia API for relevant articles
    
    Args:
        claim: The claim to search for
        client: httpx AsyncClient instance
        
    Returns:
        List of Wikipedia articles
    """
    try:
        # Search for relevant pages
        search_params = {
            'action': 'query',
            'list': 'search',
            'srsearch': claim,
            'format': 'json',
            'srlimit': 3
        }
        
        response = await client.get(WIKIPEDIA_API_URL, params=search_params, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        search_results = data.get('query', {}).get('search', [])
        
        results = []
        for item in search_results[:2]:  # Top 2 results
            page_id = item['pageid']
            title = item['title']
            
            # Get extract for the page
            extract_params = {
                'action': 'query',
                'prop': 'extracts|info',
                'exintro': True,
                'explaintext': True,
                'inprop': 'url',
                'pageids': page_id,
                'format': 'json'
            }
            
            extract_response = await client.get(WIKIPEDIA_API_URL, params=extract_params, timeout=10.0)
            extract_data = extract_response.json()
            
            pages = extract_data.get('query', {}).get('pages', {})
            page_data = pages.get(str(page_id), {})
            
            results.append({
                'title': f"Wikipedia: {title}",
                'url': page_data.get('fullurl', f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"),
                'publisher': 'Wikipedia',
                'extract': page_data.get('extract', '')[:500],  # First 500 chars
                'source': 'wikipedia'
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Wikipedia API error: {str(e)}")
        return []


async def search_evidence(claims: List[str]) -> List[Dict]:
    """
    Search for evidence for multiple claims in parallel
    
    Queries:
    1. Google Fact Check API (ClaimReview)
    2. Wikipedia API
    
    Args:
        claims: List of claims to search evidence for
        
    Returns:
        List of evidence dictionaries with title, url, publisher, text
        
    Example:
        >>> claims = ["Vaccines are safe"]
        >>> evidence = await search_evidence(claims)
        >>> print(evidence[0]['title'])
        'WHO: Vaccine Safety'
    """
    all_evidence = []
    
    async with httpx.AsyncClient() as client:
        # Search each claim in parallel
        tasks = []
        for claim in claims:
            # Search both APIs for each claim
            tasks.append(_search_google_fact_check(claim, client))
            tasks.append(_search_wikipedia(claim, client))
        
        # Wait for all searches to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten and filter results
        for result in results:
            if isinstance(result, list):
                all_evidence.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Evidence search error: {str(result)}")
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_evidence = []
    for evidence in all_evidence:
        url = evidence.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_evidence.append(evidence)
    
    # Sort by source priority (Fact checks first, then Wikipedia)
    unique_evidence.sort(key=lambda x: 0 if x.get('source') == 'google_fact_check' else 1)
    
    # Return top 5 pieces of evidence
    return unique_evidence[:5]


def get_source_reputation(url: str) -> Optional[str]:
    """
    Get the reputation name for a source URL
    
    Args:
        url: Source URL
        
    Returns:
        Source name if trusted, None otherwise
    """
    for domain, name in TRUSTED_SOURCES.items():
        if domain in url.lower():
            return name
    return None