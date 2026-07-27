import struct
import zlib

NODE_TYPE_INTERNAL = 0x01
NODE_TYPE_LEAF = 0x02
NODE_TYPE_OVERFLOW = 0x03

PAGE_HEADER_SIZE = 17 
SLOT_SIZE = 4 

OVERFLOW_MARKER = 0xFFFF 

# --- Funções de Checksum ---

def calculate_checksum(page_data):
    # Usa memoryview para evitar a cópia dos bytes ao calcular o hash!
    view = memoryview(page_data)
    return zlib.crc32(view[4:]) & 0xffffffff

def verify_page_integrity(page_data):
    # Zero-Copy unpack
    stored_checksum = struct.unpack_from('<L', page_data, 0)[0]
    if stored_checksum == 0 and page_data[4] == 0:
        return True 
    return stored_checksum == calculate_checksum(page_data)

def update_page_checksum(page_data):
    checksum = calculate_checksum(page_data)
    struct.pack_into('<L', page_data, 0, checksum)


# --- Funções do Cabeçalho (Otimizadas com Zero-Copy) ---

def get_node_type(page_data):
    return page_data[4]

def set_node_type(page_data, node_type):
    page_data[4] = node_type

def get_num_slots(page_data):
    return struct.unpack_from('<H', page_data, 5)[0] 

def set_num_slots(page_data, num):
    struct.pack_into('<H', page_data, 5, num)

def get_free_space_pointer(page_data):
    return struct.unpack_from('<H', page_data, 7)[0]

def set_free_space_pointer(page_data, offset):
    struct.pack_into('<H', page_data, 7, offset)

def get_parent_page_id(page_data):
    return struct.unpack_from('<L', page_data, 9)[0]

def set_parent_page_id(page_data, page_id):
    struct.pack_into('<L', page_data, 9, page_id)

def get_next_sibling_id(page_data):
    return struct.unpack_from('<L', page_data, 13)[0]

def set_next_sibling_id(page_data, page_id):
    struct.pack_into('<L', page_data, 13, page_id)

def get_left_most_child_id(page_data):
    return struct.unpack_from('<L', page_data, 13)[0]

def set_left_most_child_id(page_data, page_id):
    struct.pack_into('<L', page_data, 13, page_id)


# --- Funções de Manipulação de Slots ---

def get_slot(page_data, slot_id):
    slot_start = PAGE_HEADER_SIZE + (slot_id * SLOT_SIZE)
    return struct.unpack_from('<HH', page_data, slot_start)

def set_slot(page_data, slot_id, offset, size):
    slot_start = PAGE_HEADER_SIZE + (slot_id * SLOT_SIZE)
    struct.pack_into('<HH', page_data, slot_start, offset, size)

def is_slot_overflow(page_data, slot_id):
    offset, size = get_slot(page_data, slot_id)
    key_size = struct.unpack_from('<H', page_data, offset)[0]
    value_size_start = offset + 2 + key_size
    value_size = struct.unpack_from('<H', page_data, value_size_start)[0]
    return value_size == OVERFLOW_MARKER

def read_data_from_slot(page_data, slot_id):
    offset, size = get_slot(page_data, slot_id)
    if offset == 0 or size == 0:
        raise Exception(f"Slot {slot_id} inválido (offset/size nulos).")

    key_size = struct.unpack_from('<H', page_data, offset)[0]
    
    # Extraímos a chave diretamente (Ainda precisa de slice aqui para gerar o objeto final)
    key_start = offset + 2
    key_end = key_start + key_size
    key = page_data[key_start:key_end]
    
    value_size_start = key_end
    value_size = struct.unpack_from('<H', page_data, value_size_start)[0]
    
    if value_size == OVERFLOW_MARKER:
        value_size = 4 

    value_start = value_size_start + 2
    value_end = value_start + value_size
    value = page_data[value_start:value_end]
    
    return key, value

def write_data_to_heap(page_data, key_bytes, value_bytes, is_overflow=False):
    key_size = len(key_bytes)
    value_size = len(value_bytes)
    total_size = 2 + key_size + 2 + value_size
    
    free_offset = get_free_space_pointer(page_data)
    new_offset = free_offset - total_size
    
    current_num_slots = get_num_slots(page_data)
    slot_directory_end = PAGE_HEADER_SIZE + ((current_num_slots + 1) * SLOT_SIZE)
    
    if new_offset < slot_directory_end:
         raise Exception(f"Página cheia (heap colidiu com slots em {new_offset} vs {slot_directory_end})")

    pos = new_offset
    struct.pack_into('<H', page_data, pos, key_size)
    pos += 2
    
    page_data[pos : pos + key_size] = key_bytes
    pos += key_size
    
    marker = OVERFLOW_MARKER if is_overflow else value_size
    struct.pack_into('<H', page_data, pos, marker)
    pos += 2
    
    page_data[pos : pos + value_size] = value_bytes
    
    set_free_space_pointer(page_data, new_offset)
    return new_offset, total_size

def write_overflow_page(page_data, next_page_id, chunk_bytes):
    set_node_type(page_data, NODE_TYPE_OVERFLOW)
    struct.pack_into('<L', page_data, 5, next_page_id)
    
    chunk_size = len(chunk_bytes)
    struct.pack_into('<H', page_data, 9, chunk_size)
    
    page_data[11 : 11 + chunk_size] = chunk_bytes

def read_overflow_page(page_data):
    next_page_id = struct.unpack_from('<L', page_data, 5)[0]
    chunk_size = struct.unpack_from('<H', page_data, 9)[0]
    
    chunk_bytes = page_data[11 : 11 + chunk_size]
    
    return next_page_id, chunk_bytes