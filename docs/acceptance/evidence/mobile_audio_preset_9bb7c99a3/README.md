# Expo AV recording preset

Source 9bb7c99a3; independent negative checkpoint 9adf79ca4. Mounted component with SDK-shaped transport double: 71 passed / 1 failed before, 72 passed / 0 failed after. Full strict compiler remains failed with 366 diagnostics. No dependency/config/compiler changes.

Installed expo-av build/Audio/Recording.js defaults undefined to LOW_QUALITY; the old nonexistent constant passed undefined. The component now supplies RecordingOptionsPresets.HIGH_QUALITY. Existing two doubles use the actual namespace. Native Flash proposal accepted for runtime, second double and unused unsupported RNTL binding removal; its duplicate weaker require-based assertion was rejected in favor of the already captured typed assertion.

No production import caller for this component was found in the mobile source scan. These are component/SDK tests, not an integrated chat-screen, OS permission, device microphone or native recording qualification.
