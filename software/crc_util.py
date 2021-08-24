def u32(val):
    return val & 0xffffffff


def extract_addr(packed):
    address = (packed[0] << 8) + (packed[1] & 0xE0)
    crc = packed[1] & 0x1f
    return address, crc


def pack_addr(address):
    if address & 0x1f != 0:
        raise ValueError('low 5 bits of address must be clear')

    crc = address_crc(address >> 5)

    return (address | crc).to_bytes(2, 'big')


def address_crc(address):
    # Calculate 5-bit CRC with polynomial 0x15

    address &= 0xffff
    crc = 0
    bitmask = 0x400
    #flag = 0

    while bitmask != 0:
        crc = u32(crc << 1)

        if address & bitmask == 0:
            if crc & 0x20 != 0:
                #flag = 1
                crc ^= 0x15
        else:
            if crc & 0x20 != 0:
                #flag = 0
                crc ^= 0x14
            else:
                #flag = 1
                crc += 1

        bitmask >>= 1

    for i in range(5):
        crc = u32(crc << 1)
        if crc & 0x20 != 0:
            crc ^= 0x15

    return crc & 0x1f


def data_crc(buf):
    """Calculate 8-bit CRC with polynomial 0x85"""
    crc = 0
    for cur_byte in buf:
        bitmask = 0x80
        while bitmask != 0:
            crc = u32(crc << 1)

            if (cur_byte & bitmask) == 0:
                if crc & 0x100 != 0:
                    crc ^= 0x85
            else:
                if crc & 0x100 == 0:
                    crc += 1
                else:
                    crc ^= 0x84

            bitmask >>= 1

    for i in range(8):
        crc = u32(crc << 1)
        if crc & 0x100 != 0:
            crc ^= 0x85

    return crc & 0xff


DATA_CRC_TABLE = [data_crc(bytes([i])) for i in range(256)]


def data_crc_lookup(buf):
    crc = 0
    for cur_byte in buf:
        index = cur_byte ^ (crc & 0xff)
        crc = u32(crc << 8)
        crc ^= DATA_CRC_TABLE[index]

    return crc & 0xff
