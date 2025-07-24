import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_sock import Sock
from elevenlabs import set_api_key, generate, stream
from deepgram import DeepgramClient, SpeakOptions
import asyncio

app = Flask(__name__)
sock = Sock(app)

# --- Configuration ---
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
HASURA_GRAPHQL_URL = os.environ.get("HASURA_GRAPHQL_URL", "http://graphql-engine:8080/v1/graphql")
HASURA_ADMIN_SECRET = os.environ.get("HASURA_ADMIN_SECRET")

# --- Encryption/Decryption ---
# This needs to be the same implementation as in the Node.js crypto.ts
# For simplicity, this is a placeholder. A real implementation would use a robust library.
def decrypt(encrypted_secret: str) -> str:
    # In a real app, use a proper crypto library that matches the Node.js implementation
    # This is a placeholder and will not work without a proper implementation.
    return encrypted_secret # Placeholder

# --- GraphQL Client ---
async def execute_graphql_query(query, variables):
    headers = {
        "Content-Type": "application/json",
        "x-hasura-admin-secret": HASURA_ADMIN_SECRET,
    }
    payload = {"query": query, "variables": variables}
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(HASURA_GRAPHQL_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

async def get_user_tts_settings(user_id: str):
    query = """
        query GetUserSettings($userId: String!) {
            user_settings(where: {user_id: {_eq: $userId}, key: {_in: ["tts_provider", "elevenlabs_api_key", "deepgram_api_key"]}}) {
                key
                value
            }
        }
    """
    variables = {"userId": user_id}
    result = await execute_graphql_query(query, variables)
    settings = {item['key']: item['value'] for item in result.get('data', {}).get('user_settings', [])}
    return settings

# --- TTS Provider Implementations ---
async def tts_with_elevenlabs(api_key: str, text: str, output_path: str):
    set_api_key(api_key)
    audio = generate(text=text, voice="Adam", model="eleven_monolingual_v1")
    with open(output_path, 'wb') as f:
        f.write(audio)

async def tts_with_deepgram(api_key: str, text: str, output_path: str):
    deepgram = DeepgramClient(api_key)
    options = SpeakOptions(model="aura-asteria-en")
    response = await deepgram.speak.v("1").save(output_path, {"text": text}, options)
    return response

@app.route('/tts', methods=['POST'])
async def handle_tts():
    data = request.get_json()
    text_to_speak = data.get('text')
    user_id = data.get('userId') # Assuming userId is passed in the request

    if not text_to_speak or not user_id:
        return jsonify({"error": "Missing 'text' or 'userId' in request."}), 400

    try:
        settings = await get_user_tts_settings(user_id)
        provider = settings.get('tts_provider', 'deepgram') # Default to deepgram
        api_key_encrypted = settings.get(f"{provider}_api_key")

        if not api_key_encrypted:
            # Fallback to server-side key if user has not provided one
            if provider == 'deepgram' and DEEPGRAM_API_KEY:
                api_key = DEEPGRAM_API_KEY
            else:
                return jsonify({"error": f"API key for {provider} not configured for user."}), 400
        else:
            api_key = decrypt(api_key_encrypted)

        filename = f"tts_{uuid.uuid4()}.mp3"
        filepath = os.path.join('/tmp', filename)

        if provider == 'elevenlabs':
            await tts_with_elevenlabs(api_key, text_to_speak, filepath)
        elif provider == 'deepgram':
            await tts_with_deepgram(api_key, text_to_speak, filepath)
        else:
            return jsonify({"error": "Unsupported TTS provider."}), 400

        return jsonify({"audio_url": f"/audio/{filename}"})

    except Exception as e:
        app.logger.error(f"Error during TTS processing: {e}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred during TTS: {str(e)}"}), 500

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory('/tmp', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)