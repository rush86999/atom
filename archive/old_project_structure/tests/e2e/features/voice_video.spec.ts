import { test, expect } from '@playwright/test';

test.describe('Voice and Video AI Features', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/media-ai');
  });

  test('Generate video from text', async ({ page }) => {
    await page.click('[data-testid="video-gen-tab"]');
    await page.fill('[data-testid="prompt-input"]', 'A futuristic city skyline at sunset');
    await page.selectOption('[data-testid="style-select"]', 'realistic');
    await page.click('[data-testid="generate-btn"]');

    // Video generation takes time, assume async process
    await expect(page.locator('[data-testid="generation-status"]')).toContainText('Generating');
    // In a real test we might wait for completion or mock the status update
    await expect(page.locator('[data-testid="video-preview"]')).toBeVisible({ timeout: 60000 });
  });

  test('Voice synthesis (TTS)', async ({ page }) => {
    await page.click('[data-testid="voice-gen-tab"]');
    await page.fill('[data-testid="tts-input"]', 'Hello, this is Atom AI speaking.');
    await page.selectOption('[data-testid="voice-select"]', 'en-US-Neural2-F');
    await page.click('[data-testid="synthesize-btn"]');

    await expect(page.locator('[data-testid="audio-player"]')).toBeVisible();
    // Check if source is set
    await expect(page.locator('audio')).toHaveAttribute('src', /blob:|http/);
  });

  test('Voice cloning setup', async ({ page }) => {
    await page.click('[data-testid="voice-cloning-tab"]');
    await page.setInputFiles('input[type="file"]', {
        name: 'sample.mp3',
        mimeType: 'audio/mpeg',
        buffer: Buffer.from('fake audio')
    });
    await page.click('[data-testid="upload-sample"]');

    await expect(page.locator('[data-testid="cloning-progress"]')).toBeVisible();
    await expect(page.locator('[data-testid="cloned-voice-card"]')).toBeVisible({ timeout: 15000 });
  });

  test('Video editing - Trim', async ({ page }) => {
    await page.click('[data-testid="video-editor-tab"]');
    // Load a video
    await page.click('[data-testid="load-sample-video"]');

    // Perform trim
    await page.fill('[data-testid="start-time"]', '00:05');
    await page.fill('[data-testid="end-time"]', '00:10');
    await page.click('[data-testid="apply-trim"]');

    await expect(page.locator('[data-testid="processing-indicator"]')).toBeVisible();
    await expect(page.locator('[data-testid="result-video"]')).toBeVisible();
  });

  test('Real-time voice interaction', async ({ page }) => {
    await page.goto('http://localhost:3000/chat/voice');

    // Simulate microphone permission (usually requires browser launch args, here we assume it's handled or we check UI state)
    await page.click('[data-testid="start-listening"]');

    await expect(page.locator('[data-testid="listening-indicator"]')).toBeVisible();

    // Mock receiving transcription
    await page.evaluate(() => {
        window.dispatchEvent(new CustomEvent('speech-result', { detail: 'Hello Atom' }));
    });

    await expect(page.locator('[data-testid="user-transcript"]')).toContainText('Hello Atom');
  });

  test('Video transcription', async ({ page }) => {
    await page.click('[data-testid="transcription-tab"]');
    await page.setInputFiles('input[type="file"]', {
        name: 'webinar.mp4',
        mimeType: 'video/mp4',
        buffer: Buffer.from('fake video')
    });
    await page.click('[data-testid="start-transcription"]');

    await expect(page.locator('[data-testid="transcription-text"]')).toBeVisible();
  });

  test('Subtitle generation', async ({ page }) => {
    await page.click('[data-testid="subtitle-tab"]');
    await page.click('[data-testid="load-video"]');
    await page.click('[data-testid="generate-subtitles"]');

    await expect(page.locator('[data-testid="subtitle-editor"]')).toBeVisible();
    await expect(page.locator('.subtitle-block')).toHaveCount(1); // At least one block
  });

  test('Audio noise reduction', async ({ page }) => {
      await page.click('[data-testid="audio-tools-tab"]');
      await page.click('[data-testid="upload-audio"]');
      await page.click('[data-testid="apply-denoise"]');

      await expect(page.locator('[data-testid="waveform-processed"]')).toBeVisible();
  });

  test('Text to Image (Thumbnails)', async ({ page }) => {
      await page.click('[data-testid="image-gen-tab"]');
      await page.fill('[data-testid="prompt"]', 'YouTube thumbnail for coding tutorial');
      await page.click('[data-testid="generate-image"]');

      await expect(page.locator('[data-testid="generated-image"]')).toBeVisible();
  });

  test('Export media projects', async ({ page }) => {
      await page.click('[data-testid="projects-tab"]');
      await page.click('[data-testid="project-1"]');
      await page.click('[data-testid="export-btn"]');
      await page.selectOption('[data-testid="format"]', 'mp4');
      await page.click('[data-testid="confirm-export"]');

      await expect(page.locator('[data-testid="export-success"]')).toBeVisible();
  });
});
