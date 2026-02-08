#!/usr/bin/env python3
"""
Validate Step Functions ASL JSON definition.

This script validates the ASL JSON syntax and checks for common issues.
For full validation, use: aws stepfunctions validate-state-machine-definition
"""

import json
import sys
from pathlib import Path


def validate_asl(asl_file: Path) -> bool:
    """
    Validate ASL JSON file.

    Args:
        asl_file: Path to ASL JSON file

    Returns:
        True if valid, False otherwise
    """
    errors = []

    # Check 1: Valid JSON
    try:
        with open(asl_file) as f:
            asl = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False

    print("✓ Valid JSON syntax")

    # Check 2: Required top-level fields
    required_fields = ["Comment", "StartAt", "States"]
    for field in required_fields:
        if field not in asl:
            errors.append(f"Missing required field: {field}")

    if not errors:
        print("✓ Required top-level fields present")

    # Check 3: StartAt state exists
    start_at = asl.get("StartAt")
    states = asl.get("States", {})

    if start_at not in states:
        errors.append(f"StartAt state '{start_at}' not found in States")
    else:
        print(f"✓ StartAt state '{start_at}' exists")

    # Check 4: All states are reachable or are terminal states
    reachable_states = set([start_at])
    terminal_types = {"Succeed", "Fail"}
    queue = [start_at]

    while queue:
        current = queue.pop(0)
        state = states.get(current, {})
        state_type = state.get("Type")

        # Get next states
        next_states = []

        if "Next" in state:
            next_states.append(state["Next"])

        if state_type == "Choice":
            for choice in state.get("Choices", []):
                if "Next" in choice:
                    next_states.append(choice["Next"])
            if "Default" in state:
                next_states.append(state["Default"])

        if state_type == "Parallel":
            for branch in state.get("Branches", []):
                branch_start = branch.get("StartAt")
                if branch_start:
                    next_states.append(branch_start)

        if state_type == "Map":
            iterator = state.get("Iterator", {})
            iterator_start = iterator.get("StartAt")
            if iterator_start:
                next_states.append(iterator_start)
            if "Next" in state:
                next_states.append(state["Next"])

        # Add Catch and Retry next states
        for catcher in state.get("Catch", []):
            if "Next" in catcher:
                next_states.append(catcher["Next"])

        # Add to reachable and queue
        for next_state in next_states:
            if next_state and next_state not in reachable_states:
                reachable_states.add(next_state)
                queue.append(next_state)

    unreachable = set(states.keys()) - reachable_states
    # Remove terminal states from unreachable
    unreachable = {
        s for s in unreachable if states.get(s, {}).get("Type") not in terminal_types
    }

    if unreachable:
        errors.append(f"Unreachable states: {', '.join(unreachable)}")
    else:
        print(f"✓ All {len(states)} states are reachable")

    # Check 5: All Next references exist
    all_next_refs = []
    for state_name, state in states.items():
        if "Next" in state:
            all_next_refs.append((state_name, state["Next"]))

        if state.get("Type") == "Choice":
            for choice in state.get("Choices", []):
                if "Next" in choice:
                    all_next_refs.append((state_name, choice["Next"]))
            if "Default" in state:
                all_next_refs.append((state_name, state["Default"]))

        for catcher in state.get("Catch", []):
            if "Next" in catcher:
                all_next_refs.append((state_name, catcher["Next"]))

    invalid_refs = [
        (state, next_state)
        for state, next_state in all_next_refs
        if next_state not in states
    ]

    if invalid_refs:
        for state, next_state in invalid_refs:
            errors.append(f"State '{state}' references non-existent state '{next_state}'")
    else:
        print("✓ All Next references are valid")

    # Check 6: Terminal states don't have Next
    for state_name, state in states.items():
        state_type = state.get("Type")
        if state_type in terminal_types and "Next" in state:
            errors.append(
                f"Terminal state '{state_name}' (type={state_type}) should not have 'Next'"
            )

    if not errors:
        print("✓ Terminal states are properly configured")

    # Check 7: Non-terminal states have Next or are Choice/Parallel/Map
    non_terminal_types = {"Task", "Pass", "Wait"}
    for state_name, state in states.items():
        state_type = state.get("Type")
        if state_type in non_terminal_types and "Next" not in state and "End" not in state:
            # Task states with waitForTaskToken might not have explicit Next in catch-all scenarios
            has_catch_all = any(
                "States.ALL" in c.get("ErrorEquals", []) and "Next" in c
                for c in state.get("Catch", [])
            )
            if not has_catch_all:
                errors.append(
                    f"Non-terminal state '{state_name}' (type={state_type}) must have 'Next' or 'End'"
                )

    # Check 8: Task states have Resource
    for state_name, state in states.items():
        if state.get("Type") == "Task" and "Resource" not in state:
            errors.append(f"Task state '{state_name}' must have 'Resource'")

    if not errors:
        print("✓ Task states have Resource defined")

    # Check 9: Choice states have Choices and Default
    for state_name, state in states.items():
        if state.get("Type") == "Choice":
            if "Choices" not in state or not state["Choices"]:
                errors.append(f"Choice state '{state_name}' must have non-empty 'Choices'")
            if "Default" not in state:
                # Default is optional but recommended
                print(f"⚠️  Warning: Choice state '{state_name}' has no 'Default'")

    # Check 10: Validate TimeoutSeconds and HeartbeatSeconds
    for state_name, state in states.items():
        timeout = state.get("TimeoutSeconds")
        heartbeat = state.get("HeartbeatSeconds")

        if timeout is not None and timeout <= 0:
            errors.append(
                f"State '{state_name}' has invalid TimeoutSeconds: {timeout} (must be > 0)"
            )

        if heartbeat is not None:
            if heartbeat <= 0:
                errors.append(
                    f"State '{state_name}' has invalid HeartbeatSeconds: {heartbeat} (must be > 0)"
                )
            if timeout is not None and heartbeat >= timeout:
                errors.append(
                    f"State '{state_name}' has HeartbeatSeconds ({heartbeat}) >= TimeoutSeconds ({timeout})"
                )

    # Print summary
    print("\n" + "=" * 60)
    if errors:
        print("❌ VALIDATION FAILED\n")
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error}")
        print("\n" + "=" * 60)
        return False
    else:
        print("✅ VALIDATION PASSED")
        print(f"\nState machine: {asl.get('Comment', 'N/A')}")
        print(f"States: {len(states)}")
        print(f"Start: {start_at}")
        print("=" * 60)
        return True


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        asl_file = Path(sys.argv[1])
    else:
        asl_file = Path(__file__).parent / "pipeline.asl.json"

    if not asl_file.exists():
        print(f"❌ File not found: {asl_file}")
        sys.exit(1)

    print(f"Validating: {asl_file}\n")

    if validate_asl(asl_file):
        print("\n💡 For full AWS validation, run:")
        print(
            f"   aws stepfunctions validate-state-machine-definition --definition file://{asl_file}"
        )
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
