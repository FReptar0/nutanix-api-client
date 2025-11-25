"""
XML transformation module for Nutanix API Client.
Handles XML validation and SOAP envelope wrapping.
"""

from pathlib import Path
from typing import Union
import xml.etree.ElementTree as ET
from lxml import etree


class XMLTransformError(Exception):
    """Raised when XML transformation fails."""
    pass


class XMLTransformer:
    """
    Handles XML validation and SOAP envelope transformation.
    Detects if XML already has SOAP envelope and wraps it if needed.
    """
    
    # SOAP envelope template
    SOAP_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:tns="http://www.boomi.com/connector/wss"
    xmlns:ns1="http://www.nutanix.com/schemas/Services/Data/NTNXPartnerPO.xsd">
    <soapenv:Header />
    <soapenv:Body>
        <tns:GetPurchaseOrder>
{content}
        </tns:GetPurchaseOrder>
    </soapenv:Body>
</soapenv:Envelope>'''
    
    def __init__(self):
        """Initialize XML transformer."""
        self.logger = None
    
    def _get_logger(self):
        """Lazy logger initialization."""
        if self.logger is None:
            from nutanix_client.core.logger import get_logger
            self.logger = get_logger()
        return self.logger
    
    def transform_file(self, input_path: Union[str, Path]) -> str:
        """
        Transform an XML file, adding SOAP envelope if needed.
        
        Args:
            input_path: Path to input XML file
            
        Returns:
            Transformed XML string
            
        Raises:
            XMLTransformError: If transformation fails
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            self._get_logger().debug(f"Read XML file: {input_path}")
            return self.transform_string(xml_content)
            
        except FileNotFoundError:
            raise XMLTransformError(f"XML file not found: {input_path}")
        except Exception as e:
            raise XMLTransformError(f"Error reading XML file: {e}")
    
    def transform_string(self, xml_content: str) -> str:
        """
        Transform XML string, adding SOAP envelope if needed.
        
        Args:
            xml_content: XML content as string
            
        Returns:
            Transformed XML string
            
        Raises:
            XMLTransformError: If transformation fails
        """
        # Validate XML syntax
        if not self._is_valid_xml(xml_content):
            raise XMLTransformError("Invalid XML syntax")
        
        # Check if already has SOAP envelope
        if self._has_soap_envelope(xml_content):
            self._get_logger().info("XML already has SOAP envelope, no transformation needed")
            return xml_content
        
        # Wrap with SOAP envelope
        self._get_logger().info("Adding SOAP envelope to XML")
        return self._wrap_with_soap(xml_content)
    
    def _is_valid_xml(self, xml_content: str) -> bool:
        """
        Check if string is valid XML.
        
        Args:
            xml_content: XML content to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            etree.fromstring(xml_content.encode('utf-8'))
            return True
        except etree.XMLSyntaxError as e:
            self._get_logger().error(f"XML syntax error: {e}")
            return False
        except Exception as e:
            self._get_logger().error(f"XML validation error: {e}")
            return False
    
    def _has_soap_envelope(self, xml_content: str) -> bool:
        """
        Check if XML already has SOAP envelope.
        
        Args:
            xml_content: XML content to check
            
        Returns:
            True if has SOAP envelope, False otherwise
        """
        try:
            # Check for SOAP envelope indicators
            return (
                'soap:Envelope' in xml_content or
                'soapenv:Envelope' in xml_content or
                'SOAP-ENV:Envelope' in xml_content
            )
        except Exception:
            return False
    
    def _wrap_with_soap(self, xml_content: str) -> str:
        """
        Wrap XML content with SOAP envelope.
        
        Args:
            xml_content: Raw XML content
            
        Returns:
            SOAP-wrapped XML string
            
        Raises:
            XMLTransformError: If wrapping fails
        """
        try:
            # Parse the input XML to extract the content
            root = etree.fromstring(xml_content.encode('utf-8'))
            
            # Check if root is DistiPODataRq
            if 'DistiPODataRq' not in root.tag:
                self._get_logger().warning(
                    f"Root element is '{root.tag}', expected 'DistiPODataRq'. "
                    "Proceeding anyway."
                )
            
            # Convert the element to string with proper indentation
            content_str = etree.tostring(
                root, 
                encoding='unicode', 
                pretty_print=True
            )
            
            # Indent the content for proper formatting inside SOAP body
            indented_content = '\n'.join(
                '            ' + line if line.strip() else line
                for line in content_str.split('\n')
            ).rstrip()
            
            # Insert into SOAP template
            soap_xml = self.SOAP_TEMPLATE.format(content=indented_content)
            
            # Validate the result
            if not self._is_valid_xml(soap_xml):
                raise XMLTransformError("Generated SOAP XML is invalid")
            
            self._get_logger().debug("Successfully wrapped XML with SOAP envelope")
            return soap_xml
            
        except etree.XMLSyntaxError as e:
            raise XMLTransformError(f"XML parsing error: {e}")
        except Exception as e:
            raise XMLTransformError(f"Failed to wrap XML with SOAP envelope: {e}")
    
    def pretty_print(self, xml_content: str) -> str:
        """
        Pretty print XML content.
        
        Args:
            xml_content: XML content to format
            
        Returns:
            Formatted XML string
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
            return etree.tostring(
                root,
                encoding='unicode',
                pretty_print=True,
                xml_declaration=True
            )
        except Exception as e:
            self._get_logger().warning(f"Could not pretty print XML: {e}")
            return xml_content
