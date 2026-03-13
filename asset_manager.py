import os
from datetime import datetime

OUTPUT_DIR = "output_videos"

def get_output_videos():
    if not os.path.exists(OUTPUT_DIR):
        return []
    
    videos = []
    for filename in os.listdir(OUTPUT_DIR):
        if filename.endswith(".mp4"):
            path = os.path.join(OUTPUT_DIR, filename)
            stats = os.stat(path)
            videos.append({
                "name": filename,
                "path": os.path.abspath(path),
                "date": datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size": f"{stats.st_size / (1024*1024):.1f} MB"
            })
    
    # Sort by date descending
    videos.sort(key=lambda x: x['date'], reverse=True)
    return videos
