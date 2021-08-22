// Cause yosys to throw an error when we implicitly declare nets
`default_nettype none
`define UART_FORWARD
`define SEVENSEG_DISPLAY

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
   localparam [3:0]
     STATE_RESET = 0,
     STATE_RX = 1,
     STATE_PARSE = 2,
     STATE_PAK_READ = 3,
     STATE_PAK_WRITE = 4,
     STATE_DATA_CRC1 = 5,
     STATE_DATA_CRC2 = 6,
     STATE_TX = 7,
     STATE_FORWARD_LEN = 8,
     STATE_FORWARD_CMD = 9,
     STATE_FORWARD_RESPONSE = 10,
     STATE_PAK_INIT = 11;
   reg [3:0] state = STATE_PAK_INIT;
   reg       error_flag = 0;

   // N64 commands
   reg [7:0]   command = 0;
   reg [15:0]  cpak_addr = 0;
   reg [4:0]   cpak_addr_crc = 0;

   // Pad ID and status
   localparam [15:0] pad_id = 16'h 0500;
   reg [7:0]   pad_status = 8'h 01;

   // "Controller pak" memory
   reg         pak_read_en = 0;
   reg         pak_write_en = 0;
   reg [15:0]  pak_addr = 0;
   reg [15:0]  pak_write_data = 0;
   reg [15:0]  pak_read_data;

   reg         pak_initialized = 0;
   reg         pak_init_started = 0;
   reg         pak_read_ready = 0;

   // expecting at most 35 bytes (1 cmd byte + 34 optional data bytes)
   localparam MAX_RX_BYTES = 35;

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
   reg [7:0]   tx_bytes [0:32];
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

   // Data CRC for 32 byte read/write buffers
   reg [7:0] datacrc_in = 8'h 00;
   reg [7:0]   datacrc_out;
   reg         datacrc_enable = 0;
   reg         datacrc_reset = 0;

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
   assign display_wire = {1'b 0, state[2:0], command[3:0]};

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

   datacrc datacrc (
                    .data_in(datacrc_in),
                    .crc_en(datacrc_enable),
                    .crc_out(datacrc_out),
                    .rst(datacrc_reset),
                    .clk(CLK)
                    );

   mempak pakmem_mod (
                      .clk(CLK),
                      .read_enable(pak_read_en),
                      .write_enable(pak_write_en),
                      .address(pak_addr),
                      .write_data(pak_write_data),
                      .read_data(pak_read_data),
                      );

   `ifdef UART_FORWARD
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
     UART_SYNC_RX_LEN = 2,
     UART_SYNC_TX_LEN = 3;
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
   `endif

   // Extract address (page ID) from packed address & CRC-5
   function [15:0] extract_addr (input [15:0] addr_crc5);
      begin
         extract_addr = (addr_crc5[15:8] << 3) | (addr_crc5[7:0] >> 5);
      end
   endfunction // extract_addr

   always @(posedge CLK) begin
      if (state == STATE_PAK_INIT) begin
         // Initialize pak memory: set to all FFs
         if (!pak_initialized) begin
            if (pak_addr < 16'h 8000) begin
               pak_write_en <= 1;
               pak_write_data <= 16'h FFFF;
               pak_init_started <= 1;

               if (pak_init_started)
                 pak_addr <= pak_addr + 2;
            end else begin
               pak_initialized <= 1;
               pak_write_en <= 0;
               pak_addr <= 0;
               state <= STATE_RESET;
            end
         end
      end

      // Reset
      else if (state == STATE_RESET || !BTN_N) begin
         rx_enabled <= 0;
         tx_enabled <= 0;
         error_flag <= 0;
         buf_i <= 0;
         pak_read_en <= 0;
         pak_write_en <= 0;

         pad_status <= 8'h 01;

         `ifdef UART_FORWARD
         uart_transmit <= 0;
         uart_fwd_sync_state <= UART_SYNC_MAGIC1;
         uart_reset <= 1;
         `endif

         state <= STATE_RX;
      end

      else if (state == STATE_RX) begin
         `ifdef UART_FORWARD
         uart_transmit <= 0;
         uart_reset <= 0;
         `endif

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
               state <= STATE_RESET;
            end else begin
               command <= rx_bytes[0];
               error_flag <= 0;
               state <= STATE_PARSE;
            end
         end // if (rx_finished)
      end // if (state == STATE_RX)

      // respond to a command
      else if (state == STATE_PARSE) begin
         case (command)
           8'h 00, 8'h FF: begin
              // query device type and status
              tx_bytes[0] <= pad_id[15:8];
              tx_bytes[1] <= pad_id[7:0];
              tx_bytes[2] <= pad_status;
              tx_n_bytes <= 3;
              state <= STATE_TX;
           end
           8'h 01: begin
              // button status
              tx_bytes[0] <= {BTN3, BTN2, 1'b 0, BTN1, 4'b 0};
              tx_bytes[1] <= 8'h 00;
              tx_bytes[2] <= 8'h 00;
              tx_bytes[3] <= 8'h 00;
              tx_n_bytes <= 4;
              state <= STATE_TX;
           end
           8'h 02: begin
              // read data from pak
              // respond with 32 bytes of data and 8-bit data CRC
              if (rx_n_bytes != 3) begin
                 error_flag <= 1;
              end

              // Get page addr and convert to byte addr (multiply by 32)
              cpak_addr <= extract_addr({rx_bytes[1], rx_bytes[2]}) << 5;
              cpak_addr_crc <= rx_bytes[2][4:0];
              buf_i <= 0;

              // return 32 bytes of data and 1 byte CRC
              tx_n_bytes <= 33;
              state <= STATE_PAK_READ;
           end
           8'h 03: begin
              // write data to pak
              // respond with 8-bit data CRC
              if (rx_n_bytes != 35) begin
                 error_flag <= 1;
              end

              // Get page addr and convert to byte addr (multiply by 32)
              cpak_addr <= extract_addr({rx_bytes[1], rx_bytes[2]}) << 5;
              cpak_addr_crc <= rx_bytes[2][4:0];
              buf_i <= 0;

              // will set 8 bit CRC response below
              tx_n_bytes <= 1;
              state <= STATE_PAK_WRITE;
           end
           default: begin
              // TODO: wait and display unknown command for a few seconds?
              tx_n_bytes <= 0;
              error_flag <= 1;
              state <= STATE_TX;
           end
         endcase // case (command)
      end // if (state == STATE_PARSE)

      else if (state == STATE_PAK_READ) begin
         if (pak_read_en) begin
            // delay cycle for newly read address to propagate to output
            pak_read_en <= 0;
            pak_read_ready <= 1;
         end else if (pak_read_ready) begin
            tx_bytes[buf_i] <= pak_read_data[15:8];
            tx_bytes[buf_i+1] <= pak_read_data[7:0];
            buf_i <= buf_i + 2;

            pak_read_ready <= 0;
         end else if (buf_i < 32) begin
            pak_addr <= cpak_addr + buf_i;
            pak_read_en <= 1;
            pak_read_ready <= 0;
         end else begin
            state <= STATE_DATA_CRC1;
         end
      end

      else if (state == STATE_PAK_WRITE) begin
         if (cpak_addr == 16'h 8000) begin
            // it writes 00s here during format
            state <= STATE_DATA_CRC1;
         end else if (buf_i < 32) begin
            pak_write_en <= 1;
            pak_addr <= cpak_addr + buf_i;
            pak_write_data <= {rx_bytes[buf_i+3], rx_bytes[buf_i+4]};

            buf_i <= buf_i + 2;
         end else begin
            pak_write_en <= 0;
            state <= STATE_DATA_CRC1;
         end
      end

      else if (state == STATE_DATA_CRC1) begin
         if (!datacrc_reset) begin
            datacrc_reset <= 1;
            buf_i <= 0;
         end else begin
            datacrc_reset <= 0;
            state <= STATE_DATA_CRC2;
         end
      end

      else if (state == STATE_DATA_CRC2) begin
         if (buf_i < 32) begin
            case (command)
              8'h 02: datacrc_in <= tx_bytes[buf_i];
              8'h 03: datacrc_in <= rx_bytes[3+buf_i];
            endcase
            datacrc_enable <= 1;
            buf_i <= buf_i + 1;
         end else if (datacrc_enable) begin // if (buf_i < 32)
            // extra cycle for CRC calculation to propagate to result
            datacrc_enable <= 0;
         end else begin // if (buf_i < 32)
            tx_bytes[tx_n_bytes-1] <= datacrc_out;
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
         `ifdef UART_FORWARD
            state <= STATE_FORWARD_LEN;
         `else
            state <= STATE_RX;
         `endif
         end
      end

      `ifdef UART_FORWARD
      else if (state == STATE_FORWARD_LEN) begin
         // send AA 55 <length_in_bytes>

         if (rx_n_bytes == 0) begin
            state <= STATE_RX;
         end else if (!uart_transmit && !uart_is_transmitting) begin
            case (uart_fwd_sync_state)
              UART_SYNC_MAGIC1: uart_tx_byte <= 8'h AA;
              UART_SYNC_MAGIC2: uart_tx_byte <= 8'h 55;
              UART_SYNC_RX_LEN: uart_tx_byte <= {2'h 00, rx_n_bytes[5:0]};
              UART_SYNC_TX_LEN: uart_tx_byte <= {2'h 00, tx_n_bytes[5:0]};
            endcase
            uart_transmit <= 1;
         end else if (uart_transmit) begin
            uart_transmit <= 0;

            if (uart_fwd_sync_state == UART_SYNC_TX_LEN) begin
               state <= STATE_FORWARD_CMD;
               buf_i <= 0;
               uart_fwd_sync_state <= UART_SYNC_MAGIC1;
            end else begin
               uart_fwd_sync_state <= uart_fwd_sync_state + 1;
            end
         end
      end

      else if (state == STATE_FORWARD_CMD) begin
         // Forward the command over UART
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
            state <= STATE_FORWARD_RESPONSE;
         end
      end // if (state == STATE_FORWARD_CMD)

      else if (state == STATE_FORWARD_RESPONSE) begin
         // Forward the response over UART
         if (uart_transmit) begin
            uart_transmit <= 0;
         end else if (buf_i < tx_n_bytes) begin
            if (!uart_is_transmitting) begin
               uart_tx_byte <= tx_bytes[buf_i];
               buf_i <= buf_i + 1;
               uart_transmit <= 1;
            end
         end else begin
            state <= STATE_RX;
         end
      end
      `endif //  `ifdef UART_FORWARD

      // else state = reset?
   end // always @ (posedge CLK)

endmodule
