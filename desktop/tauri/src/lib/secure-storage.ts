import {
  readTextFile,
  writeTextFile,
  createDir,
  exists,
} from '@tauri-apps/api/fs';
import { appDataDir } from '@tauri-apps/api/path';
import CryptoJS from 'crypto-js';

const ENCRYPTION_KEY = 'your-super-secret-key-that-is-32-bytes'; // IMPORTANT: In a real app, this should be managed more securely.
const SETTINGS_FILE = 'atom-settings.json';

interface Settings {
  [key: string]: string;
}

// --- Helper Functions ---

async function getSettingsFilePath(): Promise<string> {
  const dir = await appDataDir();
  return `${dir}/${SETTINGS_FILE}`;
}

function encrypt(text: string): string {
  return CryptoJS.AES.encrypt(text, ENCRYPTION_KEY).toString();
}

function decrypt(ciphertext: string): string {
  const bytes = CryptoJS.AES.decrypt(ciphertext, ENCRYPTION_KEY);
  return bytes.toString(CryptoJS.enc.Utf8);
}

async function readSettingsFile(): Promise<Settings> {
  const filePath = await getSettingsFilePath();
  const dir = await appDataDir();

  if (!(await exists(dir))) {
    await createDir(dir, { recursive: true });
  }

  if (!(await exists(filePath))) {
    return {};
  }

  try {
    const content = await readTextFile(filePath);
    return JSON.parse(content) as Settings;
  } catch (error) {
    console.error(
      'Error reading settings file, returning empty settings:',
      error
    );
    return {};
  }
}

async function writeSettingsFile(settings: Settings): Promise<void> {
  const filePath = await getSettingsFilePath();
  await writeTextFile(filePath, JSON.stringify(settings, null, 2));
}

// --- Public API ---

export async function saveSetting(key: string, value: string): Promise<void> {
  const settings = await readSettingsFile();
  const encryptedValue = encrypt(value);
  settings[key] = encryptedValue;
  await writeSettingsFile(settings);
}

export async function getSetting(key: string): Promise<string | null> {
  const settings = await readSettingsFile();
  const encryptedValue = settings[key];
  if (encryptedValue) {
    try {
      return decrypt(encryptedValue);
    } catch (error) {
      console.error(`Error decrypting setting for key "${key}":`, error);
      return null; // Decryption failed
    }
  }
  return null;
}

export async function getSettingStatus(key: string): Promise<boolean> {
  const settings = await readSettingsFile();
  return !!settings[key];
}
