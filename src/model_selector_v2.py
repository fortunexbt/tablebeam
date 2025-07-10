"""
Simplified model selection with proper hardware detection
"""
import platform
import subprocess
import psutil
import streamlit as st
from typing import Dict, List, Optional, Tuple
import time
import re

class HardwareDetector:
    """Detect hardware capabilities for optimal model selection"""
    
    def __init__(self):
        self.info = self._detect_all()
    
    def _detect_all(self) -> Dict:
        """Detect all hardware information"""
        info = {
            "platform": platform.system(),
            "cpu_count": psutil.cpu_count(),
            "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "available_ram_gb": round(psutil.virtual_memory().available / (1024**3), 1),
        }
        
        # Apple Silicon detection with specific chip info
        if platform.system() == "Darwin":
            apple_info = self._detect_apple_silicon()
            if apple_info:
                info.update(apple_info)
        
        # GPU detection
        gpu_info = self._detect_gpu()
        info.update(gpu_info)
        
        return info
    
    def _detect_apple_silicon(self) -> Optional[Dict]:
        """Detect Apple Silicon and return chip details"""
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True, text=True
            )
            chip_string = result.stdout.strip()
            
            if "Apple" not in chip_string:
                return None
            
            # Extract chip model - check M4 series first (newest)
            chip_model = "Unknown Apple Silicon"
            
            # Handle different formats - sometimes it's "Apple M4", sometimes just "M4"
            # Also handle variants like "M4 Pro", "M4 Max"
            chip_patterns = [
                ("Apple M4 Max", "M4 Max"),
                ("Apple M4 Pro", "M4 Pro"),
                ("Apple M4", "M4"),
                ("M4 Max", "M4 Max"),
                ("M4 Pro", "M4 Pro"),
                ("M4", "M4"),
                ("Apple M3 Max", "M3 Max"),
                ("Apple M3 Pro", "M3 Pro"),
                ("Apple M3", "M3"),
                ("M3 Max", "M3 Max"),
                ("M3 Pro", "M3 Pro"),
                ("M3", "M3"),
                ("Apple M2 Ultra", "M2 Ultra"),
                ("Apple M2 Max", "M2 Max"),
                ("Apple M2 Pro", "M2 Pro"),
                ("Apple M2", "M2"),
                ("M2 Ultra", "M2 Ultra"),
                ("M2 Max", "M2 Max"),
                ("M2 Pro", "M2 Pro"),
                ("M2", "M2"),
                ("Apple M1 Ultra", "M1 Ultra"),
                ("Apple M1 Max", "M1 Max"),
                ("Apple M1 Pro", "M1 Pro"),
                ("Apple M1", "M1"),
                ("M1 Ultra", "M1 Ultra"),
                ("M1 Max", "M1 Max"),
                ("M1 Pro", "M1 Pro"),
                ("M1", "M1"),
            ]
            
            for pattern, model_name in chip_patterns:
                if pattern in chip_string:
                    chip_model = model_name
                    break
            
            # Chip specifications (including M4 series)
            chip_specs = {
                "M1": {"gpu_cores": 8, "neural_cores": 16, "max_ram": 16},
                "M1 Pro": {"gpu_cores": 16, "neural_cores": 16, "max_ram": 32},
                "M1 Max": {"gpu_cores": 32, "neural_cores": 16, "max_ram": 64},
                "M1 Ultra": {"gpu_cores": 64, "neural_cores": 32, "max_ram": 128},
                "M2": {"gpu_cores": 10, "neural_cores": 16, "max_ram": 24},
                "M2 Pro": {"gpu_cores": 19, "neural_cores": 16, "max_ram": 32},
                "M2 Max": {"gpu_cores": 38, "neural_cores": 16, "max_ram": 96},
                "M2 Ultra": {"gpu_cores": 76, "neural_cores": 32, "max_ram": 192},
                "M3": {"gpu_cores": 10, "neural_cores": 16, "max_ram": 24},
                "M3 Pro": {"gpu_cores": 18, "neural_cores": 16, "max_ram": 36},
                "M3 Max": {"gpu_cores": 40, "neural_cores": 16, "max_ram": 128},
                # M4 series specifications
                "M4": {"gpu_cores": 10, "neural_cores": 16, "max_ram": 32},
                "M4 Pro": {"gpu_cores": 20, "neural_cores": 16, "max_ram": 64},
                "M4 Max": {"gpu_cores": 40, "neural_cores": 16, "max_ram": 128},
            }
            
            specs = chip_specs.get(chip_model, {"gpu_cores": 8, "neural_cores": 16, "max_ram": 16})
            
            return {
                "is_apple_silicon": True,
                "chip_model": chip_model,
                "gpu_cores": specs["gpu_cores"],
                "neural_cores": specs["neural_cores"],
                "max_ram": specs["max_ram"],
                "has_metal": True,
                "unified_memory": True
            }
            
        except Exception:
            return None
    
    def _detect_gpu(self) -> Dict:
        """Detect GPU capabilities"""
        gpu_info = {"has_discrete_gpu": False}
        
        # Check for NVIDIA GPU
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    parts = output.split(', ')
                    gpu_info["has_discrete_gpu"] = True
                    gpu_info["gpu_type"] = "NVIDIA"
                    gpu_info["gpu_name"] = parts[0]
                    gpu_info["vram_gb"] = round(int(parts[1].replace(' MiB', '')) / 1024, 1)
        except:
            pass
        
        return gpu_info


class ModelRecommender:
    """Recommend models based on hardware capabilities"""
    
    # Embedding models with actual characteristics
    EMBEDDING_MODELS = {
        "mxbai-embed-large": {
            "size_mb": 560,
            "dimensions": 1024,
            "quality": "excellent",
            "min_ram_gb": 4,
            "description": "Best quality, good for complex semantic search"
        },
        "nomic-embed-text": {
            "size_mb": 274,
            "dimensions": 768,
            "quality": "good",
            "min_ram_gb": 2,
            "description": "Balanced performance and quality"
        },
        "all-minilm": {
            "size_mb": 45,
            "dimensions": 384,
            "quality": "basic",
            "min_ram_gb": 1,
            "description": "Lightweight, fast, suitable for simple queries"
        }
    }
    
    # Language models with quantization options (sorted by size)
    LLM_MODELS = {
        # Small models (< 1GB)
        "qwen2.5:0.5b": {
            "size_gb": 0.4,
            "quality": "minimal",
            "min_ram_gb": 2,
            "context": 8192,
            "quantization": "Q4_K_M",
            "category": "Small"
        },
        # 3B models (2-3.5GB)
        "llama3.2:3b-instruct-q4_K_M": {
            "size_gb": 2.0,
            "quality": "good",
            "min_ram_gb": 4,
            "context": 8192,
            "quantization": "Q4_K_M",
            "category": "3B"
        },
        "phi3:mini": {
            "size_gb": 2.2,
            "quality": "basic",
            "min_ram_gb": 3,
            "context": 4096,
            "quantization": "Q4_K_M",
            "category": "Small"
        },
        "llama3.2:3b-instruct-q8_0": {
            "size_gb": 3.4,
            "quality": "better",
            "min_ram_gb": 5,
            "context": 8192,
            "quantization": "Q8_0",
            "category": "3B"
        },
        # 7B models (4-5GB)
        "mistral:7b-instruct-q4_K_M": {
            "size_gb": 4.1,
            "quality": "very_good",
            "min_ram_gb": 6,
            "context": 32000,
            "quantization": "Q4_K_M",
            "category": "7B"
        },
        "llama3.2:7b-instruct-q4_K_M": {
            "size_gb": 4.4,
            "quality": "very_good", 
            "min_ram_gb": 6,
            "context": 8192,
            "quantization": "Q4_K_M",
            "category": "7B"
        },
        "qwen2.5:7b-instruct-q4_K_M": {
            "size_gb": 4.4,
            "quality": "very_good",
            "min_ram_gb": 8,
            "context": 128000,
            "quantization": "Q4_K_M",
            "category": "7B"
        },
        # 13B models (7GB+)
        "mistral-nemo:12b-instruct-2407-q4_K_M": {
            "size_gb": 7.1,
            "quality": "excellent",
            "min_ram_gb": 10,
            "context": 128000,
            "quantization": "Q4_K_M",
            "category": "13B"
        }
    }
    
    def __init__(self, hardware_info: Dict):
        self.hardware = hardware_info
    
    def recommend_models(self) -> Dict:
        """Get model recommendations based on hardware"""
        available_ram = self.hardware["available_ram_gb"]
        is_apple_silicon = self.hardware.get("is_apple_silicon", False)
        
        recommendations = {
            "hardware_summary": self._get_hardware_summary(),
            "embedding": self._recommend_embedding_model(available_ram),
            "llm": self._recommend_llm_model(available_ram, is_apple_silicon),
            "notes": self._get_optimization_notes()
        }
        
        return recommendations
    
    def _get_hardware_summary(self) -> str:
        """Create a human-readable hardware summary"""
        parts = []
        
        if self.hardware.get("is_apple_silicon"):
            chip = self.hardware.get("chip_model", "Apple Silicon")
            parts.append(f"{chip} with {self.hardware.get('gpu_cores', '?')} GPU cores")
        elif self.hardware.get("has_discrete_gpu"):
            gpu = self.hardware.get("gpu_name", "GPU")
            vram = self.hardware.get("vram_gb", "?")
            parts.append(f"{gpu} ({vram}GB VRAM)")
        else:
            parts.append(f"{self.hardware['cpu_count']} CPU cores")
        
        parts.append(f"{self.hardware['available_ram_gb']}GB available RAM")
        
        return " • ".join(parts)
    
    def _recommend_embedding_model(self, available_ram: float) -> Dict:
        """Recommend best embedding model for available RAM"""
        for model_name, specs in self.EMBEDDING_MODELS.items():
            if available_ram >= specs["min_ram_gb"]:
                return {
                    "name": model_name,
                    "reason": specs["description"],
                    **specs
                }
        
        # Fallback to smallest model
        return {
            "name": "all-minilm",
            "reason": "Limited RAM available",
            **self.EMBEDDING_MODELS["all-minilm"]
        }
    
    def _recommend_llm_model(self, available_ram: float, is_apple_silicon: bool) -> Dict:
        """Recommend best LLM for available RAM"""
        suitable_models = []
        
        for model_name, specs in self.LLM_MODELS.items():
            if available_ram >= specs["min_ram_gb"]:
                suitable_models.append((model_name, specs))
        
        if not suitable_models:
            # Return smallest model if nothing fits
            smallest = min(self.LLM_MODELS.items(), key=lambda x: x[1]["size_gb"])
            return {
                "name": smallest[0],
                "reason": "Limited RAM - may run slowly",
                **smallest[1]
            }
        
        # Sort by quality (best first)
        quality_order = {"excellent": 4, "very_good": 3, "better": 2.5, "good": 2, "basic": 1, "minimal": 0}
        suitable_models.sort(key=lambda x: quality_order.get(x[1]["quality"], 0), reverse=True)
        
        best_model = suitable_models[0]
        
        # Special optimization for Apple Silicon
        reason = "Best quality within RAM constraints"
        if is_apple_silicon:
            reason += " (Metal GPU acceleration enabled)"
        
        return {
            "name": best_model[0],
            "reason": reason,
            **best_model[1]
        }
    
    def _get_optimization_notes(self) -> List[str]:
        """Get optimization tips based on hardware"""
        notes = []
        
        if self.hardware.get("is_apple_silicon"):
            notes.append("✅ Metal GPU acceleration is automatically enabled for all models")
            notes.append(f"✅ Unified memory architecture allows efficient {self.hardware['total_ram_gb']}GB usage")
            
            if self.hardware.get("chip_model", "").startswith("M4"):
                notes.append("✅ M4's next-gen Neural Engine provides industry-leading inference speeds")
                notes.append("✅ Enhanced GPU architecture with hardware ray tracing for ML workloads")
            elif self.hardware.get("chip_model", "").startswith("M3"):
                notes.append("✅ M3's enhanced Neural Engine provides faster inference")
        
        if self.hardware["available_ram_gb"] < 8:
            notes.append("⚠️ Consider closing other applications for better performance")
            notes.append("💡 Use Q4_K_M quantization for best size/quality balance")
        
        if self.hardware.get("has_discrete_gpu") and self.hardware.get("gpu_type") == "NVIDIA":
            notes.append("💡 Consider using CUDA-enabled models for faster inference")
        
        return notes


def render_model_settings_ui(container):
    """Render the model settings UI in Streamlit"""
    detector = HardwareDetector()
    recommender = ModelRecommender(detector.info)
    recommendations = recommender.recommend_models()
    
    # Get available models from Ollama
    available_models = []
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if parts:
                        available_models.append(parts[0])
    except:
        pass
    
    # Hardware summary
    container.markdown("### 🖥️ System Information")
    container.info(recommendations["hardware_summary"])
    
    # Detailed hardware info
    container.markdown("#### Hardware Details")
    col1, col2 = container.columns(2)
    
    with col1:
        col1.metric("Total RAM", f"{detector.info['total_ram_gb']}GB")
        col1.metric("Available RAM", f"{detector.info['available_ram_gb']}GB")
        col1.metric("CPU Cores", detector.info['cpu_count'])
    
    with col2:
        if detector.info.get("is_apple_silicon"):
            col2.metric("Chip", detector.info.get("chip_model", "Apple Silicon"))
            col2.metric("GPU Cores", detector.info.get("gpu_cores", "Unknown"))
            col2.metric("Neural Cores", detector.info.get("neural_cores", "Unknown"))
            
            # Check MLX availability
            try:
                import mlx
                col2.success("✅ MLX Available")
            except ImportError:
                col2.info("💡 MLX not installed")
        elif detector.info.get("has_discrete_gpu"):
            col2.metric("GPU", detector.info.get("gpu_name", "Unknown"))
            col2.metric("VRAM", f"{detector.info.get('vram_gb', '?')}GB")
    
    container.markdown("---")
    
    # Model recommendations
    container.markdown("### 🤖 Recommended Models")
    
    # Embedding model
    emb_rec = recommendations["embedding"]
    container.markdown("#### Embedding Model")
    container.success(f"**{emb_rec['name']}** - {emb_rec['reason']}")
    container.caption(f"Size: {emb_rec['size_mb']}MB • Dimensions: {emb_rec['dimensions']}")
    
    # Language model
    llm_rec = recommendations["llm"]
    container.markdown("#### Language Model")
    container.success(f"**{llm_rec['name']}** - {llm_rec['reason']}")
    container.caption(f"Size: {llm_rec['size_gb']}GB • Context: {llm_rec['context']:,} tokens • Quantization: {llm_rec['quantization']}")
    
    # Optimization notes
    if recommendations["notes"]:
        container.markdown("#### Optimization Tips")
        for note in recommendations["notes"]:
            container.write(note)
    
    container.markdown("---")
    
    # Model selection UI
    container.markdown("### ⚙️ Model Configuration")
    
    # Help text
    container.info("💡 Models marked with ✅ are installed. Select ⬇️ models to download them.")
    
    # Current selections
    current_embedding = st.session_state.get("embedding_model", emb_rec["name"])
    current_llm = st.session_state.get("llm_model", llm_rec["name"])
    
    # Embedding model selection with better formatting
    container.markdown("#### Embedding Model")
    embedding_models = ModelRecommender.EMBEDDING_MODELS
    emb_options = []
    for name, info in embedding_models.items():
        status = "✅" if name in available_models else "⬇️"
        emb_options.append(f"{status} {name} ({info['size_mb']}MB, {info['quality']})") 
    
    selected_emb_display = container.selectbox(
        "Select embedding model:",
        emb_options,
        index=next((i for i, opt in enumerate(emb_options) if current_embedding in opt), 0),
        label_visibility="collapsed"
    )
    selected_embedding = list(embedding_models.keys())[emb_options.index(selected_emb_display)]
    
    # Language model selection with categories
    container.markdown("#### Language Model")
    llm_models = ModelRecommender.LLM_MODELS
    
    # Group by category
    categories = {}
    for name, info in llm_models.items():
        cat = info.get('category', 'Other')
        if cat not in categories:
            categories[cat] = []
        status = "✅" if name in available_models else "⬇️"
        categories[cat].append((name, f"{status} {name} ({info['size_gb']}GB, {info['context']//1000}K context)"))
    
    # Create flat list with category headers
    llm_options = []
    llm_values = []
    for cat in ['Small', '3B', '7B', '13B']:
        if cat in categories:
            llm_options.append(f"--- {cat} Models ---")
            llm_values.append(None)
            for name, display in categories[cat]:
                llm_options.append(f"  {display}")
                llm_values.append(name)
    
    # Find current selection
    current_idx = 0
    for i, val in enumerate(llm_values):
        if val == current_llm:
            current_idx = i
            break
    
    selected_llm_display = container.selectbox(
        "Select language model:",
        llm_options,
        index=current_idx,
        label_visibility="collapsed"
    )
    selected_llm = llm_values[llm_options.index(selected_llm_display)] if selected_llm_display and "---" not in selected_llm_display else current_llm
    
    # Check for missing models
    missing_models = []
    if selected_embedding not in available_models:
        missing_models.append((selected_embedding, embedding_models[selected_embedding]['size_mb'], 'MB'))
    if selected_llm and selected_llm not in available_models:
        missing_models.append((selected_llm, llm_models[selected_llm]['size_gb'], 'GB'))
    
    if missing_models:
        container.warning(f"⬇️ Models need to be downloaded")
        total_size = sum(size if unit == 'MB' else size * 1024 for _, size, unit in missing_models)
        container.caption(f"Total download size: ~{total_size/1024:.1f}GB")
        
        if container.button("📥 Download Missing Models", type="primary", use_container_width=True):
            progress_container = container.container()
            progress_bar = progress_container.progress(0)
            status_text = progress_container.empty()
            log_container = progress_container.container()
            
            for i, (model, size, unit) in enumerate(missing_models):
                status_text.text(f"Downloading {model} ({size}{unit})...")
                
                # Show live output
                with log_container:
                    output_placeholder = st.empty()
                    
                    def update_progress(line):
                        # Parse ollama output for progress
                        if "pulling" in line.lower():
                            output_placeholder.code(line, language="text")
                        elif "%" in line:
                            # Try to extract percentage
                            try:
                                import re
                                match = re.search(r'(\d+)%', line)
                                if match:
                                    pct = int(match.group(1))
                                    model_progress = (i + pct/100) / len(missing_models)
                                    progress_bar.progress(model_progress)
                            except:
                                pass
                            output_placeholder.code(line, language="text")
                    
                    # Pull the model
                    import subprocess
                    process = subprocess.Popen(
                        ['ollama', 'pull', model],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            update_progress(line.strip())
                    
                    process.wait()
                    
                    if process.returncode == 0:
                        container.success(f"✅ Downloaded {model}")
                    else:
                        container.error(f"❌ Failed to download {model}")
                
                progress_bar.progress((i + 1) / len(missing_models))
            
            status_text.text("✅ All downloads complete!")
            import time
            time.sleep(2)
            st.rerun()
    
    # Apply button
    col1, col2 = container.columns([2, 1])
    with col1:
        # Check if embedding model is changing with data loaded
        embedding_changed = (selected_embedding != st.session_state.get("embedding_model") and 
                           st.session_state.get("data_loaded", False))
        
        # Check if anything changed
        config_changed = (selected_embedding != st.session_state.get("embedding_model") or
                         selected_llm != st.session_state.get("llm_model"))
        
        if config_changed:
            button_label = "🔄 Apply & Reload Data" if embedding_changed else "💾 Apply Changes"
            button_type = "primary"
            
            if embedding_changed:
                container.warning("⚠️ Embedding model change detected - data will be automatically reloaded")
        else:
            button_label = "✅ No Changes"
            button_type = "secondary"
        
        if container.button(button_label, type=button_type, use_container_width=True, disabled=not config_changed):
            old_embedding = st.session_state.get("embedding_model")
            st.session_state.embedding_model = selected_embedding
            st.session_state.llm_model = selected_llm
            
            if embedding_changed and st.session_state.get("data_loaded", False):
                # Force data reload
                st.session_state.force_reload = True
                container.success("✅ Models updated! Reloading data with new embedding model...")
            else:
                container.success("✅ Model configuration updated!")
            
            import time
            time.sleep(0.5)
            st.rerun()
    
    with col2:
        if container.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    return selected_embedding, selected_llm