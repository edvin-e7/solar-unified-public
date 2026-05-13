#!/usr/bin/env python3
"""Demo: Agents with CoVe verification.

Shows how each agent's decisions are verified before AUTO_FULL execution.
"""

from __future__ import annotations

import asyncio

from coordinator import get_coordinator


async def demo_agent_verification() -> None:
    """Run all agents and verify their AUTO_FULL decisions."""
    coordinator = get_coordinator()

    print("🤖 Agent Verification Demo")
    print("=" * 70)

    # Demo input
    demo_input = {
        "address": "123 Solar St, Boston MA",
        "image_url": "https://example.com/roof.jpg",
    }

    for agent in coordinator.all:
        print(f"\n📊 {agent.name.upper()}")
        print(f"  State: {agent.state}")

        try:
            # Run with verification
            verified, _result, verification = await coordinator.run_with_verification(
                agent.name, **demo_input
            )

            print(f"  State after: {agent.state}")
            print(f"  Verified: {verified}")

            if "confidence" in verification:
                print(f"  Confidence: {verification['confidence']:.0%}")

            if agent.state.value == "auto_full":
                status = "✓ APPROVED" if verified else "✗ REJECTED"
                print(f"  Decision: {status}")
            else:
                print(f"  Decision: {agent.state.value.upper()} (no verification needed)")

        except Exception as e:
            print(f"  Error: {e}")

    # Show leaderboard
    print("\n📈 Leaderboard")
    for rank_info in coordinator.leaderboard():
        print(f"  {rank_info['rank']}. {rank_info['agent']}: {rank_info['score']:.1f}")


if __name__ == "__main__":
    asyncio.run(demo_agent_verification())
