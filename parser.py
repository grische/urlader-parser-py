#!/usr/bin/env python3

"""AVM URLADER parser"""

DEBUG = True


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
    variables["memsize"] = read_integer(urlader, endianess)
    variables["flashsize"] = read_integer(urlader, endianess)
    variables["unused1"] = read_integer(urlader, endianess)
    variables["unused2"] = read_integer(urlader, endianess)
    for i in range(0, 6):
        mtd_name = f"mtd{i}"
        variables[f"{mtd_name}_start"] = hex(read_integer(urlader, endianess))
        variables[f"{mtd_name}_length"] = hex(read_integer(urlader, endianess))
    variables["unknown_data1"] = hex(read_integer(urlader, endianess))
    variables["unknown_data2"] = hex(read_integer(urlader, endianess))

    last_data_position = read_integer(urlader, endianess)
    variables["last_data_position"] = hex(last_data_position)

    # mtd2 is the urlader device
    mtd2_offset = int(variables["mtd2_start"], 0)
    relative_last_data_position = last_data_position - mtd2_offset

    pointers = read_variable_pointers(urlader, endianess, relative_last_data_position)

    for pointer in pointers:
        name = read_string(urlader, pointer["name"] - mtd2_offset)
        value = read_string(urlader, pointer["value"] - mtd2_offset)
        variables[name] = value

    return variables


def parse_urlader_v3(urlader, endianess, offset):
    """Parse urlader v3
    Parsing urlader mtd partition
    -------------------------------
    Offset  Content
    0x57C   0x0000 0000
    0x580   urlader version
    0x584   memsize
    0x588   flashsize
    0x58C   full mtd start
    0x590   empty
    ...
    0x5AC   mtd5 start
    0x5B0   mtd5 size
    0x5B4   padding 0xffff (on 7360v2)
    ...     padding 0xffff (on 7360v2)
    0x5E8   padding 0xffff (on 7360v2)
    0x5EC   mtd pointer: end of pointer list
    0x5F0   mtd pointer: first variable value (string)
    0x5F4   mtd pointer: first variable name (string)
    0x5FC   mtd pointer: second variable value (string)
    0x600   mtd pointer: second variable name (string)
    ...     mtd pointer to other variables
    0x??    0x0000 0000 (two before "end of pointer list")
    0x??+4  0x0000 0000 (one before "end of pointer list")
    0x??+8  0xffff ffff ("end of data pointer")
    0x??+x  more 0xffff padding until first variable's value
    """
    urlader.seek(offset+4)

    variables = {}
    variables["memsize"] = hex(read_integer(urlader, endianess))
    variables["flashsize"] = hex(read_integer(urlader, endianess))
    for postfix in range(0, 5):
        mtd_name = f"mtd{postfix}"
        variables[f"{mtd_name}_start"] = hex(read_integer(urlader, endianess))
        variables[f"{mtd_name}_length"] = hex(read_integer(urlader, endianess))

    debug(
        f"parse_urlader_v3: attempting to find end of variables starting at {hex(urlader.tell())}"
    )
    struct_end_candidate = read_integer(urlader, endianess)

    pointer_offset = 0

    # Required for FB7360v2
    if struct_end_candidate == 0xFFFFFFFF:
        while struct_end_candidate == 0xFFFFFFFF:
            struct_end_candidate = read_integer(urlader, endianess)
        struct_end = struct_end_candidate
        pointer_offset = int(variables["mtd2_start"], 0)
        relative_last_data_position = struct_end - pointer_offset
    # Required for FB4040
    elif struct_end_candidate == 0x00000000:
        while struct_end_candidate == 0x00000000:
            struct_end_candidate = read_integer(urlader, endianess)
        variables[f"unknown{hex(urlader.tell())}"] = hex(struct_end_candidate)
        variables[f"unknown{hex(urlader.tell())}"] = hex(
            read_integer(urlader, endianess)
        )
        struct_end = read_integer(urlader, endianess)

        pointer_offset = struct_end - 0x140  # why 0x140???
        relative_last_data_position = 0xFFFFFFFF  # random number
    else:
        print(variables)
        raise Exception(f"Error: Unexpected struct_end_candidate {hex(struct_end_candidate)} at {hex(urlader.tell())}")

    variables["struct_end"] = hex(struct_end)
    pointers = read_variable_pointers(urlader, endianess, relative_last_data_position)

    for pointer in pointers:
        name = read_string(urlader, pointer["name"] - pointer_offset)
        value = read_string(urlader, pointer["value"] - pointer_offset)
        variables[name] = value

    return variables


def read_variable_pointers(urlader, endianess, relative_last_data_position):
    """Read list of variable pointers"""
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

    return pointers


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


def read_integer(urlader, endianess):
    """Read next 4 bytes with specified endianess"""
    debug(f"Reading integer at {hex(urlader.tell())}")
    return int.from_bytes(urlader.read(4), endianess)


def parse_urlader(filepath, endianess, offset_start):
    """parse urlader file"""
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
        elif variables["version"] == 3:
            variables = {
                **variables,
                **parse_urlader_v3(urlader, endianess, offset_start),
            }
        else:
            print(f"ERROR: Unsupported urlader version { version }")
            return variables

    return variables


def identify_urlader(filepath):
    """parse urlader file"""

    with open(filepath, "rb") as urlader:
        for endianess in ["big", "little"]:
            for offset in [0x0, 0x580]:
                urlader.seek(offset)
                version_binary = urlader.read(4)
                version = int.from_bytes(version_binary, endianess)
                if version <= 5:
                    debug(
                        f"{endianess},{hex(offset)}: Found urlader version { version }"
                    )
                    return endianess, offset

                debug(
                    f"{endianess},{hex(offset)}: Unsupported urlader version { version }"
                )

    return None, None


if __name__ == "__main__":
    import sys
    import json

    FILEPATH = sys.argv[1]
    debug(f"Parsing {FILEPATH}")
    ENDIANESS, OFFSET = identify_urlader(FILEPATH)
    print(json.dumps(parse_urlader(FILEPATH, ENDIANESS, OFFSET), indent=4))
