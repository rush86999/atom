const { Deepgram } = require('@deepgram/sdk');

class TranscriptionSkill {
  constructor(apiKey) {
    this.deepgram = new Deepgram(apiKey);
    this.connection = null;
  }

  start(callback) {
    this.connection = this.deepgram.transcription.live({
      punctuate: true,
      interim_results: true,
    });

    this.connection.on('open', () => {
      this.connection.on('message', (data) => {
        const transcript = data.channel.alternatives[0].transcript;
        if (transcript) {
          callback(transcript);
        }
      });

      this.connection.on('close', () => {
        console.log('Connection closed.');
      });
    });
  }

  stop() {
    if (this.connection) {
      this.connection.close();
    }
  }

  send(audioData) {
    if (this.connection) {
      this.connection.send(audioData);
    }
  }
}

module.exports = TranscriptionSkill;
