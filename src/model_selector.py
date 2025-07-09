"""
Model selection and hardware detection for optimal performance
"""
import platform
import subprocess
import psutil
import streamlit as st
from model_backends import BackendManager, MLX_AVAILABLE

class ModelSelector:
    def __init__(self):
        self.system_info = self.detect_hardware()
        
    def detect_hardware(self):
        """Detect system hardware capabilities"""
        info = {
            "platform": platform.system(),
            "is_apple_silicon": self._is_apple_silicon(),
            "cpu_count": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "available_ram_gb": round(psutil.virtual_memory().available / (1024**3), 1),
            "gpu_info": self._detect_gpu()
        }
        return info
    
    def _is_apple_silicon(self):
        """Check if running on Apple Silicon and get chip details"""
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                      capture_output=True, text=True)
                chip_info = result.stdout.strip()
                
                if "Apple" in chip_info:
                    # Parse specific chip model
                    self.chip_details = self._parse_apple_chip(chip_info)
                    return True
            except:
                pass
        return False
    
    def _parse_apple_chip(self, chip_string):
        """Parse Apple Silicon chip details"""
        chip_specs = {
            "M1": {"gpu_cores": 8, "neural_cores": 16, "memory_bandwidth": 68.25},
            "M1 Pro": {"gpu_cores": 16, "neural_cores": 16, "memory_bandwidth": 200},
            "M1 Max": {"gpu_cores": 32, "neural_cores": 16, "memory_bandwidth": 400},
            "M1 Ultra": {"gpu_cores": 64, "neural_cores": 32, "memory_bandwidth": 800},
            "M2": {"gpu_cores": 10, "neural_cores": 16, "memory_bandwidth": 100},
            "M2 Pro": {"gpu_cores": 19, "neural_cores": 16, "memory_bandwidth": 200},
            "M2 Max": {"gpu_cores": 38, "neural_cores": 16, "memory_bandwidth": 400},
            "M2 Ultra": {"gpu_cores": 76, "neural_cores": 32, "memory_bandwidth": 800},
            "M3": {"gpu_cores": 10, "neural_cores": 16, "memory_bandwidth": 100},
            "M3 Pro": {"gpu_cores": 18, "neural_cores": 16, "memory_bandwidth": 150},
            "M3 Max": {"gpu_cores": 40, "neural_cores": 16, "memory_bandwidth": 400},
        }
        
        for chip_name, specs in chip_specs.items():
            if chip_name in chip_string:
                return {"model": chip_name, **specs}
        
        # Default for unknown Apple Silicon
        return {"model": "Apple Silicon", "gpu_cores": 8, "neural_cores": 16, "memory_bandwidth": 68.25}
    
    def _detect_gpu(self):
        """Detect GPU capabilities"""
        gpu_info = {"has_gpu": False, "vram_gb": 0, "type": "none"}
        
        # NVIDIA detection
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', 
                                   '--format=csv,noheader,nounits'], 
                                   capture_output=True, text=True)
            if result.returncode == 0:
                vram_mb = int(result.stdout.strip().split('\n')[0])
                gpu_info = {
                    "has_gpu": True, 
                    "vram_gb": round(vram_mb / 1024, 1), 
                    "type": "nvidia"
                }
        except:
            pass
            
        # Apple Silicon unified memory
        if self._is_apple_silicon():
            gpu_info = {
                "has_gpu": True, 
                "vram_gb": self.system_info.get("ram_gb", 0),  # Unified memory
                "type": "apple_silicon",
                "chip_details": getattr(self, 'chip_details', {})
            }
            
        return gpu_info
    
    def get_available_models(self):
        """Get list of available Ollama models"""
        try:
            result = subprocess.run(['ollama', 'list'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                models = []
                for line in lines:
                    if line:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])
                return models
        except:
            pass
        return []
    
    def recommend_models(self):
        """Recommend models based on hardware"""
        ram_gb = self.system_info["available_ram_gb"]
        gpu_info = self.system_info["gpu_info"]
        is_apple = self.system_info["is_apple_silicon"]
        
        # Embedding model recommendations
        embedding_models = {
            "premium": {
                "name": "mxbai-embed-large",
                "size": "560MB",
                "quality": "Best",
                "min_ram": 4
            },
            "balanced": {
                "name": "nomic-embed-text",
                "size": "274MB", 
                "quality": "Good",
                "min_ram": 2
            },
            "lightweight": {
                "name": "all-minilm",
                "size": "45MB",
                "quality": "Basic",
                "min_ram": 1
            }
        }
        
        # Backend manager to check available options
        backend_manager = BackendManager()
        
        # LLM recommendations based on hardware
        if is_apple and backend_manager.is_mlx_available():
            # Apple Silicon with MLX available - offer both options
            print(f"Apple Silicon detected: {gpu_info.get('chip_details', {}).get('model', 'Unknown')}")
            
            # Separate Ollama and MLX recommendations
            ollama_models = {
                "premium": {
                    "name": "qwen2.5:7b-instruct-q4_K_M",
                    "size": "4.4GB",
                    "quality": "Excellent (Metal Optimized)",
                    "min_ram": 8,
                    "context": "128K",
                    "note": "Optimized for Apple Silicon"
                },
                "balanced": {
                    "name": "mistral:7b-instruct-q4_K_M", 
                    "size": "4.1GB",
                    "quality": "Very Good (Metal Optimized)",
                    "min_ram": 6,
                    "context": "32K",
                    "note": "Optimized for Apple Silicon"
                },
                "lightweight": {
                    "name": "llama3.2:3b-instruct-q4_K_M",
                    "size": "2.0GB", 
                    "quality": "Good (Metal Optimized)",
                    "min_ram": 4,
                    "context": "8K",
                    "note": "Optimized for Apple Silicon"
                }
            }
        else:
            # Standard recommendations
            if ram_gb >= 16:
                llm_models = {
                    "premium": {
                        "name": "mistral-nemo:12b-instruct-2407-q4_K_M",
                        "size": "7.1GB",
                        "quality": "Excellent",
                        "min_ram": 10,
                        "context": "128K"
                    },
                    "balanced": {
                        "name": "qwen2.5:7b-instruct-q4_K_M",
                        "size": "4.4GB",
                        "quality": "Very Good",
                        "min_ram": 8,
                        "context": "128K"
                    },
                    "lightweight": {
                        "name": "llama3.2:3b-instruct-q4_K_M",
                        "size": "2.0GB",
                        "quality": "Good",
                        "min_ram": 4,
                        "context": "8K"
                    }
                }
            elif ram_gb >= 8:
                llm_models = {
                    "premium": {
                        "name": "mistral:7b-instruct-q4_K_M",
                        "size": "4.1GB",
                        "quality": "Very Good",
                        "min_ram": 6,
                        "context": "32K"
                    },
                    "balanced": {
                        "name": "llama3.2:3b-instruct-q4_K_M",
                        "size": "2.0GB",
                        "quality": "Good",
                        "min_ram": 4,
                        "context": "8K"
                    },
                    "lightweight": {
                        "name": "phi3:mini-instruct-q4_K_M",
                        "size": "2.2GB",
                        "quality": "Basic",
                        "min_ram": 3,
                        "context": "4K"
                    }
                }
            else:
                llm_models = {
                    "premium": {
                        "name": "llama3.2:3b-instruct-q4_K_M",
                        "size": "2.0GB",
                        "quality": "Good",
                        "min_ram": 4,
                        "context": "8K"
                    },
                    "balanced": {
                        "name": "phi3:mini-instruct-q4_K_M", 
                        "size": "2.2GB",
                        "quality": "Basic",
                        "min_ram": 3,
                        "context": "4K"
                    },
                    "lightweight": {
                        "name": "qwen2.5:0.5b",
                        "size": "400MB",
                        "quality": "Minimal",
                        "min_ram": 2,
                        "context": "8K"
                    }
                }
        
        # Select best models for current hardware
        selected_embedding = None
        for tier in ["premium", "balanced", "lightweight"]:
            if ram_gb >= embedding_models[tier]["min_ram"]:
                selected_embedding = embedding_models[tier]
                break
        
        selected_llm = None
        for tier in ["premium", "balanced", "lightweight"]:
            if ram_gb >= llm_models[tier]["min_ram"]:
                selected_llm = llm_models[tier]
                break
        
        return {
            "system_info": self.system_info,
            "embedding": selected_embedding or embedding_models["lightweight"],
            "llm": selected_llm or llm_models["lightweight"],
            "all_embedding_models": embedding_models,
            "all_llm_models": llm_models
        }
    
    def pull_model(self, model_name, progress_callback=None):
        """Pull a model from Ollama"""
        try:
            process = subprocess.Popen(
                ['ollama', 'pull', model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
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


def render_model_settings(st_container):
    """Render model settings UI in Streamlit"""
    selector = ModelSelector()
    recommendations = selector.recommend_models()
    
    # System info display
    st_container.markdown("### 🖥️ System Information")
    col1, col2 = st_container.columns(2)
    
    with col1:
        st_container.metric("Available RAM", f"{recommendations['system_info']['available_ram_gb']} GB")
        st_container.metric("CPU Cores", recommendations['system_info']['cpu_count'])
    
    with col2:
        gpu_info = recommendations['system_info']['gpu_info']
        if gpu_info['has_gpu']:
            if gpu_info['type'] == 'apple_silicon':
                st_container.metric("GPU", "Apple Silicon", delta="Metal Optimized")
                st_container.caption("🚀 Using unified memory & Metal acceleration")
            else:
                st_container.metric("GPU", gpu_info['type'].replace('_', ' ').title())
                st_container.metric("VRAM", f"{gpu_info['vram_gb']} GB")
        else:
            st_container.metric("GPU", "Not detected")
    
    st_container.markdown("---")
    
    # Model recommendations
    st_container.markdown("### 🤖 Recommended Models")
    
    # Special message for Apple Silicon
    if recommendations['system_info']['is_apple_silicon']:
        st_container.info("🍎 **Apple Silicon Detected!** Models will automatically use Metal GPU acceleration for optimal performance.")
    else:
        st_container.info(f"Based on your hardware, we recommend:")
    
    # Embedding model
    st_container.markdown("#### Embedding Model")
    rec_emb = recommendations['embedding']
    st_container.success(f"**{rec_emb['name']}** - {rec_emb['quality']} quality ({rec_emb['size']})")
    
    # LLM model
    st_container.markdown("#### Language Model") 
    rec_llm = recommendations['llm']
    if recommendations['system_info']['is_apple_silicon']:
        st_container.success(f"**{rec_llm['name']}** - {rec_llm['quality']} ({rec_llm['size']}, {rec_llm['context']} context)")
    else:
        st_container.success(f"**{rec_llm['name']}** - {rec_llm['quality']} quality ({rec_llm['size']}, {rec_llm['context']} context)")
    
    st_container.markdown("---")
    
    # Model selection
    st_container.markdown("### ⚙️ Model Configuration")
    
    # Get available models
    available_models = selector.get_available_models()
    
    # Embedding model selection
    all_emb_models = list(recommendations['all_embedding_models'].values())
    emb_model_names = [m['name'] for m in all_emb_models]
    emb_model_display = [f"{m['name']} ({m['size']}, {m['quality']})" for m in all_emb_models]
    
    current_emb = st.session_state.get('embedding_model', rec_emb['name'])
    try:
        current_emb_idx = emb_model_names.index(current_emb)
    except:
        current_emb_idx = 0
    
    selected_emb_display = st_container.selectbox(
        "Embedding Model",
        emb_model_display,
        index=current_emb_idx
    )
    selected_emb = emb_model_names[emb_model_display.index(selected_emb_display)]
    
    # LLM model selection
    all_llm_models = list(recommendations['all_llm_models'].values())
    llm_model_names = [m['name'] for m in all_llm_models]
    llm_model_display = [f"{m['name']} ({m['size']}, {m['quality']}, {m['context']})" for m in all_llm_models]
    
    current_llm = st.session_state.get('llm_model', rec_llm['name'])
    try:
        current_llm_idx = llm_model_names.index(current_llm)
    except:
        current_llm_idx = 0
    
    selected_llm_display = st_container.selectbox(
        "Language Model",
        llm_model_display,
        index=current_llm_idx
    )
    selected_llm = llm_model_names[llm_model_display.index(selected_llm_display)]
    
    # Download missing models
    missing_models = []
    if selected_emb not in available_models:
        missing_models.append(selected_emb)
    if selected_llm not in available_models:
        missing_models.append(selected_llm)
    
    if missing_models:
        st_container.warning(f"Missing models: {', '.join(missing_models)}")
        if st_container.button("Download Missing Models"):
            progress_text = st_container.empty()
            for model in missing_models:
                progress_text.text(f"Downloading {model}...")
                success = selector.pull_model(
                    model, 
                    lambda msg: progress_text.text(f"Downloading {model}: {msg}")
                )
                if success:
                    st_container.success(f"✅ Downloaded {model}")
                else:
                    st_container.error(f"❌ Failed to download {model}")
            progress_text.empty()
            st_container.rerun()
    
    # Save selections
    if st_container.button("Apply Model Configuration"):
        st.session_state.embedding_model = selected_emb
        st.session_state.llm_model = selected_llm
        st_container.success("✅ Model configuration saved!")
        st_container.rerun()
    
    return selected_emb, selected_llm