# cojiro

Nintendo JoyBus device designs for the iCEBreaker FPGA development board.

Features:

- Simulate a Nintendo 64 controller with ephemeral Controller Pak memory
- Simulate a Snap Station
- Host mode for controlling devices over UART, e.g. polling controller button states or dumping data from a Controller Pak

## Setup

Install the IceStorm toolchain: see <http://bygone.clairexen.net/icestorm/>

Clone repository and submodules:

```console
$ git clone https://github.com/jamchamb/cojiro.git
$ cd cojiro
$ git submodulate update --init
```

Build and flash the basic N64 controller design:

```console
$ make prog
```

Build and flash the Snap Station design:

```console
$ make prog_snap
```

### Hardware setup

#### iCEBreaker I/O

- PMOD1A is used for simple state or debug output on the seven-segment display module
- PMOD1B is used for the JoyBus I/O (pin P1B1) and ground
- PMOD2 is used for the button module
- USB is used for UART (baud rate is 1500000, use `software/uart_sniff.py` for sniffing traffic)
- uButton is used to reset the overall state of the device

#### Console or controller connection

For the Nintendo 64 cable, buy a controller extension cord and cut it in half. One end can be used to connect the iCEBreaker to the console, the other end can be used to receive a controller. Attach the ground line to a ground on PMOD1B, data line to pin P1B1, and place a pull-up resistor between the 3.3V power line and the data line (I used a 330 Ohm resistor here). When receiving a controller, connect a 3.3V out from the iCEBreaker to the power line.

![Example cable setup](https://jamchamb.net/assets/img/snap-station/n64_controller_breakout.jpg)


## Designs

### Controller

The controller design uses buttons 3, 2, and 1 for A, B, and Start.
It also has a Controller Pak built-in, but currently the memory only exists in RAM.
Using the SPI flash to persist the pak data is a to-do.


### Snap Station

Mimics the Snap Station protocol used by Pokemon Snap and Pokemon Stadium.
See <https://jamchamb.net/2021/08/17/snap-station.html> for an overview.

Press button 1 to advance the state of the Snap Station.

1. After entering the main menu or Gallery menu, press BTN1 once to enable the station.
2. Press Print in the Gallery menu.
3. After the "Now Saving..." message appears, reset the console.
4. Press BTN1 to advance through the photo display until all 16 photos are displayed.

### Host mode UART control

With this design the iCEBreaker acts as a UART bridge between a host computer
and a Joy Bus device. This allows the host to send commands to a device such as an N64
controller as if it were the console. See `software/uart_host.py`.

Example of dumping Controller Pak memory:

```console
$ ./uart_host.py /dev/ttyUSB1 --dump-cpak cpak_joytech3.bin
/dev/ttyUSB1
Pad type: 0005, joyport status: 01
dump controller pak to cpak_joytech3.bin...
0000: 00000000000000000000000000fefefefefefefefefefefefe00000000000000
0020: 0015000000006bb50039161600000000000000000000000000010100831a7cd8
0040: 0000000000000000000000000000000000000000000000000000000000000000
0060: 0015000000006bb50039161600000000000000000000000000010100831a7cd8
0080: 0015000000006bb50039161600000000000000000000000000010100831a7cd8
00a0: 0000000000000000000000000000000000000000000000000000000000000000
00c0: 0015000000006bb50039161600000000000000000000000000010100831a7cd8
...
```
