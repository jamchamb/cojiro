#!/usr/bin/env python3
import argparse
import serial
import struct
import time
from uart_util import (sync_recv, sendall)
from crc_util import (data_crc_lookup, pack_addr)


# Recognized JoyBus commands
CMD_INFO_RESET = 0xff
CMD_INFO = 0x00
CMD_STATE = 0x01
CMD_PAK_READ = 0x02
CMD_PAK_WRITE = 0x03


def send_cmd(ser, command, verbose=False):
    if len(command) > 35:
        # limit based on current maximum in Verilog
        raise Exception('max TX length is 35')

    len_byte = len(command).to_bytes(1, 'big')
    sendall(ser, len_byte + command)

    echo_bytez, response_bytez = sync_recv(ser, verbose)
    return response_bytez


def pad_query(ser, reset=False, verbose=False):
    if reset:
        cmd = b'\xff'
    else:
        cmd = b'\x00'

    response_bytez = send_cmd(ser, cmd, verbose)

    pad_type, joyport_status = struct.unpack('<HB', response_bytez)
    return (pad_type, joyport_status)


def poll_state(ser, verbose=False):
    while True:
        # Poll button state
        response = send_cmd(ser, b'\x01', verbose)

        print(f'state: {response.hex(" ")}')

        time.sleep(0.001)


def dump_cpak(ser, cpak_filename, verbose=False):
    test_file = open(cpak_filename, 'wb')

    for i in range(0, 0x8000, 32):
        retry = False
        packed_addr = pack_addr(i)
        read_cmd = b'\x02' + packed_addr

        # read a 32 byte chunk from controller pak
        response = send_cmd(ser, read_cmd, verbose)
        if len(response) != 33:
            retry = True
            print(f'invalid response length {len(response)}')

        crc_received = response[-1]
        chunk = response[:32]
        crc_calculated = data_crc_lookup(chunk)

        if crc_received != crc_calculated:
            retry = True
            print(f'CRC mismatched (received {crc_received:02x}, '
                  f'calculated {crc_calculated:02x}')
        elif verbose:
            print(f'{i:04x} good CRC {crc_calculated:02x}')

        if retry:
            print(f'retrying address {i:04x}')
            i -= 32
        else:
            test_file.write(chunk)
            print(f'{i:04x}: {chunk.hex()}')

    test_file.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=str)
    parser.add_argument('-b', '--baudrate', type=int, default=1500000)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    parser.add_argument('--dump-cpak', type=str, default=None,
                        help='file to dump cpak memory to')
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate) as ser:
        print(ser.name)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # Send info/reset
        pad_type, joyport_status = pad_query(
            ser,
            reset=True,
            verbose=args.verbose)

        print(f'Pad type: {pad_type:04x}, joyport status: {joyport_status:02x}')

        if args.dump_cpak is not None:
            if joyport_status == 1:
                print(f'dump controller pak to {args.dump_cpak}...')
                dump_cpak(ser, args.dump_cpak, args.verbose)
            elif joyport_status == 3:
                print('pak just inserted, please retry')
            else:
                print('no pak detected')
        else:
            poll_state(ser, args.verbose)


if __name__ == '__main__':
    main()
