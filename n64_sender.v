// Cause yosys to throw an error when we implicitly declare nets
`default_nettype none

module tx_module (
                    input [5:0] in_n_bytes, // number of byte to send
                    input [7:0] in_byte, // current byte to send
                    input       clk,
                    input       tx_enabled,
                    output reg  output_bit,
                    output reg  tx_next_byte,
                    output reg  tx_finished
                    );

   reg                           current_bit;
   reg [2:0]                     cur_bit_pos;
   reg [5:0]                     n_bytes;
   reg [5:0]                     clk_pulses;

   localparam [2:0]
     STATE_RESET = 0,
     STATE_WAIT = 1,
     STATE_SENDING = 2,
     STATE_SENDBIT = 3,
     STATE_STOPBIT = 4,
     STATE_FINISHED = 5;
   reg [2:0]                     state = STATE_RESET;

   // Clock pulses per microsecond (at least 2)
   parameter ppu = 12;

   always @(posedge clk) begin
      if (state == STATE_RESET) begin
         clk_pulses <= 0;
         tx_finished <= 0;
         tx_next_byte <= 0;
         output_bit <= 1;
         state <= STATE_WAIT;
      end

      else if (state == STATE_WAIT) begin
         if (tx_enabled) begin
            n_bytes <= in_n_bytes;

            if (in_n_bytes > 0) begin
               state <= STATE_SENDING;
               cur_bit_pos <= 7;
            end else begin
               // no bits to send
               state <= STATE_FINISHED;
            end
         end
      end

      else if (state == STATE_SENDING) begin
         // queue up next bit or stop bit
         if (n_bytes > 0) begin
            // select output bit
            current_bit <= in_byte[cur_bit_pos];

            // advance bit position
            if (cur_bit_pos > 0) begin
               cur_bit_pos <= cur_bit_pos - 1;
            end else begin
               cur_bit_pos <= 7;
               n_bytes <= n_bytes - 1;
               // signal for next input byte
               tx_next_byte <= 1;
            end

            // start sending current bit
            state <= STATE_SENDBIT;
            // drop line low to init bit transmission
            output_bit <= 0;
            // make up for missed clock pulse here
            clk_pulses <= 1;
         end else begin
            // send a stop bit
            state <= STATE_STOPBIT;
            clk_pulses <= 1;
            output_bit <= 0;
         end // else: !if(n_bytes > 0)
      end // if (state == STATE_SENDING)

      else if (state == STATE_SENDBIT) begin
         // always set this low after a cycle
         tx_next_byte <= 0;

         // send output bit after 1us
         if (clk_pulses == 1*ppu) begin
            output_bit <= current_bit;
         end

         // for the last microsecond go back high
         else if (clk_pulses == 3*ppu) begin
            output_bit <= 1;
         end

         else if (clk_pulses == 4*ppu - 1) begin
            state <= STATE_SENDING;
         end

         clk_pulses <= clk_pulses + 1;
      end

      else if (state == STATE_STOPBIT) begin
         // stop bit is slightly different from a 1 bit
         // goes high after 2us (4 clk pulses)
         if (clk_pulses == 2*ppu) begin
            output_bit <= 1;
         end
         else if (clk_pulses == 4*ppu - 1) begin
            state <= STATE_FINISHED;
         end

         clk_pulses <= clk_pulses + 1;
      end

      // reset when send ends
      else if (state == STATE_FINISHED) begin
         // signal finished for a cycle
         if (!tx_finished) begin
            tx_finished <= 1;
         end else begin
            tx_finished <= 0;
            state <= STATE_RESET;
         end
      end
   end // always @ (posedge clk)

endmodule // send_module
