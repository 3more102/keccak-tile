#!/usr/bin/env python3
"""Anti-drift self-check for the Keccak-f[1600] golden model.

Two independent things are validated before this model is trusted as the
reference for anything downstream (RTL, mutation testing):

  1. The algorithmically-derived round constants and rho offsets
     (keccak_f1600.compute_round_constants/compute_rho_offsets, implemented
     from the FIPS 202 generating procedures) must exactly match XKCP's
     explicitly-published tables. A single wrong entry in either is the
     single highest-risk bug class for this whole project per the plan.
  2. Every one of theta/rho/pi/chi/iota, for every round, in both of
     XKCP's chained example permutations, must match this model's state
     step-for-step -- not just the final output. A mismatch here points
     directly at which step is wrong instead of just "output disagrees."

Exit code is nonzero on any mismatch, so this doubles as a CI gate.
"""
import sys

from keccak_f1600 import (
    compute_round_constants,
    compute_rho_offsets,
    keccak_f1600_steps,
    bytes_to_state,
    state_to_bytes,
)
from vectors.parse_xkcp import parse


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    data = parse()
    ok = True

    # --- 1. cross-check derived constants/offsets against XKCP's tables ---
    derived_rc = compute_round_constants()
    if derived_rc != data["rc"]:
        ok = False
        for i, (a, b) in enumerate(zip(derived_rc, data["rc"])):
            if a != b:
                fail(f"RC[{i}] derived={a:016X} xkcp={b:016X}")
    else:
        print(f"PASS  round constants: 24/24 derived == XKCP table")

    derived_rho = compute_rho_offsets()
    if derived_rho != data["rho_offsets"]:
        ok = False
        for x in range(5):
            for y in range(5):
                a, b = derived_rho[x][y], data["rho_offsets"][x][y]
                if a != b:
                    fail(f"RhoOffset[{x}][{y}] derived={a} xkcp={b}")
    else:
        print(f"PASS  rho offsets: 25/25 derived == XKCP table")

    if not ok:
        print("\nRefusing to trust either table for the step-by-step check below.")
        return 1

    # --- 2. step-by-step validation against both chained examples ---
    for ex_i, example in enumerate(data["examples"]):
        # round-trip the byte<->lane mapping itself before using it
        state_from_bytes = bytes_to_state(example["input_bytes"])
        if state_from_bytes != example["initial_state"]:
            ok = False
            fail(f"example {ex_i}: bytes_to_state(input) != XKCP's lane-word input")
        if state_to_bytes(example["initial_state"]) != example["input_bytes"]:
            ok = False
            fail(f"example {ex_i}: state_to_bytes(initial_state) != XKCP's input bytes")

        mismatches = 0
        lane_diffs_printed = 0
        final_state = None
        for round_idx, step_name, state in keccak_f1600_steps(
            example["initial_state"], derived_rc, derived_rho
        ):
            expected = example["rounds"][round_idx][step_name]
            if state != expected:
                mismatches += 1
                ok = False
                if lane_diffs_printed < 5:
                    for x in range(5):
                        for y in range(5):
                            if state[y][x] != expected[y][x] and lane_diffs_printed < 5:
                                fail(
                                    f"example {ex_i} round {round_idx} after {step_name}: "
                                    f"lane[{x}][{y}] got={state[y][x]:016X} "
                                    f"want={expected[y][x]:016X}"
                                )
                                lane_diffs_printed += 1
                elif lane_diffs_printed == 5:
                    fail("(further lane diffs suppressed)")
                    lane_diffs_printed += 1
            if round_idx == 23 and step_name == "iota":
                final_state = state

        if mismatches == 0:
            print(f"PASS  example {ex_i}: all 24 rounds x 5 steps == XKCP vectors")
        else:
            fail(f"example {ex_i}: {mismatches}/120 steps mismatched")

        got_out = state_to_bytes(final_state)
        if got_out != example["output_bytes"]:
            ok = False
            fail(f"example {ex_i}: final state_to_bytes != XKCP's 'State after permutation' bytes")
        else:
            print(f"PASS  example {ex_i}: final output bytes match XKCP exactly")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
