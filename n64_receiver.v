// Cause yosys to throw an error when we implicitly declare nets
`default_nettype none

module rx_module (
                  input            clk,
                  input            rx_enabled,
                  input            console_input,
                  output reg       rx_byte_ready,
                  output reg [7:0] rx_byte,
                  output reg       rx_finished,
                  output reg       rx_error,
                  `ifdef DEBUG_WIRE
                  output           debug_out
                  `endif
                  );

   reg [5:0]                      clk_pulses = 0;
   reg [5:0]                      timeout_pulses = 0;
   reg [3:0]                      bit_i = 7;
   reg                            current_bit;
   reg                            transaction_started = 0;
   reg                            console_input_sync;
   reg                            joy_latch = 1'b1;
   reg                            joy_latch_old = 1'b1;

   `ifdef DEBUG_WIRE
   reg                            read_debug = 0;
   assign debug_out = read_debug;
   `endif

   localparam [2:0]
     STATE_RESET = 0,
     STATE_WAIT = 1,
     STATE_RECEIVING = 2,
     STATE_GETBIT = 3,
     STATE_FINISHED = 4;
   reg [2:0]                     state = STATE_RESET;

   // Clock pulses per microsecond (at least 2)
   parameter ppu = 12;

   always @(posedge clk) begin
      console_input_sync <= console_input;
      joy_latch <= console_input_sync;
      joy_latch_old <= joy_latch;

      if (state == STATE_RESET) begin
         rx_finished <= 0;
         clk_pulses <= 0;
         timeout_pulses <= 0;
         transaction_started <= 0;
         bit_i <= 7;
         rx_byte_ready <= 0;

         `ifdef DEBUG_WIRE
         // signal beginning to idle for read
         read_debug <= 1;
         `endif

         state <= STATE_WAIT;
      end

      else if (state == STATE_WAIT) begin
         if (rx_enabled) begin
           `ifdef HOST_MODE
            // controller can respond very quickly, don't wait for silence
            state <= STATE_RECEIVING;
              `ifdef DEBUG_WIRE
              // go low when starting read process, high for each bit
              read_debug <= 0;
              `endif
            `else
            // wait for a period of silence
            if (joy_latch) begin
               if (timeout_pulses == 5*ppu) begin
                  state <= STATE_RECEIVING;
                  timeout_pulses <= 0;
                  `ifdef DEBUG_WIRE
                  // go low when starting read process, high for each bit
                  read_debug <= 0;
                  `endif
               end else begin
                  timeout_pulses <= timeout_pulses + 1;
               end
            end else begin
               timeout_pulses <= 0;
            end // else: !if(joy_latch)
            `endif
         end
      end

      else if (state == STATE_RECEIVING) begin
         if (rx_enabled) begin
            // detect falling edge
            if (joy_latch_old && !joy_latch) begin
               // Start transaction when input line goes low
               state <= STATE_GETBIT;
               // we'll miss a clock pulse before transaction condition
               // below is met
               clk_pulses <= 1;

               // reset stopbit timeout
               timeout_pulses <= 0;

               // shift in the last read bit, it's not a stop bit
               if (transaction_started) begin
                  rx_byte[bit_i] <= current_bit;
                  if (bit_i == 0) begin
                     bit_i <= 7;
                     rx_byte_ready <= 1;
                  end else begin
                     bit_i <= bit_i - 1;
                  end
               end else begin
                  transaction_started <= 1;
               end
            end else if (transaction_started) begin
               // Once bits are coming in, if the line idles for
               // too long then time out. Last bit should be the stop bit.
               if (timeout_pulses == 2*ppu) begin
                  state <= STATE_FINISHED;
               end
               timeout_pulses <= timeout_pulses + 1;
            end
         end else begin // if (rx_enabled)
            // received max number of bits, delay for stop bit
            if (timeout_pulses == 2*ppu) begin
               // get stop bit
               current_bit <= joy_latch;
            end else if (timeout_pulses == 4*ppu-1) begin
               state <= STATE_FINISHED;
            end
            timeout_pulses <= timeout_pulses + 1;
         end // else: !if(rx_enabled)
      end // if (state == STATE_RECEIVING)

      else if (state == STATE_GETBIT) begin
         rx_byte_ready <= 0;

         // receiving bit...
         case (clk_pulses)
           `ifdef DEBUG_WIRE
           2*ppu-2: begin
              // we're 2 cycles behind real time due to latching
              read_debug <= 1;
           end
           `endif

           // sample the bit 2us after initial low
           2*ppu: begin
              current_bit <= joy_latch;
           end

           `ifdef DEBUG_WIRE
           3*ppu + ppu/2 - 2: begin
              read_debug <= 0;
           end
           `endif

           // bit finishes at 4us; exit a little earlier
           3*ppu + ppu/2: begin
              state <= STATE_RECEIVING;
           end
         endcase // case (clk_pulses)

         clk_pulses <= clk_pulses + 1;
      end

      else if (state == STATE_FINISHED) begin
         if (!rx_finished) begin
            rx_error <= (current_bit != 1) || (bit_i != 7);
            rx_finished <= 1;
         end else begin
            rx_finished <= 0;
            state <= STATE_RESET;
         end
      end

   end
endmodule // rx_module
