import os
import logging
from flask import Blueprint, request, jsonify
from .note_handler import search_notes
from .gdrive_handler import search_gdrive
from .dropbox_handler import search_dropbox_route as search_dropbox
from .web_search import search_web

logger = logging.getLogger(__name__)

meeting_prep_bp = Blueprint('meeting_prep_bp', __name__)

@meeting_prep_bp.route('/meeting-prep', methods=['POST'])
def meeting_prep():
    """
    Prepares a meeting briefing document.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    meeting_title = data.get('meeting_title')
    attendees = data.get('attendees', [])

    if not meeting_title:
        return jsonify({"error": "Missing meeting_title"}), 400

    briefing = f"Meeting Briefing: {meeting_title}\n\n"

    # 1. Search for notes related to the meeting title
    briefing += "--- Relevant Notes ---\n"
    try:
        notes = search_notes(meeting_title)
        if notes:
            briefing += notes + "\n"
        else:
            briefing += "No relevant notes found.\n"
    except Exception as e:
        logger.error(f"Error searching notes: {e}")
        briefing += "Error searching notes.\n"

    # 2. Search for documents in Google Drive and Dropbox
    briefing += "\n--- Relevant Documents ---\n"
    try:
        gdrive_docs = search_gdrive(meeting_title)
        if gdrive_docs:
            briefing += "Google Drive:\n" + gdrive_docs + "\n"
        else:
            briefing += "No relevant documents found in Google Drive.\n"
    except Exception as e:
        logger.error(f"Error searching Google Drive: {e}")
        briefing += "Error searching Google Drive.\n"

    try:
        dropbox_docs = search_dropbox(meeting_title)
        if dropbox_docs:
            briefing += "Dropbox:\n" + dropbox_docs + "\n"
        else:
            briefing += "No relevant documents found in Dropbox.\n"
    except Exception as e:
        logger.error(f"Error searching Dropbox: {e}")
        briefing += "Error searching Dropbox.\n"


    # 3. Search the web for information about the attendees
    if attendees:
        briefing += "\n--- Attendee Information ---\n"
        for attendee in attendees:
            briefing += f"\n**{attendee}**\n"
            try:
                # Search for LinkedIn profile
                linkedin_results = search_web(f"{attendee} LinkedIn")
                if linkedin_results:
                    briefing += "LinkedIn:\n" + linkedin_results + "\n"
                else:
                    briefing += "No LinkedIn profile found.\n"

                # Search for recent news
                news_results = search_web(f"{attendee} recent news")
                if news_results:
                    briefing += "Recent News:\n" + news_results + "\n"
                else:
                    briefing += "No recent news found.\n"
            except Exception as e:
                logger.error(f"Error searching for attendee '{attendee}': {e}")
                briefing += f"Error searching for attendee '{attendee}'.\n"

    return jsonify({"briefing": briefing})
