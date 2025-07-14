import torch
import whisper

print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU device: {torch.cuda.get_device_name(0)}")
    print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# Test Whisper with CUDA
try:
    model = whisper.load_model("tiny", device="cuda")
    print("✅ Whisper loaded successfully on CUDA!")
except Exception as e:
    print(f"❌ Whisper CUDA error: {e}")