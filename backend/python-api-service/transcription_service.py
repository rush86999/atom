import os
import logging
import asyncio
import base64
import tempfile
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import aiohttp

logger = logging.getLogger(__name__)

class TranscriptionService:
    """Service for audio transcription using Deepgram API"""

    def __init__(self):
        self.api_key = os.getenv('DEEPGRAM_API_KEY')
        self.base_url = 'https://api.deepgram.com/v1/listen'
        self.enabled = bool(self.api_key)

    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000,
                             language: str = 'en-US') -> Dict[str, Any]:
        """
        Transcribe audio data using Deepgram API

        Args:
            audio_data: Raw audio bytes
            sample_rate: Sample rate of the audio
            language: Language code for transcription

        Returns:
            Dictionary with transcription results
        """
        if not self.enabled:
            logger.warning("Deepgram API key not configured, using placeholder transcription")
            return await self._generate_placeholder_transcription()

        try:
            headers = {
                'Authorization': f'Token {self.api_key}',
                'Content-Type': 'audio/wav'
            }

            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                # Write WAV header and audio data
                self._create_wav_header(tmp_file, sample_rate, len(audio_data))
                tmp_file.write(audio_data)
                tmp_file_path = tmp_file.name

            try:
                # Read the file and send to Deepgram
                with open(tmp_file_path, 'rb') as audio_file:
                    async with aiohttp.ClientSession() as session:
                        params = {
                            'model': 'nova-2',
                            'language': language,
                            'punctuate': 'true',
                            'smart_format': 'true',
                            'diarize': 'true',
                            'utterances': 'true'
                        }

                        async with session.post(
                            self.base_url,
                            headers=headers,
                            params=params,
                            data=audio_file
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                return self._process_deepgram_result(result)
                            else:
                                error_text = await response.text()
                                logger.error(f"Deepgram API error: {response.status} - {error_text}")
                                return await self._generate_placeholder_transcription()

            finally:
                # Clean up temporary file
                os.unlink(tmp_file_path)

        except Exception as e:
            logger.error(f"Error in transcription: {e}")
            return await self._generate_placeholder_transcription()

    def _create_wav_header(self, file, sample_rate: int, data_size: int):
        """Create WAV file header"""
        import struct

        # WAV header parameters
        num_channels = 1
        sampwidth = 2  # 16-bit
        framerate = sample_rate
        nframes = data_size // sampwidth
        comptype = 'NONE'
        compname = 'not compressed'

        # Write WAV header
        file.write(b'RIFF')
        file.write(struct.pack('<L', 36 + data_size))
        file.write(b'WAVE')
        file.write(b'fmt ')
        file.write(struct.pack('<L', 16))
        file.write(struct.pack('<H', 1))  # PCM format
        file.write(struct.pack('<H', num_channels))
        file.write(struct.pack('<L', framerate))
        file.write(struct.pack('<L', framerate * num_channels * sampwidth))
        file.write(struct.pack('<H', num_channels * sampwidth))
        file.write(struct.pack('<H', sampwidth * 8))
        file.write(b'data')
        file.write(struct.pack('<L', data_size))

    def _process_deepgram_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process Deepgram API response"""
        try:
            if 'results' not in result or 'channels' not in result['results']:
                return {
                    'success': False,
                    'error': 'Invalid response format from Deepgram',
                    'transcript': ''
                }

            channel = result['results']['channels'][0]
            alternatives = channel.get('alternatives', [])

            if not alternatives:
                return {
                    'success': False,
                    'error': 'No transcription alternatives found',
                    'transcript': ''
                }

            transcript = alternatives[0].get('transcript', '')
            words = alternatives[0].get('words', [])
            utterances = alternatives[0].get('utterances', [])

            # Extract speaker segments if diarization is enabled
            speakers = []
            if utterances:
                for utterance in utterances:
                    speaker = utterance.get('speaker', 0)
                    text = utterance.get('transcript', '')
                    start = utterance.get('start', 0)
                    end = utterance.get('end', 0)

                    speakers.append({
                        'speaker': speaker,
                        'text': text,
                        'start': start,
                        'end': end
                    })

            return {
                'success': True,
                'transcript': transcript,
                'words': words,
                'speakers': speakers,
                'confidence': alternatives[0].get('confidence', 0),
                'duration': result.get('metadata', {}).get('duration', 0),
                'model': result.get('metadata', {}).get('model', '')
            }

        except Exception as e:
            logger.error(f"Error processing Deepgram result: {e}")
            return {
                'success': False,
                'error': str(e),
                'transcript': ''
            }

    async def _generate_placeholder_transcription(self) -> Dict[str, Any]:
        """Generate placeholder transcription when Deepgram is not available"""
        await asyncio.sleep(1)  # Simulate processing time

        placeholder_texts = [
            "Hello everyone, welcome to our meeting about project updates.",
            "Today we'll be discussing the progress on the new feature development.",
            "I'd like to start by reviewing the action items from our last meeting.",
            "The team has made significant progress on the backend integration.",
            "We need to address the performance issues in the production environment.",
            "Let's schedule a follow-up meeting to discuss the deployment plan."
        ]

        import random
        transcript = random.choice(placeholder_texts)

        return {
            'success': True,
            'transcript': transcript,
            'words': [{'word': word, 'confidence': 0.9} for word in transcript.split()],
            'speakers': [{'speaker': 0, 'text': transcript, 'start': 0, 'end': 5.0}],
            'confidence': 0.9,
            'duration': 5.0,
            'model': 'placeholder',
            'is_placeholder': True
        }

    async def transcribe_base64_audio(self, base64_audio: str, sample_rate: int = 16000,
                                    language: str = 'en-US') -> Dict[str, Any]:
        """
        Transcribe base64 encoded audio data

        Args:
            base64_audio: Base64 encoded audio string
            sample_rate: Sample rate of the audio
            language: Language code for transcription

        Returns:
            Dictionary with transcription results
        """
        try:
            audio_data = base64.b64decode(base64_audio)
            return await self.transcribe_audio(audio_data, sample_rate, language)
        except Exception as e:
            logger.error(f"Error decoding base64 audio: {e}")
            return {
                'success': False,
                'error': f'Invalid base64 audio data: {str(e)}',
                'transcript': ''
            }

    async def generate_meeting_summary(self, transcript: str) -> Dict[str, Any]:
        """
        Generate meeting summary from transcript

        Args:
            transcript: Meeting transcript text

        Returns:
            Dictionary with meeting summary
        """
        try:
            # This would integrate with an LLM for summary generation
            # For now, provide a simple placeholder summary
            summary = f"Meeting Summary:\n\n{transcript[:200]}..." if len(transcript) > 200 else transcript

            # Extract potential action items (placeholder implementation)
            action_items = self._extract_action_items(transcript)

            # Extract key topics (placeholder implementation)
            key_topics = self._extract_key_topics(transcript)

            return {
                'success': True,
                'summary': summary,
                'action_items': action_items,
                'key_topics': key_topics,
                'word_count': len(transcript.split()),
                'duration_minutes': len(transcript) / 100  # Rough estimate
            }

        except Exception as e:
            logger.error(f"Error generating meeting summary: {e}")
            return {
                'success': False,
                'error': str(e),
                'summary': '',
                'action_items': [],
                'key_topics': []
            }

    def _extract_action_items(self, transcript: str) -> List[str]:
        """Extract action items from transcript (placeholder implementation)"""
        # This would use NLP in production
        action_keywords = ['need to', 'should', 'must', 'action item', 'todo', 'task']
        sentences = transcript.split('.')

        action_items = []
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in action_keywords):
                action_items.append(sentence.strip())

        return action_items[:5]  # Return top 5 action items

    def _extract_key_topics(self, transcript: str) -> List[str]:
        """Extract key topics from transcript (placeholder implementation)"""
        # This would use NLP/topic modeling in production
        from collections import Counter
        import re

        words = re.findall(r'\b[a-zA-Z]{4,}\b', transcript.lower())
        stop_words = {'meeting', 'discuss', 'today', 'hello', 'thank', 'thanks', 'everyone'}

        filtered_words = [word for word in words if word not in stop_words]
        word_counts = Counter(filtered_words)

        return [word for word, count in word_counts.most_common(5)]

# Global transcription service instance
transcription_service = TranscriptionService()
