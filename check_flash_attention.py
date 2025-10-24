#!/usr/bin/env python3
"""
Check if Flash Attention 2 is installed and being used by vLLM
"""

import sys

print("=" * 70)
print("Flash Attention 2 Status Check")
print("=" * 70)
print()

# 1. Check if flash-attn is installed
print("1️⃣ Checking flash-attn installation...")
try:
    import flash_attn
    print(f"   ✅ flash-attn {flash_attn.__version__} is installed")
    flash_installed = True
except ImportError:
    print("   ❌ flash-attn is NOT installed")
    print("   Install with: pip install flash-attn --no-build-isolation")
    flash_installed = False

print()

# 2. Check vLLM attention backend
print("2️⃣ Checking vLLM attention backend...")
try:
    from vllm.attention import get_attn_backend
    backend = get_attn_backend()
    backend_name = backend.__class__.__name__
    print(f"   ✅ vLLM using: {backend_name}")
    
    if "Flash" in backend_name or "flash" in str(backend):
        print("   ✅ Flash Attention is ACTIVE!")
    else:
        print(f"   ⚠️  Using {backend_name} (not Flash Attention)")
        print("   This is slower - Flash Attention provides 2-3x speedup")
except Exception as e:
    print(f"   ⚠️  Could not determine backend: {e}")

print()

# 3. Check CUDA availability
print("3️⃣ Checking CUDA...")
try:
    import torch
    if torch.cuda.is_available():
        print(f"   ✅ CUDA available: {torch.cuda.get_device_name(0)}")
        print(f"   ✅ CUDA version: {torch.version.cuda}")
    else:
        print("   ❌ CUDA not available")
except ImportError:
    print("   ❌ PyTorch not installed")

print()

# 4. Summary
print("=" * 70)
print("Summary:")
if flash_installed:
    print("✅ Flash Attention 2 is installed")
    print("✅ vLLM should use it automatically if CUDA is available")
    print()
    print("To verify it's actually being used:")
    print("  Check vLLM startup logs for 'using flash attention'")
    print("  Run: grep -i 'flash\|attention' /tmp/vllm.log")
else:
    print("❌ Flash Attention 2 is NOT installed")
    print()
    print("Expected performance impact:")
    print("  WITHOUT Flash Attention: ~15-20 tok/s")
    print("  WITH Flash Attention: ~40-60 tok/s (2-3x faster!)")
    print()
    print("To install:")
    print("  pip install flash-attn --no-build-isolation")
print("=" * 70)

