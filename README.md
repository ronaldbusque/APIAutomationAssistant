# API Test Automation Assistant

An AI-powered tool that automatically generates comprehensive API test suites from OpenAPI specifications.

## Features

- **Basic Mode:** Generates baseline test cases focusing on endpoint contract validation, HTTP status codes, and JSON schema validation.
- **Advanced Mode:** Extends Basic Mode with user-defined business rules, custom assertions, test data setup, test sequencing, and environment management.
- **Multiple Outputs:** Generate test scripts for different frameworks:
  - Postman Collections (JSON)
  - Playwright Test Scripts (JavaScript/TypeScript)
- **Intelligent Test Generation:** Leverages AI to create meaningful tests that validate API behavior.
- **Real-time Progress Updates:** Stream generation progress via WebSockets.

## Getting Started

### Prerequisites

- Python 3.9+
- Access to AI models (requires API credentials)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/api-automation-assistant.git
   cd api-automation-assistant
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```
   # Create a .env file with your API credentials
   echo "MODEL_PLANNING=gpt-4o" > .env
   echo "MODEL_CODING=gpt-4o" >> .env
   echo "MODEL_TRIAGE=gpt-3.5-turbo" >> .env
   ```

### Running the Application

Start the server:
```
python -m src.main
```

The API will be available at http://localhost:8000

## API Usage

### Generate Tests from OpenAPI Spec

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "input_type": "spec",
    "spec": "openapi: 3.0.0\ninfo:\n  title: Example API\n  version: 1.0.0\npaths:\n  /users:\n    get:\n      summary: Get users\n      responses:\n        \"200\":\n          description: Successful response",
    "mode": "basic",
    "targets": ["postman", "playwright"]
  }'
```

### Check Generation Status

```bash
curl http://localhost:8000/status/{job_id}
```

### Real-time Updates via WebSocket

```javascript
const socket = new WebSocket('ws://localhost:8000/ws/job/{job_id}');
socket.onmessage = (event) => {
  console.log(JSON.parse(event.data));
};
```

## Architecture

The system uses a multi-agent architecture:
- **Triage Agent:** Routes the workflow based on input type
- **Test Planner Agent:** Generates test blueprints from OpenAPI specs
- **Coder Agent:** Generates test scripts from blueprints

## License

[MIT License](LICENSE) 