#!/usr/bin/env bash
# Phase 0 area spike: synthesize keccak_core (state register + round
# datapath) to real sky130hd standard cells and report cell area, to
# confirm or correct the ~20.4-27.3 kGE / 8x2-tile hand estimate from the
# project plan before Phase 2 RTL goes deep. Mirrors the proven pattern in
# ../LeNet5_ASIC_Project/asic/sta/run_ppa.sh (blackbox liberty cells first,
# then RTL, synth -flatten, abc -liberty, stat -liberty for the area report)
# rather than the ORFS `make` flow, which needs place-and-route -- broken in
# this environment; not needed for an area number.
#
# Usage: bash scripts/synth_spike.sh

set -euo pipefail

ORFS_ROOT="${ORFS_ROOT:-/root/OpenROAD-flow-scripts}"
PLATFORM_DIR="$ORFS_ROOT/flow/platforms/sky130hd"
LIB="$PLATFORM_DIR/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_HOME="$(cd "$HERE/.." && pwd)"
OUT="$HERE/spike_results"
mkdir -p "$OUT"

[ -f "$LIB" ] || { echo "ERROR: missing PDK liberty file $LIB" >&2; exit 1; }
for tool in yosys; do
    command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: $tool not on PATH" >&2; exit 1; }
done

TOP="keccak_core"
PERIOD_NS="${PERIOD_NS:-20}"   # Tiny Tapeout's default synth target: 50MHz
PERIOD_PS="$(awk -v p="$PERIOD_NS" 'BEGIN{printf "%d", p*1000}')"

YS="$OUT/${TOP}_spike.ys"
YLOG="$OUT/${TOP}_spike.yosys.log"
NETLIST="$OUT/${TOP}_spike.mapped.v"

cat > "$YS" <<EOF
read_liberty -lib $LIB
read_verilog -sv -I $PROJECT_HOME/rtl $PROJECT_HOME/rtl/keccak_round.sv
read_verilog -sv -I $PROJECT_HOME/rtl $PROJECT_HOME/rtl/keccak_core.sv
hierarchy -check -top $TOP
synth -top $TOP -flatten
dfflibmap -liberty $LIB
abc -liberty $LIB -D $PERIOD_PS
setundef -zero
opt_clean -purge
check
splitnets
opt_clean -purge
stat -liberty $LIB
write_verilog -noattr $NETLIST
EOF

echo "== yosys synth: $TOP @ ${PERIOD_NS}ns"
yosys -q -l "$YLOG" -s "$YS"

echo
echo "== area report (from $YLOG) =="
awk '/Chip area for module/{print} /Number of cells:/{print} /Number of wires:/{print}' "$YLOG"
echo
echo "== cell type breakdown =="
awk '/^\s+sky130_fd_sc_hd__/{print}' "$YLOG" | sort -k2 -n -r | head -20
