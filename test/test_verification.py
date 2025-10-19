"""
Tests for TruthLens Verification Engine
"""

import pytest
from app.core.claim_extractor import extract_claims
from app.core.evidence_retriever import search_evidence
from app.core.verifier_model import verify_claim
from app.core.scorer import compute_score


@pytest.mark.asyncio
async def test_claim_extraction():
    """Test claim extraction from text"""
    text = """
    The World Health Organization confirmed that COVID-19 vaccines are safe and effective.
    Studies show that vaccines have 95% efficacy against severe disease.
    Millions of people have been vaccinated worldwide.
    """
    
    claims = await extract_claims(text)
    
    assert isinstance(claims, list)
    assert len(claims) > 0
    assert any('WHO' in claim or 'World Health Organization' in claim for claim in claims)


@pytest.mark.asyncio
async def test_evidence_retrieval():
    """Test evidence retrieval for claims"""
    claims = ["COVID-19 vaccines are safe"]
    
    evidence = await search_evidence(claims)
    
    assert isinstance(evidence, list)
    # Evidence may be empty if APIs are not configured
    if evidence:
        assert 'title' in evidence[0]
        assert 'url' in evidence[0]


@pytest.mark.asyncio
async def test_claim_verification():
    """Test NLI model verification"""
    claims = ["Vaccines are safe and effective"]
    evidence = [
        {
            'title': 'WHO Report',
            'url': 'https://who.int/vaccines',
            'extract': 'WHO confirms that vaccines are safe and effective for preventing disease.'
        }
    ]
    
    results = await verify_claim(claims, evidence)
    
    assert isinstance(results, list)
    assert len(results) > 0
    assert 'stance' in results[0]
    assert results[0]['stance'] in ['SUPPORT', 'REFUTE', 'NEUTRAL']


def test_score_computation():
    """Test final score calculation"""
    verification_results = [
        {'claim': 'Test claim', 'stance': 'SUPPORT', 'confidence': 0.9},
        {'claim': 'Test claim', 'stance': 'SUPPORT', 'confidence': 0.8}
    ]
    evidence_list = [
        {'title': 'WHO Report', 'url': 'https://who.int/test'},
        {'title': 'CDC Report', 'url': 'https://cdc.gov/test'}
    ]
    
    result = compute_score(verification_results, evidence_list)
    
    assert isinstance(result, dict)
    assert 'overall_score' in result
    assert 'verdict' in result
    assert 'explanation' in result
    assert 'sources' in result
    assert 0 <= result['overall_score'] <= 100
    assert result['verdict'] in ['Likely True', 'Likely False', 'Not Enough Information']


@pytest.mark.asyncio
async def test_full_verification_pipeline():
    """Test complete end-to-end verification"""
    text = "The WHO confirms that vaccines are safe according to research studies."
    
    # Stage 1: Extract claims
    claims = await extract_claims(text)
    assert len(claims) > 0
    
    # Stage 2: Search evidence (may return empty if APIs not configured)
    evidence = await search_evidence(claims[:1])  # Test with first claim
    
    # Stage 3: Verify (use mock evidence if real evidence not available)
    if not evidence:
        evidence = [{
            'title': 'Mock Evidence',
            'url': 'https://example.com',
            'extract': 'WHO confirms vaccines are safe.'
        }]
    
    verification_results = await verify_claim(claims[:1], evidence)
    assert len(verification_results) > 0
    
    # Stage 4: Score
    result = compute_score(verification_results, evidence)
    assert result['overall_score'] >= 0
    assert len(result['sources']) > 0


@pytest.mark.asyncio
async def test_false_claim_detection():
    """Test that obviously false claims are detected"""
    claims = ["The Earth is flat"]
    evidence = [{
        'title': 'Scientific Consensus',
        'url': 'https://nasa.gov/earth',
        'extract': 'Scientific evidence overwhelmingly confirms Earth is spherical.'
    }]
    
    verification_results = await verify_claim(claims, evidence)
    result = compute_score(verification_results, evidence)
    
    # Should detect refutation
    assert any(r['stance'] == 'REFUTE' for r in verification_results)