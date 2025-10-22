
from typing import List, Dict
import numpy as np
from core.evidence_retriever import get_source_reputation


def compute_score(verification_results: List[Dict], evidence_list: List[Dict]) -> Dict:
    """
    Compute final truth score from verification results
    
    Scoring system:
    - SUPPORT: +60 points
    - REFUTE: -60 points
    - NEUTRAL: 0 points
    - Trusted source bonus: +20 points
    - Confidence weighting applied
    
    Args:
        verification_results: List of verification results with stance and confidence
        evidence_list: List of evidence sources with URLs
        
    Returns:
        Dict with overall_score, verdict, explanation, and sources
        
    Example:
        >>> results = [{'stance': 'SUPPORT', 'confidence': 0.9}]
        >>> evidence = [{'title': 'WHO Report', 'url': 'https://who.int/...'}]
        >>> score_data = compute_score(results, evidence)
        >>> print(score_data['overall_score'])
        74
    """
    if not verification_results:
        return {
            'overall_score': 50,
            'verdict': 'Not Enough Information',
            'explanation': 'Unable to verify claims due to insufficient evidence.',
            'sources': []
        }
    
    # Calculate raw scores
    raw_scores = []
    for result in verification_results:
        stance = result['stance']
        confidence = result['confidence']
        
        # Base score from stance
        if stance == 'SUPPORT':
            base_score = 60
        elif stance == 'REFUTE':
            base_score = -60
        else:  # NEUTRAL
            base_score = 0
        
        # Weight by confidence
        weighted_score = base_score * confidence
        raw_scores.append(weighted_score)
    
    # Calculate mean score
    mean_score = np.mean(raw_scores)
    
    # Apply source reputation bonuses
    reputation_bonus = 0
    trusted_sources_found = []
    
    for evidence in evidence_list:
        url = evidence.get('url', '')
        source_name = get_source_reputation(url)
        if source_name:
            reputation_bonus += 20
            trusted_sources_found.append(source_name)
    
    # Cap reputation bonus at +40
    reputation_bonus = min(reputation_bonus, 40)
    
    # Calculate final score (normalize to 0-100)
    final_score = 50 + mean_score + reputation_bonus
    final_score = int(np.clip(final_score, 0, 100))
    
    # Determine verdict
    if final_score >= 70:
        verdict = "Likely True"
    elif final_score >= 40:
        verdict = "Not Enough Information"
    else:
        verdict = "Likely False"
    
    # Generate explanation
    support_count = sum(1 for r in verification_results if r['stance'] == 'SUPPORT')
    refute_count = sum(1 for r in verification_results if r['stance'] == 'REFUTE')
    neutral_count = sum(1 for r in verification_results if r['stance'] == 'NEUTRAL')
    
    explanation = _generate_explanation(
        verdict, 
        support_count, 
        refute_count, 
        neutral_count,
        trusted_sources_found,
        len(evidence_list)
    )
    
    # Format sources for response
    sources = []
    seen_urls = set()
    for evidence in evidence_list[:5]:  # Top 5 sources
        url = evidence.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                'title': evidence.get('title', 'Source'),
                'url': url
            })
    
    return {
        'overall_score': final_score,
        'verdict': verdict,
        'explanation': explanation,
        'sources': sources
    }


def _generate_explanation(
    verdict: str,
    support_count: int,
    refute_count: int,
    neutral_count: int,
    trusted_sources: List[str],
    total_sources: int
) -> str:
    """
    Generate human-readable explanation
    
    Args:
        verdict: The verdict (Likely True/False/Not Enough Information)
        support_count: Number of supporting evidence
        refute_count: Number of refuting evidence
        neutral_count: Number of neutral evidence
        trusted_sources: List of trusted source names
        total_sources: Total number of sources
        
    Returns:
        Explanation string
    """
    # Build source mention
    if trusted_sources:
        source_names = ', '.join(set(trusted_sources[:3]))
        source_mention = f" including {source_names}"
    else:
        source_mention = ""
    
    # Generate explanation based on verdict
    if verdict == "Likely True":
        if support_count > refute_count:
            return (
                f"Claim is supported by {support_count} independent source"
                f"{'s' if support_count != 1 else ''}{source_mention}. "
                f"Evidence strongly corroborates the main assertions."
            )
        else:
            return (
                f"Analysis of {total_sources} sources{source_mention} "
                f"indicates the claim is likely accurate based on available evidence."
            )
    
    elif verdict == "Likely False":
        if refute_count > support_count:
            return (
                f"Claim is contradicted by {refute_count} authoritative source"
                f"{'s' if refute_count != 1 else ''}{source_mention}. "
                f"Evidence indicates potential misinformation."
            )
        else:
            return (
                f"Analysis of {total_sources} sources{source_mention} "
                f"suggests the claim is likely inaccurate or misleading."
            )
    
    else:  # Not Enough Information
        if neutral_count > (support_count + refute_count):
            return (
                f"Insufficient evidence to verify claim. "
                f"Reviewed {total_sources} sources{source_mention} but found no clear consensus."
            )
        elif support_count == refute_count:
            return (
                f"Mixed evidence found with {support_count} supporting and {refute_count} "
                f"contradicting sources{source_mention}. Additional verification recommended."
            )
        else:
            return (
                f"Available evidence from {total_sources} sources{source_mention} "
                f"is inconclusive. Further investigation needed for confident assessment."
            )