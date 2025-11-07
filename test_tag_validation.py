"""Test script to verify the updated tag validation logic."""

import sys
import re
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


def run_local_checks_simple(solution: str) -> dict:
    """
    Simplified version of the local checks for testing.

    Args:
        solution: The solution text to check

    Returns:
        Dictionary of check results
    """
    checks = {}

    # Check for thought section tags
    has_begin_thought = "<|begin_of_thought|>" in solution
    has_end_thought = "<|end_of_thought|>" in solution
    checks["has_thought_begin_token"] = has_begin_thought
    checks["has_thought_end_token"] = has_end_thought
    checks["thought_tags_properly_paired"] = has_begin_thought == has_end_thought

    # Check for solution section tags
    has_begin_solution = "<|begin_of_solution|>" in solution
    has_end_solution = "<|end_of_solution|>" in solution
    checks["has_solution_begin_token"] = has_begin_solution
    checks["has_solution_end_token"] = has_end_solution
    checks["solution_tags_properly_paired"] = has_begin_solution == has_end_solution

    # Check tag ordering (thought section should come before solution section)
    if has_begin_thought and has_begin_solution:
        thought_pos = solution.index("<|begin_of_thought|>")
        solution_pos = solution.index("<|begin_of_solution|>")
        checks["tags_in_correct_order"] = thought_pos < solution_pos
    else:
        checks["tags_in_correct_order"] = False

    # Check that closing tags come after opening tags (proper nesting)
    if has_begin_thought and has_end_thought:
        begin_pos = solution.index("<|begin_of_thought|>")
        end_pos = solution.index("<|end_of_thought|>")
        checks["thought_tags_properly_nested"] = begin_pos < end_pos
    else:
        checks["thought_tags_properly_nested"] = has_begin_thought == has_end_thought

    if has_begin_solution and has_end_solution:
        begin_pos = solution.index("<|begin_of_solution|>")
        end_pos = solution.index("<|end_of_solution|>")
        checks["solution_tags_properly_nested"] = begin_pos < end_pos
    else:
        checks["solution_tags_properly_nested"] = has_begin_solution == has_end_solution

    return checks


def test_tag_validation():
    """Test various tag validation scenarios."""
    
    print("=" * 80)
    print("Tag Validation Test Suite")
    print("=" * 80)
    print()

    # Test cases
    test_cases = [
        {
            "name": "Valid: Both tags properly paired and nested",
            "solution": "<|begin_of_thought|>Reasoning here<|end_of_thought|><|begin_of_solution|>Answer here<|end_of_solution|>",
            "expected_pass": True
        },
        {
            "name": "Invalid: Missing end_of_thought tag",
            "solution": "<|begin_of_thought|>Reasoning here<|begin_of_solution|>Answer here<|end_of_solution|>",
            "expected_pass": False
        },
        {
            "name": "Invalid: Missing end_of_solution tag",
            "solution": "<|begin_of_thought|>Reasoning here<|end_of_thought|><|begin_of_solution|>Answer here",
            "expected_pass": False
        },
        {
            "name": "Invalid: Missing both begin tags",
            "solution": "Just plain text without any tags",
            "expected_pass": False
        },
        {
            "name": "Invalid: Wrong order (solution before thought)",
            "solution": "<|begin_of_solution|>Answer here<|end_of_solution|><|begin_of_thought|>Reasoning here<|end_of_thought|>",
            "expected_pass": False
        },
        {
            "name": "Invalid: Improper nesting (end before begin)",
            "solution": "<|end_of_thought|>Reasoning here<|begin_of_thought|><|begin_of_solution|>Answer here<|end_of_solution|>",
            "expected_pass": False
        },
        {
            "name": "Valid: With boxed answer",
            "solution": "<|begin_of_thought|>Let me calculate 2+2<|end_of_thought|><|begin_of_solution|>The answer is \\boxed{4}<|end_of_solution|>",
            "expected_pass": True
        }
    ]
    
    # Run tests
    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print("-" * 80)

        solution = test_case["solution"]
        expected_pass = test_case["expected_pass"]

        # Run local checks
        checks = run_local_checks_simple(solution)

        # Display check results
        print("Check Results:")
        for check_name, result in sorted(checks.items()):
            status = "✅" if result else "❌"
            print(f"  {status} {check_name}: {result}")

        # Determine if all checks passed
        all_passed = all(checks.values())

        # Compare with expected
        test_passed = all_passed == expected_pass

        if test_passed:
            print(f"\n✅ TEST PASSED (Expected: {'pass' if expected_pass else 'fail'}, Got: {'pass' if all_passed else 'fail'})")
            passed += 1
        else:
            print(f"\n❌ TEST FAILED (Expected: {'pass' if expected_pass else 'fail'}, Got: {'pass' if all_passed else 'fail'})")
            failed += 1

        print()
    
    # Summary
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Total tests: {len(test_cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    if failed == 0:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {failed} test(s) failed")
        return False


if __name__ == "__main__":
    success = test_tag_validation()
    sys.exit(0 if success else 1)

