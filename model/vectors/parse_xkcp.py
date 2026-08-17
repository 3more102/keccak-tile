"""Parser for XKCP's KeccakF-1600-IntermediateValues.txt.

File structure (confirmed by inspection, see docs/VECTOR_FORMAT.md):
  - a round-constant table:  RC[dd][0][0] = <16 hex digits>, dd = 00..23
  - a rho-offset table:      RhoOffset[x][y] = <decimal>, all 25 (x,y)
  - two "+++ Example ..." sections, the second chained from the first's
    output. Each has an "Input of permutation:" byte line, a "Same, with
    lanes as 64-bit words:" 5x5 block, 24 "--- Round N ---" blocks (each
    with "After theta/rho/pi/chi/iota:" 5x5 blocks), and a final
    "State after permutation:" byte line.

A "5x5 block" is 5 lines of 5 space-separated 16-hex-digit words; line y
holds lanes (x=0..4, y) -- see keccak_f1600.py's module docstring for how
that was established.
"""
import re
from pathlib import Path

VECTORS_PATH = Path(__file__).parent / "KeccakF-1600-IntermediateValues.txt"

_RC_RE = re.compile(r"^RC\[(\d+)\]\[0\]\[0\]\s*=\s*([0-9A-Fa-f]+)")
_RHO_RE = re.compile(r"^RhoOffset\[(\d+)\]\[(\d+)\]\s*=\s*(\d+)")
_BYTE_RE = re.compile(r"^[0-9A-Fa-f]{2}(\s+[0-9A-Fa-f]{2})*$")
_LANE_LINE_RE = re.compile(r"^[0-9A-Fa-f]{16}(\s+[0-9A-Fa-f]{16}){4}$")

STEP_NAMES = ("theta", "rho", "pi", "chi", "iota")


def _parse_lane_block(lines, i):
    state = [[0] * 5 for _ in range(5)]
    for y in range(5):
        words = lines[i + y].split()
        assert len(words) == 5, f"expected 5 words, got {words!r} at line {i + y}"
        for x, w in enumerate(words):
            state[y][x] = int(w, 16)
    return state, i + 5


def _parse_byte_line(line):
    return bytes(int(tok, 16) for tok in line.split())


def parse(path=None):
    path = Path(path) if path else VECTORS_PATH
    lines = path.read_text().splitlines()

    rc_table = {}
    rho_table = {}
    for line in lines:
        m = _RC_RE.match(line.strip())
        if m:
            rc_table[int(m.group(1))] = int(m.group(2), 16)
            continue
        m = _RHO_RE.match(line.strip())
        if m:
            rho_table[(int(m.group(1)), int(m.group(2)))] = int(m.group(3))
    assert len(rc_table) == 24, f"expected 24 round constants, found {len(rc_table)}"
    assert len(rho_table) == 25, f"expected 25 rho offsets, found {len(rho_table)}"
    rc_list = [rc_table[i] for i in range(24)]
    rho_grid = [[rho_table[(x, y)] for y in range(5)] for x in range(5)]

    example_starts = [i for i, l in enumerate(lines) if l.startswith("+++ Example")]
    assert len(example_starts) == 2, f"expected 2 example sections, found {len(example_starts)}"
    bounds = example_starts + [len(lines)]

    examples = []
    for ex_i in range(2):
        start, end = bounds[ex_i], bounds[ex_i + 1]
        block = lines[start:end]

        input_line_idx = next(i for i, l in enumerate(block) if l.startswith("Input of permutation:")) + 1
        input_bytes = _parse_byte_line(block[input_line_idx])
        assert len(input_bytes) == 200

        lanes_hdr_idx = next(i for i, l in enumerate(block) if l.startswith("Same, with lanes"))
        initial_state, _ = _parse_lane_block(block, lanes_hdr_idx + 1)

        rounds = []
        for r in range(24):
            marker = f"--- Round {r} ---"
            r_idx = next(i for i, l in enumerate(block) if l.strip() == marker)
            steps = {}
            cursor = r_idx
            for step_name in STEP_NAMES:
                hdr = f"After {step_name}:"
                h_idx = next(i for i in range(cursor, len(block)) if block[i].strip() == hdr)
                state, cursor = _parse_lane_block(block, h_idx + 1)
                steps[step_name] = state
            rounds.append(steps)

        out_idx = next(i for i, l in enumerate(block) if l.startswith("State after permutation:")) + 1
        output_bytes = _parse_byte_line(block[out_idx])
        assert len(output_bytes) == 200

        examples.append({
            "input_bytes": input_bytes,
            "initial_state": initial_state,
            "rounds": rounds,
            "output_bytes": output_bytes,
        })

    return {"rc": rc_list, "rho_offsets": rho_grid, "examples": examples}


if __name__ == "__main__":
    data = parse()
    print(f"RC: {len(data['rc'])} entries")
    print(f"rho offsets: {sum(len(col) for col in data['rho_offsets'])} entries")
    print(f"examples: {len(data['examples'])}, each with {len(data['examples'][0]['rounds'])} rounds")
