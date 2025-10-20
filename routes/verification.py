
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from core.claim_extractor import extract_claims
from core.evidence_retriever import search_evidence
from core.verifier_model import verify_claim
from core.scorer import compute_score
from auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["verification"])


class VerifyRequest(BaseModel):
    """Request model for verification endpoint"""
    text: str
    url: Optional[str] = None
    title: Optional[str] = None


class Source(BaseModel):
    """Evidence source model"""
    title: str
    url: str


class VerifyResponse(BaseModel):
    """Response model for verification endpoint"""
    overall_score: int
    verdict: str
    explanation: str
    sources: List[Source]


@router.post("/verify", response_model=VerifyResponse)
async def verify_article(
    request: VerifyRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Verify the truthfulness of a text/claim
    
    This endpoint:
    1. Extracts factual claims from the text
    2. Retrieves evidence from trusted sources
    3. Uses NLI model to verify claims against evidence
    4. Computes overall truth score and verdict
    
    Args:
        request: VerifyRequest containing text to verify
        current_user: Authenticated user (from JWT token)
    
    Returns:
        VerifyResponse with score, verdict, explanation, and sources
    
    Raises:
        HTTPException: If text is empty or processing fails
    """
    try:
        # Validate input
        if not request.text or len(request.text.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text must be at least 10 characters long"
            )
        
        logger.info(f"Verification request from user: {current_user.get('username')}")
        
        # Stage 1: Extract claims from text
        claims = await extract_claims(request.text)
        
        if not claims:
            # No verifiable claims found
            return VerifyResponse(
                overall_score=50,
                verdict="Not Enough Information",
                explanation="No verifiable factual claims could be extracted from the text.",
                sources=[]
            )
        
        logger.info(f"Extracted {len(claims)} claims")
        
        # Stage 2: Retrieve evidence for each claim (parallel)
        evidence_results = await search_evidence(claims)
        
        if not evidence_results:
            return VerifyResponse(
                overall_score=50,
                verdict="Not Enough Information",
                explanation="Unable to find sufficient evidence to verify claims.",
                sources=[]
            )
        
        logger.info(f"Retrieved {len(evidence_results)} evidence items")
        
        # Stage 3: Verify each claim against evidence using NLI model
        verification_results = await verify_claim(claims, evidence_results)
        
        logger.info(f"Completed verification for {len(verification_results)} claim-evidence pairs")
        
        # Stage 4: Compute final score and generate response
        result = compute_score(verification_results, evidence_results)
        
        logger.info(f"Final score: {result['overall_score']}, verdict: {result['verdict']}")
        
        return VerifyResponse(**result)
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Verification error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during verification. Please try again."
        )