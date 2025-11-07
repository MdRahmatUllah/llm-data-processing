"""Test JSON parsing utilities with various edge cases."""

import json
from src.common.json_utils import (
    sanitize_json_string,
    extract_json_from_markdown,
    parse_json_robust,
    validate_json_string
)


def test_sanitize_json_string():
    """Test JSON string sanitization."""
    print("=" * 80)
    print("Test 1: JSON String Sanitization")
    print("=" * 80)
    
    test_cases = [
        # (input, description)
        ('{"path": "C:\\Users\\file"}', "Unescaped backslashes in path"),
        ('{"text": "Line 1\\nLine 2"}', "Valid newline escape"),
        ('{"text": "Tab\\there"}', "Valid tab escape"),
        ('{"text": "Quote\\"here"}', "Valid quote escape"),
        ('{"text": "Backslash\\\\here"}', "Valid backslash escape"),
        ('{"text": "Invalid\\xescape"}', "Invalid \\x escape"),
        ('{"text": "Invalid\\aescape"}', "Invalid \\a escape"),
        ('{"latex": "\\boxed{42}"}', "LaTeX with \\b (backspace escape)"),
        ('{"unicode": "\\u0041"}', "Valid unicode escape"),
        ('{"unicode": "\\u00"}', "Invalid unicode escape (too short)"),
    ]
    
    for i, (test_input, description) in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {description}")
        print(f"Input:  {test_input}")
        
        sanitized = sanitize_json_string(test_input)
        print(f"Output: {sanitized}")
        
        # Try to parse the sanitized version
        try:
            parsed = json.loads(sanitized)
            print(f"✅ Successfully parsed: {parsed}")
        except json.JSONDecodeError as e:
            print(f"❌ Parse failed: {e}")
    
    print()


def test_extract_json_from_markdown():
    """Test JSON extraction from markdown."""
    print("=" * 80)
    print("Test 2: Extract JSON from Markdown")
    print("=" * 80)
    
    test_cases = [
        ('```json\n{"key": "value"}\n```', "JSON in ```json fence"),
        ('```\n{"key": "value"}\n```', "JSON in ``` fence"),
        ('{"key": "value"}', "Plain JSON without fence"),
        ('Some text\n```json\n{"key": "value"}\n```\nMore text', "JSON with surrounding text"),
    ]
    
    for i, (test_input, description) in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {description}")
        print(f"Input:  {repr(test_input)}")
        
        extracted = extract_json_from_markdown(test_input)
        print(f"Output: {repr(extracted)}")
        
        try:
            parsed = json.loads(extracted)
            print(f"✅ Successfully parsed: {parsed}")
        except json.JSONDecodeError as e:
            print(f"❌ Parse failed: {e}")
    
    print()


def test_parse_json_robust():
    """Test robust JSON parsing."""
    print("=" * 80)
    print("Test 3: Robust JSON Parsing")
    print("=" * 80)
    
    test_cases = [
        # Valid JSON
        ('{"key": "value"}', "Valid JSON"),
        
        # JSON with markdown fences
        ('```json\n{"key": "value"}\n```', "JSON in markdown fence"),
        
        # JSON with escape issues
        ('{"path": "C:\\Users\\file"}', "Unescaped backslashes"),
        
        # JSON with trailing commas
        ('{"key": "value",}', "Trailing comma in object"),
        ('[1, 2, 3,]', "Trailing comma in array"),
        
        # Complex case: markdown + escapes + trailing comma
        ('```json\n{"path": "C:\\Users\\file", "items": [1, 2,],}\n```', "Multiple issues"),
        
        # LaTeX in JSON
        ('{"solution": "The answer is \\boxed{42}"}', "LaTeX with \\b escape"),
        
        # Newlines and tabs
        ('{"text": "Line 1\\nLine 2\\tTabbed"}', "Valid escapes"),
    ]
    
    for i, (test_input, description) in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {description}")
        print(f"Input:  {repr(test_input)}")
        
        try:
            result = parse_json_robust(test_input)
            print(f"✅ Successfully parsed: {result}")
        except json.JSONDecodeError as e:
            print(f"❌ Parse failed: {e}")
    
    print()


def test_validate_json_string():
    """Test JSON validation."""
    print("=" * 80)
    print("Test 4: JSON Validation")
    print("=" * 80)
    
    test_cases = [
        ('{"key": "value"}', "Valid JSON"),
        ('{"key": "value",}', "Invalid: trailing comma"),
        ('{"key": "C:\\Users"}', "Invalid: unescaped backslash"),
        ('{key: "value"}', "Invalid: unquoted key"),
        ('{"key": undefined}', "Invalid: undefined value"),
    ]
    
    for i, (test_input, description) in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {description}")
        print(f"Input:  {test_input}")
        
        is_valid, error = validate_json_string(test_input)
        if is_valid:
            print(f"✅ Valid JSON")
        else:
            print(f"❌ Invalid JSON: {error}")
    
    print()


def test_real_world_example():
    """Test with a real-world example similar to what LLMs might generate."""
    print("=" * 80)
    print("Test 5: Real-World Example")
    print("=" * 80)
    
    # Simulate LLM response with common issues
    llm_response = '''```json
[
  {
    "problem": "What is the file path for the configuration?",
    "solution": "<|begin_of_thought|>\\nLet me check the documentation. The config file is located at C:\\Users\\Admin\\config.yaml\\n<|end_of_thought|>\\n<|begin_of_solution|>\\nThe configuration file path is \\boxed{C:\\Users\\Admin\\config.yaml}\\n<|end_of_solution|>"
  },
  {
    "problem": "Calculate 2 + 2",
    "solution": "<|begin_of_thought|>\\nThis is a simple addition: 2 + 2 = 4\\n<|end_of_thought|>\\n<|begin_of_solution|>\\nThe answer is \\boxed{4}\\n<|end_of_solution|>",
  }
]
```'''
    
    print("LLM Response:")
    print(llm_response)
    print()
    
    try:
        result = parse_json_robust(llm_response)
        print(f"✅ Successfully parsed!")
        print(f"Number of items: {len(result)}")
        for i, item in enumerate(result, 1):
            print(f"\nItem {i}:")
            print(f"  Problem: {item['problem'][:50]}...")
            print(f"  Solution: {item['solution'][:80]}...")
    except json.JSONDecodeError as e:
        print(f"❌ Parse failed: {e}")
    
    print()


def test_edge_cases():
    """Test edge cases and corner scenarios."""
    print("=" * 80)
    print("Test 6: Edge Cases")
    print("=" * 80)
    
    test_cases = [
        # Empty and whitespace
        ('{}', "Empty object"),
        ('[]', "Empty array"),
        ('  {"key": "value"}  ', "JSON with whitespace"),
        
        # Nested structures
        ('{"a": {"b": {"c": "value"}}}', "Deeply nested object"),
        ('[[[1, 2], [3, 4]], [[5, 6]]]', "Nested arrays"),
        
        # Special characters
        ('{"text": "Line\\nwith\\ttabs\\rand\\rreturns"}', "Multiple escape sequences"),
        ('{"emoji": "😀"}', "Unicode emoji"),
        
        # Large numbers
        ('{"big": 123456789012345678901234567890}', "Very large number"),
        ('{"float": 3.14159265358979323846}', "High precision float"),
    ]
    
    for i, (test_input, description) in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {description}")
        
        try:
            result = parse_json_robust(test_input)
            print(f"✅ Parsed successfully")
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("JSON Parsing Utilities Test Suite")
    print("=" * 80 + "\n")
    
    test_sanitize_json_string()
    test_extract_json_from_markdown()
    test_parse_json_robust()
    test_validate_json_string()
    test_real_world_example()
    test_edge_cases()
    
    print("=" * 80)
    print("All tests completed!")
    print("=" * 80)

