"""
🎤 Zoom Speech-to-Text Integration
Advanced speech recognition and transcription services for Zoom meetings
"""

import os
import json
import logging
import asyncio
import numpy as np
import librosa
import webrtcvad
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import io
import wave
import struct

import asyncpg
import httpx
import whisper
from openai import AsyncOpenAI
import torch
import torchaudio
import soundfile as sf
from scipy import signal

logger = logging.getLogger(__name__)

class TranscriptionProvider(Enum):
    """Speech-to-text transcription providers"""
    WHISPER = "whisper"
    OPENAI_WHISPER = "openai_whisper"
    GOOGLE_SPEECH = "google_speech"
    AZURE_SPEECH = "azure_speech"
    AWS_TRANSCRIBE = "aws_transcribe"
    DEEPGRAM = "deepgram"
    ASSEMBLYAI = "assemblyai"

class AudioFormat(Enum):
    """Supported audio formats"""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    OGG = "ogg"
    M4A = "m4a"
    WEBM = "webm"

class LanguageCode(Enum):
    """Supported language codes"""
    ENGLISH = "en"
    ENGLISH_US = "en-US"
    ENGLISH_UK = "en-GB"
    SPANISH = "es"
    SPANISH_ES = "es-ES"
    SPANISH_MX = "es-MX"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    PORTUGUESE_BR = "pt-BR"
    CHINESE = "zh"
    CHINESE_CN = "zh-CN"
    JAPANESE = "ja"
    KOREAN = "ko"
    RUSSIAN = "ru"
    ARABIC = "ar"

class SpeechDetectionStatus(Enum):
    """Speech detection status"""
    SPEECH = "speech"
    SILENCE = "silence"
    MUSIC = "music"
    NOISE = "noise"
    UNKNOWN = "unknown"

@dataclass
class TranscriptionSegment:
    """Transcription segment data"""
    segment_id: str
    meeting_id: str
    participant_id: str
    audio_segment_id: str
    start_time: float
    end_time: float
    duration: float
    text: str
    confidence: float
    language: str
    provider: TranscriptionProvider
    model_used: str
    speaker_confidence: float
    emotion_detected: Optional[str]
    keywords: List[str]
    entities: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class AudioSegment:
    """Audio segment data"""
    segment_id: str
    meeting_id: str
    participant_id: str
    start_time: float
    end_time: float
    duration: float
    audio_data: bytes
    audio_format: AudioFormat
    sample_rate: int
    channels: int
    bitrate: int
    file_size: int
    speech_probability: float
    volume_level: float
    silence_percentage: float
    speech_detection_status: SpeechDetectionStatus
    transcription_segments: List[str]  # IDs of transcription segments
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class TranscriptionJob:
    """Transcription job data"""
    job_id: str
    meeting_id: str
    participant_id: str
    audio_segment_ids: List[str]
    provider: TranscriptionProvider
    language: str
    model_config: Dict[str, Any]
    status: str
    progress: float
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    transcription_segments: List[str]
    metadata: Dict[str, Any]
    updated_at: datetime

@dataclass
class SpeakerProfile:
    """Speaker profile for voice recognition"""
    profile_id: str
    participant_id: str
    voiceprint: str
    speech_patterns: Dict[str, Any]
    vocabulary: List[str]
    accent: str
    speech_rate: float
    pitch_variance: float
    language_preferences: List[str]
    accuracy_metrics: Dict[str, float]
    created_at: datetime
    updated_at: datetime

class ZoomSpeechToText:
    """Advanced speech-to-text integration for Zoom meetings"""
    
    def __init__(self, db_pool: asyncpg.Pool, openai_api_key: Optional[str] = None,
                 google_credentials: Optional[str] = None, azure_credentials: Optional[str] = None):
        self.db_pool = db_pool
        self.openai_api_key = openai_api_key
        self.google_credentials = google_credentials
        self.azure_credentials = azure_credentials
        
        # Initialize transcription models
        self.whisper_models: Dict[str, Any] = {}
        self.openai_client = None
        self.google_speech_client = None
        self.azure_speech_client = None
        self.vad = webrtcvad.Vad(2)  # Aggressive VAD mode
        
        # Storage
        self.audio_segments: Dict[str, AudioSegment] = {}
        self.transcription_segments: Dict[str, TranscriptionSegment] = {}
        self.transcription_jobs: Dict[str, TranscriptionJob] = {}
        self.speaker_profiles: Dict[str, SpeakerProfile] = {}
        
        # Processing queues
        self.audio_processing_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.transcription_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.speaker_diarization_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # Configuration
        self.config = {
            'default_provider': TranscriptionProvider.WHISPER,
            'default_language': LanguageCode.ENGLISH,
            'audio_sample_rate': 16000,
            'audio_channels': 1,
            'audio_bit_depth': 16,
            'segment_duration': 30.0,  # seconds
            'silence_threshold': 0.3,  # seconds
            'speech_probability_threshold': 0.7,
            'confidence_threshold': 0.8,
            'max_concurrent_transcriptions': 5,
            'min_segment_length': 2.0,  # seconds
            'max_segment_length': 60.0,  # seconds
            'auto_diarization': True,
            'speaker_identification': True,
            'real_time_processing': True,
            'batch_processing_interval': 5.0,  # seconds
            'retry_attempts': 3,
            'retry_delay': 2.0,
            'cache_enabled': True,
            'cache_ttl_seconds': 3600
        }
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # Performance metrics
        self.metrics = {
            'audio_segments_processed': 0,
            'transcriptions_completed': 0,
            'transcription_jobs_completed': 0,
            'speaker_profiles_created': 0,
            'total_audio_duration': 0.0,
            'average_transcription_time': 0.0,
            'transcription_accuracy': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'error_count': 0,
            'provider_usage': defaultdict(int)
        }
        
        # Initialize providers
        asyncio.create_task(self._init_providers())
    
    async def _init_providers(self) -> None:
        """Initialize speech-to-text providers"""
        try:
            # Initialize OpenAI client
            if self.openai_api_key:
                self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI Whisper client initialized successfully")
            
            # Initialize Whisper models
            self.whisper_models['base'] = whisper.load_model("base")
            self.whisper_models['small'] = whisper.load_model("small")
            self.whisper_models['medium'] = whisper.load_model("medium")
            
            logger.info("Whisper models loaded successfully")
            
            # Initialize Google Speech (if credentials provided)
            # Note: This would require google-cloud-speech package
            if self.google_credentials:
                logger.info("Google Speech client would be initialized here")
                # self.google_speech_client = speech.SpeechClient(credentials=self.google_credentials)
            
            # Initialize Azure Speech (if credentials provided)
            # Note: This would require azure-cognitiveservices-speech package
            if self.azure_credentials:
                logger.info("Azure Speech client would be initialized here")
                # self.azure_speech_client = speechsdk.SpeechRecognizer(...)
            
            logger.info("Speech-to-text providers initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize speech-to-text providers: {e}")
    
    async def start_processing(self) -> None:
        """Start speech-to-text processing"""
        try:
            self.is_running = True
            
            # Start background tasks
            self.background_tasks = [
                asyncio.create_task(self._audio_processor()),
                asyncio.create_task(self._transcription_processor()),
                asyncio.create_task(self._speaker_diarization_processor()),
                asyncio.create_task(self._batch_processor()),
                asyncio.create_task(self._metrics_collector()),
                asyncio.create_task(self._cache_cleanup())
            ]
            
            logger.info("Speech-to-text processing started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start speech-to-text processing: {e}")
            raise
    
    async def stop_processing(self) -> None:
        """Stop speech-to-text processing"""
        try:
            self.is_running = False
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Speech-to-text processing stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop speech-to-text processing: {e}")
    
    async def process_audio_stream(self, meeting_id: str, participant_id: str, 
                                 audio_chunk: bytes, timestamp: datetime,
                                 audio_format: AudioFormat = AudioFormat.WAV) -> Optional[str]:
        """Process audio stream for real-time transcription"""
        try:
            # Create audio segment
            segment = AudioSegment(
                segment_id=f"{meeting_id}_{participant_id}_{int(timestamp.timestamp())}",
                meeting_id=meeting_id,
                participant_id=participant_id,
                start_time=timestamp.timestamp(),
                end_time=timestamp.timestamp() + len(audio_chunk) / (self.config['audio_sample_rate'] * 2),  # Approximate
                duration=len(audio_chunk) / (self.config['audio_sample_rate'] * 2),
                audio_data=audio_chunk,
                audio_format=audio_format,
                sample_rate=self.config['audio_sample_rate'],
                channels=self.config['audio_channels'],
                bitrate=self.config['audio_bit_depth'] * self.config['audio_sample_rate'],
                file_size=len(audio_chunk),
                speech_probability=0.0,
                volume_level=0.0,
                silence_percentage=0.0,
                speech_detection_status=SpeechDetectionStatus.UNKNOWN,
                transcription_segments=[],
                metadata={'processing_mode': 'real_time'},
                created_at=timestamp
            )
            
            # Queue for processing
            await self.audio_processing_queue.put(segment)
            
            return segment.segment_id
            
        except Exception as e:
            logger.error(f"Failed to process audio stream: {e}")
            return None
    
    async def transcribe_audio_file(self, meeting_id: str, participant_id: str,
                                  audio_file_path: str, audio_format: AudioFormat = AudioFormat.WAV,
                                  provider: TranscriptionProvider = None,
                                  language: LanguageCode = None) -> Optional[str]:
        """Transcribe audio file"""
        try:
            # Set defaults
            if provider is None:
                provider = self.config['default_provider']
            if language is None:
                language = self.config['default_language']
            
            # Read audio file
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            # Create audio segment
            timestamp = datetime.now(timezone.utc)
            segment = AudioSegment(
                segment_id=f"{meeting_id}_{participant_id}_{int(timestamp.timestamp())}",
                meeting_id=meeting_id,
                participant_id=participant_id,
                start_time=timestamp.timestamp(),
                end_time=timestamp.timestamp(),  # Will be updated after audio analysis
                duration=0.0,  # Will be calculated
                audio_data=audio_data,
                audio_format=audio_format,
                sample_rate=self.config['audio_sample_rate'],
                channels=self.config['audio_channels'],
                bitrate=self.config['audio_bit_depth'] * self.config['audio_sample_rate'],
                file_size=len(audio_data),
                speech_probability=0.0,
                volume_level=0.0,
                silence_percentage=0.0,
                speech_detection_status=SpeechDetectionStatus.UNKNOWN,
                transcription_segments=[],
                metadata={'processing_mode': 'batch', 'file_path': audio_file_path},
                created_at=timestamp
            )
            
            # Analyze audio duration
            segment.duration = self._calculate_audio_duration(audio_data, audio_format)
            segment.end_time = segment.start_time + segment.duration
            
            # Create transcription job
            job = TranscriptionJob(
                job_id=f"job_{meeting_id}_{participant_id}_{int(timestamp.timestamp())}",
                meeting_id=meeting_id,
                participant_id=participant_id,
                audio_segment_ids=[segment.segment_id],
                provider=provider,
                language=language.value,
                model_config={
                    'provider': provider.value,
                    'language': language.value,
                    'audio_format': audio_format.value
                },
                status='queued',
                progress=0.0,
                started_at=datetime.now(timezone.utc),
                completed_at=None,
                error_message=None,
                transcription_segments=[],
                metadata={'job_type': 'file_transcription'},
                updated_at=datetime.now(timezone.utc)
            )
            
            # Store and queue
            self.audio_segments[segment.segment_id] = segment
            self.transcription_jobs[job.job_id] = job
            
            await self.transcription_queue.put((job, [segment]))
            
            return job.job_id
            
        except Exception as e:
            logger.error(f"Failed to transcribe audio file: {e}")
            return None
    
    async def transcribe_with_provider(self, audio_data: bytes, provider: TranscriptionProvider,
                                    language: LanguageCode = None,
                                    model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe audio using specified provider"""
        try:
            if language is None:
                language = self.config['default_language']
            
            # Route to appropriate provider
            if provider == TranscriptionProvider.WHISPER:
                result = await self._transcribe_with_whisper(audio_data, language, model_config)
            elif provider == TranscriptionProvider.OPENAI_WHISPER:
                result = await self._transcribe_with_openai_whisper(audio_data, language, model_config)
            elif provider == TranscriptionProvider.GOOGLE_SPEECH:
                result = await self._transcribe_with_google_speech(audio_data, language, model_config)
            elif provider == TranscriptionProvider.AZURE_SPEECH:
                result = await self._transcribe_with_azure_speech(audio_data, language, model_config)
            elif provider == TranscriptionProvider.AWS_TRANSCRIBE:
                result = await self._transcribe_with_aws_transcribe(audio_data, language, model_config)
            elif provider == TranscriptionProvider.DEEPGRAM:
                result = await self._transcribe_with_deepgram(audio_data, language, model_config)
            elif provider == TranscriptionProvider.ASSEMBLYAI:
                result = await self._transcribe_with_assemblyai(audio_data, language, model_config)
            else:
                raise ValueError(f"Unsupported transcription provider: {provider}")
            
            # Update provider usage metrics
            self.metrics['provider_usage'][provider.value] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to transcribe with provider {provider}: {e}")
            self.metrics['error_count'] += 1
            return {'error': str(e), 'provider': provider.value}
    
    async def _transcribe_with_whisper(self, audio_data: bytes, language: LanguageCode,
                                     model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using local Whisper model"""
        try:
            # Select model size
            model_size = model_config.get('model_size', 'base') if model_config else 'base'
            
            if model_size not in self.whisper_models:
                model_size = 'base'
            
            model = self.whisper_models[model_size]
            
            # Convert audio to numpy array
            audio_array = self._convert_audio_to_numpy(audio_data)
            
            # Transcribe
            options = {
                'language': language.value if language != LanguageCode.ENGLISH else 'en',
                'task': 'transcribe',
                'fp16': torch.cuda.is_available(),
                'verbose': False
            }
            
            result = model.transcribe(audio_array, **options)
            
            return {
                'text': result['text'],
                'segments': result['segments'],
                'language': result['language'],
                'confidence': result.get('avg_logprob', 0.0),
                'provider': 'whisper',
                'model_size': model_size,
                'processing_time': result.get('time', 0.0)
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with Whisper: {e}")
            return {'error': str(e), 'provider': 'whisper'}
    
    async def _transcribe_with_openai_whisper(self, audio_data: bytes, language: LanguageCode,
                                           model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper API with BYOK"""
        try:
            # Import BYOK system
            try:
                from zoom_speech_byok_system import ProviderType
                from zoom_speech_byok_routes import byok_manager
            except ImportError:
                logger.error("BYOK system not available")
                return {'error': 'BYOK system not available', 'provider': 'openai_whisper'}
            
            if not self.openai_client:
                raise ValueError("OpenAI client not initialized")
            
            # Get API key from BYOK system
            if byok_manager:
                active_key = await byok_manager.get_active_key(
                    ProviderType.OPENAI, 
                    model_config.get('account_id') if model_config else None
                )
                
                if not active_key:
                    return {'error': 'No active OpenAI key found', 'provider': 'openai_whisper'}
                
                # Get decrypted API key
                api_key = await byok_manager.get_decrypted_key(
                    active_key.key_id,
                    'system',
                    '0.0.0.0',
                    'BYOK-System'
                )
                
                if not api_key:
                    return {'error': 'Failed to retrieve OpenAI key', 'provider': 'openai_whisper'}
                
                # Update OpenAI client with new key
                import openai
                self.openai_client = AsyncOpenAI(api_key=api_key)
            
            # Create audio file
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"
            
            request_id = f"req_{secrets.token_urlsafe(16)}"
            start_time = datetime.now(timezone.utc)
            
            # Call OpenAI Whisper API
            response = await self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", audio_file, "audio/wav"),
                language=language.value if language != LanguageCode.ENGLISH else None,
                response_format="verbose_json"
            )
            
            end_time = datetime.now(timezone.utc)
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Calculate cost (OpenAI pricing as of 2024: $0.006 per minute)
            audio_duration = await self._get_audio_duration(audio_data)
            cost_incurred = (audio_duration / 60) * 0.006  # Cost per minute
            
            # Log usage to BYOK system
            if byok_manager and active_key:
                await byok_manager.update_key_usage(
                    active_key.key_id,
                    'transcription',
                    audio_duration,
                    cost_incurred,
                    request_id,
                    None,  # meeting_id
                    None,  # participant_id
                    response_time_ms,
                    True,  # success
                    None,  # error_message
                    'system',  # user_id
                    '0.0.0.0',  # ip_address
                    'BYOK-System',  # user_agent
                    {'model': 'whisper-1', 'provider': 'openai'}
                )
            
            return {
                'text': response.text,
                'segments': response.segments,
                'language': response.language,
                'confidence': getattr(response, 'confidence', 0.0),
                'provider': 'openai_whisper',
                'model': 'whisper-1',
                'processing_time': getattr(response, 'processing_time', 0.0),
                'cost_usd': cost_incurred,
                'audio_duration_seconds': audio_duration,
                'request_id': request_id,
                'byok_key_id': active_key.key_id if active_key else None
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with OpenAI Whisper: {e}")
            
            # Log error to BYOK system
            try:
                from zoom_speech_byok_system import ProviderType
                from zoom_speech_byok_routes import byok_manager
                
                if byok_manager and active_key:
                    await byok_manager.update_key_usage(
                        active_key.key_id,
                        'transcription',
                        0,  # audio_duration
                        0,  # cost_incurred
                        request_id,
                        None,  # meeting_id
                        None,  # participant_id
                        0,  # response_time_ms
                        False,  # success
                        str(e),  # error_message
                        'system',  # user_id
                        '0.0.0.0',  # ip_address
                        'BYOK-System',  # user_agent
                        {'error': str(e), 'provider': 'openai'}
                    )
            except:
                pass  # Don't let BYOK logging errors break the main flow
            
            return {'error': str(e), 'provider': 'openai_whisper'}
    
    async def _get_audio_duration(self, audio_data: bytes) -> float:
        """Get audio duration in seconds"""
        try:
            import soundfile as sf
            with sf.BytesIO(audio_data) as f:
                info = sf.info(f)
                return info.duration
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0
    
    async def _transcribe_with_google_speech(self, audio_data: bytes, language: LanguageCode,
                                          model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using Google Speech-to-Text API"""
        try:
            # This would be implemented with google-cloud-speech
            # For now, return placeholder
            return {
                'text': 'Google Speech transcription placeholder',
                'segments': [],
                'language': language.value,
                'confidence': 0.95,
                'provider': 'google_speech',
                'model': 'latest',
                'processing_time': 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with Google Speech: {e}")
            return {'error': str(e), 'provider': 'google_speech'}
    
    async def _transcribe_with_azure_speech(self, audio_data: bytes, language: LanguageCode,
                                         model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using Azure Speech Services"""
        try:
            # This would be implemented with azure-cognitiveservices-speech
            # For now, return placeholder
            return {
                'text': 'Azure Speech transcription placeholder',
                'segments': [],
                'language': language.value,
                'confidence': 0.93,
                'provider': 'azure_speech',
                'model': 'latest',
                'processing_time': 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with Azure Speech: {e}")
            return {'error': str(e), 'provider': 'azure_speech'}
    
    async def _transcribe_with_aws_transcribe(self, audio_data: bytes, language: LanguageCode,
                                           model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using AWS Transcribe"""
        try:
            # This would be implemented with boto3 AWS Transcribe
            # For now, return placeholder
            return {
                'text': 'AWS Transcribe transcription placeholder',
                'segments': [],
                'language': language.value,
                'confidence': 0.91,
                'provider': 'aws_transcribe',
                'model': 'latest',
                'processing_time': 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with AWS Transcribe: {e}")
            return {'error': str(e), 'provider': 'aws_transcribe'}
    
    async def _transcribe_with_deepgram(self, audio_data: bytes, language: LanguageCode,
                                      model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using Deepgram API"""
        try:
            # This would be implemented with deepgram Python SDK
            # For now, return placeholder
            return {
                'text': 'Deepgram transcription placeholder',
                'segments': [],
                'language': language.value,
                'confidence': 0.97,
                'provider': 'deepgram',
                'model': 'latest',
                'processing_time': 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with Deepgram: {e}")
            return {'error': str(e), 'provider': 'deepgram'}
    
    async def _transcribe_with_assemblyai(self, audio_data: bytes, language: LanguageCode,
                                        model_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transcribe using AssemblyAI API"""
        try:
            # This would be implemented with assemblyai Python SDK
            # For now, return placeholder
            return {
                'text': 'AssemblyAI transcription placeholder',
                'segments': [],
                'language': language.value,
                'confidence': 0.94,
                'provider': 'assemblyai',
                'model': 'latest',
                'processing_time': 0.0
            }
            
        except Exception as e:
            logger.error(f"Failed to transcribe with AssemblyAI: {e}")
            return {'error': str(e), 'provider': 'assemblyai'}
    
    # Background Processing Tasks
    async def _audio_processor(self) -> None:
        """Process audio segments"""
        while self.is_running:
            try:
                # Get audio segment
                segment = await asyncio.wait_for(
                    self.audio_processing_queue.get(),
                    timeout=1.0
                )
                
                # Analyze audio
                analyzed_segment = await self._analyze_audio(segment)
                
                # Store updated segment
                self.audio_segments[segment.segment_id] = analyzed_segment
                
                # Queue for transcription if speech detected
                if (analyzed_segment.speech_probability > self.config['speech_probability_threshold'] and
                    analyzed_segment.duration >= self.config['min_segment_length']):
                    await self.transcription_queue.put((None, [analyzed_segment]))
                
                # Update metrics
                self.metrics['audio_segments_processed'] += 1
                self.metrics['total_audio_duration'] += analyzed_segment.duration
                
                logger.debug(f"Processed audio segment: {segment.segment_id}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in audio processor: {e}")
                self.metrics['error_count'] += 1
    
    async def _transcription_processor(self) -> None:
        """Process transcription jobs"""
        while self.is_running:
            try:
                # Get transcription job
                job_segments = await asyncio.wait_for(
                    self.transcription_queue.get(),
                    timeout=1.0
                )
                
                if len(job_segments) == 2:
                    job, segments = job_segments
                else:
                    job, segments = None, job_segments
                
                start_time = datetime.now(timezone.utc)
                
                # Process each segment
                for segment in segments:
                    try:
                        # Determine provider and language
                        provider = job.provider if job else self.config['default_provider']
                        language = LanguageCode(job.language) if job else self.config['default_language']
                        
                        # Transcribe
                        transcription_result = await self.transcribe_with_provider(
                            segment.audio_data, provider, language, job.model_config if job else None
                        )
                        
                        if 'error' not in transcription_result:
                            # Create transcription segments
                            transcription_segments = self._create_transcription_segments(
                                segment, transcription_result, provider
                            )
                            
                            # Store segments
                            for trans_segment in transcription_segments:
                                self.transcription_segments[trans_segment.segment_id] = trans_segment
                            
                            # Update audio segment
                            segment.transcription_segments.extend([s.segment_id for s in transcription_segments])
                            self.audio_segments[segment.segment_id] = segment
                            
                        else:
                            logger.error(f"Transcription failed for segment {segment.segment_id}: {transcription_result['error']}")
                            self.metrics['error_count'] += 1
                    
                    except Exception as e:
                        logger.error(f"Error transcribing segment {segment.segment_id}: {e}")
                        self.metrics['error_count'] += 1
                
                # Update job status
                if job:
                    job.progress = 100.0
                    job.status = 'completed'
                    job.completed_at = datetime.now(timezone.utc)
                    job.transcription_segments = [
                        segment_id for segment in segments 
                        for segment_id in segment.transcription_segments
                    ]
                    self.transcription_jobs[job.job_id] = job
                
                # Update metrics
                processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.metrics['transcriptions_completed'] += 1
                self.metrics['average_transcription_time'] = (
                    (self.metrics['average_transcription_time'] * (self.metrics['transcriptions_completed'] - 1) + processing_time) /
                    self.metrics['transcriptions_completed']
                )
                
                logger.debug(f"Completed transcription for job {job.job_id if job else 'direct'}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in transcription processor: {e}")
                self.metrics['error_count'] += 1
    
    async def _speaker_diarization_processor(self) -> None:
        """Process speaker diarization"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Process every minute
                
                if not self.config['auto_diarization']:
                    continue
                
                # Get meetings for diarization
                meetings_for_diarization = await self._get_meetings_for_diarization()
                
                for meeting_id in meetings_for_diarization:
                    await self._perform_speaker_diarization(meeting_id)
                
            except Exception as e:
                logger.error(f"Error in speaker diarization processor: {e}")
                self.metrics['error_count'] += 1
    
    async def _batch_processor(self) -> None:
        """Process batch jobs"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config['batch_processing_interval'])
                
                # Process queued batch jobs
                pending_jobs = [job for job in self.transcription_jobs.values() if job.status == 'queued']
                
                for job in pending_jobs:
                    # Get audio segments
                    segments = [self.audio_segments[seg_id] for seg_id in job.audio_segment_ids if seg_id in self.audio_segments]
                    
                    if segments:
                        await self.transcription_queue.put((job, segments))
                
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                self.metrics['error_count'] += 1
    
    async def _metrics_collector(self) -> None:
        """Collect performance metrics"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Collect metrics every minute
                
                # Store metrics in database
                await self._store_transcription_metrics(self.metrics)
                
                logger.info(f"Speech-to-Text Metrics: {self.metrics}")
                
            except Exception as e:
                logger.error(f"Error in metrics collector: {e}")
    
    async def _cache_cleanup(self) -> None:
        """Clean up cache"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Clean up every hour
                
                # Implement cache cleanup logic
                await self._cleanup_transcription_cache()
                
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    # Utility Methods
    def _convert_audio_to_numpy(self, audio_data: bytes) -> np.ndarray:
        """Convert audio data to numpy array"""
        try:
            # Use soundfile to read audio
            audio_array, sample_rate = sf.read(io.BytesIO(audio_data))
            
            # Convert to mono if stereo
            if len(audio_array.shape) > 1:
                audio_array = np.mean(audio_array, axis=1)
            
            # Resample if necessary
            if sample_rate != self.config['audio_sample_rate']:
                audio_array = librosa.resample(
                    audio_array, 
                    orig_sr=sample_rate, 
                    target_sr=self.config['audio_sample_rate']
                )
            
            # Convert to float32
            audio_array = audio_array.astype(np.float32)
            
            return audio_array
            
        except Exception as e:
            logger.error(f"Failed to convert audio to numpy: {e}")
            # Fallback: create empty array
            return np.array([], dtype=np.float32)
    
    def _calculate_audio_duration(self, audio_data: bytes, audio_format: AudioFormat) -> float:
        """Calculate audio duration from data"""
        try:
            # Use soundfile to get duration
            duration = sf.info(io.BytesIO(audio_data)).duration
            return duration
            
        except Exception as e:
            logger.error(f"Failed to calculate audio duration: {e}")
            # Fallback: estimate based on file size
            return len(audio_data) / (self.config['audio_sample_rate'] * 2)  # Approximate
    
    async def _analyze_audio(self, segment: AudioSegment) -> AudioSegment:
        """Analyze audio segment"""
        try:
            # Convert to numpy array
            audio_array = self._convert_audio_to_numpy(segment.audio_data)
            
            if len(audio_array) == 0:
                return segment
            
            # Calculate volume level
            volume_level = np.sqrt(np.mean(audio_array ** 2))
            segment.volume_level = float(volume_level)
            
            # Calculate speech probability using VAD
            audio_int16 = (audio_array * 32767).astype(np.int16)
            
            # Convert audio to 16kHz mono 16-bit PCM
            audio_pcm = b''
            for sample in audio_int16:
                audio_pcm += struct.pack('<h', sample)
            
            try:
                # Split audio into 30ms frames for VAD
                frame_size = int(0.03 * self.config['audio_sample_rate'])
                frames = [audio_pcm[i:i + frame_size * 2] for i in range(0, len(audio_pcm), frame_size * 2)]
                
                speech_frames = 0
                for frame in frames:
                    if len(frame) == frame_size * 2:
                        if self.vad.is_speech(frame, self.config['audio_sample_rate']):
                            speech_frames += 1
                
                segment.speech_probability = speech_frames / len(frames) if frames else 0.0
                
                # Determine speech detection status
                if segment.speech_probability > 0.7:
                    segment.speech_detection_status = SpeechDetectionStatus.SPEECH
                elif segment.speech_probability > 0.3:
                    segment.speech_detection_status = SpeechDetectionStatus.SILENCE
                else:
                    segment.speech_detection_status = SpeechDetectionStatus.NOISE
                
                # Calculate silence percentage
                segment.silence_percentage = 1.0 - segment.speech_probability
                
            except Exception as e:
                logger.error(f"VAD analysis failed: {e}")
                segment.speech_probability = 0.0
                segment.speech_detection_status = SpeechDetectionStatus.UNKNOWN
                segment.silence_percentage = 1.0
            
            return segment
            
        except Exception as e:
            logger.error(f"Failed to analyze audio: {e}")
            return segment
    
    def _create_transcription_segments(self, audio_segment: AudioSegment, 
                                   transcription_result: Dict[str, Any],
                                   provider: TranscriptionProvider) -> List[TranscriptionSegment]:
        """Create transcription segments from result"""
        segments = []
        
        try:
            # Process segments from transcription result
            if 'segments' in transcription_result:
                for i, seg in enumerate(transcription_result['segments']):
                    segment = TranscriptionSegment(
                        segment_id=f"{audio_segment.segment_id}_seg_{i}",
                        meeting_id=audio_segment.meeting_id,
                        participant_id=audio_segment.participant_id,
                        audio_segment_id=audio_segment.segment_id,
                        start_time=seg.get('start', 0.0),
                        end_time=seg.get('end', 0.0),
                        duration=seg.get('end', 0.0) - seg.get('start', 0.0),
                        text=seg.get('text', ''),
                        confidence=seg.get('avg_logprob', transcription_result.get('confidence', 0.0)),
                        language=transcription_result.get('language', 'en'),
                        provider=provider,
                        model_used=transcription_result.get('model', 'unknown'),
                        speaker_confidence=0.8,  # Would be calculated from diarization
                        emotion_detected=None,  # Would be detected separately
                        keywords=[],  # Would be extracted
                        entities=[],  # Would be extracted
                        metadata={
                            'segment_index': i,
                            'provider_confidence': transcription_result.get('confidence', 0.0)
                        },
                        created_at=datetime.now(timezone.utc)
                    )
                    segments.append(segment)
            else:
                # Single segment transcription
                segment = TranscriptionSegment(
                    segment_id=f"{audio_segment.segment_id}_seg_0",
                    meeting_id=audio_segment.meeting_id,
                    participant_id=audio_segment.participant_id,
                    audio_segment_id=audio_segment.segment_id,
                    start_time=audio_segment.start_time,
                    end_time=audio_segment.end_time,
                    duration=audio_segment.duration,
                    text=transcription_result.get('text', ''),
                    confidence=transcription_result.get('confidence', 0.0),
                    language=transcription_result.get('language', 'en'),
                    provider=provider,
                    model_used=transcription_result.get('model', 'unknown'),
                    speaker_confidence=0.8,
                    emotion_detected=None,
                    keywords=[],
                    entities=[],
                    metadata={},
                    created_at=datetime.now(timezone.utc)
                )
                segments.append(segment)
            
            return segments
            
        except Exception as e:
            logger.error(f"Failed to create transcription segments: {e}")
            return []
    
    async def _init_database(self) -> None:
        """Initialize speech-to-text database tables"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create audio segments table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_audio_segments (
                        segment_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        participant_id VARCHAR(255) NOT NULL,
                        start_time NUMERIC(12,6) NOT NULL,
                        end_time NUMERIC(12,6) NOT NULL,
                        duration NUMERIC(8,2) NOT NULL,
                        audio_data BYTEA NOT NULL,
                        audio_format VARCHAR(10) NOT NULL,
                        sample_rate INTEGER NOT NULL,
                        channels INTEGER NOT NULL,
                        bitrate INTEGER,
                        file_size INTEGER NOT NULL,
                        speech_probability NUMERIC(4,3),
                        volume_level NUMERIC(8,6),
                        silence_percentage NUMERIC(4,3),
                        speech_detection_status VARCHAR(20) DEFAULT 'unknown',
                        transcription_segments JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create transcription segments table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_transcription_segments (
                        segment_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        participant_id VARCHAR(255) NOT NULL,
                        audio_segment_id VARCHAR(255) NOT NULL,
                        start_time NUMERIC(12,6) NOT NULL,
                        end_time NUMERIC(12,6) NOT NULL,
                        duration NUMERIC(8,2) NOT NULL,
                        text TEXT NOT NULL,
                        confidence NUMERIC(4,3) NOT NULL,
                        language VARCHAR(10) NOT NULL,
                        provider VARCHAR(50) NOT NULL,
                        model_used VARCHAR(100) NOT NULL,
                        speaker_confidence NUMERIC(4,3),
                        emotion_detected VARCHAR(50),
                        keywords JSONB DEFAULT '[]'::jsonb,
                        entities JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create transcription jobs table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_transcription_jobs (
                        job_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        participant_id VARCHAR(255) NOT NULL,
                        audio_segment_ids JSONB DEFAULT '[]'::jsonb,
                        provider VARCHAR(50) NOT NULL,
                        language VARCHAR(10) NOT NULL,
                        model_config JSONB DEFAULT '{}'::jsonb,
                        status VARCHAR(20) DEFAULT 'queued',
                        progress NUMERIC(5,2) DEFAULT 0.0,
                        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        completed_at TIMESTAMP WITH TIME ZONE,
                        error_message TEXT,
                        transcription_segments JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create speaker profiles table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_speaker_profiles (
                        profile_id VARCHAR(255) PRIMARY KEY,
                        participant_id VARCHAR(255) NOT NULL,
                        voiceprint TEXT,
                        speech_patterns JSONB DEFAULT '{}'::jsonb,
                        vocabulary JSONB DEFAULT '[]'::jsonb,
                        accent VARCHAR(50),
                        speech_rate NUMERIC(6,2),
                        pitch_variance NUMERIC(8,6),
                        language_preferences JSONB DEFAULT '[]'::jsonb,
                        accuracy_metrics JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_audio_segments_meeting ON zoom_audio_segments(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_audio_segments_participant ON zoom_audio_segments(participant_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_audio_segments_created ON zoom_audio_segments(created_at);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_audio_segments_speech_prob ON zoom_audio_segments(speech_probability);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_segments_meeting ON zoom_transcription_segments(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_segments_participant ON zoom_transcription_segments(participant_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_segments_audio ON zoom_transcription_segments(audio_segment_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_segments_created ON zoom_transcription_segments(created_at);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_segments_confidence ON zoom_transcription_segments(confidence);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_segments_text ON zoom_transcription_segments USING gin(to_tsvector('english', text));",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_jobs_meeting ON zoom_transcription_jobs(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_jobs_participant ON zoom_transcription_jobs(participant_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_jobs_status ON zoom_transcription_jobs(status);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_transcription_jobs_created ON zoom_transcription_jobs(started_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_speaker_profiles_participant ON zoom_speaker_profiles(participant_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_speaker_profiles_created ON zoom_speaker_profiles(created_at);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("Speech-to-text database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize speech-to-text database: {e}")
    
    # Public API Methods
    def get_transcription_segments(self, meeting_id: str) -> List[TranscriptionSegment]:
        """Get transcription segments for a meeting"""
        return [
            segment for segment in self.transcription_segments.values()
            if segment.meeting_id == meeting_id
        ]
    
    def get_audio_segments(self, meeting_id: str) -> List[AudioSegment]:
        """Get audio segments for a meeting"""
        return [
            segment for segment in self.audio_segments.values()
            if segment.meeting_id == meeting_id
        ]
    
    def get_transcription_job(self, job_id: str) -> Optional[TranscriptionJob]:
        """Get transcription job by ID"""
        return self.transcription_jobs.get(job_id)
    
    def get_speaker_profile(self, participant_id: str) -> Optional[SpeakerProfile]:
        """Get speaker profile for participant"""
        return next(
            (profile for profile in self.speaker_profiles.values()
             if profile.participant_id == participant_id),
            None
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get speech-to-text metrics"""
        return self.metrics.copy()
    
    async def create_speaker_profile(self, participant_id: str, audio_samples: List[bytes]) -> Optional[str]:
        """Create speaker profile from audio samples"""
        try:
            # This would implement voiceprint extraction
            profile_id = f"profile_{participant_id}_{int(datetime.now(timezone.utc).timestamp())}"
            
            profile = SpeakerProfile(
                profile_id=profile_id,
                participant_id=participant_id,
                voiceprint="voiceprint_placeholder",
                speech_patterns={'patterns': 'analysis_placeholder'},
                vocabulary=[],
                accent='unknown',
                speech_rate=150.0,
                pitch_variance=0.5,
                language_preferences=[self.config['default_language'].value],
                accuracy_metrics={'base_accuracy': 0.85},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Store profile
            self.speaker_profiles[profile_id] = profile
            self.metrics['speaker_profiles_created'] += 1
            
            return profile_id
            
        except Exception as e:
            logger.error(f"Failed to create speaker profile: {e}")
            return None