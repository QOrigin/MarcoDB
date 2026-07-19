# serialization.py (Versão Enterprise - Com suporte a Checksum)

import struct
import zlib

# Constantes de Tipo de Nó
NODE_TYPE_INTERNAL = 0x01
NODE_TYPE_LEAF = 0x02
NODE_TYPE_OVERFLOW = 0x03

# O Cabeçalho agora tem 17 bytes (4 do checksum + 13 de metadados originais)
PAGE_HEADER_SIZE = 17 
SLOT_SIZE = 4 # 2 bytes para offset, 2 bytes para tamanho

# Constante mágica para colocar no lugar do "tamanho do valor" 
# quando o dado for muito grande para a página folha.
OVERFLOW_MARKER = 0xFFFF # 65535, um tamanho impossível numa página de 4KB

# --- Funções de Checksum (Segurança contra Corrupção de Disco) ---

def calculate_checksum(page_data):
    """Calcula o hash seguro ignorando os primeiros 4 bytes (onde o próprio hash fica)."""
    return zlib.crc32(page_data[4:]) & 0xffffffff

def verify_page_integrity(page_data):
    """Garante que o disco não devolveu lixo corrompido."""
    stored_checksum = struct.unpack('<L', page_data[0:4])[0]
    # Se a página for nova (toda zero), o checksum será 0
    if stored_checksum == 0 and page_data[4:5] == b'\x00':
        return True 
    return stored_checksum == calculate_checksum(page_data)

def update_page_checksum(page_data):
    """Deve ser chamado logo antes do Pager salvar a página no disco."""
    checksum = calculate_checksum(page_data)
    page_data[0:4] = struct.pack('<L', checksum)


# --- Funções do Cabeçalho (Offsets rigorosamente alinhados) ---

def get_node_type(page_data):
    """Lê o byte 4: Tipo de Nó (Folha ou Interno)."""
    return page_data[4]

def set_node_type(page_data, node_type):
    """Escreve no byte 4: Tipo de Nó."""
    page_data[4] = node_type

def get_num_slots(page_data):
    """Lê os bytes 5-6: Número de slots na página."""
    return struct.unpack('<H', page_data[5:7])[0] 

def set_num_slots(page_data, num):
    """Escreve nos bytes 5-6: Número de slots na página."""
    page_data[5:7] = struct.pack('<H', num)

def get_free_space_pointer(page_data):
    """Lê os bytes 7-8: Onde o 'heap' de dados começa."""
    return struct.unpack('<H', page_data[7:9])[0]

def set_free_space_pointer(page_data, offset):
    """Atualiza os bytes 7-8: Onde o 'heap' de dados começa."""
    page_data[7:9] = struct.pack('<H', offset)

def get_parent_page_id(page_data):
    """Lê os bytes 9-12: ID da página Pai."""
    return struct.unpack('<L', page_data[9:13])[0] # L = 4 bytes

def set_parent_page_id(page_data, page_id):
    """Escreve nos bytes 9-12: ID da página Pai."""
    page_data[9:13] = struct.pack('<L', page_id)

def get_next_sibling_id(page_data):
    """(APENAS NÓS FOLHA) Lê os bytes 13-16: ID da próxima página folha."""
    return struct.unpack('<L', page_data[13:17])[0]

def set_next_sibling_id(page_data, page_id):
    """(APENAS NÓS FOLHA) Escreve nos bytes 13-16: ID da próxima página folha."""
    page_data[13:17] = struct.pack('<L', page_id)

def get_left_most_child_id(page_data):
    """(APENAS NÓS INTERNOS) Lê os bytes 13-16: ID do filho mais à esquerda."""
    return struct.unpack('<L', page_data[13:17])[0]

def set_left_most_child_id(page_data, page_id):
    """(APENAS NÓS INTERNOS) Escreve nos bytes 13-16: ID do filho mais à esquerda."""
    page_data[13:17] = struct.pack('<L', page_id)


# --- Funções de Manipulação de Slots ---

def get_slot(page_data, slot_id):
    """Lê um slot (offset e tamanho) do Diretório de Slots."""
    slot_start = PAGE_HEADER_SIZE + (slot_id * SLOT_SIZE)
    slot_end = slot_start + SLOT_SIZE
    (offset, size) = struct.unpack('<HH', page_data[slot_start:slot_end])
    return offset, size

def set_slot(page_data, slot_id, offset, size):
    """Escreve um slot (offset e tamanho) no Diretório de Slots."""
    slot_start = PAGE_HEADER_SIZE + (slot_id * SLOT_SIZE)
    page_data[slot_start : slot_start + 4] = struct.pack('<HH', offset, size)

# --- Adicione esta função para detectar se o slot aponta para um Big Data ---
def is_slot_overflow(page_data, slot_id):
    offset, size = get_slot(page_data, slot_id)
    data_bytes = page_data[offset : offset + size]
    key_size = struct.unpack('<H', data_bytes[0:2])[0]
    value_size_start = 2 + key_size
    value_size = struct.unpack('<H', data_bytes[value_size_start : value_size_start+2])[0]
    return value_size == OVERFLOW_MARKER

# --- Substitua as funções antigas por estas ---
def read_data_from_slot(page_data, slot_id):
    offset, size = get_slot(page_data, slot_id)
    if offset == 0 or size == 0:
        raise Exception(f"Slot {slot_id} inválido (offset/size nulos).")

    data_bytes = page_data[offset : offset + size]
    key_size = struct.unpack('<H', data_bytes[0:2])[0]
    key_start = 2
    key_end = key_start + key_size
    key = data_bytes[key_start:key_end]
    
    value_size_start = key_end
    value_size_end = value_size_start + 2
    value_size = struct.unpack('<H', data_bytes[value_size_start:value_size_end])[0]
    
    # MUDANÇA: Se o tamanho for 65535, é um Overflow! O valor real aqui é só um ID de 4 bytes.
    if value_size == OVERFLOW_MARKER:
        value_size = 4 

    value_start = value_size_end
    value_end = value_start + value_size
    value = data_bytes[value_start:value_end]
    
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
    
    # MUDANÇA: Escreve o Marcador Mágico se for Big Data
    marker = OVERFLOW_MARKER if is_overflow else value_size
    struct.pack_into('<H', page_data, pos, marker)
    pos += 2
    
    page_data[pos : pos + value_size] = value_bytes
    
    set_free_space_pointer(page_data, new_offset)
    return new_offset, total_size

def write_overflow_page(page_data, next_page_id, chunk_bytes):
    """
    Formata uma página de overflow:
    [Byte 4: Tipo] [Bytes 5-8: ID da Próxima Página (0 se for a última)] [Bytes 9+: O pedaço do texto]
    """
    set_node_type(page_data, NODE_TYPE_OVERFLOW)
    page_data[5:9] = struct.pack('<L', next_page_id)
    
    # O tamanho do texto que coube nesta página
    chunk_size = len(chunk_bytes)
    page_data[9:11] = struct.pack('<H', chunk_size)
    
    # Escreve o pedaço do texto gigante
    page_data[11 : 11 + chunk_size] = chunk_bytes

def read_overflow_page(page_data):
    """Lê uma página de overflow e retorna (next_page_id, chunk_bytes)."""
    next_page_id = struct.unpack('<L', page_data[5:9])[0]
    chunk_size = struct.unpack('<H', page_data[9:11])[0]
    chunk_bytes = page_data[11 : 11 + chunk_size]
    
    return next_page_id, chunk_bytes