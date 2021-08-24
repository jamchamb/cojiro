// Cause yosys to throw an error when we implicitly declare nets
`default_nettype none
`define SEVENSEG_DISPLAY
`define HOST_MODE

// Project entry point
module top (
	input  CLK,
    input  RX, // RS232
    output TX, // RS232
	input  BTN_N, BTN1, BTN2, BTN3,
    inout  P1B1, // bidirectional IO w/ console
	output LED1, LED2, LED3, LED4, LED5,
    `ifdef SEVENSEG_DISPLAY
	output P1A1, P1A2, P1A3, P1A4, P1A7, P1A8, P1A9, P1A10,
    `endif
    `ifdef DEBUG_WIRE
    output P1B10, // debug output
    `endif
);

   `ifdef DEBUG_WIRE
   wire debug_wire;
   assign P1B10 = debug_wire;
   `endif

   // State constants
   localparam [2:0]
     STATE_RESET = 0,
     STATE_UART_LEN = 1,
     STATE_UART_CMD = 2,
     STATE_TX = 3,
     STATE_RX = 4,
     STATE_FORWARD_LEN = 5,
     STATE_FORWARD_TX = 6,
     STATE_FORWARD_RX = 7;
   reg [2:0] state = STATE_RESET;
   reg       error_flag = 0;

   // expecting at most 35 bytes (1 cmd byte + 34 optional data bytes)
   localparam MAX_RX_BYTES = 33;
   localparam MAX_TX_BYTES = 35;

   // Joybus RX module stuff
   reg [5:0]   rx_n_bytes = 0;
   reg [7:0]   rx_bytes [0:MAX_RX_BYTES-1];
   reg [7:0]   rx_byte;
   reg         rx_byte_ready;
   reg         rx_enabled = 0;
   reg         rx_finished;
   reg         rx_error;

   wire        rx_enable_wire;
   assign rx_enable_wire = rx_enabled;

   // Joybus TX module stuff
   reg [5:0]   tx_n_bytes;
   reg [7:0]   tx_bytes [0:MAX_TX_BYTES-1];
   reg [7:0]   tx_byte;
   reg         tx_output_bit;
   reg         tx_enabled = 0;
   reg         tx_next_byte;
   reg         tx_finished;

   wire       tx_enable_wire;
   assign tx_enable_wire = tx_enabled;

   // Console data IO line (open drain output)
   // setup is a little weird because trying to assign Z for 1 later didn't work
   // We pull to ground for a 0, release the line for 1 and it should return to 3.3V
   wire       console_input;
   assign P1B1 = (tx_enabled && tx_output_bit == 0) ? 1'b 0 : 1'b z;
   assign console_input = P1B1;

   // General TX/RX buffer index
   reg [5:0] buf_i = 0;

   // LED assignments
   assign LED1 = error_flag;
   assign LED2 = rx_n_bytes == MAX_RX_BYTES;
   assign LED3 = rx_error;
   assign LED4 = rx_enabled;
   assign LED5 = !console_input;

   `ifdef SEVENSEG_DISPLAY
   // 7 segment control line bus
   wire [7:0]  seven_segment;

   // Assign 7 segment control line bus to Pmod pins
   assign { P1A10, P1A9, P1A8, P1A7, P1A4, P1A3, P1A2, P1A1 } = seven_segment;

   wire [7:0] display_wire;
   assign display_wire = {5'd 0, state[2:0]};

   // 7 segment display control Pmod 1A
   seven_seg_ctrl seven_segment_ctrl (
		.CLK(CLK),
        .din(display_wire),
		.dout(seven_segment)
	);
   `endif

   tx_module sender (
                       .in_n_bytes(tx_n_bytes),
                       .in_byte(tx_byte),
                       .clk(CLK),
                       .tx_enabled(tx_enable_wire),
                       .output_bit(tx_output_bit),
                       .tx_next_byte(tx_next_byte),
                       .tx_finished(tx_finished)
                       );

   rx_module receiver (
                       .clk(CLK),
                       .rx_enabled(rx_enable_wire),
                       .console_input(console_input),
                       .rx_byte_ready(rx_byte_ready),
                       .rx_byte(rx_byte),
                       .rx_finished(rx_finished),
                       .rx_error(rx_error),
                       `ifdef DEBUG_WIRE
                       .debug_out(debug_wire)
                       `endif
                       );

   // UART stuff
   reg        uart_reset = 0;
   reg        uart_transmit = 0;
   reg [7:0]  uart_tx_byte;
   wire       uart_received;
   wire [7:0] uart_rx_byte;
   wire       uart_is_receiving;
   wire       uart_is_transmitting;
   wire       uart_recv_error;

   localparam [1:0]
     UART_SYNC_MAGIC1 = 0,
     UART_SYNC_MAGIC2 = 1,
     UART_SYNC_TX_LEN = 2,
     UART_SYNC_RX_LEN = 3;
   reg [1:0]  uart_fwd_sync_state = UART_SYNC_MAGIC1;

   uart #(
		  .baud_rate(1500000),                 // The baud rate in bits/s
		  .sys_clk_freq(12000000)           // The master clock frequency
	      )
   uart0(
		 .clk(CLK),                    // The master clock for this module
		 .rst(uart_reset),                      // Synchronous reset
		 .rx(RX),                // Incoming serial line
		 .tx(TX),                // Outgoing serial line
		 .transmit(uart_transmit),              // Signal to transmit
		 .tx_byte(uart_tx_byte),                // Byte to transmit
		 .received(uart_received),              // Indicated that a byte has been received
		 .rx_byte(uart_rx_byte),                // Byte received
		 .is_receiving(uart_is_receiving),      // Low when receive line is idle
		 .is_transmitting(uart_is_transmitting),// Low when transmit line is idle
		 .recv_error(uart_recv_error)           // Indicates error in receiving packet.
	     );

   always @(posedge CLK) begin
      // Reset
      if (state == STATE_RESET || !BTN_N) begin
         rx_enabled <= 0;
         tx_enabled <= 0;
         error_flag <= 0;
         buf_i <= 0;

         uart_transmit <= 0;
         uart_fwd_sync_state <= UART_SYNC_MAGIC1;
         uart_reset <= 1;

         state <= STATE_UART_LEN;
      end // if (state == STATE_RESET || !BTN_N)

      else if (state == STATE_UART_LEN) begin
         uart_transmit <= 0;
         uart_reset <= 0;

         // Wait for initial cmd length byte on UART
         if (uart_received) begin
            // TODO check MAX_TX_BYTES
            tx_n_bytes <= uart_rx_byte[5:0];
            buf_i <= 0;
            state <= STATE_UART_CMD;
         end
      end

      else if (state == STATE_UART_CMD) begin
         if (buf_i < tx_n_bytes) begin
            if (uart_received) begin
               tx_bytes[buf_i] <= uart_rx_byte;
               buf_i <= buf_i + 1;
            end
         end else begin
            state <= STATE_TX;
         end
      end

      else if (state == STATE_TX) begin
         if (!tx_enabled) begin
            tx_enabled <= 1;

            // Set up first output byte
            buf_i <= 1;
            tx_byte <= tx_bytes[0];
         end else if (tx_next_byte && buf_i < tx_n_bytes) begin
            // Advance to next output byte
            tx_byte <= tx_bytes[buf_i];
            buf_i <= buf_i + 1;
         end else if (tx_finished) begin
            tx_enabled <= 0;
            state <= STATE_RX;
         end
      end

      else if (state == STATE_RX) begin
         if (!rx_enabled) begin
            rx_enabled <= 1;
            rx_n_bytes <= 0;
         end
         else if (rx_byte_ready) begin
            if (rx_n_bytes < MAX_RX_BYTES) begin
               rx_bytes[rx_n_bytes] <= rx_byte;
               rx_n_bytes <= rx_n_bytes + 1;
            end else begin
               error_flag <= 1;
            end
         end
         else if (rx_finished) begin
            rx_enabled <= 0;

            if (rx_error) begin
               error_flag <= 1;
               // TODO send the bad buffer?
               state <= STATE_FORWARD_LEN;
            end else begin
               error_flag <= 0;
               state <= STATE_FORWARD_LEN;
            end
         end // if (rx_finished)
      end // if (state == STATE_RX)

      else if (state == STATE_FORWARD_LEN) begin
         // send AA 55 <length_in_bytes>

         if (!uart_transmit && !uart_is_transmitting) begin
            case (uart_fwd_sync_state)
              UART_SYNC_MAGIC1: uart_tx_byte <= 8'h AA;
              UART_SYNC_MAGIC2: uart_tx_byte <= 8'h 55;
              UART_SYNC_TX_LEN: uart_tx_byte <= {2'h 00, tx_n_bytes[5:0]};
              UART_SYNC_RX_LEN: uart_tx_byte <= {2'h 00, rx_n_bytes[5:0]};
            endcase
            uart_transmit <= 1;
         end else if (uart_transmit) begin
            uart_transmit <= 0;

            if (uart_fwd_sync_state == UART_SYNC_RX_LEN) begin
               state <= STATE_FORWARD_TX;
               buf_i <= 0;
               uart_fwd_sync_state <= UART_SYNC_MAGIC1;
            end else begin
               uart_fwd_sync_state <= uart_fwd_sync_state + 1;
            end
         end
      end

      else if (state == STATE_FORWARD_TX) begin
         // Forward the TX buffer over UART
         if (uart_transmit) begin
            uart_transmit <= 0;
         end else if (buf_i < tx_n_bytes) begin
            if (!uart_is_transmitting) begin
               uart_tx_byte <= tx_bytes[buf_i];
               buf_i <= buf_i + 1;
               uart_transmit <= 1;
            end
         end else begin
            buf_i <= 0;
            state <= STATE_FORWARD_RX;
         end
      end // if (state == STATE_FORWARD_TX)

      else if (state == STATE_FORWARD_RX) begin
         // Forward the RX buffer over UART
         if (uart_transmit) begin
            uart_transmit <= 0;
         end else if (buf_i < rx_n_bytes) begin
            if (!uart_is_transmitting) begin
               uart_tx_byte <= rx_bytes[buf_i];
               buf_i <= buf_i + 1;
               uart_transmit <= 1;
            end
         end else begin
            buf_i <= 0;
            state <= STATE_UART_LEN;
         end
      end // if (state == STATE_FORWARD_RX)

      // else state = reset?
   end // always @ (posedge CLK)

endmodule
