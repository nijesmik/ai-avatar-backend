# AI Avatar Chat Backend

This repository contains the backend for the **AI Avatar Chat** project. It provides services for speech-to-text (STT), text-to-speech (TTS), and real-time communication using WebRTC.

## Prerequisites

Before running the project, ensure you have the following installed:

- Python 3.13
- Docker (optional, for containerized deployment)
- `pip` (Python package manager)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-avatar-backend
```

### 2. Install Dependencies

#### Using Python Virtual Environment (Recommended)

1. Create a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

#### Using Docker (Optional)

1. Build the Docker image:

   ```bash
   docker build -t ai-avatar-backend .
   ```

2. Run the Docker container:
   ```bash
   docker run -p 8000:8000 --env-file .env ai-avatar-backend
   ```

### 3. Configure Environment Variables

Create a `.env` file in the root directory with the following content:

```env
ALLOWED_ORIGINS=http://localhost:3000

CLOVA_SPEECH_SECRET_KEY=<your-clova-speech-secret-key>

AZURE_SPEECH_KEY=<your-azure-speech-key>
AZURE_SPEECH_REGION=<your-azure-region>
AZURE_SPEECH_ENDPOINT=<your-azure-speech-endpoint>

GEMINI_API_KEY=<your-gemini-api-key>

RNNOISE_PATH="./app/rnnoise/libs/librnnoise.dylib"

GROQ_API_KEY=<your-groq-api-key>
```

Replace `<your-...>` placeholders with your actual API keys and configuration values.

### 4. Run the Application

#### Locally

1. Start the application:

   ```bash
   uvicorn app.main:sio_app --host 0.0.0.0 --port 8000
   ```

2. Access the application at `http://localhost:8000`.

#### Using Docker

1. Run the container (if not already running):

   ```bash
   docker run -p 8000:8000 --env-file .env ai-avatar-backend
   ```

2. Access the application at `http://localhost:8000`.
