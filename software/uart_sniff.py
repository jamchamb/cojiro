#!/usr/bin/env python3
import argparse
import serial

# Recognized JoyBus commands
CMD_INFO_RESET = 0xff
CMD_INFO = 0x00
CMD_STATE = 0x01
CMD_PAK_READ = 0x02
CMD_PAK_WRITE = 0x03


def extract_addr(packed):
    address = (packed[0] << 3) | (packed[1] >> 5)
    address *= 32
    crc = packed[1] & 0x1f
    return address, crc


def sendall(ser, data):
    n = 0
    while n < len(data):
        n += ser.write(data[n:])
    #print(f'sent {data}')


def sync_recv(ser, verbose=False):
    while True:
        # get number of bytes to receive
        sync_magic1 = ser.read(1)
        if len(sync_magic1) != 1:
            continue
        if sync_magic1 != b'\xaa':
            if verbose:
                print('out of sync')
                print(sync_magic1)
            continue

        sync_magic2 = ser.read(1)
        if len(sync_magic2) != 1 or sync_magic2 != b'\x55':
            if verbose:
                print('out of sync 2')
                print(sync_magic2)
            continue

        byte_count = ser.read(1)
        if len(byte_count) != 1:
            print('error: no command length received')
        byte_count = ord(byte_count)

        response_byte_count = ser.read(1)
        if len(response_byte_count) != 1:
            print('error: no response length received')
            continue
        response_byte_count = ord(response_byte_count)

        bytez = ser.read(byte_count)
        if len(bytez) == 0:
            continue

        if response_byte_count > 0:
            response_bytez = ser.read(response_byte_count)
        else:
            response_bytez = b''

        return (bytez, response_bytez)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=str)
    parser.add_argument('-b', '--baudrate', type=int, default=1500000)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate) as ser:
        print(ser.name)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        while True:
            bytez, response_bytez = sync_recv(ser, args.verbose)

            cmd = bytez[0]
            if args.verbose and cmd != CMD_STATE:
                print(f'cmd {cmd:02x}')
                print(bytez.hex())

            if cmd in [CMD_INFO, CMD_INFO_RESET, CMD_STATE]:
                # state cmd is spammy
                pass
            elif cmd == CMD_PAK_READ:
                address, crc = extract_addr(bytez[1:3])
                print(f'read cmd: {address:04x} (addr CRC-5 {crc:02x})')
                print(f'  response: {response_bytez.hex()}')
            elif cmd == CMD_PAK_WRITE:
                address, crc = extract_addr(bytez[1:3])
                data = bytez[3:]
                print(f'write cmd: {address:04x} (addr CRC-5 {crc:02x})')
                print(f'  {data.hex()}')
                print(f'  response: {response_bytez.hex()}')
            else:
                print(f'unknown cmd {cmd:02x}')


if __name__ == '__main__':
    main()
