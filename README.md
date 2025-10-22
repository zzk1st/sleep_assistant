## Sleeping Assistant (Prototype)
The sleeping assistant is a voice-only agent that help users peacefully fall into sleep while still feeling connected to the world by slowly reading today's world news.

### Technical Architecture
Two-thread Python app:
- Thread 1 (Producer): waits for a signal and enqueues news transcript from the transcript agent.
- Thread 2 (Consumer): dequeues text, calls ElevenLabs TTS to synthesize WAV, plays it, and signals the producer when the queue drops below a low-water mark.

### Prerequisites
- Python 3.10+
- An ElevenLabs API key and a Voice ID
- Reddit usernames and keys (see config.py for more details)
- Google Gemini API Keys

### Setup
1. Create your environment file:
```bash
cp .env.example .env
$EDITOR .env
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
python -m app.main
```