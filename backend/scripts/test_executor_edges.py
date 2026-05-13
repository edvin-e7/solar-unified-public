#!/usr/bin/env python3
"""Edge case testing for executor roles — find and document bugs."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from executors.orchestrator import Orchestrator
from learning_journal import record


async def test_empty_batch() -> dict:
    """Test executor handles empty batch gracefully."""
    try:
        orch = Orchestrator()
        result = await orch.run_data_gathering_cycle([])
        record(
            phase="edge-test-empty-batch",
            outcome="passed",
            lesson="Empty batch handled: no crash, returns zeros",
            files=[],
            metadata={"result": result},
        )
        return {"test": "empty_batch", "passed": True, "result": result}
    except Exception as e:
        record(
            phase="edge-test-empty-batch",
            outcome="failed",
            lesson=f"Empty batch caused crash: {e}",
            files=[],
            error=str(e),
        )
        return {"test": "empty_batch", "passed": False, "error": str(e)}


async def test_single_address() -> dict:
    """Test with single address (minimal case)."""
    try:
        orch = Orchestrator()
        result = await orch.run_data_gathering_cycle(["Strandvägen 5, Stockholm"])
        record(
            phase="edge-test-single-address",
            outcome="passed",
            lesson=f"Single address works: {result}",
            files=[],
            metadata={"result": result},
        )
        return {"test": "single_address", "passed": True, "result": result}
    except Exception as e:
        record(
            phase="edge-test-single-address",
            outcome="failed",
            lesson=f"Single address failed: {e}",
            files=[],
            error=str(e),
        )
        return {"test": "single_address", "passed": False, "error": str(e)}


async def test_large_batch() -> dict:
    """Test with large batch (stress test)."""
    try:
        orch = Orchestrator()
        addresses = [
            f"Address {i}, Stockholm" for i in range(20)
        ]  # 20 addresses
        result = await orch.run_data_gathering_cycle(addresses)
        record(
            phase="edge-test-large-batch",
            outcome="passed",
            lesson=f"Large batch (20 addresses) works: scanned={result.get('scanned')}",
            files=[],
            metadata={"result": result},
        )
        return {"test": "large_batch", "passed": True, "result": result}
    except Exception as e:
        record(
            phase="edge-test-large-batch",
            outcome="failed",
            lesson=f"Large batch failed: {e}",
            files=[],
            error=str(e),
        )
        return {"test": "large_batch", "passed": False, "error": str(e)}


async def test_learning_without_data() -> dict:
    """Test learning cycle when journal is empty or has no patterns."""
    try:
        orch = Orchestrator()
        result = await orch.run_learning_cycle()
        record(
            phase="edge-test-learning-no-data",
            outcome="passed",
            lesson=f"Learning with no patterns: patterns_found={result.get('patterns_found')}",
            files=[],
            metadata={"result": result},
        )
        return {"test": "learning_no_data", "passed": True, "result": result}
    except Exception as e:
        record(
            phase="edge-test-learning-no-data",
            outcome="failed",
            lesson=f"Learning failed: {e}",
            files=[],
            error=str(e),
        )
        return {"test": "learning_no_data", "passed": False, "error": str(e)}


async def test_concurrent_cycles() -> dict:
    """Test multiple cycles running in parallel."""
    try:
        orch = Orchestrator()
        results = await asyncio.gather(
            orch.run_learning_cycle(),
            orch.run_learning_cycle(),
            orch.run_learning_cycle(),
        )
        record(
            phase="edge-test-concurrent-cycles",
            outcome="passed",
            lesson=f"Concurrent cycles work: {len(results)} cycles completed",
            files=[],
            metadata={"count": len(results)},
        )
        return {"test": "concurrent_cycles", "passed": True, "count": len(results)}
    except Exception as e:
        record(
            phase="edge-test-concurrent-cycles",
            outcome="failed",
            lesson=f"Concurrent cycles failed: {e}",
            files=[],
            error=str(e),
        )
        return {"test": "concurrent_cycles", "passed": False, "error": str(e)}


async def main() -> None:
    """Run all edge case tests."""
    print("=== EDGE CASE TESTING ===\n")

    tests = [
        test_empty_batch,
        test_single_address,
        test_large_batch,
        test_learning_without_data,
        test_concurrent_cycles,
    ]

    results = []
    for test_func in tests:
        print(f"Running: {test_func.__name__}...")
        result = await test_func()
        results.append(result)
        status = "✓ PASS" if result.get("passed") else "✗ FAIL"
        print(f"  {status}\n")

    # Summary
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print("\n=== SUMMARY ===")
    print(f"Passed: {passed}/{total}")
    for result in results:
        status = "✓" if result.get("passed") else "✗"
        print(f"  {status} {result.get('test')}")

    if passed == total:
        print("\n✓ All edge case tests PASSED")
    else:
        print(f"\n✗ {total - passed} tests FAILED — see journal for details")


if __name__ == "__main__":
    asyncio.run(main())
