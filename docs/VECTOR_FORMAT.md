# XKCP vector file format

`model/vectors/KeccakF-1600-IntermediateValues.txt`, vendored from
[XKCP](https://github.com/XKCP/XKCP/blob/master/tests/TestVectors/KeccakF-1600-IntermediateValues.txt),
gives the round constants, rho offsets, and per-step intermediate state for
two chained Keccak-f[1600] permutations (all-zero input, then the first
permutation's output fed back in as the second's input).

## Round constants and rho offsets

Listed explicitly as `RC[round][0][0] = <16 hex digits>` (24 entries) and
`RhoOffset[x][y] = <decimal>` (25 entries). The rho offsets cross-check
directly against the well-known Keccak reference table (offset(1,0)=1,
offset(2,0)=62, offset(0,1)=36, ... ), confirming `RhoOffset[x][y]` uses x as
the first index, not y.

## State grid layout: `state[y][x]`, not `state[x][y]`

Each 5x5 state snapshot prints as 5 lines of 5 space-separated 16-hex-digit
words. Which grid axis is which isn't stated explicitly, so it was
determined empirically rather than assumed, using round 1's "After theta"
output (round 0 leaves the all-zero input untouched by theta -- only iota's
round-constant XOR into lane(0,0) makes anything nonzero, which isn't enough
to disambiguate axes).

Going into round 1, the state is all-zero except lane(0,0) = 1 (from round
0's iota). Theta's column parity is `C[x] = XOR of A[x, 0..4]`, and its
diffusion term `D[x] = C[x-1] xor rotl(C[x+1], 1)` depends only on x -- so
`D[x]` is added identically to *every* lane that shares that x, regardless
of y. Working through the five `D[x]` values by hand for this specific
input:

- `D[0] = 0`, `D[1] = 1`, `D[2] = 0`, `D[3] = 0`, `D[4] = 2`

Since every lane started at 0 except `A[0,0]=1` (and `D[0]=0` leaves that one
alone), every OTHER lane at a given x should equal `D[x]` after theta,
identically across whichever axis theta doesn't touch. The published output
for round 1's "After theta" is:

```
0000000000000001 0000000000000001 0000000000000000 0000000000000000 0000000000000002
0000000000000000 0000000000000001 0000000000000000 0000000000000000 0000000000000002
0000000000000000 0000000000000001 0000000000000000 0000000000000000 0000000000000002
0000000000000000 0000000000000001 0000000000000000 0000000000000000 0000000000000002
0000000000000000 0000000000000001 0000000000000000 0000000000000000 0000000000000002
```

Column index 1 (second word) is `1` on every line; column index 4 (fifth
word) is `2` on every line; column index 0 is `1` only on the first line.
That's exactly the `D[x]` pattern above, constant down each *column* -- so
**column index = x, line index = y**. `state[y][x]` is the layout used
throughout `model/keccak_f1600.py` and `model/vectors/parse_xkcp.py`.

This is exactly the class of bug this project's plan flags as the top
verification risk (a transposed fixed table, invisible to an all-zero
vector) -- worth spelling out precisely *because* it was derived, not
assumed, and because getting the axes backwards here would silently
poison every downstream check without ever producing an obviously-wrong
result (a transposed grid is still internally consistent with itself).

## Byte <-> lane mapping

Not independently re-derived from this file (the all-zero first example
can't distinguish byte order, since it's zero either way) -- implemented per
FIPS 202's stated convention (`Lane(x,y) = bytes[8(5y+x) : 8(5y+x)+8]`,
little-endian) and validated by round-tripping both examples' `Input of
permutation:` / `State after permutation:` byte lines against
`bytes_to_state`/`state_to_bytes`, including example 1's *non-zero* input
(chained from example 0's output) -- see `model/validate_against_xkcp.py`.
Both round-trips pass exactly, which is the real evidence for this mapping,
not the FIPS reading alone.
