const STORAGE_KEY_PREFIX = "stock-invoice-launch:v1:";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function storageKeyFor(opaqueIntentId: string): string {
  if (opaqueIntentId.trim().length === 0) {
    throw new Error("Stock invoice intent id must not be blank.");
  }

  return `${STORAGE_KEY_PREFIX}${opaqueIntentId}`;
}

function isMalformedLaunchKey(value: string): boolean {
  return !UUID_PATTERN.test(value);
}

export function getStockInvoiceLaunchKey(
  storage: Storage,
  opaqueIntentId: string,
  newKey: () => string = () => crypto.randomUUID(),
): string {
  const storageKey = storageKeyFor(opaqueIntentId);
  const storedKey = storage.getItem(storageKey);

  if (storedKey !== null) {
    if (isMalformedLaunchKey(storedKey)) {
      throw new Error("Stored stock invoice launch key is malformed.");
    }

    return storedKey;
  }

  const createdKey = newKey();
  if (isMalformedLaunchKey(createdKey)) {
    throw new Error("Generated stock invoice launch key is malformed.");
  }

  storage.setItem(storageKey, createdKey);

  if (storage.getItem(storageKey) !== createdKey) {
    throw new Error("Stock invoice launch key was not persisted.");
  }

  return createdKey;
}

export function clearStockInvoiceLaunchKey(
  storage: Storage,
  opaqueIntentId: string,
  expectedKey: string,
): void {
  const storageKey = storageKeyFor(opaqueIntentId);
  const storedKey = storage.getItem(storageKey);

  if (storedKey === null) {
    return;
  }

  if (isMalformedLaunchKey(storedKey)) {
    throw new Error("Stored stock invoice launch key is malformed.");
  }

  if (storedKey === expectedKey) {
    storage.removeItem(storageKey);
  }
}
