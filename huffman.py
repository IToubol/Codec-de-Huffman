# file.huf format:

#    offset  |       info
# ---------------------------------
#      0     | HUFF
#      4     | data lenght (bytes number)
#      8     | tree, leafs, data
# ! ajouter nom du fichier ?



BYTE_LENGTH  = 8                                # in bits
CHUNK_SIZE   = 4                                # in bytes
CHUNK_LENGTH = CHUNK_SIZE * BYTE_LENGTH         # in bits

CHUNK_MASK = (1 << CHUNK_LENGTH) - 1


type Byte = int
type HuffmanMap = dict[Byte, tuple[int, int]]   # Byte => code, codelength


class _Node:
    def __init__(self, value: Byte|None = None, frequency: int = 0) -> None:
        self.value: Byte|None = value
        self.frequency: int = frequency
        self.left: _Node|None = None
        self.right: _Node|None = None

    def copy(self) -> "_Node":
        node = _Node(self.value, self.frequency)
        node.left = self.left
        node.right = self.right
        return node


class Code:
    def __init__(self, decimal: int, length: int) -> None:
        self.decimal = decimal
        self.length = length

    def increment(self, plus_one:bool = False) -> None:
        self.decimal = self.decimal * 2 + plus_one
        self.length += 1




def _huffman_tree(leafs: list[_Node]) -> _Node:
    index = 0
    leafs_bound = len(leafs) - 1
    while index < leafs_bound:
        left = leafs[index]
        right = leafs[index + 1].copy()

        index += 1
        leafs[index].value = None
        leafs[index].left = left
        leafs[index].right = right
        leafs[index].frequency = left.frequency + right.frequency
        
        i = index
        while (i < leafs_bound) and leafs[i].frequency > leafs[i+1].frequency:
            leafs[i], leafs[i+1] = leafs[i+1], leafs[i]
            i += 1

    return leafs[-1]


def _encode_tree(
        node: _Node,
        leaf_bytes: list[int],
        huf_map: HuffmanMap,
        code: int = 1,
        n_bits: int = 0,
        tree_code: Code = Code(1, 0)
    ) -> Code:

    # if node.value is not None (byte),
    # this node is leaf and his code and value most be registered in huf_map and leafs
    if node.value is not None:  # but it can be zero!
        leaf_bytes.append(node.value)
        huf_map[node.value] = (code, n_bits)
        return tree_code        # return tree code; maybe the right branch most be yet encoded

    tree_code.increment()

    code *= 2
    n_bits += 1

    tree_code = _encode_tree( node.left, leaf_bytes, huf_map, code, n_bits, tree_code )     # type: ignore

    tree_code.increment(plus_one=True)
    
    tree_code = _encode_tree( node.right, leaf_bytes, huf_map, code+1, n_bits, tree_code)   # type: ignore
    
    return tree_code


def _huffman_parse(source: bytes, leaf_bytes: list[int], huf_map: HuffmanMap) -> Code:
    counts = {}
    for byte in source:
        if byte in counts:
            counts[byte] += 1
        else:
            counts[byte] = 1

    nodes = sorted(
        ( _Node(byte, frequency) for byte, frequency in counts.items() ),
        key = lambda node: node.frequency
    )

    tree_code = _encode_tree(
        _huffman_tree(nodes),
        leaf_bytes,
        huf_map
    )
    tree_code.increment(plus_one=True)
    return tree_code




# Flush Accumulator
def _flush_chunk_from_accumulator(buffer: bytearray, accumulator:int, acc_length:int) -> tuple[int, int]:
    while acc_length >= CHUNK_LENGTH:
        acc_length -= CHUNK_LENGTH
        buffer.extend(((accumulator & (CHUNK_MASK << acc_length)) >> acc_length).to_bytes(CHUNK_SIZE))

    mask = 1 << acc_length
    return (accumulator & (mask - 1)) + mask, acc_length


def _flush_accumulator(buffer: bytearray, accumulator:int, acc_length:int) -> None:
    n_bytes, n_bits = divmod(acc_length, BYTE_LENGTH)
    last_byte = None
    if n_bits:
        last_byte = accumulator & ((1 << n_bits) - 1)
        last_byte <<= (BYTE_LENGTH - n_bits) # l'oubli de cette ligne m'a longtemps embêté...
        accumulator >>= n_bits
    if n_bytes:
        buffer.extend((accumulator & ((1 << (n_bytes << 3)) - 1)).to_bytes(n_bytes))
    if last_byte is not None:
        buffer.append(last_byte)



def not_verify_huf_signature(height_bytes: bytes) -> bool:
    return height_bytes[:4] != b"HUFF"

def _decode_tree(
        source: bytes,
        leaf_codes: list[int],
        index: int = 8,
        offset: int = 7,
        code: int = 1
    ) -> int: # index

    new_bit = ((source[index] & (1 << offset)) >> offset)
    code_last_bit = code & 1

    if new_bit == 1 and code_last_bit == 1:     # (new_bit: 1; code_last_bit: 1)
        leaf_codes.append(code)
        while code > 1 and code & 1:
            code >>= 1
        if code < 0b10:        
            return index + 1
        # sinon (on retombe dans le cas code_last_bit == 0, sauf qu'on a déjà append):
        #     prépare lecture prochain bit
        #     dernier return

    offset -= 1
    if offset < 0:
        index += 1
        offset = 7

    if new_bit == 0:                            # (new_bit: 0; code_last_bit: 1/0)
        return _decode_tree(source, leaf_codes, index, offset, code*2)

    if code_last_bit == 0:                      # (new_bit: 1; code_last_bit: 0)
        leaf_codes.append(code)
                                                # (new_bit: 1; code_last_bit: 1/0)
    return _decode_tree(source, leaf_codes, index, offset, code+1)




# ---------------------------------------------------------------------------------------------------------
# final tools [encoding and decoding]

def huffman_compress(source: bytes, debug=False) -> bytearray:
    leaf_bytes: list[int] = []
    huf_map: HuffmanMap = {}
    tree_code = _huffman_parse(source, leaf_bytes, huf_map)

    buffer = bytearray(b"HUFF" + (len(source)).to_bytes(4)) # ! pas bytes() car immutable dans la fonction flush
    _flush_accumulator(buffer, tree_code.decimal, tree_code.length)

    accumulator, acc_length = 1, 0

    for byte in leaf_bytes:
        accumulator <<= BYTE_LENGTH
        accumulator |= byte
        acc_length += BYTE_LENGTH

        if acc_length >= CHUNK_LENGTH:
            accumulator, acc_length = _flush_chunk_from_accumulator(buffer, accumulator, acc_length)

    for byte in source:
        code, cod_length = huf_map[byte]
        accumulator <<= cod_length
        accumulator |= (code & ((1 << (cod_length)) - 1)) # skip le premier 1 du code
        acc_length += cod_length

        if acc_length >= CHUNK_LENGTH:
            accumulator, acc_length = _flush_chunk_from_accumulator(buffer, accumulator, acc_length)

    if acc_length:
        _flush_accumulator(buffer, accumulator, acc_length)

    if debug:
        s_len = len(source)
        c_len = len(buffer)
        print(f"source length: {s_len}; compressed length: {c_len}; compression rate: {c_len / s_len}")

    return buffer



def huffman_decompress(source: bytes, debug=False) -> bytearray:
    if not_verify_huf_signature(source):
        return bytearray()

    leaf_codes = []
    src_index = _decode_tree(source, leaf_codes)

    codes_map: dict[int, Byte] = {}
    for code in leaf_codes:
        codes_map[code] = source[src_index]
        src_index += 1

    n_bytes = int.from_bytes(source[4:8])
    offset = 7
    code = 1

    buffer = bytearray()
    while n_bytes:
        code = code * 2 + ((source[src_index] & (1 << offset)) >> offset)

        if code in codes_map:
            buffer.append(codes_map[code])
            code = 1
            n_bytes -= 1

        offset -= 1
        if offset < 0:
            offset = 7
            src_index += 1

    if debug:
        s_len = len(source)
        d_len = len(buffer)
        print(f"source length: {s_len}; decompressed length: {d_len}; compression rate: {d_len / s_len}")

    return buffer
    



if __name__ == "__main__":
    import sys

    n_args = len(sys.argv) -1

    if not n_args:
        print("ajouter une commande [c/d] et un nom de fichier")
        sys.exit(1)
    if sys.argv[1] not in "cd":
        print(f"Commande inconnue: {sys.argv[1]}")
        sys.exit(1)
    if n_args < 2:
        print("Aucun fichier n'a été fourni")
        sys.exit(1)


    debug = n_args > 2 and sys.argv[2] == "-D"

    file_ext, command = (
        (".dec", huffman_decompress),
        (".huf", huffman_compress)
    )[sys.argv[1] == "c"]

    file = sys.argv[2]
    file_name = "".join(file.split(".")[:-1]) if "." in file else file

    with open(file, "rb") as source, open(file_name+file_ext, "wb") as dest:
        dest.write(command(source.read(), debug=debug))

