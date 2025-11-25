"""
API client module for Nutanix API Client.
Handles HTTP communication with the Nutanix API.
"""

import time
from pathlib import Path
from typing import Dict, Optional
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError


class APIError(Exception):
    """Raised when API communication fails."""
    pass


class APIClient:
    """
    Handles communication with the Nutanix API.
    Manages HTTP requests, retries, and response handling.
    """
    
    def __init__(self, api_url: str, timeout: int = 30, 
                 max_retries: int = 3, retry_delay: int = 5):
        """
        Initialize API client.
        
        Args:
            api_url: Base URL for the API endpoint
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = None
    
    def _get_logger(self):
        """Lazy logger initialization."""
        if self.logger is None:
            from nutanix_client.core.logger import get_logger
            self.logger = get_logger()
        return self.logger
    
    def post_purchase_order(self, jwt_token: str, xml_content: str) -> str:
        """
        Post a purchase order to the Nutanix API.
        
        Args:
            jwt_token: JWT authentication token
            xml_content: XML content to send (SOAP-wrapped)
            
        Returns:
            API response XML as string
            
        Raises:
            APIError: If API request fails
        """
        headers = {
            'Content-Type': 'text/xml',
            'x-frontline-jwt': jwt_token,
            'SOAPAction': 'GetPurchaseOrder'
        }
        
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            attempt += 1
            
            try:
                self._get_logger().info(
                    f"Sending request to {self.api_url} (attempt {attempt}/{self.max_retries})"
                )
                self._get_logger().debug(f"Request headers: {headers}")
                
                response = requests.post(
                    self.api_url,
                    data=xml_content.encode('utf-8'),
                    headers=headers,
                    timeout=self.timeout
                )
                
                self._get_logger().info(f"Received response: HTTP {response.status_code}")
                
                # Check for HTTP errors
                if response.status_code == 401:
                    raise APIError(
                        "Authentication failed (HTTP 401). "
                        "Check JWT token configuration."
                    )
                elif response.status_code == 403:
                    raise APIError(
                        "Access forbidden (HTTP 403). "
                        "Check customer ID and permissions."
                    )
                elif response.status_code == 400:
                    raise APIError(
                        f"Bad request (HTTP 400). Invalid XML or request format.\n"
                        f"Response: {response.text[:500]}"
                    )
                elif response.status_code >= 500:
                    # Server errors - retry
                    last_error = APIError(
                        f"Server error (HTTP {response.status_code}). "
                        f"Response: {response.text[:200]}"
                    )
                    self._get_logger().warning(f"Server error, will retry: {last_error}")
                    
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        raise last_error
                elif response.status_code != 200:
                    raise APIError(
                        f"Unexpected response (HTTP {response.status_code}): "
                        f"{response.text[:500]}"
                    )
                
                # Success
                self._get_logger().info("Request successful")
                self._get_logger().debug(f"Response length: {len(response.text)} bytes")
                
                return response.text
                
            except Timeout:
                last_error = APIError(
                    f"Request timeout after {self.timeout} seconds"
                )
                self._get_logger().warning(f"Timeout on attempt {attempt}: {last_error}")
                
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise last_error
                    
            except ConnectionError as e:
                last_error = APIError(f"Connection error: {e}")
                self._get_logger().warning(f"Connection error on attempt {attempt}: {e}")
                
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    raise last_error
                    
            except RequestException as e:
                raise APIError(f"HTTP request failed: {e}")
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise APIError("Request failed after all retry attempts")
    
    def save_response(self, response_xml: str, output_path: Path, 
                     po_number: Optional[str] = None) -> Path:
        """
        Save API response to file.
        
        Args:
            response_xml: Response XML content
            output_path: Directory to save response
            po_number: Purchase order number (for filename)
            
        Returns:
            Path to saved file
            
        Raises:
            APIError: If file save fails
        """
        try:
            # Ensure output directory exists
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            if po_number:
                filename = f"response_{po_number}.xml"
            else:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"response_{timestamp}.xml"
            
            output_file = output_path / filename
            
            # Save response
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(response_xml)
            
            self._get_logger().info(f"Saved response to {output_file}")
            return output_file
            
        except Exception as e:
            raise APIError(f"Failed to save response: {e}")
    
    def extract_po_number(self, xml_content: str) -> Optional[str]:
        """
        Extract PO number from XML content for filename generation.
        
        Args:
            xml_content: XML content to parse
            
        Returns:
            PO number if found, None otherwise
        """
        try:
            # Simple regex-based extraction
            import re
            match = re.search(r'<(?:\w+:)?DistiPONumber>([^<]+)</(?:\w+:)?DistiPONumber>', xml_content)
            if match:
                po_number = match.group(1)
                self._get_logger().debug(f"Extracted PO number: {po_number}")
                return po_number
        except Exception as e:
            self._get_logger().warning(f"Could not extract PO number: {e}")
        
        return None
