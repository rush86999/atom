# Icon Placeholder

This directory should contain the following icon files:

- `32x32.png` - 32x32 pixel PNG
- `128x128.png` - 128x128 pixel PNG
- `128x128@2x.png` - 256x256 pixel PNG (Retina)
- `icon.icns` - macOS icon file
- `icon.ico` - Windows icon file

For development, you can use placeholder icons or generate proper icons using:

```bash
# Generate icons from a 1024x1024 PNG source
# Using tauri-icon (npm install -g tauri-icon)
tauri-icon source.png

# Or use online tools like:
# - https://cloudconvert.com/png-to-icns
# - https://www.img2icnsapp.com/
```

The Atom logo should be used for production icons.
