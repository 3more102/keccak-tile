# Phase 0 area spike: results

`scripts/synth_spike.sh` synthesizes `rtl/keccak_core.sv` (1600-bit state
register + round datapath + minimal control FSM — not yet the byte-serial
GPIO bus from `docs/SPEC.md`) to real sky130hd standard cells, to check the
plan's ~20.4-27.3 kGE / 8x2-tile hand estimate against real numbers before
Phase 2 RTL goes deep. Reproduce with `bash scripts/synth_spike.sh`.

## Real numbers

From Yosys's `stat -liberty` report (`scripts/spike_results/keccak_core_spike.yosys.log`):

| | area (um2) | % | GE (/ NAND2_1's 3.7536 um2) |
|---|---|---|---|
| Sequential (1608 DFF + 1 DFST) | 40,264.9 | 32.9% | 10,727 |
| Combinational | 82,211.3 | 67.1% | 21,902 |
| **Total** | **122,476.2** | | **32,629** |

1,609 flip-flops synthesized (1608 `dfrtp_1` + 1 `dfstp_2`) against an
expected 1600 (state) + 5 (round_idx) + 2 (fsm_state) + 1 (busy) + 1 (done)
= 1609 -- an exact match, a good sanity check that synthesis captured the
design correctly rather than dropping or duplicating registers.

## Reconciling against the plan's hand estimate

32,629 GE is **~39% over the plan's central estimate (~23,500 GE)**, and
~20% over even its pessimistic end (~27,300 GE). That's a real gap, but not
a surprising one: it lands almost exactly inside the 20-40% band that
Option A's own design report explicitly flagged ("hand-estimated gate
counts routinely undershoot real synthesized area by 20-40% once glue
logic ... are accounted for") -- this measurement confirms that named risk
precisely rather than revealing a new one. Plausible contributors: `abc`
was run delay-constrained (`-D`, targeting the real 20ns/50MHz clock, not
minimum area) exactly as the real submission needs to; `synth -flatten`
re-optimizes theta/rho/pi/chi/iota as one flattened boolean network rather
than five separate hand-counted regions, so the mapped cells (a lot of
compound gates: `a21oi`, `o21ai`, `mux2i`, etc.) don't map 1:1 onto the
"XOR2-equivalent" units the hand estimate counted in.

## What this means for tile count -- better news than the GE gap suggests

The plan's "~1000 GE per 1x1 tile" heuristic turns out not to be
calibrated on the same NAND2-area basis used above: at Tiny Tapeout's own
stated tile dimensions (~160x100 to 167x108 um, i.e. 16,000-18,036 um2 per
1x1 tile), "1000 gates" would imply ~16-18 um2/gate -- roughly **5x** a
real sky130hd NAND2_1 (3.75 um2). Trusting the *direct* um2 comparison
instead of routing through that heuristic:

| tile um2 basis | tile-equivalents for the core (bus interface not yet added) |
|---|---|
| 16,000 (FAQ low estimate) | 7.65 |
| 17,955-18,036 (info.yaml / third-party) | 6.79-6.82 |

Adding the byte-serial bus interface from `docs/SPEC.md` (address counter,
load/unload muxing, synchronizers -- not yet built) will add some area, but
nowhere near enough to double it. **Real data suggests 6x2 (12 tiles,
~€840) may comfortably fit, not just the originally-planned 8x2 (16 tiles,
~€1,120)** -- a plausible ~€280 saving. 4x2 (8 tiles) is close to the
measured core-only number and almost certainly too tight once the bus
interface and real place-and-route routing congestion (raw cell area never
packs at 100% utilization) are added.

## What this number does *not* yet settle

This is a synthesis-only cell-area number, not a placed-and-routed one --
routing congestion, the required power distribution network, and Tiny
Tapeout's own harness/margin overhead aren't visible here. The only fully
authoritative answer to "how many tiles" is Tiny Tapeout's own hardening
flow (`tt-gds-action`, LibreLane-based) actually placing and routing the
final design. Treat 6x2 as a well-evidenced *candidate* to try first, not
a locked decision -- confirm before any real tile purchase (Phase 5).

## Follow-up worth trying, not yet done

`rho`'s rotation is implemented as a general `rotl64(v, n)` function
(shift-and-OR) called with a compile-time-constant `n` at each generate-loop
instantiation, rather than as explicit bit-slice concatenation. The plan
assumes rho costs ~0 gates because the rotation amount is a compile-time
constant; whether Yosys's constant-folding actually collapses the shift
expression into pure wiring, or synthesizes real shift logic per instance,
hasn't been directly confirmed. Worth an isolated before/after area check
in Phase 2 -- if the shift isn't fully folding, forcing it via explicit
concatenation is a legitimate, bounded area recovery, not a rewrite.
