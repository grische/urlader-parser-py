#!/usr/bin/env python3

"""AVM URLADER parser"""

DEBUG = False


def debug(string):
    """debug log"""
    if DEBUG:
        print(string)


def parse_urlader_v2(urlader, endianess, offset):
    """Parse urlader v2
    Parsing urlader mtd partition
    -------------------------------
    Offset  Content
    0x57C   0x0000 0000
    0x580   urlader version
    ...     ???
    0x5A4   size of memory
    0x5A8   size of flash
    0x5AC   ??? (empty for 7360v1)
    0x5B0   ??? (empty for 7360v1)
    0x5B4   mtd0 start
    0x5B8   mtd0 size
    ...
    0x5DC   mtd5 start? (empty for 7360v1)
    0x5E8   mtd5 size? (empty for 7360v1)
    0x5E4   ???
    0x5E8   ??? (empty for 7360v1)
    0x5F0   mtd pointer: end of pointer list
    0x5F4   mtd pointer: first variable value (string)
    0x5F8   mtd pointer: first variable name (string)
    0x5FC   mtd pointer: second variable value (string)
    0x600   mtd pointer: second variable name (string)
    ...     mtd pointer to other variables
    0x??    0x0000 0000 (two before "end of pointer list")
    0x??+4  0x0000 0000 (one before "end of pointer list")
    0x??+8  0xffff ffff ("end of data pointer")
    0x??+x  more 0xffff padding until first variable's value
    """
    offset_memsize = offset + 0x24

    variables = {}
    urlader.seek(offset_memsize)
    variables["memsize"] = int.from_bytes(urlader.read(4), endianess)
    variables["flashsize"] = int.from_bytes(urlader.read(4), endianess)
    variables["unused1"] = int.from_bytes(urlader.read(4), endianess)
    variables["unused2"] = int.from_bytes(urlader.read(4), endianess)
    for i in range(0, 6):
        mtd_name = f"mtd{i}"
        variables[f"{mtd_name}_start"] = hex(int.from_bytes(urlader.read(4), endianess))
        variables[f"{mtd_name}_length"] = hex(
            int.from_bytes(urlader.read(4), endianess)
        )
    variables["unknown_data1"] = hex(int.from_bytes(urlader.read(4), endianess))
    variables["unknown_data2"] = hex(int.from_bytes(urlader.read(4), endianess))

    last_data_position = int.from_bytes(urlader.read(4), endianess)
    variables["last_data_position"] = hex(last_data_position)

    # mtd2 is the urlader device
    mtd2_offset = int(variables["mtd2_start"], 0)
    relative_last_data_position = last_data_position - mtd2_offset

    pointers = []
    while urlader.tell() < relative_last_data_position:
        value = urlader.read(4)
        name = urlader.read(4)
        if value == b"\x00\x00\x00\x00" and name == b"\x00\x00\x00\x00":
            debug(f"Found end of variables at {hex(urlader.tell())}")
            break

        pointers.append(
            {
                "value": int.from_bytes(value, endianess),
                "name": int.from_bytes(name, endianess),
            }
        )
    debug(f"List of pointers: {pointers}")

    for pointer in pointers:
        name = read_string(urlader, pointer["name"] - mtd2_offset)
        value = read_string(urlader, pointer["value"] - mtd2_offset)
        variables[name] = value

    return variables


def read_string(urlader, position):
    """Read NULL terminated string
    Reads bytes until NULL marker has been found
    """
    debug(f"Parsing string at {hex(position)}")
    urlader.seek(position)
    full_data = b""
    data = urlader.read(1)
    # Read until the 0x00 marker
    while data != b"\x00":
        full_data = full_data + data
        data = urlader.read(1)

    return full_data.decode("utf-8")


def parse_urlader(filepath):
    """parse urlader file"""
    endianess = "big"
    offset_start = 0x580
    variables = {}

    with open(filepath, "rb") as urlader:
        urlader.seek(offset_start)
        version = urlader.read(4)
        variables["version"] = int.from_bytes(version, endianess)
        if variables["version"] == 2:
            variables = {
                **variables,
                **parse_urlader_v2(urlader, endianess, offset_start),
            }
        else:
            print(f"ERROR: Unsupported urlader version { version }")
            return variables

    return variables


if __name__ == "__main__":
    import sys
    import json

    FILEPATH = sys.argv[1]
    debug(f"Parsing {FILEPATH}")
    print(json.dumps(parse_urlader(FILEPATH), indent=4))
