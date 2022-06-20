# urlader-parser-py
A Python-based parser for AVM's urlader partition

## Usage

In an OpenWRT-based installation, install python3-light:

```sh
opkg install python3-light
```

Check what mtd partition contains the urlader:
```sh
cat /proc/mtd
```

Copy the python file to your router and run the tool on the partition from above (e.g. mtd0):
```sh
chmod +x ./parser.py
./parser.py /dev/mtd0ro
```
