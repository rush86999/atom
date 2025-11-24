Add-Type -AssemblyName System.Drawing

$pngPath = Join-Path $PSScriptRoot "icons\atom-ai-256.png"
$icoPath = Join-Path $PSScriptRoot "icons\atom-ai-2.ico"

Write-Host "Converting $pngPath to $icoPath..."

# Load the PNG image
$image = [System.Drawing.Image]::FromFile($pngPath)

# Create a new bitmap at 256x256
$bitmap = New-Object System.Drawing.Bitmap 256, 256

# Draw the image onto the bitmap
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.DrawImage($image, 0, 0, 256, 256)
$graphics.Dispose()

# Create the icon
$icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())

# Save as ICO file
$fileStream = [System.IO.File]::Create($icoPath)
$icon.Save($fileStream)
$fileStream.Close()

# Cleanup
$image.Dispose()
$bitmap.Dispose()

Write-Host "Conversion complete!"
