from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"

def create_jwt_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT token with the provided data.
    
    Args:
        data: Dictionary containing the claims to encode
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token as string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

def decode_jwt_token(token: str) -> Optional[Dict]:
    """
    Decode and verify a JWT token.
    
    Args:
        token: JWT token string to decode
        
    Returns:
        Dictionary containing the decoded claims, or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def verify_token(token: str) -> bool:
    """
    Verify if a JWT token is valid.
    
    Args:
        token: JWT token string to verify
        
    Returns:
        True if token is valid, False otherwise
    """
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False