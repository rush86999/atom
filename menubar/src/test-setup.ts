import '@testing-library/jest-dom';

beforeEach(() => {
  // Default-deny network access; individual tests may override this with a controlled fixture.
  globalThis.fetch = jest.fn(() =>
    Promise.reject(new Error('Unexpected network request in test'))
  );
});
