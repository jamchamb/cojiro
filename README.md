# cojiro

FPGA design for Nintendo JoyBus devices


## Setup

Clone submodules first:

```sh
$ git submodulate update --init
```

Build and flash the basic N64 controller design:

```sh
$ make prog
```

Build and program the Snap Station design:

```sh
$ make prog_snap
```

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

