import os
from google.cloud import texttospeech
import uuid # Though not strictly needed if using voice names for uniqueness

# --- Configuration ---
TEXT_TO_SYNTHESIZE = "Atom"
OUTPUT_DIR = "audio_samples"  # This directory will be created inside tts_data_generator
TARGET_SAMPLE_RATE_HZ = 16000  # Standard for wake word models like Porcupine

# A diverse list of voices to generate samples.
# Using a mix of US, GB, and AU accents, and both male/female.
# Ensure these voice names are valid as per Google Cloud TTS documentation.
VOICES_TO_USE = [
    "en-US-Wavenet-A",  # Male
    "en-US-Wavenet-B",  # Male
    "en-US-Wavenet-C",  # Female
    "en-US-Wavenet-D",  # Male
    "en-US-Wavenet-E",  # Female
    "en-US-Wavenet-F",  # Female
    "en-GB-Wavenet-A",  # Female (UK)
    "en-GB-Wavenet-B",  # Male (UK)
    "en-GB-Wavenet-C",  # Female (UK)
    "en-GB-Wavenet-D",  # Male (UK)
    "en-AU-Wavenet-A",  # Female (Australia)
    "en-AU-Wavenet-B",  # Male (Australia)
    "en-AU-Wavenet-C",  # Female (Australia)
    "en-AU-Wavenet-D",  # Male (Australia)
    # Adding some Standard voices as well for variety, if Wavenet proves too costly or has limits for bulk generation.
    # "en-US-Standard-A",
    # "en-US-Standard-B",
    # "en-GB-Standard-A",
    # "en-GB-Standard-B",
]

def main():
    """
    Generates audio samples of the TEXT_TO_SYNTHESIZE ("Atom") using various Google Cloud TTS voices.
    """
    print("Google Cloud Text-to-Speech Audio Sample Generator")
    print("--------------------------------------------------")
    print("Important: This script uses Google Cloud services and may incur costs.")
    print("Ensure you have authenticated with Google Cloud:")
    print("1. Run 'gcloud auth application-default login'")
    print("   OR")
    print("2. Set the GOOGLE_APPLICATION_CREDENTIALS environment variable pointing to your service account key JSON file.")
    print("   See: https://cloud.google.com/docs/authentication/provide-credentials-adc")
    print("--------------------------------------------------")

    # Create the output directory if it doesn't exist
    # This script is expected to be run from within the tts_data_generator directory.
    # So, OUTPUT_DIR will be created as tts_data_generator/audio_samples/
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    try:
        # Initialize the TextToSpeechClient
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print(f"Error: Could not initialize TextToSpeechClient: {e}")
        print("Please ensure your Google Cloud authentication is set up correctly.")
        return

    print(f"\nStarting synthesis for the text: '{TEXT_TO_SYNTHESIZE}'")
    print(f"Target sample rate: {TARGET_SAMPLE_RATE_HZ} Hz")
    print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")

    for voice_name in VOICES_TO_USE:
        print(f"\nProcessing voice: {voice_name}...")
        try:
            synthesis_input = texttospeech.SynthesisInput(text=TEXT_TO_SYNTHESIZE)

            # Extract language code from the voice name (e.g., "en-US" from "en-US-Wavenet-A")
            # This assumes standard voice naming convention.
            language_code = "-".join(voice_name.split("-")[:2])

            voice_params = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            )

            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16, # WAV format
                sample_rate_hertz=TARGET_SAMPLE_RATE_HZ,
                # For Wavenet voices, you might specify effects_profile_id for certain use cases,
                # but for wake word generation, clean audio is usually preferred.
                # effects_profile_id=['telephony-class-application']
            )

            print(f"  Requesting synthesis with Language: {language_code}, Voice: {voice_name}")
            response = client.synthesize_speech(
                request={
                    "input": synthesis_input,
                    "voice": voice_params,
                    "audio_config": audio_config,
                }
            )

            # Construct filename (e.g., Atom_en-US-Wavenet-A.wav)
            filename = f"{TEXT_TO_SYNTHESIZE.replace(' ', '_')}_{voice_name}.wav"
            filepath = os.path.join(OUTPUT_DIR, filename)

            # Write the binary audio content to the file
            with open(filepath, "wb") as out_file:
                out_file.write(response.audio_content)
            print(f"  Successfully saved audio to: {filepath}")

        except Exception as e:
            print(f"  Error processing voice {voice_name}: {e}")
            # Optionally, continue to the next voice or stop
            # continue

    print("\nFinished generating all audio samples.")

if __name__ == "__main__":
    main()
