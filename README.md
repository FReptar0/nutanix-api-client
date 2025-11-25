# Nutanix API Client

A unified Python CLI application for automating Nutanix purchase order submissions. This tool handles JWT token generation, XML transformation (SOAP envelope wrapping), API communication, and comprehensive error handling with automatic file archiving.

## Features

- **JWT Authentication**: Automatic RS256 token generation with configurable expiration
- **Smart XML Processing**: Detects and adds SOAP envelope only when needed
- **Robust API Communication**: Retry logic, timeout handling, and detailed error reporting
- **Mandatory Archiving**: All processed files automatically archived (success/error paths)
- **Environment-Aware**: Separate UAT and production configurations
- **CLI Interface**: Simple commands for processing, validation, and cleanup
- **Comprehensive Logging**: Environment-specific log levels with file rotation

## Installation

### Prerequisites

- Python 3.7 or higher
- RSA private key for JWT signing (`private_key.pem`)

### Setup

1. **Clone or copy this directory to your deployment location**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application**:
   ```bash
   cp config.example.yaml config.yaml
   ```

4. **Edit `config.yaml`** with your settings:
   - Update `environment` (uat or production)
   - Configure `jwt.private_key_path` to point to your private key
   - Set directory paths for your environment

### Windows Server Deployment

For Windows Server deployment, update paths in `config.yaml` to use Windows format:

```yaml
paths:
  input: C:\nutanix\input
  output: C:\nutanix\output
  archive_success: C:\nutanix\archive\success
  archive_error: C:\nutanix\archive\error

jwt:
  private_key_path: C:\nutanix\keys\private_key.pem
```

## Configuration

### Example Configuration

```yaml
# Select environment: uat or production
environment: uat

# API endpoints
api:
  uat:
    url: https://frontline-uat.nutanix.com/frontline/v1/partner/partnerPos
  production:
    url: https://frontline.nutanix.com/frontline/v1/partner/partnerPos

# JWT authentication
jwt:
  issuer: YOUR_COMPANY_NAME
  customer_id: CUST-XXXXXX
  private_key_path: ../keys/private_key.pem
  token_expiry_minutes: 5

# File paths (use Windows paths for server deployment)
paths:
  input: ./input
  output: ./output
  archive_success: ./archive/success
  archive_error: ./archive/error

# Logging (DEBUG for uat, INFO for production)
logging:
  level:
    uat: DEBUG
    production: INFO
```

## Usage

### Process a Single File

Process an individual XML file:

```bash
python main.py process --input /path/to/order.xml
```

**What happens:**
1. Validates configuration and input file
2. Generates fresh JWT token
3. Transforms XML (adds SOAP envelope if needed)
4. Posts to Nutanix API
5. Saves response to output directory
6. Archives processed file to `archive/success/` (or `archive/error/` on failure)

### Watch Mode (Continuous Processing)

Monitor input directory and automatically process new files:

```bash
python main.py process --watch
```

**Use case**: Start this mode on server startup to continuously process XML files as they arrive from external systems (like Sage ERP).

Press `Ctrl+C` to stop watching.

### Validate Configuration

Test configuration and connectivity without processing files:

```bash
python main.py validate
```

Checks:
- Configuration file is valid
- All required directories exist
- Private key is accessible
- JWT token generation works

### Clean Up Old Archives

Delete archived files older than specified days:

```bash
# Preview what would be deleted
python main.py cleanup --older-than 30 --dry-run

# Actually delete files
python main.py cleanup --older-than 30
```

## Exit Codes

The application returns specific exit codes for automation/scripting:

| Code | Meaning | Description |
|------|---------|-------------|
| 0 | Success | Operation completed successfully |
| 1 | Configuration/Input Error | Invalid config or input file |
| 2 | Authentication Error | JWT generation or API authentication failed |
| 3 | API Error | API returned error response |
| 4 | Network Error | Connection timeout or network failure |

### Example: Calling from External System

```batch
REM Windows batch script example
python C:\nutanix\nutanix-api-client\main.py process --input %1

IF %ERRORLEVEL% EQU 0 (
    ECHO Success
) ELSE IF %ERRORLEVEL% EQU 2 (
    ECHO Authentication failed
    REM Handle auth error
) ELSE (
    ECHO Processing failed with code %ERRORLEVEL%
    REM Handle other errors
)
```

## Directory Structure

```
nutanix-api-client/
├── nutanix_client/              # Main Python package
│   ├── __init__.py              # Package exports and version
│   ├── cli.py                   # CLI commands and main entry point
│   ├── core/                    # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py            # Configuration management
│   │   └── logger.py            # Logging system
│   ├── handlers/                # Business logic handlers
│   │   ├── __init__.py
│   │   ├── jwt_handler.py       # JWT token generation
│   │   ├── xml_transformer.py   # XML/SOAP processing
│   │   └── api_client.py        # API communication
│   └── utils/                   # Utilities
│       ├── __init__.py
│       └── archiver.py          # File archiving and helpers
├── config/                      # Configuration files
│   ├── config.example.yaml      # Template (Windows paths)
│   ├── config.dev.yaml          # Development config
│   └── config.yaml              # Active configuration
├── tests/                       # Test files
│   └── __init__.py
├── examples/                    # Example XML files
│   └── example_raw.xml
├── main.py                      # Entry point script
├── setup.py                     # Package installation
├── requirements.txt             # Dependencies
├── README.md                    # Documentation
└── .gitignore                   # Git exclusions
```

## XML Transformation

### Input XML (without SOAP envelope)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ns1:DistiPODataRq xmlns:ns1="http://www.nutanix.com/schemas/Services/Data/NTNXPartnerPO.xsd">
    <ns1:Header>
        <ns1:SendToPartnerName>NUTANIX INC</ns1:SendToPartnerName>
        ...
    </ns1:Header>
    ...
</ns1:DistiPODataRq>
```

### Output XML (with SOAP envelope)

The transformer automatically wraps the content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:tns="http://www.boomi.com/connector/wss"
    xmlns:ns1="http://www.nutanix.com/schemas/Services/Data/NTNXPartnerPO.xsd">
    <soapenv:Header />
    <soapenv:Body>
        <tns:GetPurchaseOrder>
            <ns1:DistiPODataRq ...>
                ...
            </ns1:DistiPODataRq>
        </tns:GetPurchaseOrder>
    </soapenv:Body>
</soapenv:Envelope>
```

**Note**: If the input XML already has a SOAP envelope, no transformation is applied.

## Troubleshooting

### Configuration Errors

**Error**: `Configuration file not found`
- **Solution**: Copy `config.example.yaml` to `config.yaml` and configure it

**Error**: `Missing required configuration fields`
- **Solution**: Ensure all required fields in `config.yaml` are filled out

### Authentication Errors

**Error**: `Private key file not found`
- **Solution**: Verify `jwt.private_key_path` in config points to correct location

**Error**: `Authentication failed (HTTP 401)`
- **Solution**: Check JWT credentials (issuer, customer_id) in configuration

### API Errors

**Error**: `Connection timeout`
- **Solution**: Check network connectivity and firewall rules

**Error**: `HTTP 400 - Bad request`
- **Solution**: Verify XML format is correct. Check logs for details.

### File Processing

**Error**: `Input file validation failed`
- **Solution**: Ensure file exists and is valid XML

**Error**: `Failed to archive file`
- **Solution**: Check write permissions on archive directories

## Logging

Logs are written to both console and file (`logs/nutanix-api-client.log`).

- **UAT Environment**: DEBUG level (detailed logging)
- **Production Environment**: INFO level (standard logging)

View recent logs:
```bash
tail -f logs/nutanix-api-client.log
```

## Development

### Running Tests

```bash
cd tests
python -m pytest -v
```

### Adding New Features

1. Update relevant module (jwt_handler.py, xml_transformer.py, etc.)
2. Add tests in `tests/` directory
3. Update README with new functionality
4. Test in UAT environment before production

## License

Internal use only - Grupo DICE / Nutanix integration

## Support

For issues or questions, contact the development team.
