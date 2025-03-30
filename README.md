# API Automation Assistant

A powerful tool for automating API testing with AI. This application analyzes your OpenAPI specification and automatically generates comprehensive test blueprints and executable test scripts for multiple frameworks.

## Features

- **OpenAPI Spec Analysis**: Upload or paste your OpenAPI specification to get started
- **Autonomous Mode**: AI agents iteratively refine both blueprints and test scripts for maximum quality
- **Multi-Framework Support**: Generate test scripts for Postman and Playwright
- **Interactive UI**: View, edit, and manage test blueprints and scripts
- **Detailed Progress Tracking**: Monitor the generation process in real-time

## Setup

### Prerequisites

- Python 3.10+
- Node.js 16+ and npm (for the UI)
- OpenAI API key

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/APIAutomationAssistant.git
   cd APIAutomationAssistant
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install UI dependencies:
   ```
   cd ui
   npm install
   cd ..
   ```

4. Create an environment file:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```

### Running the Application

1. Start the backend server:
   ```
   python src/main.py
   ```

2. Start the frontend development server:
   ```
   cd ui
   npm run dev
   ```

3. Access the application at http://localhost:5173

## Usage

1. **Input Your API Specification**: Upload, paste, or provide a URL to your OpenAPI specification
2. **Configure Test Generation**: Choose between basic and advanced mode, enable autonomous mode if desired
3. **Review the Generated Blueprint**: Examine and edit the test blueprint if needed
4. **Generate Test Scripts**: Select target frameworks and generate executable test scripts
5. **Download Scripts**: Download individual files or all scripts as a ZIP archive

## Configuration

You can customize the application's behavior by modifying the `.env` file:

- `MODEL_BLUEPRINT_AUTHORING`: The model used for blueprint generation (default: gpt-4o)
- `MODEL_BLUEPRINT_REVIEWING`: The model used for reviewing blueprints (default: gpt-4o)
- `MODEL_SCRIPT_CODING`: The model used for generating test scripts (default: gpt-4o)
- `AUTONOMOUS_MAX_ITERATIONS`: Maximum number of iterations for autonomous mode (default: 3)
- `LOG_LEVEL`: Sets the logging verbosity (default: INFO)

## License

[MIT License](LICENSE) 