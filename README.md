# cojiro

Nintendo JoyBus device designs for the iCEBreaker FPGA development board.

### Features

- Simulate a Nintendo 64 controller with ephemeral Controller Pak memory
- Simulate a Snap Station
- Host mode for controlling devices over USB (send/receive data through the Joy Bus connection)
  - Poll controller button states
  - Dump data from a Controller Pak
  - Use a Transfer Pak for Gameboy cartridge I/O

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

#### Example of dumping Controller Pak memory

```console
$ ./uart_host.py /dev/ttyUSB1 --dump-cpak cpak_gray.bin
Using port: /dev/ttyUSB1
Pad type: 0005, joyport status: 01
dump controller pak to cpak_gray.bin...
100%|███████████████████████████████████████████████| 1024/1024 [00:16<00:00, 62.55it/s]
$ hexdump cpak_gray.bin | head
000000 81 fe fd fc fb fa f9 f8 00 fe fd fc 08 08 08 08  >................<
000010 ef ee ed ec 00 00 00 15 10 ee ed ec f5 00 00 f4  >................<
000020 ff ff ff ff 04 bc 62 75 05 4c 46 f2 07 87 27 07  >......bu.LF...'.<
000030 00 00 00 00 4f 4b 4b 0a 00 01 01 00 7d 51 82 a1  >....OKK.....}Q..<
000040 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  >................<
*
000060 ff ff ff ff 04 bc 62 75 05 4c 46 f2 07 87 27 07  >......bu.LF...'.<
000070 00 00 00 00 4f 4b 4b 0a 00 01 01 00 7d 51 82 a1  >....OKK.....}Q..<
000080 ff ff ff ff 04 bc 62 75 05 4c 46 f2 07 87 27 07  >......bu.LF...'.<
000090 00 00 00 00 4f 4b 4b 0a 00 01 01 00 7d 51 82 a1  >....OKK.....}Q..<
```

#### Example of dumping Game Boy cartridge RAM

```console
$ ./uart_host.py /dev/ttyUSB1 --dump-tpak-ram pokemon_blue.sav
Using port: /dev/ttyUSB1
Pad type: 0005, joyport status: 01
transfer pak present: True
ROM header:
00000000: 00 C3 50 01 CE ED 66 66  CC 0D 00 0B 03 73 00 83  ..P...ff.....s..
00000010: 00 0C 00 0D 00 08 11 1F  88 89 00 0E DC CC 6E E6  ..............n.
00000020: DD DD D9 99 BB BB 67 63  6E 0E EC CC DD DC 99 9F  ......gcn.......
00000030: BB B9 33 3E 50 4F 4B 45  4D 4F 4E 20 42 4C 55 45  ..3>POKEMON BLUE
00000040: 00 00 00 00 30 31 03 13  05 03 01 33 00 D3 9D 0A  ....01.....3....
Raw title: b'POKEMON BLUE'
MBC type: MBC3
ROM size: 0x100000 bytes
RAM size: 0x8000 bytes
Dumping 4 RAM banks to pokemon_blue.sav...
100%|███████████████████████████████████████████| 32768/32768 [00:16<00:00, 1968.87it/s]
```
