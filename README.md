# Codec-de-Huffman

# Huffman Codec

A Python implementation of Huffman compression/decompression from scratch,
with a custom binary file format (`.huf`).

## Features

- File compression and decompression via command line
- Custom `.huf` binary format with embedded Huffman tree and data length
- Handles any binary file (text, images, etc.)
- Debug mode showing compression ratio

## Usage

```bash
# Compress
python3 huffman.py c myfile.txt

# Decompress
python3 huffman.py d myfile.huf

# With debug info (compression ratio)
python huffman.py c myfile.txt -D
```

## .huf File Format

| Offset | Content              |
|--------|----------------------|
| 0–3    | Signature `HUFF`     |
| 4–7    | Original data length |
| 8+     | Encoded tree + data  |

## Stack

- Python 3.12+
- Standard library only

## Notes

- Compression is effective on repetitive data (text files, logs)
- Decompression performance is a known limitation and is being improved
- A C rewrite is in progress
