import logging
from flask import Blueprint, jsonify, request
import json
from datetime import datetime
from typing import Dict, Any, Optional
from transcription_service import transcription_service
from db_utils import execute_insert, execute_query

# Create blueprint
transcription_bp = Blueprint("transcription", __name__, url_prefix="/api/transcription")

logger = logging.getLogger(__name__)


@transcription_bp.route("/transcribe", methods=["POST"])
def transcribe_audio():
    """Transcribe audio data from meeting recording"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data provided"}), 400

        audio_data = data.get("audio_data")
        meeting_id = data.get("meeting_id")
        sample_rate = data.get("sample_rate", 16000)
        language = data.get("language", "en-US")

        if not audio_data:
            return jsonify({"success": False, "error": "audio_data is required"}), 400

        if not meeting_id:
            return jsonify({"success": False, "error": "meeting_id is required"}), 400

        # Transcribe audio
        transcription_result = transcription_service.transcribe_base64_audio(
            audio_data, sample_rate, language
        )

        # Generate meeting summary
        if transcription_result["success"]:
            summary_result = transcription_service.generate_meeting_summary(
                transcription_result["transcript"]
            )

            # Combine results
            result = {
                **transcription_result,
                "summary": summary_result.get("summary", ""),
                "action_items": summary_result.get("action_items", []),
                "key_topics": summary_result.get("key_topics", []),
                "meeting_id": meeting_id,
                "processed_at": datetime.now().isoformat(),
            }

            # Store transcription in database
            _store_transcription(meeting_id, result)

            return jsonify(result)
        else:
            return jsonify(transcription_result), 500

    except Exception as e:
        logger.error(f"Error in transcription endpoint: {e}")
        return jsonify(
            {"success": False, "error": f"Internal server error: {str(e)}"}
        ), 500


@transcription_bp.route("/meetings/<meeting_id>", methods=["GET"])
def get_meeting_transcription(meeting_id):
    """Get transcription for a specific meeting"""
    try:
        # Get transcription from database
        query = """
            SELECT transcript, summary, action_items, key_topics,
                   confidence, duration, model, processed_at, is_placeholder
            FROM meeting_transcriptions
            WHERE meeting_id = %s
            ORDER BY processed_at DESC
            LIMIT 1
        """

        results = execute_query(query, (meeting_id,))

        if not results:
            return jsonify(
                {"success": False, "error": "Transcription not found for this meeting"}
            ), 404

        transcription = results[0]

        return jsonify(
            {
                "success": True,
                "meeting_id": meeting_id,
                "transcript": transcription["transcript"],
                "summary": transcription["summary"],
                "action_items": transcription["action_items"] or [],
                "key_topics": transcription["key_topics"] or [],
                "confidence": transcription["confidence"],
                "duration": transcription["duration"],
                "model": transcription["model"],
                "processed_at": transcription["processed_at"],
                "is_placeholder": transcription["is_placeholder"],
            }
        )

    except Exception as e:
        logger.error(f"Error fetching meeting transcription: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@transcription_bp.route("/meetings/<meeting_id>/summary", methods=["GET"])
def get_meeting_summary(meeting_id):
    """Get only the summary for a specific meeting"""
    try:
        query = """
            SELECT summary, action_items, key_topics, processed_at
            FROM meeting_transcriptions
            WHERE meeting_id = %s
            ORDER BY processed_at DESC
            LIMIT 1
        """

        results = execute_query(query, (meeting_id,))

        if not results:
            return jsonify(
                {"success": False, "error": "Meeting summary not found"}
            ), 404

        summary = results[0]

        return jsonify(
            {
                "success": True,
                "meeting_id": meeting_id,
                "summary": summary["summary"],
                "action_items": summary["action_items"] or [],
                "key_topics": summary["key_topics"] or [],
                "processed_at": summary["processed_at"],
            }
        )

    except Exception as e:
        logger.error(f"Error fetching meeting summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@transcription_bp.route("/health", methods=["GET"])
def transcription_health():
    """Health check for transcription service"""
    try:
        return jsonify(
            {
                "status": "ok",
                "deepgram_configured": transcription_service.enabled,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Transcription health check failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


def _store_transcription(meeting_id: str, transcription_data: Dict[str, Any]):
    """Store transcription in database"""
    try:
        query = """
            INSERT INTO meeting_transcriptions
            (meeting_id, transcript, summary, action_items, key_topics,
             confidence, duration, model, is_placeholder, processed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (meeting_id)
            DO UPDATE SET
                transcript = EXCLUDED.transcript,
                summary = EXCLUDED.summary,
                action_items = EXCLUDED.action_items,
                key_topics = EXCLUDED.key_topics,
                confidence = EXCLUDED.confidence,
                duration = EXCLUDED.duration,
                model = EXCLUDED.model,
                is_placeholder = EXCLUDED.is_placeholder,
                processed_at = EXCLUDED.processed_at
        """

        execute_insert(
            query,
            (
                meeting_id,
                transcription_data.get("transcript", ""),
                transcription_data.get("summary", ""),
                json.dumps(transcription_data.get("action_items", [])),
                json.dumps(transcription_data.get("key_topics", [])),
                transcription_data.get("confidence", 0),
                transcription_data.get("duration", 0),
                transcription_data.get("model", ""),
                transcription_data.get("is_placeholder", False),
                transcription_data.get("processed_at", datetime.now().isoformat()),
            ),
        )

        logger.info(f"Successfully stored transcription for meeting {meeting_id}")

    except Exception as e:
        logger.error(f"Error storing transcription for meeting {meeting_id}: {e}")
        # Don't fail the request if storage fails, just log the error


# Error handlers
@transcription_bp.errorhandler(400)
def bad_request(error):
    return jsonify(
        {"success": False, "error": "Bad request", "message": str(error)}
    ), 400


@transcription_bp.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Not found", "message": str(error)}), 404


@transcription_bp.errorhandler(500)
def internal_error(error):
    return jsonify(
        {"success": False, "error": "Internal server error", "message": str(error)}
    ), 500
