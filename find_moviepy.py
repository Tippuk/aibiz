import os
import sys

try:
    import moviepy
    print(f"PYTHONPATH={sys.executable}")
    path = os.path.join(os.path.dirname(moviepy.__file__), 'config_defaults.py')
    print(f"MOVIEPY_CONFIG={path}")
    
    # Let's read it
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the line
    new_content = []
    for line in content.split('\n'):
        if line.startswith("IMAGEMAGICK_BINARY = "):
            new_content.append('IMAGEMAGICK_BINARY = r"C:\\Program Files\\ImageMagick-7.1.1-Q16-HDRI\\magick.exe"')
        else:
            new_content.append(line)
            
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_content))
        
    print("PATCHED_SUCCESSFULLY")
except Exception as e:
    print(f"ERROR: {e}")
