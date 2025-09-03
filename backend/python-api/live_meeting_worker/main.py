from fastapi import FastAPI, HTTPException
import datetime
from pydantic import BaseModel
import uvicorn
import os
from typing import Optional, List, Dict, Any
import logging
import base64
import io
import tempfile
import json
import sqlite3
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Live Meeting Worker API",
    description="API for processing live meeting audio and transcripts",
    version="1.0.0"
)

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str

class AudioDevice(BaseModel):
    id: str
    name: str
    sample_rate: int
    channels: int

class MeetingTranscript(BaseModel):
    meeting_id: str
    transcript: str
    start_time: str
    end_time: str
    participants: List[str]

class ProcessAudioRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    meeting_id: str
    sample_rate: int = 16000
    channels: int = 1

@app.get("/")
async def root():
    return {"message": "Live Meeting Worker API", "version": "1.0.0"}

@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.datetime.now().isoformat()
    )

@app.get("/list_audio_devices", response_model=List[AudioDevice])
async def list_audio_devices():
    """List available audio devices"""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        host_apis = sd.query_hostapis()

        audio_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:  # Only input devices
                audio_devices.append(
                    AudioDevice(
                        id=str(i),
                        name=f"{device['name']} ({host_apis[device['hostapi']]['name']})",
                        sample_rate=device['default_samplerate'],
                        channels=device['max_input_channels']
                    )
                )

        if not audio_devices:
            # Fallback if no devices found
            audio_devices.append(
                AudioDevice(
                    id="default",
                    name="Default System Audio",
                    sample_rate=16000,
                    channels=1
                )
            )

        return audio_devices

    except ImportError:
        logger.warning("sounddevice not available, using placeholder devices")
        return [
            AudioDevice(
                id="default",
                name="Default Audio Device (sounddevice not installed)",
                sample_rate=16000,
                channels=1
            )
        ]
    except Exception as e:
        logger.error(f"Error listing audio devices: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing audio devices: {str(e)}")

@app.post("/process_audio")
async def process_audio(request: ProcessAudioRequest):
    """Process audio data from live meetings"""
    try:
        logger.info(f"Processing audio for meeting {request.meeting_id}")

        # 1. Decode base64 audio
        import base64
        import wave
        import io
        import tempfile

        try:
            audio_data = base64.b64decode(request.audio_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 audio data: {str(e)}")

        # 2. Perform speech-to-text conversion
        transcript = await transcribe_audio(audio_data, request.sample_rate or 16000)

        # 3. Process the transcript
        processed_transcript = process_transcript(transcript, request.meeting_id)

        # 4. Store results
        storage_result = await store_transcript(processed_transcript, request.meeting_id)

        return {
            "status": "success",
            "meeting_id": request.meeting_id,
            "processing_time": storage_result.get("processing_time", 0),
            "transcript_length": len(transcript),
            "transcript": transcript[:500] + "..." if len(transcript) > 500 else transcript,
            "word_count": len(transcript.split())
        }
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transcripts/{meeting_id}", response_model=MeetingTranscript)
async def get_transcript(meeting_id: str):
    """Get transcript for a specific meeting"""
    try:
        # Query database for stored transcript
        import sqlite3
        import json

        conn = sqlite3.connect('/data/meeting_transcripts.db')
        cursor = conn.cursor()

        cursor.execute(
            "SELECT transcript, start_time, end_time, participants FROM transcripts WHERE meeting_id = ?",
            (meeting_id,)
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            transcript, start_time, end_time, participants_json = result
            participants = json.loads(participants_json) if participants_json else []

            return MeetingTranscript(
                meeting_id=meeting_id,
                transcript=transcript,
                start_time=start_time,
                end_time=end_time,
                participants=participants
            )
        else:
            raise HTTPException(status_code=404, detail=f"Transcript not found for meeting {meeting_id}")

    except Exception as e:
        logger.error(f"Error retrieving transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving transcript: {str(e)}")

@app.post("/transcripts/{meeting_id}")
async def save_transcript(meeting_id: str, transcript: MeetingTranscript):
    """Save transcript for a meeting"""
    try:
        logger.info(f"Saving transcript for meeting {meeting_id}")

        # Save to SQLite database
        import sqlite3
        import json
        import datetime

        try:
            conn = sqlite3.connect('/data/meeting_transcripts.db')
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transcripts (
                    meeting_id TEXT PRIMARY KEY,
                    transcript TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    participants TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Insert or replace transcript
            cursor.execute(
                '''
                INSERT OR REPLACE INTO transcripts
                (meeting_id, transcript, start_time, end_time, participants)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    transcript.meeting_id,
                    transcript.transcript,
                    transcript.start_time,
                    transcript.end_time,
                    json.dumps(transcript.participants) if transcript.participants else '[]'
                )
            )

            conn.commit()
            conn.close()

            return {"status": "success", "meeting_id": meeting_id}

        except Exception as e:
            logger.error(f"Error saving transcript: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error saving transcript: {str(e)}")
    except Exception as e:
        logger.error(f"Error saving transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def transcribe_audio(audio_data: bytes, sample_rate: int = 16000) -> str:
    """Transcribe audio data using speech-to-text service"""
    try:
        # Check if Deepgram API key is available
        deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
        if deepgram_api_key:
            # Use Deepgram for transcription
            import deepgram
            try:
                dg_client = deepgram.Deepgram(deepgram_api_key)

                # Create a temporary file for audio data
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    # Create a simple WAV file header
                    import wave
                    import struct

                    with wave.open(tmp.name, 'wb') as wav_file:
                        wav_file.setnchannels(1)  # Mono
                        wav_file.setsampwidth(2)  # 16-bit
                        wav_file.setframerate(sample_rate)
                        wav_file.writeframes(audio_data)

                    # Read the file back for Deepgram
                    with open(tmp.name, 'rb') as audio_file:
                        source = {'buffer': audio_file.read(), 'mimetype': 'audio/wav'}

                    response = await dg_client.transcription.prerecorded(
                        source,
                        {
                            'smart_format': True,
                            'model': 'nova-2',
                            'punctuate': True,
                            'language': 'en-US'
                        }
                    )

                    transcript = response['results']['channels'][0]['alternatives'][0]['transcript']
                    return transcript

            except Exception as e:
                logger.error(f"Deepgram transcription error: {e}")
                # Fall back to placeholder

        # Placeholder implementation - simulate transcription
        logger.warning("Using placeholder transcription (no Deepgram API key configured)")
        await asyncio.sleep(1)  # Simulate processing time

        # Generate a placeholder transcript
        placeholder_texts = [
            "Hello everyone, welcome to our meeting about project updates.",
            "Today we'll be discussing the progress on the new feature development.",
            "I'd like to start by reviewing the action items from our last meeting.",
            "The team has made significant progress on the backend integration.",
            "We need to address the performance issues in the production environment.",
            "Let's schedule a follow-up meeting to discuss the deployment plan."
        ]

        import random
        return random.choice(placeholder_texts)

    except Exception as e:
        logger.error(f"Error in audio transcription: {e}")
        return "Error: Could not transcribe audio"

def process_transcript(transcript: str, meeting_id: str) -> Dict[str, Any]:
    """Process and enhance the transcript with meeting context"""
    try:
        # Basic transcript processing
        processed = {
            "raw_transcript": transcript,
            "meeting_id": meeting_id,
            "processed_at": datetime.datetime.now().isoformat(),
            "word_count": len(transcript.split()),
            "character_count": len(transcript),
            "sentences": len([s for s in transcript.split('.') if s.strip()]),
            "estimated_duration": len(transcript) / 15  # Rough estimate: 15 chars per second
        }

        # Simple keyword extraction (placeholder)
        keywords = extract_keywords(transcript)
        processed["keywords"] = keywords[:10]  # Top 10 keywords

        # Sentiment analysis (placeholder)
        processed["sentiment"] = analyze_sentiment(transcript)

        return processed

    except Exception as e:
        logger.error(f"Error processing transcript: {e}")
        return {"raw_transcript": transcript, "error": str(e)}

async def store_transcript(processed_transcript: Dict[str, Any], meeting_id: str) -> Dict[str, Any]:
    """Store processed transcript in database"""
    try:
        start_time = datetime.datetime.now()

        # Ensure data directory exists
        os.makedirs('/data', exist_ok=True)

        # Connect to SQLite database
        conn = sqlite3.connect('/data/meeting_transcripts.db')
        cursor = conn.cursor()

        # Create processed_transcripts table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_transcripts (
                meeting_id TEXT PRIMARY KEY,
                raw_transcript TEXT,
                processed_data TEXT,
                word_count INTEGER,
                character_count INTEGER,
                sentences INTEGER,
                estimated_duration REAL,
                keywords TEXT,
                sentiment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Insert or update processed transcript
        cursor.execute(
            '''
            INSERT OR REPLACE INTO processed_transcripts
            (meeting_id, raw_transcript, processed_data, word_count, character_count,
             sentences, estimated_duration, keywords, sentiment, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''',
            (
                meeting_id,
                processed_transcript.get('raw_transcript', ''),
                json.dumps(processed_transcript),
                processed_transcript.get('word_count', 0),
                processed_transcript.get('character_count', 0),
                processed_transcript.get('sentences', 0),
                processed_transcript.get('estimated_duration', 0),
                json.dumps(processed_transcript.get('keywords', [])),
                json.dumps(processed_transcript.get('sentiment', {}))
            )
        )

        conn.commit()
        conn.close()

        processing_time = (datetime.datetime.now() - start_time).total_seconds()

        return {
            "status": "success",
            "meeting_id": meeting_id,
            "processing_time": processing_time,
            "stored_at": datetime.datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error storing transcript: {e}")
        return {
            "status": "error",
            "error": str(e),
            "meeting_id": meeting_id
        }

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text (placeholder implementation)"""
    # Simple keyword extraction - would use NLP library in production
    words = text.lower().split()
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

    # Count word frequencies
    from collections import Counter
    word_counts = Counter(word for word in words if word not in stop_words and len(word) > 3)

    return [word for word, count in word_counts.most_common(max_keywords)]

def analyze_sentiment(text: str) -> Dict[str, float]:
    """Analyze sentiment of text (placeholder implementation)"""
    # Simple sentiment analysis - would use proper NLP in production
    positive_words = {'good', 'great', 'excellent', 'amazing', 'wonderful', 'perfect', 'awesome'}
    negative_words = {'bad', 'terrible', 'awful', 'horrible', 'poor', 'disappointing'}

    words = text.lower().split()
    positive_count = sum(1 for word in words if word in positive_words)
    negative_count = sum(1 for word in words if word in negative_words)
    total_words = len(words)

    if total_words == 0:
        return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}

    positive_score = positive_count / total_words
    negative_score = negative_count / total_words
    neutral_score = 1.0 - positive_score - negative_score

    return {
        "positive": round(positive_score, 3),
        "negative": round(negative_score, 3),
        "neutral": round(neutral_score, 3)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
