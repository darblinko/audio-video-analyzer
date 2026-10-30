"""
Test script for audio and video analyzers
Run this to verify your setup before starting the full application
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from audio_processor import AudioProcessor
from video_analyzer import VideoAnalyzer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_audio_processor():
    """Test audio processor with a sample file"""
    print("\n" + "="*60)
    print("Testing Audio Processor")
    print("="*60)
    
    processor = AudioProcessor()
    
    # Check if test audio file exists
    test_file = "test_audio.mp3"
    if not os.path.exists(test_file):
        print("❌ No test audio file found")
        print("   Create a test_audio.mp3 file in the backend directory")
        print("   Or record audio using the web app first")
        return False
    
    print(f"✓ Found test file: {test_file}")
    print("  Analyzing audio...")
    
    result = processor.analyze_audio(test_file)
    
    if result["success"]:
        print("✅ Audio analysis successful!")
        print("\nSample features:")
        features = result["features"]
        print(f"  Duration: {features['basic_info']['duration_seconds']:.2f}s")
        print(f"  Sample Rate: {features['basic_info']['sample_rate']} Hz")
        print(f"  Audio Type: {features['classification']['type']}")
        print(f"  Energy Level: {features['classification']['energy_level']}")
        print(f"  Tempo: {features['temporal_features']['tempo_bpm']:.1f} BPM")
        return True
    else:
        print("❌ Audio analysis failed!")
        print(f"   Error: {result['error']}")
        return False


def test_video_analyzer():
    """Test video analyzer with a sample file"""
    print("\n" + "="*60)
    print("Testing Video Analyzer")
    print("="*60)
    
    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in .env file")
        print("   1. Create a .env file in the backend directory")
        print("   2. Add: GOOGLE_API_KEY=your_key_here")
        print("   3. Get key from: https://aistudio.google.com/app/apikey")
        return False
    
    print("✓ Found API key")
    
    try:
        analyzer = VideoAnalyzer(api_key=api_key)
        print("✓ Video analyzer initialized")
    except Exception as e:
        print(f"❌ Failed to initialize video analyzer: {e}")
        return False
    
    # Check if test video file exists
    test_file = "test_video.webm"
    if not os.path.exists(test_file):
        print("❌ No test video file found")
        print("   Create a test_video.webm file in the backend directory")
        print("   Or record video using the web app first")
        return False
    
    print(f"✓ Found test file: {test_file}")
    print("  Uploading to Gemini and analyzing...")
    print("  This may take 30-60 seconds...")
    
    result = analyzer.analyze_video(test_file)
    
    if result["success"]:
        print("✅ Video analysis successful!")
        print("\nGemini Analysis (first 200 chars):")
        analysis = result["analysis"]
        print(f"  {analysis[:200]}...")
        return True
    else:
        print("❌ Video analysis failed!")
        print(f"   Error: {result['error']}")
        return False


def test_dependencies():
    """Test that all required dependencies are installed"""
    print("\n" + "="*60)
    print("Testing Dependencies")
    print("="*60)
    
    dependencies = {
        "librosa": "Audio analysis",
        "soundfile": "Audio file I/O",
        "fastapi": "Web framework",
        "uvicorn": "ASGI server",
        "google.generativeai": "Gemini API",
        "aiosqlite": "Async SQLite",
    }
    
    all_ok = True
    for module, description in dependencies.items():
        try:
            __import__(module)
            print(f"✅ {module:25} - {description}")
        except ImportError:
            print(f"❌ {module:25} - {description} (NOT INSTALLED)")
            all_ok = False
    
    return all_ok


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Audio/Video Analyzer - Test Suite")
    print("="*60)
    
    # Test dependencies
    deps_ok = test_dependencies()
    if not deps_ok:
        print("\n❌ Some dependencies are missing!")
        print("   Run: pip install -r requirements.txt")
        return
    
    # Test audio processor
    audio_ok = test_audio_processor()
    
    # Test video analyzer
    video_ok = test_video_analyzer()
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Dependencies: {'✅' if deps_ok else '❌'}")
    print(f"Audio Processor: {'✅' if audio_ok else '⚠️  (no test file)'}")
    print(f"Video Analyzer: {'✅' if video_ok else '⚠️  (no test file or API key)'}")
    
    if deps_ok:
        print("\n✅ Core dependencies are working!")
        print("   Ready to start the server with: python server.py")
    
    if not audio_ok or not video_ok:
        print("\n⚠️  To test with actual files:")
        print("   1. Start the full app: python server.py")
        print("   2. Record audio/video in the web interface")
        print("   3. Files will be in uploads/ directory")
        print("   4. Copy a file to test_audio.mp3 or test_video.webm")
        print("   5. Run this test again")


if __name__ == "__main__":
    main()
