# cojiro

FPGA design for Nintendo JoyBus devices


## Setup

Install the IceStorm toolchain: see <http://bygone.clairexen.net/icestorm/>

Clone repository and submodules:

```sh
$ git clone https://github.com/jamchamb/cojiro.git
$ cd cojiro
$ git submodulate update --init
```

Build and flash the basic N64 controller design:

```sh
$ make prog
```

Build and flash the Snap Station design:

```sh
$ make prog_snap
```

### Hardware setup

For the Nintendo 64 cable setup see <https://jamchamb.net/2021/08/17/snap-station.html>.

- PMOD1A is used for simple state or debug output on the seven-segment display module
- PMOD1B is used for the JoyBus I/O (pin P1B1) and ground
- PMOD2 is used for the button module
- USB is used for UART (baud rate is 1500000, use `software/uart_sniff.py` for sniffing traffic)

## Controller

The controller design uses buttons 3, 2, and 1 for A, B, and Start.
It also has a Controller Pak built-in, but currently the memory only exists in RAM.
Using the SPI flash to persist the pak data is a to-do.


## Snap Station

Mimics the Snap Station protocol used by Pokemon Snap and Pokemon Stadium.
Press button 1 to advance the state of the Snap Station.

1. After entering the main menu or Gallery menu, press the button once to enable the station.
2. Press the Print button. After the "Now Saving..." message appears, reset the console.
3. Press the button to advance through the photo display until all 16 photos are displayed.

