"""
ATOM Audio AI Service
Advanced speech recognition, audio analysis, and multimodal integration
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
import base64
import wave
import io
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from loguru import logger
import librosa
import soundfile as sf

# Audio AI Models
try:
    import torch
    import torchaudio
    from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
    import whisper
    import speech_recognition as sr
except ImportError:
    torch = None
    torchaudio = None
    Wav2Vec2Processor = Wav2Vec2ForCTC = None
    whisper = None
    sr = None

# OpenAI Audio Models
try:
    import openai
    from openai import OpenAI
except ImportError:
    openai = None
    OpenAI = None

# Google Speech-to-Text
try:
    from google.cloud import speech
    from google.cloud.speech import types
except ImportError:
    speech = None
    types = None

# AWS Transcribe
try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = None

# Existing Services
from advanced_ai_models_service import create_advanced_ai_models_service, AIModelType

class AudioTask(Enum):
    """Audio AI task types"""
    SPEECH_RECOGNITION = "speech_recognition"
    SPEAKER_IDENTIFICATION = "speaker_identification"
    AUDIO_CLASSIFICATION = "audio_classification"
    AUDIO_ANALYSIS = "audio_analysis"
    EMOTION_DETECTION = "emotion_detection"
    MUSIC_ANALYSIS = "music_analysis"
    AUDIO_TRANSLATION = "audio_translation"
    MULTIMODAL_ANALYSIS = "multimodal_analysis"

class AudioModel(Enum):
    """Supported audio AI models"""
    OPENAI_WHISPER = "openai_whisper"
    GOOGLE_SPEECH = "google_speech"
    AWS_TRANSCRIBE = "aws_transcribe"
    WHISPER_LOCAL = "whisper_local"
    WAV2VEC2 = "wav2vec2"
    CUSTOM_MODEL = "custom_model"

@dataclass
class AudioRequest:
    """Audio AI request"""
    request_id: str
    task_type: AudioTask
    audio_model: AudioModel
    audio_data: Union[str, bytes, np.ndarray]  # URL, base64, or audio array
    audio_format: Optional[str] = None
    sample_rate: Optional[int] = None
    language: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    options: Dict[str, Any] = None
    priority: int = 5
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.options is None:
            self.options = {}
        if self.context is None:
            self.context = {}

@dataclass
class SpeechSegment:
    """Speech recognition segment"""
    segment_id: str
    start_time: float
    end_time: float
    text: str
    confidence: float
    language: str
    speaker_id: Optional[str]
    emotions: Dict[str, float]
    
    def __post_init__(self):
        if self.emotions is None:
            self.emotions = {}

@dataclass
class AudioClassification:
    """Audio classification result"""
    class_id: str
    class_name: str
    confidence: float
    audio_segment: Optional[Tuple[float, float]]
    features: Dict[str, float]
    
    def __post_init__(self):
        if self.features is None:
            self.features = {}

@dataclass
class AudioAnalysis:
    """Audio analysis results"""
    analysis_id: str
    duration: float
    sample_rate: int
    channels: int
    volume_level: float
    silence_percentage: float
    frequency_content: Dict[str, float]
    temporal_features: Dict[str, float]
    
    def __post_init__(self):
        if self.frequency_content is None:
            self.frequency_content = {}
        if self.temporal_features is None:
            self.temporal_features = {}

@dataclass
class MusicAnalysis:
    """Music analysis results"""
    track_id: str
    tempo: float
    key: str
    mode: str
    time_signature: str
    instruments: List[str]
    genre: str
    valence: float
    energy: float
    danceability: float
    acousticness: float
    
    def __post_init__(self):
        if self.instruments is None:
            self.instruments = []

@dataclass
class AudioResponse:
    """Audio AI response"""
    request_id: str
    task_type: AudioTask
    audio_model: AudioModel
    success: bool
    results: Dict[str, Any]
    processing_time: float
    cost: float
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def __post_init__(self):
        if self.results is None:
            self.results = {}
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class AudioAIService:
    """Enterprise audio AI service with multimodal capabilities"""
    
    def __init__(self):
        # API keys and credentials
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        
        # Audio models
        self.audio_models = {}
        
        # Initialize audio models
        self._initialize_audio_models()
        
        # Existing AI services
        self.advanced_ai = create_advanced_ai_models_service()
        
        # Performance tracking
        self.performance_metrics = {}
        
        logger.info("Audio AI Service initialized")
    
    def _initialize_audio_models(self):
        """Initialize audio AI models"""
        try:
            # Initialize OpenAI Whisper
            if self.openai_api_key and OpenAI:
                openai_client = OpenAI(api_key=self.openai_api_key)
                self.audio_models[AudioModel.OPENAI_WHISPER] = openai_client
                logger.info("OpenAI Whisper model initialized")
            
            # Initialize Google Speech-to-Text
            if self.google_credentials and speech:
                speech_client = speech.SpeechClient.from_service_account_json(self.google_credentials)
                self.audio_models[AudioModel.GOOGLE_SPEECH] = speech_client
                logger.info("Google Speech-to-Text model initialized")
            
            # Initialize AWS Transcribe
            if self.aws_access_key and self.aws_secret_key and boto3:
                transcribe_client = boto3.client(
                    'transcribe',
                    aws_access_key_id=self.aws_access_key,
                    aws_secret_access_key=self.aws_secret_key,
                    region_name=self.aws_region
                )
                self.audio_models[AudioModel.AWS_TRANSCRIBE] = transcribe_client
                logger.info("AWS Transcribe model initialized")
            
            # Initialize Local Whisper
            if whisper:
                whisper_model = whisper.load_model("base")  # Can be "tiny", "base", "small", "medium", "large"
                self.audio_models[AudioModel.WHISPER_LOCAL] = whisper_model
                logger.info("Local Whisper model initialized")
            
            # Initialize Wav2Vec2
            if torch and Wav2Vec2Processor and Wav2Vec2ForCTC:
                try:
                    processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base-960h")
                    model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-base-960h")
                    
                    self.audio_models[AudioModel.WAV2VEC2] = {
                        "processor": processor,
                        "model": model
                    }
                    logger.info("Wav2Vec2 model initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize Wav2Vec2: {e}")
            
            logger.info(f"Initialized {len(self.audio_models)} audio models")
            
        except Exception as e:
            logger.error(f"Failed to initialize audio models: {e}")
    
    async def process_audio_request(self, request: AudioRequest) -> AudioResponse:
        """Process audio AI request"""
        try:
            logger.info(f"Processing audio request {request.request_id} with model {request.audio_model}")
            start_time = datetime.utcnow()
            
            # Validate model availability
            if request.audio_model not in self.audio_models:
                raise ValueError(f"Audio model {request.audio_model} not available")
            
            # Prepare audio data
            audio_data, sample_rate = await self._prepare_audio_data(request.audio_data, request.sample_rate)
            
            # Route to appropriate processor
            if request.audio_model == AudioModel.OPENAI_WHISPER:
                results = await self._process_openai_whisper(request, audio_data, sample_rate)
            elif request.audio_model == AudioModel.GOOGLE_SPEECH:
                results = await self._process_google_speech(request, audio_data, sample_rate)
            elif request.audio_model == AudioModel.AWS_TRANSCRIBE:
                results = await self._process_aws_transcribe(request, audio_data, sample_rate)
            elif request.audio_model == AudioModel.WHISPER_LOCAL:
                results = await self._process_local_whisper(request, audio_data, sample_rate)
            elif request.audio_model == AudioModel.WAV2VEC2:
                results = await self._process_wav2vec2(request, audio_data, sample_rate)
            else:
                raise ValueError(f"Unsupported audio model: {request.audio_model}")
            
            # Calculate processing time and cost
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            cost = self._calculate_audio_cost(request.audio_model, audio_data)
            
            # Update performance metrics
            self._update_performance_metrics(request.audio_model, processing_time, request.success)
            
            response = AudioResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                audio_model=request.audio_model,
                success=True,
                results=results,
                processing_time=processing_time,
                cost=cost,
                metadata={"audio_duration": len(audio_data) / sample_rate if audio_data else 0}
            )
            
            logger.info(f"Completed audio request {request.request_id} in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"Failed to process audio request {request.request_id}: {e}")
            return AudioResponse(
                request_id=request.request_id,
                task_type=request.task_type,
                audio_model=request.audio_model,
                success=False,
                results={"error": str(e)},
                processing_time=0.0,
                cost=0.0,
                metadata={"error": True}
            )
    
    async def _prepare_audio_data(self, audio_data: Union[str, bytes, np.ndarray], 
                                 sample_rate: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """Prepare audio data for processing"""
        try:
            if isinstance(audio_data, str):
                # Handle URL or base64
                if audio_data.startswith(('http://', 'https://')):
                    # Download audio from URL
                    async with aiohttp.ClientSession() as session:
                        async with session.get(audio_data) as response:
                            audio_bytes = await response.read()
                    audio_array, sr = librosa.load(io.BytesIO(audio_bytes), sr=sample_rate)
                else:
                    # Handle base64
                    if audio_data.startswith('data:audio'):
                        # Remove data URL prefix
                        audio_data = audio_data.split(',')[1]
                    audio_bytes = base64.b64decode(audio_data)
                    audio_array, sr = librosa.load(io.BytesIO(audio_bytes), sr=sample_rate)
            elif isinstance(audio_data, np.ndarray):
                # Use numpy array directly
                audio_array = audio_data
                sr = sample_rate or 16000  # Default to 16kHz
            else:
                # Handle bytes
                audio_array, sr = librosa.load(io.BytesIO(audio_data), sr=sample_rate)
            
            return audio_array, sr
            
        except Exception as e:
            logger.error(f"Failed to prepare audio data: {e}")
            raise ValueError(f"Invalid audio data: {e}")
    
    async def _process_openai_whisper(self, request: AudioRequest, 
                                     audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Process audio with OpenAI Whisper API"""
        try:
            client = self.audio_models[AudioModel.OPENAI_WHISPER]
            
            # Save audio to temporary buffer
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, sample_rate, format='wav')
            buffer.seek(0)
            
            # Create file-like object
            audio_file = ('audio.wav', buffer.read(), 'audio/wav')
            
            # Make API call based on task
            if request.task_type == AudioTask.SPEECH_RECOGNITION:
                transcript = client.audio.translations.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    language=request.language or "en"
                )
                
                return {
                    "text": transcript.text,
                    "segments": [
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "confidence": segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.8
                        } for segment in transcript.segments or []
                    ],
                    "language": transcript.language,
                    "duration": transcript.duration,
                    "provider": "openai",
                    "model": "whisper-1"
                }
            elif request.task_type == AudioTask.MULTIMODAL_ANALYSIS:
                # Transcribe and then analyze with GPT
                transcript = client.audio.translations.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
                
                # Analyze text with AI
                analysis_prompt = f"""
                Analyze this transcribed audio content:
                {transcript}
                
                Provide insights on:
                1. Key topics and themes
                2. Emotional tone and sentiment
                3. Speaker characteristics
                4. Important keywords and entities
                5. Overall summary and implications
                """
                
                ai_request = type('AIRequest', (), {
                    'request_id': request.request_id,
                    'model_type': AIModelType.GPT_4_TURBO,
                    'prompt': analysis_prompt,
                    'context': request.context,
                    'priority': 5
                })()
                
                analysis = await self.advanced_ai.process_request(ai_request)
                
                return {
                    "transcript": transcript,
                    "analysis": analysis.response,
                    "provider": "openai",
                    "model": "whisper-1+gpt-4"
                }
            else:
                raise ValueError(f"Task {request.task_type} not supported by OpenAI Whisper")
            
        except Exception as e:
            logger.error(f"OpenAI Whisper processing failed: {e}")
            return {"error": str(e), "provider": "openai"}
    
    async def _process_google_speech(self, request: AudioRequest, 
                                    audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Process audio with Google Speech-to-Text"""
        try:
            client = self.audio_models[AudioModel.GOOGLE_SPEECH]
            
            # Prepare audio content
            audio_content = sf.write(io.BytesIO(), audio_data, sample_rate, format='wav', subtype='PCM_16')
            
            # Create speech recognition config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code=request.language or "en-US",
                enable_automatic_punctuation=True,
                enable_word_confidence=True,
                enable_speaker_diarization=request.task_type == AudioTask.SPEAKER_IDENTIFICATION,
                model="latest_short" if len(audio_data) / sample_rate < 30 else "latest_long"
            )
            
            audio = speech.RecognitionAudio(content=audio_content)
            
            # Process based on task
            if request.task_type == AudioTask.SPEECH_RECOGNITION:
                response = client.recognize(config=config, audio=audio)
                
                results = []
                for result in response.results:
                    alternative = result.alternatives[0]
                    results.append({
                        "text": alternative.transcript,
                        "confidence": alternative.confidence,
                        "word_confidences": [
                            {"word": word.word, "confidence": word.confidence}
                            for word in alternative.words or []
                        ]
                    })
                
                return {
                    "transcripts": results,
                    "provider": "google_speech",
                    "model": "speech-to-text"
                }
            
            elif request.task_type == AudioTask.SPEAKER_IDENTIFICATION:
                response = client.recognize(config=config, audio=audio)
                
                speaker_segments = []
                for result in response.results:
                    for alternative in result.alternatives:
                        if hasattr(alternative, 'words'):
                            for word in alternative.words:
                                if hasattr(word, 'speaker_tag'):
                                    speaker_segments.append({
                                        "text": word.word,
                                        "start_time": word.start_time.total_seconds(),
                                        "end_time": word.end_time.total_seconds(),
                                        "speaker_id": f"speaker_{word.speaker_tag}",
                                        "confidence": word.confidence
                                    })
                
                return {
                    "speaker_segments": speaker_segments,
                    "provider": "google_speech",
                    "model": "speech-to-text"
                }
            
            else:
                raise ValueError(f"Task {request.task_type} not supported by Google Speech")
            
        except Exception as e:
            logger.error(f"Google Speech processing failed: {e}")
            return {"error": str(e), "provider": "google_speech"}
    
    async def _process_local_whisper(self, request: AudioRequest, 
                                  audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Process audio with local Whisper model"""
        try:
            model = self.audio_models[AudioModel.WHISPER_LOCAL]
            
            # Resample if necessary
            if sample_rate != 16000:
                audio_data = librosa.resample(audio_data, orig_sr=sample_rate, target_sr=16000)
                sample_rate = 16000
            
            # Process with Whisper
            result = model.transcribe(
                audio_data,
                language=request.language or "en",
                fp16=torch.cuda.is_available(),
                verbose=False
            )
            
            if request.task_type == AudioTask.SPEECH_RECOGNITION:
                return {
                    "text": result["text"],
                    "segments": [
                        {
                            "start": segment["start"],
                            "end": segment["end"],
                            "text": segment["text"],
                            "confidence": 0.8  # Whisper doesn't provide confidence
                        } for segment in result["segments"]
                    ],
                    "language": result["language"],
                    "provider": "whisper_local",
                    "model": "whisper-base"
                }
            else:
                # For other tasks, transcribe and analyze
                text = result["text"]
                
                # Analyze with AI if needed
                if request.task_type == AudioTask.MULTIMODAL_ANALYSIS:
                    analysis_prompt = f"""
                    Analyze this transcribed audio content:
                    {text}
                    
                    Provide insights on:
                    1. Key topics and themes
                    2. Emotional tone and sentiment
                    3. Important keywords and entities
                    4. Overall summary and implications
                    """
                    
                    ai_request = type('AIRequest', (), {
                        'request_id': request.request_id,
                        'model_type': AIModelType.GPT_4_TURBO,
                        'prompt': analysis_prompt,
                        'context': request.context,
                        'priority': 5
                    })()
                    
                    analysis = await self.advanced_ai.process_request(ai_request)
                    
                    return {
                        "transcript": text,
                        "analysis": analysis.response,
                        "provider": "whisper_local",
                        "model": "whisper-base+gpt-4"
                    }
                
                return {
                    "text": text,
                    "provider": "whisper_local",
                    "model": "whisper-base"
                }
            
        except Exception as e:
            logger.error(f"Local Whisper processing failed: {e}")
            return {"error": str(e), "provider": "whisper_local"}
    
    async def _process_wav2vec2(self, request: AudioRequest, 
                                audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Process audio with Wav2Vec2"""
        try:
            wav2vec_data = self.audio_models[AudioModel.WAV2VEC2]
            processor = wav2vec_data["processor"]
            model = wav2vec_data["model"]
            
            # Prepare input
            input_values = processor(audio_data, sampling_rate=sample_rate, return_tensors="pt").input_values
            
            if torch.cuda.is_available():
                input_values = input_values.cuda()
            
            # Process with model
            with torch.no_grad():
                logits = model(input_values).logits
            
            # Get predictions
            predicted_ids = torch.argmax(logits, dim=-1)
            transcription = processor.decode(predicted_ids[0])
            
            return {
                "text": transcription,
                "confidence": 0.8,  # Wav2Vec2 doesn't provide confidence
                "provider": "wav2vec2",
                "model": "facebook/wav2vec2-base-960h"
            }
            
        except Exception as e:
            logger.error(f"Wav2Vec2 processing failed: {e}")
            return {"error": str(e), "provider": "wav2vec2"}
    
    async def _process_aws_transcribe(self, request: AudioRequest, 
                                    audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Process audio with AWS Transcribe"""
        try:
            client = self.audio_models[AudioModel.AWS_TRANSCRIBE]
            
            # Save audio to temporary file
            temp_file = f"/tmp/{request.request_id}.wav"
            sf.write(temp_file, audio_data, sample_rate)
            
            # Upload to S3 (simplified - in production would use proper S3)
            s3_uri = f"s3://atom-audio-bucket/audio/{request.request_id}.wav"
            
            # Start transcription job
            job_name = f"atom-transcribe-{request.request_id}"
            
            response = client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': s3_uri},
                MediaFormat='wav',
                LanguageCode=request.language or 'en-US',
                Settings={
                    'ShowSpeakerLabels': request.task_type == AudioTask.SPEAKER_IDENTIFICATION,
                    'MaxSpeakerLabels': 10 if request.task_type == AudioTask.SPEAKER_IDENTIFICATION else 0
                }
            )
            
            # Wait for completion (in production would use polling)
            job_status = 'IN_PROGRESS'
            while job_status in ['IN_PROGRESS', 'QUEUED']:
                job_response = client.get_transcription_job(TranscriptionJobName=job_name)
                job_status = job_response['TranscriptionJob']['TranscriptionJobStatus']
                
                if job_status == 'COMPLETED':
                    # Download transcript
                    transcript_uri = job_response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                    async with aiohttp.ClientSession() as session:
                        transcript_response = await session.get(transcript_uri)
                        transcript_data = await transcript_response.json()
                    
                    return {
                        "transcript": transcript_data['results']['transcripts'][0]['transcript'],
                        "speaker_labels": transcript_data['results'].get('speaker_labels', {}).get('segments', []),
                        "provider": "aws_transcribe",
                        "model": "aws-transcribe"
                    }
                elif job_status == 'FAILED':
                    return {"error": "AWS Transcribe job failed", "provider": "aws_transcribe"}
                
                await asyncio.sleep(5)  # Wait before checking again
            
            return {"error": "AWS Transcribe job timed out", "provider": "aws_transcribe"}
            
        except Exception as e:
            logger.error(f"AWS Transcribe processing failed: {e}")
            return {"error": str(e), "provider": "aws_transcribe"}
    
    async def analyze_audio_features(self, audio_data: Union[str, bytes, np.ndarray],
                                  sample_rate: Optional[int] = None) -> AudioAnalysis:
        """Analyze audio features"""
        try:
            # Prepare audio data
            audio_array, sr = await self._prepare_audio_data(audio_data, sample_rate)
            
            # Extract features
            duration = len(audio_array) / sr
            volume_level = np.mean(np.abs(audio_array))
            
            # Temporal features
            rms = librosa.feature.rms(y=audio_array)[0]
            zero_crossing_rate = librosa.feature.zero_crossing_rate(audio_array)[0]
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_array, sr=sr)[0]
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_array, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_array, sr=sr)[0]
            
            # Frequency content
            mfcc = librosa.feature.mfcc(y=audio_array, sr=sr)
            chroma = librosa.feature.chroma_stft(y=audio_array, sr=sr)
            
            # Calculate silence percentage
            silence_threshold = 0.01
            silence_frames = np.sum(rms < silence_threshold)
            silence_percentage = (silence_frames / len(rms)) * 100
            
            analysis = AudioAnalysis(
                analysis_id=str(uuid.uuid4()),
                duration=duration,
                sample_rate=sr,
                channels=1 if len(audio_array.shape) == 1 else audio_array.shape[0],
                volume_level=volume_level,
                silence_percentage=silence_percentage,
                frequency_content={
                    "rms_mean": float(np.mean(rms)),
                    "rms_std": float(np.std(rms)),
                    "spectral_centroid_mean": float(np.mean(spectral_centroid)),
                    "spectral_bandwidth_mean": float(np.mean(spectral_bandwidth)),
                    "spectral_rolloff_mean": float(np.mean(spectral_rolloff))
                },
                temporal_features={
                    "zcr_mean": float(np.mean(zero_crossing_rate)),
                    "zcr_std": float(np.std(zero_crossing_rate)),
                    "mfcc_mean": [float(np.mean(mfcc[i])) for i in range(min(13, mfcc.shape[0]))],
                    "chroma_mean": [float(np.mean(chroma[i])) for i in range(min(12, chroma.shape[0]))]
                }
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Audio feature analysis failed: {e}")
            raise ValueError(f"Audio analysis failed: {e}")
    
    async def classify_audio(self, audio_data: Union[str, bytes, np.ndarray],
                           sample_rate: Optional[int] = None) -> List[AudioClassification]:
        """Classify audio content"""
        try:
            # Prepare audio data
            audio_array, sr = await self._prepare_audio_data(audio_data, sample_rate)
            
            # Extract features for classification
            mfcc = librosa.feature.mfcc(y=audio_array, sr=sr, n_mfcc=20)
            mfcc_scaled = np.mean(mfcc.T, axis=0)
            
            # Simple rule-based classification (in production would use trained model)
            classifications = []
            
            # Classify based on audio characteristics
            if np.mean(np.abs(audio_array)) > 0.1:
                # Likely speech
                classifications.append(AudioClassification(
                    class_id=str(uuid.uuid4()),
                    class_name="speech",
                    confidence=0.8,
                    features={"rms": float(np.mean(np.abs(audio_array)))}
                ))
            
            if np.std(audio_array) > 0.2:
                # Likely music
                classifications.append(AudioClassification(
                    class_id=str(uuid.uuid4()),
                    class_name="music",
                    confidence=0.7,
                    features={"std": float(np.std(audio_array))}
                ))
            
            if len(audio_array) / sr < 1.0:
                # Short audio - sound effect
                classifications.append(AudioClassification(
                    class_id=str(uuid.uuid4()),
                    class_name="sound_effect",
                    confidence=0.6,
                    features={"duration": len(audio_array) / sr}
                ))
            
            return classifications
            
        except Exception as e:
            logger.error(f"Audio classification failed: {e}")
            return []
    
    async def detect_emotions(self, audio_data: Union[str, bytes, np.ndarray],
                            sample_rate: Optional[int] = None) -> Dict[str, float]:
        """Detect emotions in speech"""
        try:
            # Transcribe speech first
            request = AudioRequest(
                request_id=str(uuid.uuid4()),
                task_type=AudioTask.SPEECH_RECOGNITION,
                audio_model=AudioModel.WHISPER_LOCAL,
                audio_data=audio_data,
                sample_rate=sample_rate
            )
            
            response = await self.process_audio_request(request)
            
            if not response.success:
                return {"error": "Failed to transcribe audio"}
            
            # Analyze emotions in transcribed text
            text = response.results.get("text", "")
            
            # Simple emotion detection (in production would use trained model)
            emotions = {
                "joy": 0.0,
                "sadness": 0.0,
                "anger": 0.0,
                "fear": 0.0,
                "surprise": 0.0,
                "neutral": 0.5
            }
            
            # Analyze text for emotion indicators
            joy_words = ["happy", "great", "wonderful", "excellent", "amazing", "love"]
            sadness_words = ["sad", "depressed", "unhappy", "terrible", "awful", "hate"]
            anger_words = ["angry", "mad", "furious", "irritated", "annoyed", "frustrated"]
            fear_words = ["scared", "afraid", "terrified", "worried", "anxious", "nervous"]
            surprise_words = ["surprised", "shocked", "amazed", "astonished", "unexpected"]
            
            text_lower = text.lower()
            
            for word in joy_words:
                if word in text_lower:
                    emotions["joy"] += 0.1
            
            for word in sadness_words:
                if word in text_lower:
                    emotions["sadness"] += 0.1
            
            for word in anger_words:
                if word in text_lower:
                    emotions["anger"] += 0.1
            
            for word in fear_words:
                if word in text_lower:
                    emotions["fear"] += 0.1
            
            for word in surprise_words:
                if word in text_lower:
                    emotions["surprise"] += 0.1
            
            # Normalize emotions
            total = sum(emotions.values())
            if total > 0:
                emotions = {k: v / total for k, v in emotions.items()}
            
            return emotions
            
        except Exception as e:
            logger.error(f"Emotion detection failed: {e}")
            return {"error": str(e)}
    
    async def analyze_music(self, audio_data: Union[str, bytes, np.ndarray],
                          sample_rate: Optional[int] = None) -> MusicAnalysis:
        """Analyze music content"""
        try:
            # Prepare audio data
            audio_array, sr = await self._prepare_audio_data(audio_data, sample_rate)
            
            # Extract music features
            tempo, beats = librosa.beat.beat_track(y=audio_array, sr=sr)
            chroma = librosa.feature.chroma_stft(y=audio_array, sr=sr)
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_array, sr=sr)
            
            # Determine key (simplified)
            chroma_mean = np.mean(chroma, axis=1)
            key_index = np.argmax(chroma_mean)
            keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            key = keys[key_index]
            
            # Determine mode (major/minor)
            major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
            
            major_corr = np.corrcoef(chroma_mean, major_profile)[0, 1]
            minor_corr = np.corrcoef(chroma_mean, minor_profile)[0, 1]
            mode = "major" if major_corr > minor_corr else "minor"
            
            # Estimate genre (simplified)
            if tempo > 120:
                genre = "electronic" if np.mean(spectral_centroids) > 2000 else "rock"
            else:
                genre = "classical" if np.mean(spectral_centroids) < 1500 else "jazz"
            
            # Estimate audio characteristics
            valence = np.mean(chroma_mean) / 10.0  # Simplified
            energy = np.mean(np.abs(audio_array))
            danceability = min(1.0, tempo / 150.0)  # Simplified
            acousticness = 1.0 - min(1.0, energy)  # Simplified
            
            analysis = MusicAnalysis(
                track_id=str(uuid.uuid4()),
                tempo=float(tempo),
                key=key,
                mode=mode,
                time_signature="4/4",  # Default
                instruments=["unknown"],  # Would need instrument recognition model
                genre=genre,
                valence=max(0.0, min(1.0, valence)),
                energy=max(0.0, min(1.0, energy)),
                danceability=max(0.0, min(1.0, danceability)),
                acousticness=max(0.0, min(1.0, acousticness))
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Music analysis failed: {e}")
            raise ValueError(f"Music analysis failed: {e}")
    
    def _calculate_audio_cost(self, model: AudioModel, audio_data: np.ndarray) -> float:
        """Calculate processing cost for audio model"""
        try:
            audio_duration = len(audio_data) / 16000  # Assuming 16kHz
            
            if model == AudioModel.OPENAI_WHISPER:
                # OpenAI Whisper costs per minute
                return audio_duration * 0.006  # $0.006 per minute
            elif model == AudioModel.GOOGLE_SPEECH:
                # Google Speech costs per minute
                return audio_duration * 0.004  # $0.004 per minute
            elif model == AudioModel.AWS_TRANSCRIBE:
                # AWS Transcribe costs per minute
                return audio_duration * 0.024  # $0.024 per minute
            elif model in [AudioModel.WHISPER_LOCAL, AudioModel.WAV2VEC2]:
                # Local models - compute cost
                return audio_duration * 0.0001  # Rough compute cost
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Failed to calculate audio cost: {e}")
            return 0.0
    
    def _update_performance_metrics(self, model: AudioModel, processing_time: float, success: bool):
        """Update performance metrics"""
        if model not in self.performance_metrics:
            self.performance_metrics[model] = {
                "total_requests": 0,
                "successful_requests": 0,
                "total_time": 0.0,
                "average_time": 0.0,
                "success_rate": 0.0
            }
        
        metrics = self.performance_metrics[model]
        metrics["total_requests"] += 1
        
        if success:
            metrics["successful_requests"] += 1
        
        metrics["total_time"] += processing_time
        metrics["average_time"] = metrics["total_time"] / metrics["total_requests"]
        metrics["success_rate"] = metrics["successful_requests"] / metrics["total_requests"]
    
    def get_available_models(self) -> Dict[str, Any]:
        """Get available audio models and their capabilities"""
        models = {}
        
        for model in AudioModel:
            models[model.value] = {
                "available": model in self.audio_models,
                "capabilities": self._get_model_capabilities(model),
                "supported_tasks": self._get_supported_tasks(model)
            }
        
        return {
            "models": models,
            "total_models": len([m for m in AudioModel if m in self.audio_models]),
            "performance_metrics": self.performance_metrics
        }
    
    def _get_model_capabilities(self, model: AudioModel) -> List[str]:
        """Get capabilities for specific model"""
        capabilities_map = {
            AudioModel.OPENAI_WHISPER: ["speech_recognition", "audio_translation", "multimodal_analysis"],
            AudioModel.GOOGLE_SPEECH: ["speech_recognition", "speaker_identification", "punctuation"],
            AudioModel.AWS_TRANSCRIBE: ["speech_recognition", "speaker_identification", "punctuation", "custom_vocabulary"],
            AudioModel.WHISPER_LOCAL: ["speech_recognition", "multilingual", "noise_robust"],
            AudioModel.WAV2VEC2: ["speech_recognition", "low_resource", "fast_processing"]
        }
        
        return capabilities_map.get(model, [])
    
    def _get_supported_tasks(self, model: AudioModel) -> List[str]:
        """Get supported tasks for specific model"""
        task_map = {
            AudioModel.OPENAI_WHISPER: [AudioTask.SPEECH_RECOGNITION, AudioTask.MULTIMODAL_ANALYSIS],
            AudioModel.GOOGLE_SPEECH: [AudioTask.SPEECH_RECOGNITION, AudioTask.SPEAKER_IDENTIFICATION],
            AudioModel.AWS_TRANSCRIBE: [AudioTask.SPEECH_RECOGNITION, AudioTask.SPEAKER_IDENTIFICATION],
            AudioModel.WHISPER_LOCAL: [AudioTask.SPEECH_RECOGNITION, AudioTask.MULTIMODAL_ANALYSIS],
            AudioModel.WAV2VEC2: [AudioTask.SPEECH_RECOGNITION]
        }
        
        return [t.value for t in task_map.get(model, [])]

# Factory function
def create_audio_ai_service() -> AudioAIService:
    """Create audio AI service instance"""
    return AudioAIService()