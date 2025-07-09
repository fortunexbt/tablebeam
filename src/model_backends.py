"""
Model backend abstraction for Ollama and MLX support
"""
import os
import subprocess
import platform
from typing import Optional, Dict, Any, Union
from abc import ABC, abstractmethod

# Check MLX availability
try:
    import mlx
    import mlx.core as mx
    from mlx_lm import load, generate
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

class ModelBackend(ABC):
    """Abstract base class for model backends"""
    
    @abstractmethod
    def load_model(self, model_name: str):
        """Load a model"""
        pass
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response"""
        pass
    
    @abstractmethod
    def list_models(self) -> list:
        """List available models"""
        pass
    
    @abstractmethod
    def download_model(self, model_name: str, progress_callback=None):
        """Download a model"""
        pass


class OllamaBackend(ModelBackend):
    """Ollama backend for model inference"""
    
    def __init__(self):
        self.base_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        
    def load_model(self, model_name: str):
        """Ollama loads models automatically on first use"""
        self.current_model = model_name
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate using Ollama (handled by langchain-ollama)"""
        # This is handled by ChatOllama in the main app
        pass
    
    def list_models(self) -> list:
        """List installed Ollama models"""
        try:
            result = subprocess.run(['ollama', 'list'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                models = []
                for line in lines:
                    if line:
                        parts = line.split()
                        if parts:
                            models.append({
                                "name": parts[0],
                                "size": parts[1] if len(parts) > 1 else "Unknown"
                            })
                return models
        except:
            pass
        return []
    
    def download_model(self, model_name: str, progress_callback=None):
        """Download Ollama model"""
        try:
            process = subprocess.Popen(
                ['ollama', 'pull', model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            for line in process.stdout:
                if progress_callback:
                    progress_callback(line.strip())
                    
            process.wait()
            return process.returncode == 0
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False


class MLXBackend(ModelBackend):
    """MLX backend for Apple Silicon optimized inference"""
    
    def __init__(self):
        if not MLX_AVAILABLE:
            raise ImportError("MLX is not installed. Run: pip install mlx-lm")
        
        self.model = None
        self.tokenizer = None
        self.model_name = None
        
    def load_model(self, model_name: str):
        """Load MLX model from Hugging Face"""
        try:
            self.model, self.tokenizer = load(model_name)
            self.model_name = model_name
        except Exception as e:
            raise Exception(f"Failed to load MLX model {model_name}: {str(e)}")
    
    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7, **kwargs) -> str:
        """Generate response using MLX"""
        if not self.model or not self.tokenizer:
            raise Exception("No model loaded")
            
        response = generate(
            self.model, 
            self.tokenizer, 
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temperature,
            **kwargs
        )
        return response
    
    def list_models(self) -> list:
        """List recommended MLX models"""
        # These are known good MLX models for Apple Silicon
        return [
            {"name": "mlx-community/quantized-gemma-2b", "size": "2GB"},
            {"name": "mlx-community/quantized-llama-3.2-3b", "size": "3GB"},
            {"name": "mlx-community/quantized-mistral-7b", "size": "7GB"},
            {"name": "mlx-community/quantized-qwen2.5-7b", "size": "7GB"},
        ]
    
    def download_model(self, model_name: str, progress_callback=None):
        """MLX models are downloaded automatically on first load"""
        try:
            if progress_callback:
                progress_callback(f"Downloading {model_name} from Hugging Face...")
            
            # MLX handles download internally
            self.load_model(model_name)
            
            if progress_callback:
                progress_callback(f"Successfully loaded {model_name}")
            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error: {str(e)}")
            return False


class BackendManager:
    """Manages switching between Ollama and MLX backends"""
    
    def __init__(self):
        self.backends = {
            "ollama": OllamaBackend(),
        }
        
        # Only add MLX backend if available and on Apple Silicon
        if MLX_AVAILABLE and platform.system() == "Darwin" and self._is_apple_silicon():
            self.backends["mlx"] = MLXBackend()
            
        self.current_backend = "ollama"  # Default
        
    def _is_apple_silicon(self):
        """Check if running on Apple Silicon"""
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                  capture_output=True, text=True)
            return "Apple" in result.stdout
        except:
            return False
    
    def list_backends(self) -> list:
        """List available backends"""
        return list(self.backends.keys())
    
    def get_backend(self, backend_name: str = None) -> ModelBackend:
        """Get a specific backend or the current one"""
        if backend_name is None:
            backend_name = self.current_backend
            
        if backend_name not in self.backends:
            raise ValueError(f"Backend '{backend_name}' not available")
            
        return self.backends[backend_name]
    
    def set_backend(self, backend_name: str):
        """Switch to a different backend"""
        if backend_name not in self.backends:
            raise ValueError(f"Backend '{backend_name}' not available")
            
        self.current_backend = backend_name
    
    def is_mlx_available(self) -> bool:
        """Check if MLX backend is available"""
        return "mlx" in self.backends