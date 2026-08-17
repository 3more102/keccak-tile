# keccak-tile

A Keccak-f[1600] permutation core — the sponge permutation behind SHA3/SHAKE (FIPS 202) and reused throughout ML-KEM/Kyber (FIPS 203) and ML-DSA/Dilithium (FIPS 204) for hashing, expansion, and sampling — designed, verified, and carried through physical implementation toward a real [Tiny Tapeout](https://tinytapeout.com/) silicon submission.

**Status: early build.** Golden model done and validated against official reference vectors. RTL and hardware verification are not done yet — this README will be updated as each stage lands, and nothing here should be read as a finished claim until it has a passing check behind it.

## Why this exists

A passing testbench proves the environment didn't complain, not that the design is right — especially for a permutation whose fixed rotation/permutation tables can be silently transposed while every self-consistency check still agrees with itself. This project's verification is built around that: every stage of the round function is checked against externally-sourced reference vectors (not just self-authored ones), and every mutation-testing survivor gets a written reason, not a silent pass.

## Architecture

One full round (theta→rho→pi→chi→iota) per clock cycle. 24 cycles for the permutation; the 1600-bit state is loaded and read back through Tiny Tapeout's narrow GPIO budget via a byte-addressed register interface, so a full load+permute+unload operation is dominated by I/O, not compute. Full register map and protocol: [`docs/SPEC.md`](docs/SPEC.md) (coming in the next commit).

## Layout

```
model/    Python golden model of Keccak-f[1600], cross-checked against official test vectors
rtl/      SystemVerilog RTL (round datapath, state/control core, bus interface)
tb/       Testbenches, protocol checkers, KAT-driven scoreboard
scripts/  Mutation campaign, regression, and equivalence-proof drivers
docs/     Spec, verification plan, and results write-ups
```

## Golden model

`model/keccak_f1600.py` implements the permutation from the FIPS 202 spec —
including deriving its own round constants (LFSR generator) and rho offsets
(triangular-number walk) algorithmically, rather than only hand-transcribing
published tables. Both derivations, and every one of theta/rho/pi/chi/iota
for all 24 rounds of two chained permutations, are cross-checked bit-for-bit
against [XKCP's official reference vectors](model/vectors/KeccakF-1600-IntermediateValues.txt) —
run it yourself:

```
python3 model/validate_against_xkcp.py
```

Checking *every step*, not just final output, matters here specifically: a
transposed rho offset or pi index is invisible to an all-zero test vector
(rotating or permuting zero is still zero) and can pass a self-consistent
check while silently disagreeing with the spec. See
[`docs/VECTOR_FORMAT.md`](docs/VECTOR_FORMAT.md) for how the vector file's
state-grid layout was determined empirically rather than assumed, for
exactly that reason.

## Documentation

- [`docs/SPEC.md`](docs/SPEC.md) — register map and bus protocol
- [`docs/VECTOR_FORMAT.md`](docs/VECTOR_FORMAT.md) — how the XKCP vector file's layout was determined
- `docs/VERIF_PLAN.md` — verification tiers and mutation methodology (coming)
- `docs/RESULTS.md` — numbers, as they land (coming)

## Honest limitations

Nothing has shipped yet — this section will carry the real, itemized gaps once there's a design to have gaps in.

## License

MIT — see [LICENSE](LICENSE).
