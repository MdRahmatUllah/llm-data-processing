"""Test Ollama performance and timeout behavior."""

import asyncio
import time
import httpx
from datetime import datetime


async def test_ollama_performance():
    """Test Ollama API performance with different timeout settings."""
    
    print("=" * 80)
    print("Ollama Performance Test")
    print("=" * 80)
    print()
    
    # Test configuration
    api_base = "http://localhost:11434/v1"
    model_name = "gpt-oss:20b"
    test_prompt = "Explain what a neural network is in 2-3 sentences."
    
    print(f"API Base: {api_base}")
    print(f"Model: {model_name}")
    print(f"Test Prompt: {test_prompt}")
    print()
    
    # Test 1: Check if Ollama is running
    print("-" * 80)
    print("Test 1: Checking Ollama Server Status")
    print("-" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                print("✅ Ollama server is running")
                models = response.json().get("models", [])
                print(f"   Available models: {len(models)}")
                for model in models:
                    print(f"   - {model.get('name', 'unknown')}")
            else:
                print(f"❌ Ollama server returned status {response.status_code}")
                return
    except Exception as e:
        print(f"❌ Failed to connect to Ollama server: {e}")
        print("   Make sure Ollama is running: http://localhost:11434")
        return
    
    print()
    
    # Test 2: Test with short timeout (should fail)
    print("-" * 80)
    print("Test 2: Testing with SHORT timeout (30 seconds)")
    print("-" * 80)
    print("Expected: This will likely timeout for a 20B model")
    print()
    
    timeout_config = httpx.Timeout(
        connect=10.0,
        read=30.0,  # Short timeout
        write=10.0,
        pool=5.0
    )
    
    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            start_time = time.time()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending request...")
            
            response = await client.post(
                f"{api_base}/chat/completions",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "user", "content": test_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 100
                },
                headers={
                    "Authorization": "Bearer ollama",
                    "Content-Type": "application/json"
                }
            )
            
            elapsed = time.time() - start_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Response received in {elapsed:.1f} seconds")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"✅ SUCCESS (unexpected!)")
                print(f"   Response: {content[:100]}...")
            else:
                print(f"❌ FAILED with status {response.status_code}")
                
    except httpx.ReadTimeout as e:
        elapsed = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️  TIMEOUT after {elapsed:.1f} seconds (expected)")
        print(f"   Error: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print()
    
    # Test 3: Test with long timeout (should succeed)
    print("-" * 80)
    print("Test 3: Testing with LONG timeout (600 seconds / 10 minutes)")
    print("-" * 80)
    print("Expected: This should succeed (may take several minutes)")
    print()
    
    timeout_config = httpx.Timeout(
        connect=10.0,
        read=600.0,  # Long timeout (10 minutes)
        write=10.0,
        pool=5.0
    )
    
    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            start_time = time.time()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending request...")
            print("   (This may take 3-5 minutes on CPU, please wait...)")
            
            response = await client.post(
                f"{api_base}/chat/completions",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "user", "content": test_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 100
                },
                headers={
                    "Authorization": "Bearer ollama",
                    "Content-Type": "application/json"
                }
            )
            
            elapsed = time.time() - start_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Response received in {elapsed:.1f} seconds")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"✅ SUCCESS!")
                print(f"   Response time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
                print(f"   Response: {content[:200]}...")
                print()
                print("📊 Performance Analysis:")
                print(f"   - Average time per request: {elapsed:.1f} seconds")
                print(f"   - Estimated time for 30 chunks: {(elapsed * 30)/60:.1f} minutes")
                print(f"   - Estimated time for 60 items (30 chunks × 2): {(elapsed * 60)/60:.1f} minutes")
                print()
                print("💡 Recommendations:")
                if elapsed > 300:  # > 5 minutes
                    print("   ⚠️  Very slow performance detected!")
                    print("   - Consider using a smaller model (e.g., qwen3:8b)")
                    print("   - Or use GPU acceleration if available")
                    print("   - Recommended timeout: 900 seconds (15 minutes)")
                elif elapsed > 180:  # > 3 minutes
                    print("   ⚠️  Slow performance (CPU-based inference)")
                    print("   - Current timeout (600s) should be sufficient")
                    print("   - Consider GPU acceleration for faster processing")
                elif elapsed > 60:  # > 1 minute
                    print("   ✅ Moderate performance")
                    print("   - Current timeout (600s) is more than sufficient")
                else:
                    print("   ✅ Excellent performance (likely GPU-accelerated)")
                    print("   - You can reduce timeout to 300s (5 minutes)")
                    print("   - You can increase parallel_chunks to 2-4")
            else:
                print(f"❌ FAILED with status {response.status_code}")
                print(f"   Response: {response.text}")
                
    except httpx.ReadTimeout as e:
        elapsed = time.time() - start_time
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏱️  TIMEOUT after {elapsed:.1f} seconds")
        print(f"   Error: {e}")
        print()
        print("❌ CRITICAL: Even 10-minute timeout is insufficient!")
        print("   Recommendations:")
        print("   1. Increase timeout to 1200s (20 minutes) in config/app.config.yaml")
        print("   2. Use a smaller model (e.g., qwen3:8b instead of gpt-oss:20b)")
        print("   3. Check if Ollama has sufficient resources (CPU/RAM/GPU)")
        print("   4. Restart Ollama server")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    
    print()
    print("=" * 80)
    print("Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_ollama_performance())

