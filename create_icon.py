#!/usr/bin/env python3

import os
import subprocess
from PIL import Image, ImageDraw

def create_icon():
    """Create a basic icon for the application"""
    # Create a 1024x1024 image with a transparent background
    size = 1024
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a simple calculator icon
    # Background circle
    margin = size // 10
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 fill=(52, 152, 219, 255))  # Blue color
    
    # Calculator display
    display_margin = size // 4
    draw.rectangle([display_margin, display_margin, 
                   size-display_margin, size//2], 
                  fill=(255, 255, 255, 255))
    
    # Calculator buttons
    button_size = size // 6
    button_margin = size // 8
    for i in range(4):
        for j in range(4):
            x = display_margin + (i * (button_size + button_margin))
            y = size//2 + button_margin + (j * (button_size + button_margin))
            draw.rectangle([x, y, x+button_size, y+button_size], 
                         fill=(255, 255, 255, 255))
    
    # Save as PNG first
    image.save('assets/icon.png')
    
    # Convert to ICNS for macOS
    if os.path.exists('iconutil'):
        # Create iconset directory
        os.makedirs('assets/icon.iconset', exist_ok=True)
        
        # Generate different sizes
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        for size in sizes:
            resized = image.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(f'assets/icon.iconset/icon_{size}x{size}.png')
            if size <= 32:
                resized.save(f'assets/icon.iconset/icon_{size//2}x{size//2}@2x.png')
        
        # Convert to ICNS
        subprocess.run(['iconutil', '-c', 'icns', 'assets/icon.iconset'])
        print("Icon created successfully!")

if __name__ == "__main__":
    create_icon() 