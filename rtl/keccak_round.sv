// Keccak-f[1600] combinational round function: theta -> rho -> pi -> chi -> iota.
// One full round per cycle -- see docs/SPEC.md for the architecture rationale.
//
// Lane addressing: lane(addr) = lane(x, y) where addr = 5*y + x, matching
// model/keccak_f1600.py and the byte<->lane mapping in docs/SPEC.md.
//
// Ports are flat 1600-bit packed vectors, not unpacked arrays -- Yosys's
// native SystemVerilog frontend (read_verilog -sv) rejects unpacked-array
// ports (confirmed directly: it errors on the port declaration itself, see
// scripts/synth_spike.sh's history). Internally this still works lane-by-
// lane via an unpacked array, sliced from/into the flat ports at the edge.
`timescale 1ns / 1ps

module keccak_round (
    input  logic [1599:0] state_in,
    input  logic [4:0]    round_idx,        // 0..23
    output logic [1599:0] state_out
);

  `include "keccak_tables.svh"

  function automatic logic [63:0] rotl64(input logic [63:0] v, input int unsigned n);
    rotl64 = (n == 0) ? v : ((v << n) | (v >> (64 - n)));
  endfunction

  logic [63:0] lane_in [0:24];

  genvar gx, gy, ga;

  generate
    for (ga = 0; ga < 25; ga++) begin : g_unpack
      assign lane_in[ga] = state_in[64*ga +: 64];
    end
  endgenerate

  // --- theta ---
  logic [63:0] col_parity [0:4];   // C[x]
  logic [63:0] col_diffuse [0:4];  // D[x]
  logic [63:0] theta_out [0:24];

  generate
    for (gx = 0; gx < 5; gx++) begin : g_col_parity
      assign col_parity[gx] = lane_in[gx] ^ lane_in[5 + gx] ^ lane_in[10 + gx]
                             ^ lane_in[15 + gx] ^ lane_in[20 + gx];
    end
    for (gx = 0; gx < 5; gx++) begin : g_col_diffuse
      assign col_diffuse[gx] = col_parity[(gx + 4) % 5] ^ rotl64(col_parity[(gx + 1) % 5], 1);
    end
    for (ga = 0; ga < 25; ga++) begin : g_theta
      assign theta_out[ga] = lane_in[ga] ^ col_diffuse[ga % 5];
    end
  endgenerate

  // --- rho: fixed per-lane rotation (compile-time constant, ~0 gates) ---
  logic [63:0] rho_out [0:24];
  generate
    for (ga = 0; ga < 25; ga++) begin : g_rho
      assign rho_out[ga] = rotl64(theta_out[ga], rot_amount(ga));
    end
  endgenerate

  // --- pi: fixed lane relabeling (compile-time constant, ~0 gates) ---
  logic [63:0] pi_out [0:24];
  generate
    for (ga = 0; ga < 25; ga++) begin : g_pi
      assign pi_out[ga] = rho_out[pi_src(ga)];
    end
  endgenerate

  // --- chi: A'[x,y] = A[x,y] xor ((~A[x+1,y]) & A[x+2,y]) ---
  logic [63:0] chi_out [0:24];
  generate
    for (gy = 0; gy < 5; gy++) begin : g_chi_y
      for (gx = 0; gx < 5; gx++) begin : g_chi_x
        localparam int A   = 5 * gy + gx;
        localparam int AP1 = 5 * gy + ((gx + 1) % 5);
        localparam int AP2 = 5 * gy + ((gx + 2) % 5);
        assign chi_out[A] = pi_out[A] ^ (~pi_out[AP1] & pi_out[AP2]);
      end
    end
  endgenerate

  // --- iota: round constant into lane 0 (x=0,y=0) only ---
  logic [63:0] lane_out [0:24];
  generate
    for (ga = 0; ga < 25; ga++) begin : g_iota
      if (ga == 0) begin : g_iota_lane0
        assign lane_out[ga] = chi_out[ga] ^ round_constant(round_idx);
      end else begin : g_iota_pass
        assign lane_out[ga] = chi_out[ga];
      end
    end
    for (ga = 0; ga < 25; ga++) begin : g_pack
      assign state_out[64*ga +: 64] = lane_out[ga];
    end
  endgenerate

endmodule
