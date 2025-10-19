from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, HttpUrl
from typing import List, Optional

from database import get_db
from models import User, Article
from auth import get_current_active_user

router = APIRouter()

# Pydantic schemas
class ArticleVerifyRequest(BaseModel):
    url: HttpUrl
    title: Optional[str] = None
    content: Optional[str] = None

class ArticleResponse(BaseModel):
    id: int
    url: str
    title: Optional[str]
    verification_status: Optional[str]
    verification_score: Optional[int]
    analysis: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

@router.post("/article", response_model=ArticleResponse, status_code=status.HTTP_201_CREATED)
def verify_article(
    article_data: ArticleVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit an article for verification.
    This is a placeholder - you'll integrate actual verification logic here.
    """
    # Create article record
    new_article = Article(
        user_id=current_user.id,
        url=str(article_data.url),
        title=article_data.title,
        content=article_data.content,
        verification_status="pending",
        verification_score=None,
        analysis="Verification in progress..."
    )
    
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    
    # TODO: Add actual verification logic here
    # This could involve:
    # - Scraping the article content
    # - Analyzing claims
    # - Checking against fact-checking databases
    # - Using AI/ML models for verification
    
    return {
        "id": new_article.id,
        "url": new_article.url,
        "title": new_article.title,
        "verification_status": new_article.verification_status,
        "verification_score": new_article.verification_score,
        "analysis": new_article.analysis,
        "created_at": str(new_article.created_at)
    }

@router.get("/articles", response_model=List[ArticleResponse])
def get_user_articles(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """
    Get all articles submitted by the current user.
    """
    articles = db.query(Article).filter(
        Article.user_id == current_user.id
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": article.id,
            "url": article.url,
            "title": article.title,
            "verification_status": article.verification_status,
            "verification_score": article.verification_score,
            "analysis": article.analysis,
            "created_at": str(article.created_at)
        }
        for article in articles
    ]

@router.get("/article/{article_id}", response_model=ArticleResponse)
def get_article(
    article_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific article.
    """
    article = db.query(Article).filter(
        Article.id == article_id,
        Article.user_id == current_user.id
    ).first()
    
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found"
        )
    
    return {
        "id": article.id,
        "url": article.url,
        "title": article.title,
        "verification_status": article.verification_status,
        "verification_score": article.verification_score,
        "analysis": article.analysis,
        "created_at": str(article.created_at)
    }