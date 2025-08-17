import os
import tempfile
import subprocess
import requests
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
import logging
import json
import re
from mutagen import File as MutagenFile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000')
OUTPUT_DIR = os.path.join(os.getcwd(), 'output')
TEMP_DIR = os.path.join(os.getcwd(), 'temp')

# Create directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def download_file(url, local_path):
    """Download file from URL to local path"""
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded file: {url} -> {local_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False

def get_media_duration(file_path):
    """Get media file duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        logger.info(f"Duration of {file_path}: {duration} seconds")
        return duration
    except Exception as e:
        logger.error(f"Error getting duration for {file_path}: {str(e)}")
        return None

def extract_audio_with_whisper(audio_path, language='tr'):
    """Extract transcript and SRT from audio using Whisper"""
    try:
        # Use whisper to transcribe audio
        cmd = [
            'whisper', audio_path,
            '--language', language,
            '--model', 'base',
            '--output_format', 'srt',
            '--output_dir', TEMP_DIR,
            '--verbose', 'False'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            logger.error(f"Whisper error: {result.stderr}")
            return None
        
        # Find generated SRT file
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        srt_path = os.path.join(TEMP_DIR, f"{base_name}.srt")
        
        if os.path.exists(srt_path):
            return srt_path
        else:
            logger.error(f"SRT file not found: {srt_path}")
            return None
            
    except Exception as e:
        logger.error(f"Whisper transcription error: {str(e)}")
        return None

def merge_video_audio_subtitle(video_path, audio_path, srt_path, output_path,
                               soft_subtitles=True, burn_subtitles=False,
                               audio_offset_ms=0, volume=1.0):
    """Merge video with new audio and subtitles using FFmpeg, adjusting video to audio length."""
    try:
        video_duration = get_media_duration(video_path)
        audio_duration = get_media_duration(audio_path)

        if video_duration is None or audio_duration is None:
            logger.error("Could not determine media durations. Aborting merge.")
            return False

        cmd = ['ffmpeg', '-y', '-i', video_path, '-i', audio_path]
        
        # Base filter complex for audio processing
        audio_delay = f"{audio_offset_ms}ms" if audio_offset_ms != 0 else "0ms"
        filter_complex = f"[1:a]volume={volume},adelay={audio_delay}[a_out];"

        # Video processing filters
        if audio_duration > video_duration:
            # Loop video to match audio duration
            filter_complex += f"[0:v]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB[v_looped];"
            video_stream = "[v_looped]"
        else:
            # Video is long enough, no looping needed
            video_stream = "[0:v]"

        # Subtitle burning filter
        if burn_subtitles and srt_path:
            safe_srt_path = srt_path.replace('\\', '/').replace(':', '\\:')
            filter_complex += f"{video_stream}subtitles='{safe_srt_path}'[v_out]"
            video_map = "[v_out]"
        else:
            # If not burning subtitles, just pass the video stream through
            filter_complex += f"{video_stream}null[v_out]"
            video_map = "[v_out]"

        cmd.extend(['-filter_complex', filter_complex])
        cmd.extend(['-map', video_map, '-map', '[a_out]'])

        # Add soft subtitles if requested and not burning them
        if soft_subtitles and not burn_subtitles and srt_path:
            cmd.extend(['-i', srt_path, '-map', '2:s', '-c:s', 'srt'])

        # Set output duration to audio duration
        cmd.extend(['-t', str(audio_duration)])

        # Output settings
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ])

        logger.info(f"FFmpeg command: {' '.join(cmd)}")

        # Execute FFmpeg
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False

        logger.info(f"Video merge completed: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Video merge error: {str(e)}")
        return False

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/process', methods=['POST'])
def process_video():
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'video_url' not in data or 'audio_url' not in data:
            return jsonify({"error": "video_url and audio_url are required"}), 400
        
        video_url = data['video_url']
        audio_url = data['audio_url']
        soft_subtitles = data.get('soft_subtitles', True)
        burn_subtitles = data.get('burn_subtitles', False)
        audio_offset_ms = data.get('audio_offset_ms', 0)
        subtitle_language = data.get('subtitle_language', 'tr')
        volume = data.get('volume', 1.0)
        
        # Generate unique ID for this process
        process_id = str(uuid.uuid4())
        
        # Create temporary file paths
        video_temp = os.path.join(TEMP_DIR, f"{process_id}_video.mp4")
        audio_temp = os.path.join(TEMP_DIR, f"{process_id}_audio.mp3")
        output_file = os.path.join(OUTPUT_DIR, f"{process_id}_merged.mp4")
        srt_file = os.path.join(OUTPUT_DIR, f"{process_id}_subtitles.srt")
        
        # Download video and audio
        logger.info(f"Downloading video: {video_url}")
        if not download_file(video_url, video_temp):
            return jsonify({"error": "Failed to download video"}), 500
        
        logger.info(f"Downloading audio: {audio_url}")
        if not download_file(audio_url, audio_temp):
            return jsonify({"error": "Failed to download audio"}), 500
        
        # Generate subtitles from audio
        logger.info(f"Generating subtitles from audio")
        srt_temp = extract_audio_with_whisper(audio_temp, subtitle_language)
        
        if srt_temp and os.path.exists(srt_temp):
            # Copy SRT to output directory
            import shutil
            shutil.copy2(srt_temp, srt_file)
        else:
            logger.warning("Failed to generate subtitles, proceeding without them")
            srt_file = None
        
        # Merge video, audio and subtitles
        logger.info(f"Merging video with audio and subtitles")
        success = merge_video_audio_subtitle(
            video_temp, audio_temp, srt_file, output_file,
            soft_subtitles, burn_subtitles, audio_offset_ms, volume
        )
        
        if not success:
            return jsonify({"error": "Failed to merge video and audio"}), 500
        
        # Clean up temporary files
        try:
            os.remove(video_temp)
            os.remove(audio_temp)
            if srt_temp and os.path.exists(srt_temp):
                os.remove(srt_temp)
        except:
            pass
        
        # Generate download URLs
        download_url = f"{PUBLIC_BASE_URL}/download/{process_id}_merged.mp4"
        srt_url = f"{PUBLIC_BASE_URL}/download/{process_id}_subtitles.srt" if srt_file else None
        
        return jsonify({
            "success": True,
            "process_id": process_id,
            "download_url": download_url,
            "srt_url": srt_url,
            "subtitle_language": subtitle_language,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Process error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def create_subtitle_from_text(text, audio_url, output_path, language='tr'):
    """Create SRT subtitle file from text and audio URL"""
    try:
        # Download audio file temporarily to get duration
        temp_audio = os.path.join(TEMP_DIR, f"temp_audio_{uuid.uuid4()}.mp3")
        
        if not download_file(audio_url, temp_audio):
            logger.error("Failed to download audio file")
            return False
        
        # Get audio duration
        try:
            audio_file = MutagenFile(temp_audio)
            if audio_file is not None:
                duration = audio_file.info.length
            else:
                # Fallback to ffprobe
                result = subprocess.run(
                    ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
                     '-of', 'csv=p=0', temp_audio],
                    capture_output=True, text=True
                )
                duration = float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            duration = 60.0  # Default fallback
        
        # Clean up temporary audio file
        try:
            os.remove(temp_audio)
        except:
            pass
        
        # Clean and prepare text
        text = text.strip()
        if not text:
            logger.error("Empty text provided")
            return False
        
        # Remove unwanted characters and normalize
        text = re.sub(r'[\r\n]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Split text into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            logger.error("No valid sentences found in text")
            return False
        
        # Calculate timing for each sentence
        time_per_sentence = duration / len(sentences)
        
        # Generate SRT content
        srt_content = []
        for i, sentence in enumerate(sentences):
            start_time = i * time_per_sentence
            end_time = (i + 1) * time_per_sentence
            
            # Format time as SRT timestamp
            start_srt = format_srt_time(start_time)
            end_srt = format_srt_time(end_time)
            
            srt_content.append(f"{i + 1}")
            srt_content.append(f"{start_srt} --> {end_srt}")
            srt_content.append(sentence)
            srt_content.append("")  # Empty line between subtitles
        
        # Write SRT file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(srt_content))
        
        logger.info(f"Subtitle file created: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating subtitle: {str(e)}")
        return False

def format_srt_time(seconds):
    """Format seconds to SRT time format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"

@app.route('/create_subtitle', methods=['POST'])
def create_subtitle():
    """Create subtitle file from text and audio URL"""
    try:
        data = request.get_json()
        
        # Validate input
        if not data or 'text' not in data or 'audio_url' not in data:
            return jsonify({"error": "text and audio_url are required"}), 400
        
        text = data['text']
        audio_url = data['audio_url']
        language = data.get('language', 'tr')
        
        if not text.strip():
            return jsonify({"error": "Text cannot be empty"}), 400
        
        # Generate unique ID for this subtitle
        subtitle_id = str(uuid.uuid4())
        output_file = os.path.join(OUTPUT_DIR, f"{subtitle_id}_subtitle.srt")
        
        # Create subtitle
        success = create_subtitle_from_text(text, audio_url, output_file, language)
        
        if not success:
            return jsonify({"error": "Failed to create subtitle"}), 500
        
        # Generate download URL
        download_url = f"{PUBLIC_BASE_URL}/download/{subtitle_id}_subtitle.srt"
        
        return jsonify({
            "success": True,
            "subtitle_id": subtitle_id,
            "download_url": download_url,
            "language": language,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Subtitle creation error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file_endpoint(filename):
    try:
        file_path = os.path.join(OUTPUT_DIR, secure_filename(filename))
        
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({"error": "Download failed"}), 500

if __name__ == '__main__':
    # Check dependencies
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        logger.info("FFmpeg is available")
    except:
        logger.error("FFmpeg not found! Please install FFmpeg")
        exit(1)
    
    try:
        subprocess.run(['whisper', '--help'], capture_output=True, check=True)
        logger.info("Whisper is available")
    except:
        logger.error("Whisper not found! Please install openai-whisper")
        exit(1)
    
    app.run(host='0.0.0.0', port=8000, debug=False)
