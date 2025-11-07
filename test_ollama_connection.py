"""Test script to verify Ollama connection and model availability."""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.model_client import create_model_client


async def test_ollama_connection():
    """Test connection to Ollama and verify models work."""
    
    # Load environment variables
    load_dotenv()
    
    api_base = os.getenv("MODEL_API_BASE", "http://localhost:11434/v1")
    api_key = os.getenv("MODEL_API_KEY", "ollama")
    gen_model = os.getenv("GENERATION_MODEL_NAME", "gpt-oss:20b")
    ver_model = os.getenv("VERIFICATION_MODEL_NAME", "qwen3:8b")
    
    print("=" * 80)
    print("Ollama Connection Test")
    print("=" * 80)
    print(f"API Base: {api_base}")
    print(f"Generation Model: {gen_model}")
    print(f"Verification Model: {ver_model}")
    print()
    
    # Create client
    print("Creating model client...")
    client = create_model_client(
        api_base=api_base,
        api_key=api_key,
        max_requests_per_minute=120,
        max_tokens_per_minute=200000,
        timeout=120,
        max_retries=3,
        backoff_base=2
    )
    
    try:
        # Test 1: Generation model
        print("-" * 80)
        print(f"Test 1: Testing generation model ({gen_model})...")
        print("-" * 80)
        
        messages = [
            {"role": "user", "content": "Say 'Hello, Ollama!' and nothing else."}
        ]
        
        response = await client.generate_with_retry(
            model=gen_model,
            messages=messages,
            temperature=0.0,
            max_tokens=50
        )
        
        content = response['choices'][0]['message']['content']
        print(f"✅ Generation model response: {content}")
        print()
        
        # Test 2: Verification model
        print("-" * 80)
        print(f"Test 2: Testing verification model ({ver_model})...")
        print("-" * 80)
        
        messages = [
            {"role": "user", "content": "Respond with only 'OK' if you can read this."}
        ]
        
        response = await client.generate_with_retry(
            model=ver_model,
            messages=messages,
            temperature=0.0,
            max_tokens=50
        )
        
        content = response['choices'][0]['message']['content']
        print(f"✅ Verification model response: {content}")
        print()
        
        # Test 3: JSON generation
        print("-" * 80)
        print(f"Test 3: Testing JSON generation with {gen_model}...")
        print("-" * 80)
        
        messages = [
            {
                "role": "user",
                "content": 'Generate a JSON object with two fields: "status" (set to "success") and "message" (set to "Ollama is working"). Return only the JSON, no markdown fences.'
            }
        ]
        
        response = await client.generate_with_retry(
            model=gen_model,
            messages=messages,
            temperature=0.0,
            max_tokens=100
        )
        
        content = response['choices'][0]['message']['content']
        print(f"✅ JSON response: {content}")
        print()
        
        # Test 4: Longer generation
        print("-" * 80)
        print(f"Test 4: Testing longer generation with {gen_model}...")
        print("-" * 80)
        
        messages = [
            {
                "role": "user",
                "content": "Write a short math problem and its solution. Use <|begin_of_thought|> before your reasoning and <|begin_of_solution|> before the final answer. Put the final answer in \\boxed{...} format."
            }
        ]
        
        response = await client.generate_with_retry(
            model=gen_model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        content = response['choices'][0]['message']['content']
        print(f"✅ Generated content:")
        print(content[:500] + ("..." if len(content) > 500 else ""))
        print()
        
        # Success!
        print("=" * 80)
        print("✅ All tests passed! Ollama is configured correctly.")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Run chunking: python -m src.script1_chunk_md --input-root ./input --project GC24_072_Eastern_Greenlink_4_HVDC --workspace ./workspace --config ./config/app.config.yaml")
        print("2. Run generation: python -m src.script2_generate_verify --workspace ./workspace --config ./config/app.config.yaml --parallel 2")
        print("3. Run packing: python -m src.script3_pack_json --workspace ./workspace --output ./output --config ./config/app.config.yaml")
        print()
        
    except Exception as e:
        print("=" * 80)
        print("❌ Test failed!")
        print("=" * 80)
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("1. Check if Ollama is running: ollama ps")
        print("2. Check if models are available: ollama list")
        print("3. Verify API endpoint: curl http://localhost:11434/v1/models")
        print("4. Check .env file configuration")
        print()
        raise
    
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_ollama_connection())

