## Sleeping Assistant (Prototype)

Two-thread Python app:
- Thread 1 (Producer): waits for a signal and enqueues random short paragraphs.
- Thread 2 (Consumer): dequeues text, calls ElevenLabs TTS to synthesize WAV, plays it, and signals the producer when the queue drops below a low-water mark.

### Prerequisites
- Python 3.10+
- An ElevenLabs API key and a Voice ID

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

### Notes
- The producer currently generates random placeholder text. Replace with real logic later.
- The consumer only considers an item "consumed" after audio playback completes.
- The consumer triggers the producer when the queue size is less than or equal to the configured low-water mark.
