`default_nettype none

module mempak (
               input            clk,
               input            read_enable,
               input            write_enable,
               input [15:0]     address,
               input [15:0]      write_data,
               output reg [15:0] read_data
);

   SB_SPRAM256KA spram_inst (
        // Max addr. 15'h 7FFF, divide by 2 to address halfwords
        .ADDRESS(address[14:1]),
        .DATAIN(write_data),
        .MASKWREN(4'b 1111),
        .WREN(write_enable),
        .CHIPSELECT(1'b1),
        .CLOCK(clk),
        .STANDBY(1'b0),
        .SLEEP(1'b0),
        .POWEROFF(1'b1),
        .DATAOUT(read_data)
    );

endmodule // mempak
