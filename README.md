# Coupon Clipper API

An automated coupon clipping service that uses AI-powered web automation to clip digital coupons from various grocery and retail stores.

## Features

- Dynamic store discovery and analysis
- Automated login and coupon clipping
- No storage of sensitive credentials
- Support for multiple grocery store chains
- REST API with OpenAPI/Swagger documentation
- JWT-based authentication
- Email validation for user accounts

## Prerequisites

- Python 3.11+
- pip
- virtualenv or venv
- AgentQL API Key (get one from [AgentQL Developer Portal](https://agentql.com))

## Installation

1. Clone the repository:
```bash
git clone https://github.com/jakkpotts/unlimited-ammo-coupon-clipper.git
cd unlimited-ammo-coupon-clipper
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

5. Create `.env` file:
```bash
cp .env.example .env
```

6. Update the `.env` file with your configurations:
```env
# Application Settings
APP_NAME=Coupon Clipper API
ENVIRONMENT=development
DEBUG=True

# Security
SECRET_KEY=your-secret-key-here  # Change this to a secure random string
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_URL=sqlite:///./coupon_clipper.db

# AgentQL Configuration
AGENTQL_API_KEY=your_api_key_here
AGENTQL_ENVIRONMENT=production
AGENTQL_TIMEOUT=30000
```

## Running the Application

1. Start the API server:
```bash
uvicorn main:app --reload
```

2. Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
```http
POST /auth/register
```
Register a new user account.

```http
POST /auth/login
```
Login and get access token.

### Store Discovery
```http
POST /coupons/discover-store
```
Discovers and analyzes a store website using just the URL.

Example request:
```json
{
    "url": "https://www.kroger.com",
    "credentials": {
        "email": "user@example.com",
        "password": "your_password"
    }
}
```

### List Stores
```http
GET /coupons/stores
```
Lists all discovered store configurations.

### Clip Coupons
```http
POST /coupons/clip-all
```
Clips all available coupons for a given store.

Example request:
```json
{
    "id": 1,
    "name": "Kroger",
    "base_url": "https://www.kroger.com",
    "login_url": "https://www.kroger.com/signin",
    "credentials": {
        "email": "user@example.com",
        "password": "your_password"
    }
}
```

## Troubleshooting

### Common Issues

1. **Email Validation Error**
   If you encounter an error about email validation, install the email-validator package:
   ```bash
   pip install email-validator
   ```

2. **Database Errors**
   - Ensure SQLite is installed on your system
   - Check if the database file has proper permissions
   - Run database migrations if needed:
     ```bash
     alembic upgrade head
     ```

3. **Authentication Issues**
   - Verify that `SECRET_KEY` is properly set in `.env`
   - Check if the token expiration time is appropriate for your use case
   - Ensure all authentication headers are properly formatted

4. **Store Integration Issues**
   - Verify store credentials are correct
   - Check if store website is accessible
   - Ensure store configuration is properly set up

## Security Notes

- Store credentials are never persisted, only used at runtime
- HTTPS is recommended for production deployments
- API key should be kept secure and never committed to version control
- Adjust CORS settings in production
- Use strong, unique `SECRET_KEY` for JWT token generation
- Implement rate limiting in production

## Development

### Project Structure
```
unlimited-ammo-coupon-clipper/
├── app/
│   ├── api/
│   │   └── endpoints/     # API route handlers
│   ├── core/             # Core configuration
│   ├── db/               # Database models and setup
│   ├── schemas/          # Pydantic models
│   └── services/         # Business logic
├── tests/                # Test suite
├── .env                  # Environment variables
├── .env.example          # Environment template
├── main.py              # Application entry point
└── requirements.txt     # Python dependencies
```

### Running Tests
```bash
pytest
```

### Development Best Practices
- Follow PEP 8 style guide
- Write comprehensive tests
- Document all API endpoints
- Handle errors gracefully
- Use type hints
- Keep dependencies updated

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 