# Spec

## The core

Keccak-f[1600]: the FIPS 202 permutation over a 1600-bit state (5x5 array of
64-bit lanes), 24 rounds of theta / rho / pi / chi / iota. This project
implements the raw permutation as an accelerator core, not a full SHA3/SHAKE
sponge (no padding, no rate/capacity split, no absorb/squeeze bookkeeping) --
the host is responsible for sponge construction around it, exactly like a
real crypto-accelerator IP block.

## Architecture

One full round per clock cycle: theta -> rho -> pi -> chi -> iota computed
combinationally between two state-register cycles. Rho and pi cost ~0 logic
gates -- both are compile-time-constant wiring (fixed per-lane rotation
amounts, fixed lane relabeling), not runtime-selected. 24 cycles for the
permutation itself.

## Bus interface

Tiny Tapeout gives 24 usable GPIO regardless of tile size: 8 dedicated
inputs, 8 dedicated outputs, 8 bidirectional, plus clk/rst_n/ena. The
1600-bit state cannot be exposed directly, so it's loaded and read back
8 bits at a time through a byte-addressed register interface.

| Pin(s) | Direction | Function |
|---|---|---|
| `ui_in[7:0]` | in | `DATA_IN` -- byte written during LOAD |
| `uo_out[7:0]` | out | `DATA_OUT` -- byte read during UNLOAD (registered) |
| `uio[1:0]` | out | `BUSY`, `DONE` |
| `uio[3:2]` | out | `PHASE[1:0]`: `00` IDLE / `01` LOAD / `10` PERMUTE / `11` UNLOAD |
| `uio[4]` | in | `STROBE` -- accept byte & advance address (LOAD) / advance & present next byte (UNLOAD) |
| `uio[5]` | in | `START`/`GO` |
| `uio[7:6]` | in | reserved, tie 0 |

### Byte <-> lane mapping

The 1600-bit state is exactly 200 bytes. Byte address `a` (0-199) maps to
lane `(x, y)` and byte-within-lane `k` as:

```
lane_index    = a / 8            # 0..24
x             = lane_index % 5
y             = lane_index / 5
k             = a % 8            # 0 = LSB of the lane
```

i.e. lanes in address order `(0,0), (1,0), (2,0), (3,0), (4,0), (0,1), ...`
(x fastest, then y), each lane little-endian -- this is exactly FIPS 202's
own `Lane(x,y) = S[8*(5y+x) .. 8*(5y+x)+7]` byte convention, and matches
`bytes_to_state`/`state_to_bytes` in `model/keccak_f1600.py` (cross-checked
against XKCP's reference vectors -- see `model/validate_against_xkcp.py`).
Host software can therefore treat the state as a flat 200-byte array with a
straight memcpy against any standard byte-oriented Keccak reference; no
bit-shuffling required on either side of the interface.

### Sequencing

1. Reset: `rst_n` low -> `PHASE=IDLE`, address pointer = 0, `BUSY=DONE=0`.
2. Host pulses `START` while `PHASE=IDLE` -> `PHASE=LOAD`, `BUSY=1`.
3. Repeat x200: host drives `ui_in` with the next byte (address order above),
   pulses `STROBE` for exactly 1 cycle. Core latches the byte, advances the
   pointer. Fully synchronous to `clk`; no core-imposed wait state.
4. Host pulses `START` -> `PHASE=PERMUTE`, pointer resets, 24-cycle
   permutation runs autonomously. `BUSY` stays high.
5. On completion: `BUSY` deasserts, `DONE` pulses for 1 cycle, `PHASE` auto-
   advances to `UNLOAD`, pointer resets to 0, byte 0 presented on `uo_out`.
6. Repeat x200: host reads `uo_out` (stable at the current pointer), pulses
   `STROBE` -> pointer advances, next byte presented one cycle later.
7. After the 200th unload strobe, `PHASE` returns to `IDLE`.

`START` and `STROBE` originate off-chip and are treated as asynchronous to
the DUT clock -- routed through a 2-flop synchronizer + edge-detector rather
than assumed clock-aligned with the host.

### Cycle budget

200 (load) + 24 (permute) + ~204 (unload + phase transitions) ~= 428 cycles
per full operation, ~8.6us at Tiny Tapeout's default 50MHz synth target. I/O
dominates wall-clock (~94%), not the datapath -- the permutation itself is a
small fraction of one operation. That contrast is the honest, quotable
throughput number: this core computes a full 24-round permutation in 24
cycles; the narrow GPIO, not the accelerator, sets the pace of a one-shot
call.

## Verification strategy

See `docs/VERIF_PLAN.md`. The short version: every round's *full* state is
checked against externally-sourced reference vectors (XKCP's
`KeccakF-1600-IntermediateValues.txt`), not just final output -- because a
transposed rho offset or pi index is exactly the kind of bug that a
self-consistent testbench can miss entirely (rotating/permuting zero is
still zero; only real, externally-authored non-trivial test data catches a
mistranscribed fixed table).
