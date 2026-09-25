import os
from moviepy import VideoFileClip

def convert_and_compress(input_path, output_path):
    print(f"🎬 Loading {input_path}...")
    clip = VideoFileClip(input_path)

    # clip.size returns [width, height] in MoviePy v2.x
    width, height = clip.size
    print(f"📐 Original resolution: {width}x{height}")

    if height > 1080:
        print("📉 Resizing video to 1080p for better compression...")
        clip = clip.resized(height=1080)

    print(f"⏳ Compressing and saving to {output_path}. Please wait...")

    clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        bitrate="1500k",
        preset="medium"
    )

    clip.close()
    print("✅ Done! File successfully compressed.")

# Absolute paths to your frontend assets folder
input_file = "/Users/user/Desktop/FaceVerifySystem/frontend/src/assets/common/tutorial.mov"
output_file = "/Users/user/Desktop/FaceVerifySystem/frontend/src/assets/common/tutorial.mp4"

if os.path.exists(input_file):
    convert_and_compress(input_file, output_file)
else:
    print(f"❌ Error: Could not find '{input_file}' on your system.")
