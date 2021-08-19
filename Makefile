# based on icestorm example and https://projectf.io/posts/building-ice40-fpga-toolchain/#ice40-makefile

PROJ = top
ADD_SRC = seven_seg.v n64_sender.v n64_receiver.v datacrc_8wide.v mempak.v osdvu/uart.v
FPGA_PKG = sg48
FPGA_TYPE = up5k
FREQ = 12
PCF = data/icebreaker.pcf

top_pad: $(PROJ).rpt $(PROJ).bin
top_snap: top_snapstation.rpt top_snapstation.bin
all: top_pad top_snap


%.json: %.v $(ADD_SRC)
	yosys -ql "$(basename $@).yslog" -p 'synth_ice40 -top top -json $@' $< $(ADD_SRC)

%.asc: %.json ${PCF}
	nextpnr-ice40 -ql "$(basename $@).nplog" --${FPGA_TYPE} --package ${FPGA_PKG} --freq ${FREQ} --asc $@ --pcf ${PCF} --json $<

%.bin: %.asc
	icepack $< $@

%.rpt: %.asc
	icetime -d ${FPGA_TYPE} -c ${FREQ} -mtr $@ $<

$(PROJ)_tb: $(PROJ)_tb.v $(PROJ).v
	iverilog -o $@ $^

$(PROJ)_tb.vcd: $(PROJ)_tb
	vvp -N $< +vcd=$@

$(PROJ)_syn.v: $(PROJ).json
	yosys -p 'read_json $^; write_verilog $@'

$(PROJ)_syntb: $(PROJ)_tb.v $(PROJ)_syn.v
	iverilog -o $@ $^ `yosys-config --datdir/ice40/cells_sim.v`

$(PROJ)_syntb.vcd: $(PROJ)_syntb
	vvp -N $< +vcd=$@

prog: $(PROJ).bin
	iceprog $<

prog_snap: top_snapstation.bin
	iceprog $<

sudo-prog: $(PROJ).bin
	@echo 'Executing prog as root!!!'
	sudo iceprog $<

clean:
#rm -f $(PROJ).yslog $(PROJ).nplog $(PROJ).json $(PROJ).asc $(PROJ).rpt $(PROJ).bin
	rm -f top*.yslog top*.nplog top*.json top*.asc top*.rpt top*.bin
	rm -f $(PROJ)_tb $(PROJ)_tb.vcd $(PROJ)_syn.v $(PROJ)_syntb $(PROJ)_syntb.vcd

.SECONDARY:
.PHONY: all prog prog_uart prog_test clean
