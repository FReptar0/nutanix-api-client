"""
JWT token generation module for Nutanix API Client.
Handles RSA-based JWT token creation for API authentication.
"""

import jwt
import datetime
from pathlib import Path
from typing import Dict, Any


class JWTError(Exception):
    """Raised when JWT token generation fails."""
    pass


class JWTHandler:
    """
    Handles JWT token generation for Nutanix API authentication.
    Uses RS256 algorithm with RSA private key.
    """
    
    def __init__(self, private_key_path: str, issuer: str, customer_id: str, 
                 expiry_minutes: int = 5):
        """
        Initialize JWT handler.
        
        Args:
            private_key_path: Path to RSA private key PEM file
            issuer: JWT issuer claim
            customer_id: JWT subject (customer ID)
            expiry_minutes: Token expiration time in minutes
        """
        self.issuer = issuer
        self.customer_id = customer_id
        self.expiry_minutes = expiry_minutes
        self.logger = None
        
        # Load private key
        try:
            with open(private_key_path, 'r') as key_file:
                self.private_key = key_file.read()
        except FileNotFoundError:
            raise JWTError(f"Private key file not found: {private_key_path}")
        except Exception as e:
            raise JWTError(f"Error reading private key: {e}")
    
    def _get_logger(self):
        """Lazy logger initialization."""
        if self.logger is None:
            from nutanix_client.core.logger import get_logger
            self.logger = get_logger()
        return self.logger
    
    def generate_token(self) -> str:
        """
        Generate a new JWT token.
        
        Returns:
            JWT token string
            
        Raises:
            JWTError: If token generation fails
        """
        try:
            now = datetime.datetime.utcnow()
            expiry = now + datetime.timedelta(minutes=self.expiry_minutes)
            
            payload = {
                "iss": self.issuer,
                "sub": self.customer_id,
                "iat": now,
                "exp": expiry
            }
            
            token = jwt.encode(payload, self.private_key, algorithm="RS256")
            
            self._get_logger().info(
                f"Generated JWT token for {self.customer_id} "
                f"(expires in {self.expiry_minutes} minutes)"
            )
            self._get_logger().debug(f"Token payload: iss={self.issuer}, sub={self.customer_id}")
            
            return token
            
        except Exception as e:
            raise JWTError(f"Failed to generate JWT token: {e}")
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if a token is expired.
        
        Args:
            token: JWT token string
            
        Returns:
            True if expired, False otherwise
        """
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp')
            
            if exp_timestamp:
                exp_datetime = datetime.datetime.fromtimestamp(exp_timestamp)
                return datetime.datetime.utcnow() >= exp_datetime
            
            return True  # No expiration means treat as expired
            
        except Exception:
            return True  # If can't decode, treat as expired
