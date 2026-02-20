# Homebrew Formula for Atom Menu Bar
# This formula installs the Atom Menu Bar application from GitHub releases

class AtomMenubar < Formula
  desc "AI-powered automation at your fingertips"
  homepage "https://github.com/rush86999/atom"
  url "https://github.com/rush86999/atom/releases/download/v1.0.0/Atom_Menu_Bar_1.0.0_aarch64.dmg"
  version "1.0.0"
  sha256 "PLACEHOLDER_SHA256"

  depends_on macos: :catalina

  app "Atom Menu Bar.app"

  caveats do
    <<~EOS
      Atom Menu Bar requires macOS 10.15 (Catalina) or later.

      First-time setup:
      1. Launch Atom Menu Bar from Applications
      2. Click the menu bar icon
      3. Sign in or create an account
      4. Grant necessary permissions (location, notifications, etc.)

      For more information, visit:
        https://github.com/rush86999/atom/blob/main/docs/MENUBAR_DEPLOYMENT.md

      To get started, run:
        open "#{appdir}/Atom Menu Bar.app"
    EOS
  end

  test do
    # Verify the app bundle exists
    app_bundle = appdir/"Atom Menu Bar.app"
    assert_predicate app_bundle, :exist?

    # Verify the app is signed (on macOS)
    if OS.mac?
      system_command "codesign", args: ["-v", app_bundle]
    end
  end
end
