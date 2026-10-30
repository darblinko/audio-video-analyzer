"""
Audio DSP processor using librosa for feature extraction and analysis
"""
import librosa
import numpy as np
import soundfile as sf
from typing import Dict, Any
import os


class AudioProcessor:
    """Process audio files and extract DSP features"""
    
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
    
    def analyze_audio(self, audio_path: str) -> Dict[str, Any]:
        """
        Perform comprehensive audio analysis
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Dictionary containing audio features and metrics
        """
        try:
            # Load audio file
            y, sr = librosa.load(audio_path, sr=self.sample_rate)
            
            # Basic properties
            duration = librosa.get_duration(y=y, sr=sr)
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            
            # Zero crossing rate (useful for voiced/unvoiced detection)
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            
            # MFCCs (Mel-frequency cepstral coefficients)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            
            # Tempo and beat tracking
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # RMS Energy
            rms = librosa.feature.rms(y=y)[0]
            
            # Chroma features (pitch class)
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            
            # Harmonic and percussive components
            y_harmonic, y_percussive = librosa.effects.hpss(y)
            
            # Aggregate statistics
            results = {
                "basic_info": {
                    "duration_seconds": float(duration),
                    "sample_rate": int(sr),
                    "total_samples": len(y),
                    "channels": 1  # librosa loads as mono
                },
                "spectral_features": {
                    "centroid_mean": float(np.mean(spectral_centroids)),
                    "centroid_std": float(np.std(spectral_centroids)),
                    "rolloff_mean": float(np.mean(spectral_rolloff)),
                    "bandwidth_mean": float(np.mean(spectral_bandwidth)),
                    "bandwidth_std": float(np.std(spectral_bandwidth))
                },
                "temporal_features": {
                    "zero_crossing_rate_mean": float(np.mean(zcr)),
                    "zero_crossing_rate_std": float(np.std(zcr)),
                    "tempo_bpm": float(tempo),
                    "beat_count": len(beats)
                },
                "energy_features": {
                    "rms_mean": float(np.mean(rms)),
                    "rms_std": float(np.std(rms)),
                    "rms_max": float(np.max(rms)),
                    "dynamic_range_db": float(20 * np.log10(np.max(rms) / (np.mean(rms) + 1e-10)))
                },
                "mfcc_features": {
                    f"mfcc_{i}_mean": float(np.mean(mfccs[i]))
                    for i in range(min(5, len(mfccs)))  # First 5 MFCCs
                },
                "harmonic_percussive": {
                    "harmonic_ratio": float(np.sum(np.abs(y_harmonic)) / (np.sum(np.abs(y)) + 1e-10)),
                    "percussive_ratio": float(np.sum(np.abs(y_percussive)) / (np.sum(np.abs(y)) + 1e-10))
                },
                "chroma_features": {
                    "chroma_mean": float(np.mean(chroma)),
                    "chroma_std": float(np.std(chroma))
                }
            }
            
            # Classify audio type based on features
            results["classification"] = self._classify_audio(results)
            
            return {
                "success": True,
                "features": results,
                "message": "Audio analysis completed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to analyze audio"
            }
    
    def _classify_audio(self, features: Dict[str, Any]) -> Dict[str, str]:
        """
        Simple classification based on extracted features
        
        Args:
            features: Extracted audio features
            
        Returns:
            Classification results
        """
        classifications = []
        
        # Check if predominantly harmonic (music) or percussive (speech/noise)
        harmonic_ratio = features["harmonic_percussive"]["harmonic_ratio"]
        if harmonic_ratio > 0.6:
            classifications.append("musical")
        elif harmonic_ratio < 0.4:
            classifications.append("speech_or_noise")
        else:
            classifications.append("mixed")
        
        # Energy level classification
        rms_mean = features["energy_features"]["rms_mean"]
        if rms_mean > 0.1:
            classifications.append("high_energy")
        elif rms_mean > 0.05:
            classifications.append("medium_energy")
        else:
            classifications.append("low_energy")
        
        # Tempo classification
        tempo = features["temporal_features"]["tempo_bpm"]
        if tempo > 120:
            classifications.append("fast_tempo")
        elif tempo > 80:
            classifications.append("moderate_tempo")
        else:
            classifications.append("slow_tempo")
        
        return {
            "type": classifications[0] if classifications else "unknown",
            "energy_level": classifications[1] if len(classifications) > 1 else "unknown",
            "tempo_category": classifications[2] if len(classifications) > 2 else "unknown",
            "all_tags": ", ".join(classifications)
        }
    
    def extract_audio_from_video(self, video_path: str, output_path: str) -> Dict[str, Any]:
        """
        Extract audio from video file (requires ffmpeg installed)
        Note: For local demo, we rely on client-side extraction with FFmpeg.wasm
        This is a fallback server-side option.
        
        Args:
            video_path: Path to video file
            output_path: Path for extracted audio
            
        Returns:
            Status dictionary
        """
        try:
            import subprocess
            
            # Use ffmpeg to extract audio
            command = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # Convert to WAV
                '-ar', '44100',  # Sample rate
                '-ac', '2',  # Stereo
                output_path,
                '-y'  # Overwrite
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "output_path": output_path,
                    "message": "Audio extracted successfully"
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr,
                    "message": "Failed to extract audio from video"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Audio extraction failed"
            }


if __name__ == "__main__":
    # Test the processor
    processor = AudioProcessor()
    
    # This is just for testing - you'd need a real audio file
    print("AudioProcessor module loaded successfully")
    print("Available methods:")
    print("  - analyze_audio(audio_path)")
    print("  - extract_audio_from_video(video_path, output_path)")
