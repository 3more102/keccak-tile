// Keccak-f[1600] state register + round counter + control, wrapping
// keccak_round. Area/synthesis spike scope: a flat parallel load/unload
// interface, not yet the byte-serial GPIO bus from docs/SPEC.md (that's
// real Phase 2 scope) -- this exists to get a real cell-area number for
// the register + round datapath, which dominate the estimate, before
// committing to the byte-serial bus's extra control logic.
//
// State is kept as a flat 1600-bit packed vector throughout, not an
// unpacked array, to match keccak_round's ports (see that file's header
// comment for why: Yosys's native SV frontend rejects unpacked-array ports).
`timescale 1ns / 1ps

module keccak_core (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          load,          // 1 cycle: capture state_in_flat
    input  logic          start,         // 1 cycle: begin 24-round permutation
    input  logic [1599:0] state_in_flat,
    output logic [1599:0] state_out_flat,
    output logic          busy,
    output logic          done
);

  logic [1599:0] state;
  logic [1599:0] round_out;
  logic [4:0]    round_idx;

  keccak_round u_round (
      .state_in  (state),
      .round_idx (round_idx),
      .state_out (round_out)
  );

  typedef enum logic [1:0] {ST_IDLE, ST_RUN, ST_DONE} state_e;
  state_e fsm_state;

  assign state_out_flat = state;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      fsm_state <= ST_IDLE;
      round_idx <= 5'd0;
      busy      <= 1'b0;
      done      <= 1'b0;
      state     <= 1600'h0;
    end else begin
      done <= 1'b0;
      unique case (fsm_state)
        ST_IDLE: begin
          if (load) begin
            state <= state_in_flat;
          end else if (start) begin
            fsm_state <= ST_RUN;
            round_idx <= 5'd0;
            busy      <= 1'b1;
          end
        end
        ST_RUN: begin
          state <= round_out;
          if (round_idx == 5'd23) begin
            fsm_state <= ST_DONE;
            busy      <= 1'b0;
            done      <= 1'b1;
          end else begin
            round_idx <= round_idx + 5'd1;
          end
        end
        ST_DONE: begin
          fsm_state <= ST_IDLE;
        end
        default: fsm_state <= ST_IDLE;
      endcase
    end
  end

endmodule
