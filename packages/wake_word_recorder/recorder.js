document.addEventListener('DOMContentLoaded', () => {
  const startButton = document.getElementById('startButton');
  const stopButton = document.getElementById('stopButton');
  const playButton = document.getElementById('playButton');
  const downloadButton = document.getElementById('downloadButton'); // Will be used in next step
  const audioPlayback = document.getElementById('audioPlayback');
  const statusMessages = document.getElementById('statusMessages');

  let mediaRecorder;
  let audioChunks = [];
  let audioBlob;

  function setStatus(message) {
    statusMessages.textContent = `Status: ${message}`;
    console.log(`Status: ${message}`);
  }

  startButton.addEventListener('click', async () => {
    audioChunks = [];
    audioBlob = null; // Reset previous recording

    startButton.disabled = true;
    stopButton.disabled = false;
    playButton.disabled = true;
    downloadButton.disabled = true;
    audioPlayback.src = ''; // Clear previous playback src

    setStatus('Requesting microphone access...');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStatus('Microphone access granted. Initializing recorder...');

      // Determine a suitable MIME type. Browsers vary.
      // Common options: 'audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/wav' (less common for MediaRecorder directly)
      // Let's try a few common ones or let the browser decide by not specifying.
      const options = { mimeType: 'audio/webm;codecs=opus' };
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        console.warn(
          `${options.mimeType} is not supported. Trying 'audio/ogg;codecs=opus'.`
        );
        options.mimeType = 'audio/ogg;codecs=opus';
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          console.warn(
            `${options.mimeType} is not supported. Trying without specifying.`
          );
          delete options.mimeType; // Let browser pick
        }
      }

      mediaRecorder = new MediaRecorder(stream, options);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm'; // Fallback if not set in options
        console.log(
          `Recording stopped. MimeType: ${mimeType}, Chunks: ${audioChunks.length}`
        );
        if (audioChunks.length === 0) {
          setStatus(
            'Recording stopped, but no audio data was captured. Please try again.'
          );
          console.warn('No audio chunks recorded.');
        } else {
          audioBlob = new Blob(audioChunks, { type: mimeType });
          const audioUrl = URL.createObjectURL(audioBlob);
          audioPlayback.src = audioUrl;
          setStatus('Recording stopped. Ready to play or download.');
          playButton.disabled = false;
          downloadButton.disabled = false; // Enable download when blob is ready
        }

        stopButton.disabled = true;
        startButton.disabled = false;
        // Clean up the stream tracks
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.onerror = (event) => {
        setStatus(`Recorder error: ${event.error.name}`);
        console.error('MediaRecorder error:', event.error);
        startButton.disabled = false;
        stopButton.disabled = true;
        playButton.disabled = true;
        downloadButton.disabled = true;
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setStatus("Recording... Click 'Stop Recording' when done.");
    } catch (err) {
      console.error('Error accessing microphone:', err);
      setStatus(
        `Error: ${err.message}. Ensure microphone is connected and permission granted.`
      );
      startButton.disabled = false;
      stopButton.disabled = true;
      playButton.disabled = true;
      downloadButton.disabled = true;
    }
  });

  stopButton.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      setStatus('Stopping recording...');
      // Button states are handled in mediaRecorder.onstop
    }
  });

  playButton.addEventListener('click', () => {
    if (audioBlob) {
      audioPlayback.play();
      setStatus('Playing recording...');
    } else {
      setStatus('No recording available to play.');
    }
  });

  audioPlayback.onplay = () => {
    setStatus('Playing recording...');
  };

  audioPlayback.onended = () => {
    setStatus('Playback finished. Ready to play again or download.');
  };

  audioPlayback.onerror = (e) => {
    setStatus('Error playing audio.');
    console.error('Error during audio playback:', e);
  };

  // Initial state message
  setStatus("Idle. Click 'Start Recording' to begin.");
});
