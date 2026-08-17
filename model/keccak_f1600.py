"""Keccak-f[1600] permutation, implemented from the FIPS 202 spec.

State representation: state[y][x] is the 64-bit lane at coordinate (x, y),
matching FIPS 202's A[x, y] indexing. This layout (row = y, column = x) is
not a free choice made here -- it's the layout XKCP's own reference test
vectors print in, confirmed by tracing theta's per-column diffusion through
a known non-trivial round (see docs/VECTOR_FORMAT.md).

Round constants and rho offsets are each produced two independent ways:
derived algorithmically from the spec's generating procedures (below), and
parsed from XKCP's explicit tables (vectors/parse_xkcp.py). validate_against_xkcp.py
cross-checks the two before trusting either -- the exact same "don't trust a
single source for a fixed lookup table" discipline the project plan calls
for, applied to this model before it's ever used to check RTL.
"""

W = 64
MASK = (1 << W) - 1


def rotl(v, n):
    """Rotate a W-bit lane left by n bits (n taken mod W)."""
    n %= W
    v &= MASK
    if n == 0:
        return v
    return ((v << n) | (v >> (W - n))) & MASK


def compute_round_constants(n_rounds=24):
    """Derive RC[0..n_rounds-1] via the LFSR generator from FIPS 202 Algorithm 5
    (equivalently, the standard Keccak reference software's LFSR86540 routine).
    """
    def lfsr_step(box):
        lfsr = box[0]
        bit = (lfsr & 0x01) != 0
        if lfsr & 0x80:
            lfsr = ((lfsr << 1) ^ 0x71) & 0xFF
        else:
            lfsr = (lfsr << 1) & 0xFF
        box[0] = lfsr
        return bit

    rc = []
    box = [0x01]
    for _ in range(n_rounds):
        lane = 0
        for j in range(7):
            bit_pos = (1 << j) - 1  # 2^j - 1: 0,1,3,7,15,31,63
            if lfsr_step(box):
                lane ^= (1 << bit_pos)
        rc.append(lane & MASK)
    return rc


def compute_rho_offsets():
    """Derive RhoOffset[x][y] via the triangular-number walk from FIPS 202
    Algorithm 2 ("Rho"). offsets[0][0] is left at 0 by construction -- the
    walk starting at (1,0) never revisits the origin in 24 steps.
    """
    offsets = [[0] * 5 for _ in range(5)]
    x, y = 1, 0
    for t in range(24):
        offsets[x][y] = ((t + 1) * (t + 2) // 2) % 64
        x, y = y, (2 * x + 3 * y) % 5
    return offsets


def empty_state():
    return [[0] * 5 for _ in range(5)]


def theta(state):
    c = [0] * 5
    for x in range(5):
        v = 0
        for y in range(5):
            v ^= state[y][x]
        c[x] = v
    d = [c[(x - 1) % 5] ^ rotl(c[(x + 1) % 5], 1) for x in range(5)]
    return [[state[y][x] ^ d[x] for x in range(5)] for y in range(5)]


def rho(state, rho_offsets):
    return [[rotl(state[y][x], rho_offsets[x][y]) for x in range(5)] for y in range(5)]


def pi(state):
    # FIPS 202 Algorithm 3: A'[x,y] = A[(x+3y) mod 5, x]
    new_state = empty_state()
    for x in range(5):
        for y in range(5):
            new_state[y][x] = state[x][(x + 3 * y) % 5]
    return new_state


def chi(state):
    # FIPS 202 Algorithm 4: A'[x,y] = A[x,y] xor ((NOT A[x+1,y]) AND A[x+2,y])
    new_state = empty_state()
    for x in range(5):
        for y in range(5):
            a = state[y][x]
            b = state[y][(x + 1) % 5]
            c = state[y][(x + 2) % 5]
            new_state[y][x] = a ^ ((~b & MASK) & c)
    return new_state


def iota(state, round_idx, rc_table):
    new_state = [row[:] for row in state]
    new_state[0][0] ^= rc_table[round_idx]
    return new_state


def keccak_f1600_steps(state, rc_table, rho_offsets):
    """Run all 24 rounds, yielding (round_idx, step_name, state) after every
    one of theta/rho/pi/chi/iota -- not just after full rounds -- so a
    mismatch against reference vectors localizes to one step, not one round.
    """
    s = state
    for r in range(24):
        s = theta(s)
        yield (r, "theta", s)
        s = rho(s, rho_offsets)
        yield (r, "rho", s)
        s = pi(s)
        yield (r, "pi", s)
        s = chi(s)
        yield (r, "chi", s)
        s = iota(s, r, rc_table)
        yield (r, "iota", s)


def keccak_f1600(state, rc_table=None, rho_offsets=None):
    """Full permutation, final state only."""
    rc_table = rc_table if rc_table is not None else compute_round_constants()
    rho_offsets = rho_offsets if rho_offsets is not None else compute_rho_offsets()
    final = state
    for _, _, final in keccak_f1600_steps(state, rc_table, rho_offsets):
        pass
    return final


def bytes_to_state(b):
    """FIPS 202: Lane(x,y) = bytes[8*(5y+x) : 8*(5y+x)+8], little-endian."""
    assert len(b) == 200, f"expected 200 bytes, got {len(b)}"
    state = empty_state()
    for y in range(5):
        for x in range(5):
            idx = 8 * (5 * y + x)
            state[y][x] = int.from_bytes(b[idx:idx + 8], "little")
    return state


def state_to_bytes(state):
    out = bytearray(200)
    for y in range(5):
        for x in range(5):
            idx = 8 * (5 * y + x)
            out[idx:idx + 8] = state[y][x].to_bytes(8, "little")
    return bytes(out)
