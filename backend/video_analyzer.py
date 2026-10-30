"""
Video analyzer using Google Gemini API for visual analysis
"""
import google.generativeai as genai
from typing import Dict, Any, Optional
import os
from pathlib import Path
import mimetypes


class VideoAnalyzer:
    """Analyze video content using Google Gemini API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Video Analyzer with Gemini API
        
        Args:
            api_key: Google AI Studio API key (or reads from env)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment or constructor")
        
        genai.configure(api_key=self.api_key)
        
        # Use Gemini 2.0 Flash for video analysis
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    def analyze_video(self, video_path: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze video content using Gemini
        
        Args:
            video_path: Path to video file
            prompt: Optional custom prompt for analysis
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Verify file exists
            if not os.path.exists(video_path):
                return {
                    "success": False,
                    "error": "Video file not found",
                    "message": f"File does not exist: {video_path}"
                }
            
            # Get file info
            file_size = os.path.getsize(video_path)
            mime_type, _ = mimetypes.guess_type(video_path)
            
            # Upload video to Gemini
            print(f"Uploading video: {video_path} ({file_size / 1024 / 1024:.2f} MB)")
            video_file = genai.upload_file(path=video_path)
            
            # Wait for processing
            print(f"Waiting for video processing... (state: {video_file.state.name})")
            while video_file.state.name == "PROCESSING":
                import time
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED":
                return {
                    "success": False,
                    "error": "Video processing failed",
                    "message": "Gemini failed to process the video"
                }
            
            # Default analysis prompt
            if not prompt:
                prompt = """Analyze this video and provide:
1. A brief description of what's happening
2. Key objects or subjects visible
3. Scene/setting description
4. Any notable actions or movements
5. Overall mood or atmosphere
6. Audio-visual observations (if audio is present)

Be specific and detailed in your analysis."""
            
            # Generate analysis
            print("Generating analysis...")
            response = self.model.generate_content([video_file, prompt])
            
            # Clean up uploaded file
            genai.delete_file(video_file.name)
            
            return {
                "success": True,
                "analysis": response.text,
                "video_info": {
                    "file_size_mb": file_size / 1024 / 1024,
                    "mime_type": mime_type or "unknown",
                    "gemini_model": "gemini-2.0-flash-exp"
                },
                "message": "Video analysis completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to analyze video: {str(e)}"
            }
    
    def analyze_with_custom_prompt(
        self, 
        video_path: str, 
        questions: list[str]
    ) -> Dict[str, Any]:
        """
        Analyze video with specific questions
        
        Args:
            video_path: Path to video file
            questions: List of specific questions to ask about the video
            
        Returns:
            Dictionary with answers to each question
        """
        try:
            if not os.path.exists(video_path):
                return {
                    "success": False,
                    "error": "Video file not found"
                }
            
            # Upload video
            video_file = genai.upload_file(path=video_path)
            
            # Wait for processing
            while video_file.state.name == "PROCESSING":
                import time
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
            
            if video_file.state.name == "FAILED":
                genai.delete_file(video_file.name)
                return {
                    "success": False,
                    "error": "Video processing failed"
                }
            
            # Ask each question
            answers = {}
            for i, question in enumerate(questions, 1):
                response = self.model.generate_content([video_file, question])
                answers[f"question_{i}"] = {
                    "question": question,
                    "answer": response.text
                }
            
            # Clean up
            genai.delete_file(video_file.name)
            
            return {
                "success": True,
                "answers": answers,
                "message": "Custom analysis completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to analyze video: {str(e)}"
            }
    
    def analyze_video_audio_sync(
        self, 
        video_path: str, 
        audio_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze video with context from audio DSP analysis
        
        Args:
            video_path: Path to video file
            audio_features: Audio features from AudioProcessor
            
        Returns:
            Combined audio-visual analysis
        """
        try:
            # Create context-aware prompt
            audio_context = f"""
Based on audio analysis showing:
- Duration: {audio_features.get('basic_info', {}).get('duration_seconds', 'unknown')}s
- Audio type: {audio_features.get('classification', {}).get('type', 'unknown')}
- Energy level: {audio_features.get('classification', {}).get('energy_level', 'unknown')}
- Tempo: {audio_features.get('temporal_features', {}).get('tempo_bpm', 'unknown')} BPM

Analyze this video and explain:
1. How the visual content matches or contrasts with the audio characteristics
2. Whether the audio and visual elements are synchronized
3. The overall coherence between audio and visual information
4. Any notable audio-visual relationships or patterns
"""
            
            result = self.analyze_video(video_path, prompt=audio_context)
            
            if result["success"]:
                result["audio_features_used"] = audio_features.get("classification", {})
                result["analysis_type"] = "audio_visual_sync"
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to perform audio-visual analysis"
            }


if __name__ == "__main__":
    # Test the analyzer
    print("VideoAnalyzer module loaded successfully")
    print("Available methods:")
    print("  - analyze_video(video_path, prompt=None)")
    print("  - analyze_with_custom_prompt(video_path, questions)")
    print("  - analyze_video_audio_sync(video_path, audio_features)")
    print("\nRequires GOOGLE_API_KEY in environment")
