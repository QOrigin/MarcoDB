import serialization as srl
from pager import Pager
from serialization import NODE_TYPE_INTERNAL, NODE_TYPE_LEAF

PAGE_SIZE = 4096 
MIN_SLOTS_THRESHOLD = 1 
MAX_LEAF_VALUE_SIZE = 2000 # Se o valor for maior que isso, vira Overflow!

class BPlusTree:
    def __init__(self, pager):
        self.pager = pager
        meta_page = self.pager.get_page(0)
        self.root_page_id = int.from_bytes(meta_page[17:21], 'little')

        if self.root_page_id == 0:
            print("INFO: Criando novo banco de dados...")
            root_page_id, root_page_data = self.pager.new_page()
            self.root_page_id = root_page_id 

            srl.set_node_type(root_page_data, NODE_TYPE_LEAF)
            srl.set_num_slots(root_page_data, 0)
            srl.set_free_space_pointer(root_page_data, PAGE_SIZE)
            srl.set_parent_page_id(root_page_data, 0)
            srl.set_next_sibling_id(root_page_data, 0) 
            
            meta_page[17:21] = self.root_page_id.to_bytes(4, 'little')
            
            self.pager.mark_dirty(0) 
            self.pager.mark_dirty(self.root_page_id)
        else:
            print(f"INFO: Abrindo banco de dados existente. Raiz na página {self.root_page_id}")

    # --- FUNÇÕES DE OVERFLOW (Trem de Páginas) ---
    def _write_overflow_pages(self, value_bytes):
        chunk_size = 4000 # Deixa um espaço seguro para o cabeçalho
        chunks = [value_bytes[i:i + chunk_size] for i in range(0, len(value_bytes), chunk_size)]
        
        next_page_id = 0
        # Escreve de trás pra frente para que cada página saiba o ID da próxima
        for chunk in reversed(chunks):
            new_page_id, new_page_data = self.pager.new_page()
            srl.write_overflow_page(new_page_data, next_page_id, chunk)
            self.pager.mark_dirty(new_page_id)
            next_page_id = new_page_id
            
        return next_page_id # Retorna a cabeça do trem

    def _read_overflow_pages(self, first_page_id):
        value_bytes = bytearray()
        current_page_id = first_page_id
        
        while current_page_id != 0:
            page_data = self.pager.get_page(current_page_id)
            next_page_id, chunk_bytes = srl.read_overflow_page(page_data)
            value_bytes.extend(chunk_bytes)
            current_page_id = next_page_id
            
        return bytes(value_bytes)

    # --- FUNÇÃO DE BUSCA ---
    def search(self, key):
        key_bytes = key.encode('utf-8') 
        try:
            value_bytes = self._search_recursive(self.root_page_id, key_bytes)
            if value_bytes:
                return value_bytes.decode('utf-8')
            else:
                return None
        except Exception as e:
            print(f"ERRO ao buscar '{key}': {e}")
            raise 

    def _search_recursive(self, page_id, key_bytes):
        page = self.pager.get_page(page_id)
        node_type = srl.get_node_type(page) 

        if node_type == NODE_TYPE_LEAF:
            return self._search_in_leaf_node(page, key_bytes)
        elif node_type == NODE_TYPE_INTERNAL:
            next_page_id = self._search_in_internal_node(page, key_bytes)
            if next_page_id == 0: 
                return None
            return self._search_recursive(next_page_id, key_bytes)
        else:
            raise Exception(f"Corrupção: Página {page_id} tem tipo desconhecido ({node_type})")

    def _search_in_leaf_node(self, page_data, key_bytes_to_find):
        num_slots = srl.get_num_slots(page_data)
        for slot_id in range(num_slots):
            key, value = srl.read_data_from_slot(page_data, slot_id)
            if key == key_bytes_to_find:
                # SE FOR GIGANTE, LÊ O TREM DE PÁGINAS!
                if srl.is_slot_overflow(page_data, slot_id):
                    first_page_id = int.from_bytes(value, 'little')
                    return self._read_overflow_pages(first_page_id)
                return value
        return None 
    
    def _search_in_internal_node(self, page_data, key_bytes_to_find):
        num_slots = srl.get_num_slots(page_data)
        next_page_id = srl.get_left_most_child_id(page_data)
        for slot_id in range(num_slots):
            key, value_bytes = srl.read_data_from_slot(page_data, slot_id)
            child_page_id = int.from_bytes(value_bytes, 'little')
            if key_bytes_to_find >= key:
                next_page_id = child_page_id
            else:
                break
        return next_page_id

    # --- FUNÇÃO DE INSERÇÃO ---
    def insert(self, key, value):
        key_bytes = key.encode('utf-8')
        value_bytes = value.encode('utf-8')
        try:
            self._insert_recursive(self.root_page_id, key_bytes, value_bytes)
        except Exception as e:
            print(f"ERRO ao inserir ('{key}', '{value[:20]}...'): {e}")
            raise 
    
    def update(self, key, value):
        """Atualiza um valor existente deletando o antigo e inserindo o novo."""
        # 1. Verifica se a chave realmente existe antes de tentar atualizar
        if self.search(key) is None:
            raise Exception(f"Chave '{key}' não encontrada para atualização.")
        
        # 2. Faz o 'Falso Update' (Deleta e Insere novamente)
        try:
            self.delete(key)
            self.insert(key, value)
        except Exception as e:
            print(f"ERRO ao atualizar ('{key}'): {e}")
            raise

    def _insert_recursive(self, page_id, key_bytes, value_bytes):
        page = self.pager.get_page(page_id)
        node_type = srl.get_node_type(page)

        if node_type == NODE_TYPE_LEAF:
            self._insert_into_leaf(page_id, page, key_bytes, value_bytes)
        elif node_type == NODE_TYPE_INTERNAL: 
            child_page_id = self._search_in_internal_node(page, key_bytes)
            self._insert_recursive(child_page_id, key_bytes, value_bytes)
        else:
            raise Exception(f"Corrupção: Página {page_id} tipo desconhecido.")
            
    def _insert_into_leaf(self, page_id, page_data, key_bytes, value_bytes):
        is_overflow = False
        # SE O DADO FOR MUITO GRANDE, TRANFORMA EM OVERFLOW
        if len(value_bytes) > MAX_LEAF_VALUE_SIZE:
            first_overflow_id = self._write_overflow_pages(value_bytes)
            # O valor a ser salvo na Folha passa a ser só o ID de 4 bytes
            value_bytes = first_overflow_id.to_bytes(4, 'little')
            is_overflow = True

        key_size = len(key_bytes)
        value_size = len(value_bytes)
        data_block_size = 2 + key_size + 2 + value_size 
        
        num_slots = srl.get_num_slots(page_data)
        slot_size = srl.SLOT_SIZE
        free_space_pointer = srl.get_free_space_pointer(page_data)
        slot_directory_end = srl.PAGE_HEADER_SIZE + ((num_slots + 1) * slot_size)
        available_space = free_space_pointer - slot_directory_end
        
        if (data_block_size) > available_space: 
            self._split_leaf_node(page_id, page_data, key_bytes, value_bytes, is_overflow)
        else:
            self._insert_data_into_page(page_id, page_data, key_bytes, value_bytes, data_block_size, is_overflow)

    def _insert_data_into_page(self, page_id, page_data, key_bytes, value_bytes, data_block_size, is_overflow=False):
        num_slots = srl.get_num_slots(page_data)
        insertion_point = 0
        for i in range(num_slots):
            key, _ = srl.read_data_from_slot(page_data, i)
            if key == key_bytes:
                raise Exception(f"Chave '{key_bytes.decode()}' já existe.")
            if key > key_bytes:
                break
            insertion_point = i + 1
            
        new_offset, total_size = srl.write_data_to_heap(page_data, key_bytes, value_bytes, is_overflow)
        
        slot_dir_start = srl.PAGE_HEADER_SIZE
        slot_to_insert_at = slot_dir_start + (insertion_point * srl.SLOT_SIZE)
        end_of_slots = slot_dir_start + (num_slots * srl.SLOT_SIZE)
        
        page_data[slot_to_insert_at + srl.SLOT_SIZE : end_of_slots + srl.SLOT_SIZE] = \
            page_data[slot_to_insert_at : end_of_slots]

        srl.set_slot(page_data, insertion_point, new_offset, total_size)
        srl.set_num_slots(page_data, num_slots + 1)
        self.pager.mark_dirty(page_id)

    # --- FUNÇÕES DE ESTRUTURA E BALANCEAMENTO ---
    def _create_new_root(self, left_child_id, right_child_id, median_key):
        new_root_id, new_root_data = self.pager.new_page()
        srl.set_node_type(new_root_data, NODE_TYPE_INTERNAL)
        srl.set_num_slots(new_root_data, 1) 
        srl.set_free_space_pointer(new_root_data, PAGE_SIZE)
        srl.set_parent_page_id(new_root_data, 0) 
        srl.set_left_most_child_id(new_root_data, left_child_id)
        
        child_id_bytes = right_child_id.to_bytes(4, 'little')
        offset, size = srl.write_data_to_heap(new_root_data, median_key, child_id_bytes)
        srl.set_slot(new_root_data, 0, offset, size)
        
        left_page = self.pager.get_page(left_child_id)
        srl.set_parent_page_id(left_page, new_root_id)
        right_page = self.pager.get_page(right_child_id)
        srl.set_parent_page_id(right_page, new_root_id)

        self.root_page_id = new_root_id
        meta_page = self.pager.get_page(0)
        meta_page[17:21] = self.root_page_id.to_bytes(4, 'little')
        
        self.pager.mark_dirty(0)
        self.pager.mark_dirty(self.root_page_id)
        self.pager.mark_dirty(left_child_id)
        self.pager.mark_dirty(right_child_id)

    def _split_leaf_node(self, old_page_id, old_page_data, key_to_insert, value_to_insert, is_overflow_insert=False):
        all_data = []
        num_slots = srl.get_num_slots(old_page_data)
        
        for i in range(num_slots):
            k, v = srl.read_data_from_slot(old_page_data, i)
            ovf = srl.is_slot_overflow(old_page_data, i)
            all_data.append((k, v, ovf))
            
        all_data.append((key_to_insert, value_to_insert, is_overflow_insert))
        all_data.sort(key=lambda item: item[0])
        
        new_page_id, new_page_data = self.pager.new_page()
        srl.set_node_type(new_page_data, NODE_TYPE_LEAF)
        srl.set_num_slots(new_page_data, 0)
        srl.set_free_space_pointer(new_page_data, PAGE_SIZE)
        
        parent_page_id = srl.get_parent_page_id(old_page_data)
        srl.set_parent_page_id(new_page_data, parent_page_id)
        
        old_sibling_id = srl.get_next_sibling_id(old_page_data)
        srl.set_next_sibling_id(new_page_data, old_sibling_id)
        srl.set_next_sibling_id(old_page_data, new_page_id)

        srl.set_num_slots(old_page_data, 0)
        srl.set_free_space_pointer(old_page_data, PAGE_SIZE)
        
        split_point = len(all_data) // 2
        median_key = all_data[split_point][0] 
        
        for i in range(0, split_point):
            k, v, ovf = all_data[i]
            data_size = 2 + len(k) + 2 + len(v)
            self._insert_data_into_page(old_page_id, old_page_data, k, v, data_size, ovf)
            
        for i in range(split_point, len(all_data)):
            k, v, ovf = all_data[i]
            data_size = 2 + len(k) + 2 + len(v)
            self._insert_data_into_page(new_page_id, new_page_data, k, v, data_size, ovf)

        if parent_page_id == 0:
            self._create_new_root(old_page_id, new_page_id, median_key)
        else:
            self._insert_into_parent(parent_page_id, old_page_id, median_key, new_page_id)
            
        self.pager.mark_dirty(old_page_id)
        self.pager.mark_dirty(new_page_id)

    def _insert_into_internal_node(self, page_id, page_data, key_bytes, child_id):
        num_slots = srl.get_num_slots(page_data)
        value_bytes = child_id.to_bytes(4, 'little')
        
        insertion_point = 0
        for i in range(num_slots):
            key, _ = srl.read_data_from_slot(page_data, i)
            if key == key_bytes:
                raise Exception(f"Chave duplicada no nó interno {page_id}")
            if key > key_bytes:
                break
            insertion_point = i + 1
            
        new_offset, total_size = srl.write_data_to_heap(page_data, key_bytes, value_bytes, False)
        
        slot_dir_start = srl.PAGE_HEADER_SIZE
        slot_to_insert_at = slot_dir_start + (insertion_point * srl.SLOT_SIZE)
        end_of_slots = slot_dir_start + (num_slots * srl.SLOT_SIZE)
        page_data[slot_to_insert_at + srl.SLOT_SIZE : end_of_slots + srl.SLOT_SIZE] = \
            page_data[slot_to_insert_at : end_of_slots]

        srl.set_slot(page_data, insertion_point, new_offset, total_size)
        srl.set_num_slots(page_data, num_slots + 1)
        self.pager.mark_dirty(page_id)

    def _insert_into_parent(self, parent_page_id, left_child_id, median_key, right_child_id):
        parent_page = self.pager.get_page(parent_page_id)
        key_size = len(median_key)
        data_block_size = 2 + key_size + 2 + 4
        
        num_slots = srl.get_num_slots(parent_page)
        free_space_pointer = srl.get_free_space_pointer(parent_page)
        slot_directory_end = srl.PAGE_HEADER_SIZE + ((num_slots + 1) * srl.SLOT_SIZE)
        
        if (data_block_size) <= (free_space_pointer - slot_directory_end):
            self._insert_into_internal_node(parent_page_id, parent_page, median_key, right_child_id)
            right_child_page = self.pager.get_page(right_child_id)
            srl.set_parent_page_id(right_child_page, parent_page_id)
            self.pager.mark_dirty(right_child_id)
        else:
            self._split_internal_node(parent_page_id, parent_page, median_key, right_child_id)

    def _split_internal_node(self, old_page_id, old_page_data, key_to_insert, child_id_to_insert):
        all_pointers = []
        num_slots = srl.get_num_slots(old_page_data)
        for i in range(num_slots):
            key, value_bytes = srl.read_data_from_slot(old_page_data, i)
            all_pointers.append((key, int.from_bytes(value_bytes, 'little')))
            
        all_pointers.append((key_to_insert, child_id_to_insert))
        all_pointers.sort(key=lambda item: item[0])

        new_page_id, new_page_data = self.pager.new_page()
        srl.set_node_type(new_page_data, NODE_TYPE_INTERNAL)
        srl.set_num_slots(new_page_data, 0)
        srl.set_free_space_pointer(new_page_data, PAGE_SIZE)
        
        parent_page_id = srl.get_parent_page_id(old_page_data)
        srl.set_parent_page_id(new_page_data, parent_page_id)
        
        split_point = len(all_pointers) // 2
        median_key_promoted, median_child_id = all_pointers[split_point]
        
        left_pointers = all_pointers[:split_point]
        right_pointers = all_pointers[split_point + 1:] 
        
        srl.set_num_slots(old_page_data, 0)
        srl.set_free_space_pointer(old_page_data, PAGE_SIZE)
        
        for key, child_id in left_pointers:
            self._insert_into_internal_node(old_page_id, old_page_data, key, child_id)
            
        srl.set_left_most_child_id(new_page_data, median_child_id)
        for key, child_id in right_pointers:
            self._insert_into_internal_node(new_page_id, new_page_data, key, child_id)

        child_page = self.pager.get_page(median_child_id)
        srl.set_parent_page_id(child_page, new_page_id)
        self.pager.mark_dirty(median_child_id)
        
        for _, child_id in right_pointers:
            child_page = self.pager.get_page(child_id)
            srl.set_parent_page_id(child_page, new_page_id)
            self.pager.mark_dirty(child_id)

        if parent_page_id == 0:
            self._create_new_root(old_page_id, new_page_id, median_key_promoted)
        else:
            self._insert_into_parent(parent_page_id, old_page_id, median_key_promoted, new_page_id)
            
        self.pager.mark_dirty(old_page_id)
        self.pager.mark_dirty(new_page_id)

    # --- FUNÇÕES DE DELEÇÃO E REARRANJO ---
    def delete(self, key):
        key_bytes = key.encode('utf-8')
        try:
            self._delete_recursive(self.root_page_id, key_bytes)
        except Exception as e:
            print(f"ERRO ao deletar ('{key}'): {e}")
            raise 

    def _delete_recursive(self, page_id, key_bytes_to_delete):
        page = self.pager.get_page(page_id)
        node_type = srl.get_node_type(page)

        if node_type == NODE_TYPE_LEAF:
            return self._delete_from_leaf(page_id, page, key_bytes_to_delete)
        elif node_type == NODE_TYPE_INTERNAL: 
            child_page_id = self._search_in_internal_node(page, key_bytes_to_delete)
            if child_page_id == 0: raise Exception(f"Chave '{key_bytes_to_delete.decode()}' não encontrada.")
            self._delete_recursive(child_page_id, key_bytes_to_delete)
        else:
            raise Exception(f"Corrupção de Memória ao deletar.")
            
    def _delete_from_leaf(self, page_id, page_data, key_bytes_to_delete):
        num_slots = srl.get_num_slots(page_data)
        all_data = []
        found = False
        for i in range(num_slots):
            key, value = srl.read_data_from_slot(page_data, i)
            ovf = srl.is_slot_overflow(page_data, i)
            if key == key_bytes_to_delete:
                found = True # Idealmente, num banco comercial, liberaríamos as páginas de overflow aqui.
            else:
                all_data.append((key, value, ovf))
        
        if not found:
            raise Exception(f"Chave não encontrada.")

        srl.set_num_slots(page_data, 0)
        srl.set_free_space_pointer(page_data, PAGE_SIZE)
        
        for k, v, ovf in all_data:
            data_size = 2 + len(k) + 2 + len(v)
            self._insert_data_into_page(page_id, page_data, k, v, data_size, ovf)
            
        self.pager.mark_dirty(page_id)
        if self.root_page_id == page_id: return 
        if srl.get_num_slots(page_data) < MIN_SLOTS_THRESHOLD:
            self._handle_leaf_underflow(page_id, page_data)
        
    def _find_sibling_info(self, parent_page_data, child_page_id):
        num_slots = srl.get_num_slots(parent_page_data)
        left_most = srl.get_left_most_child_id(parent_page_data)
        
        if child_page_id == left_most:
            if num_slots == 0: return (None, None, None, None)
            _, right_sib_bytes = srl.read_data_from_slot(parent_page_data, 0)
            return (None, int.from_bytes(right_sib_bytes, 'little'), None, 0)

        for i in range(num_slots):
            _, child_id_bytes = srl.read_data_from_slot(parent_page_data, i)
            child_id = int.from_bytes(child_id_bytes, 'little')
            
            if child_id == child_page_id:
                if i == 0: left_sib_id = left_most
                else: left_sib_id = int.from_bytes(srl.read_data_from_slot(parent_page_data, i - 1)[1], 'little')

                right_sib_id, index_right = None, None
                if i + 1 < num_slots:
                    right_sib_id = int.from_bytes(srl.read_data_from_slot(parent_page_data, i + 1)[1], 'little')
                    index_right = i + 1
                    
                return (left_sib_id, right_sib_id, i, index_right) 
        raise Exception("Erro ao buscar irmão.")

    def _handle_leaf_underflow(self, page_id, page_data):
        parent_page_id = srl.get_parent_page_id(page_data)
        if parent_page_id == 0: return
        parent_page_data = self.pager.get_page(parent_page_id)
        
        left_sib_id, right_sib_id, key_idx_left, key_idx_right = self._find_sibling_info(parent_page_data, page_id)
        
        if right_sib_id is not None:
            right_sib_data = self.pager.get_page(right_sib_id)
            if srl.get_num_slots(right_sib_data) > MIN_SLOTS_THRESHOLD:
                self._borrow_from_right_leaf(page_id, page_data, right_sib_id, right_sib_data, parent_page_id, parent_page_data, key_idx_right)
                return 

        if left_sib_id is not None:
            left_sib_data = self.pager.get_page(left_sib_id)
            if srl.get_num_slots(left_sib_data) > MIN_SLOTS_THRESHOLD:
                self._borrow_from_left_leaf(page_id, page_data, left_sib_id, left_sib_data, parent_page_id, parent_page_data, key_idx_left)
                return
        
        if right_sib_id is not None:
            self._merge_leaf_nodes(page_id, page_data, right_sib_id, self.pager.get_page(right_sib_id), parent_page_id, parent_page_data, key_idx_right)
            return 
        
        if left_sib_id is not None:
             self._merge_leaf_nodes(left_sib_id, self.pager.get_page(left_sib_id), page_id, page_data, parent_page_id, parent_page_data, key_idx_left)

    def _borrow_from_right_leaf(self, page_id, page_data, right_sib_id, right_sib_data, parent_page_id, parent_page_data, parent_key_index_RIGHT):
        my_data = []
        for i in range(srl.get_num_slots(page_data)):
            k, v = srl.read_data_from_slot(page_data, i)
            my_data.append((k, v, srl.is_slot_overflow(page_data, i)))
            
        right_data = []
        for i in range(srl.get_num_slots(right_sib_data)):
            k, v = srl.read_data_from_slot(right_sib_data, i)
            right_data.append((k, v, srl.is_slot_overflow(right_sib_data, i)))
            
        borrowed = right_data.pop(0)
        my_data.append(borrowed)
        new_separator_key = right_data[0][0]
        
        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        srl.set_num_slots(right_sib_data, 0); srl.set_free_space_pointer(right_sib_data, PAGE_SIZE)

        for k, v, ovf in my_data:
            self._insert_data_into_page(page_id, page_data, k, v, 2+len(k)+2+len(v), ovf)
        for k, v, ovf in right_data:
            self._insert_data_into_page(right_sib_id, right_sib_data, k, v, 2+len(k)+2+len(v), ovf)

        old_key = srl.read_data_from_slot(parent_page_data, parent_key_index_RIGHT)[0]
        old_child_id = int.from_bytes(srl.read_data_from_slot(parent_page_data, parent_key_index_RIGHT)[1], 'little') 
        self._delete_entry_from_internal_node(parent_page_id, parent_page_data, old_key, skip_underflow_check=True)
        self._insert_into_internal_node(parent_page_id, parent_page_data, new_separator_key, old_child_id)

        self.pager.mark_dirty(page_id); self.pager.mark_dirty(right_sib_id); self.pager.mark_dirty(parent_page_id)

    def _borrow_from_left_leaf(self, page_id, page_data, left_sib_id, left_sib_data, parent_page_id, parent_page_data, parent_key_index_LEFT):
        my_data = []
        for i in range(srl.get_num_slots(page_data)):
            k, v = srl.read_data_from_slot(page_data, i)
            my_data.append((k, v, srl.is_slot_overflow(page_data, i)))
            
        left_data = []
        for i in range(srl.get_num_slots(left_sib_data)):
            k, v = srl.read_data_from_slot(left_sib_data, i)
            left_data.append((k, v, srl.is_slot_overflow(left_sib_data, i)))
            
        borrowed = left_data.pop()
        my_data.insert(0, borrowed)
        new_separator_key = borrowed[0]
        
        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        srl.set_num_slots(left_sib_data, 0); srl.set_free_space_pointer(left_sib_data, PAGE_SIZE)
        
        for k, v, ovf in my_data: self._insert_data_into_page(page_id, page_data, k, v, 2+len(k)+2+len(v), ovf)
        for k, v, ovf in left_data: self._insert_data_into_page(left_sib_id, left_sib_data, k, v, 2+len(k)+2+len(v), ovf)
        
        old_key = srl.read_data_from_slot(parent_page_data, parent_key_index_LEFT)[0]
        old_child_id = int.from_bytes(srl.read_data_from_slot(parent_page_data, parent_key_index_LEFT)[1], 'little')
        self._delete_entry_from_internal_node(parent_page_id, parent_page_data, old_key, skip_underflow_check=True)
        self._insert_into_internal_node(parent_page_id, parent_page_data, new_separator_key, old_child_id)
        self.pager.mark_dirty(page_id); self.pager.mark_dirty(left_sib_id); self.pager.mark_dirty(parent_page_id)

    def _merge_leaf_nodes(self, page_id, page_data, right_sib_id, right_sib_data, parent_page_id, parent_page_data, parent_key_index): 
        all_data = []
        for i in range(srl.get_num_slots(page_data)):
            k, v = srl.read_data_from_slot(page_data, i)
            all_data.append((k, v, srl.is_slot_overflow(page_data, i)))
        for i in range(srl.get_num_slots(right_sib_data)):
            k, v = srl.read_data_from_slot(right_sib_data, i)
            all_data.append((k, v, srl.is_slot_overflow(right_sib_data, i)))
            
        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        for k, v, ovf in all_data: self._insert_data_into_page(page_id, page_data, k, v, 2+len(k)+2+len(v), ovf)

        srl.set_next_sibling_id(page_data, srl.get_next_sibling_id(right_sib_data))
        key_to_delete = srl.read_data_from_slot(parent_page_data, parent_key_index)[0]
        self._delete_entry_from_internal_node(parent_page_id, parent_page_data, key_to_delete)
        self.pager.mark_dirty(page_id)
        
    def _delete_entry_from_internal_node(self, page_id, page_data, key_to_delete, skip_underflow_check=False):
        num_slots = srl.get_num_slots(page_data)
        slot_to_delete = -1
        for i in range(num_slots):
            k, _ = srl.read_data_from_slot(page_data, i)
            if k == key_to_delete: slot_to_delete = i; break
        
        if slot_to_delete == -1: raise Exception("Chave não encontrada no pai.")
        
        all_pointers = [(None, srl.get_left_most_child_id(page_data))]
        for i in range(num_slots):
            k, val_bytes = srl.read_data_from_slot(page_data, i)
            if k != key_to_delete: all_pointers.append((k, int.from_bytes(val_bytes, 'little')))
        
        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        srl.set_left_most_child_id(page_data, all_pointers.pop(0)[1])
        for k, child_id in all_pointers: self._insert_into_internal_node(page_id, page_data, k, child_id)
            
        self.pager.mark_dirty(page_id)
        num_slots = srl.get_num_slots(page_data)

        if skip_underflow_check: return
        if page_id == self.root_page_id:
            if num_slots == 0 and srl.get_node_type(page_data) == NODE_TYPE_INTERNAL: self._shrink_root(page_data)
            return
        if num_slots < MIN_SLOTS_THRESHOLD: self._handle_internal_underflow(page_id, page_data)

    def _handle_internal_underflow(self, page_id, page_data):
        parent_page_id = srl.get_parent_page_id(page_data)
        if parent_page_id == 0: return
        parent_page_data = self.pager.get_page(parent_page_id)
        left_sib_id, right_sib_id, key_idx_left, key_idx_right = self._find_sibling_info(parent_page_data, page_id)
        
        if right_sib_id is not None:
            right_sib_data = self.pager.get_page(right_sib_id)
            if srl.get_num_slots(right_sib_data) > MIN_SLOTS_THRESHOLD:
                self._borrow_from_right_internal(page_id, page_data, right_sib_id, right_sib_data, parent_page_id, parent_page_data, key_idx_right)
                return 

        if left_sib_id is not None:
            left_sib_data = self.pager.get_page(left_sib_id)
            if srl.get_num_slots(left_sib_data) > MIN_SLOTS_THRESHOLD:
                self._borrow_from_left_internal(page_id, page_data, left_sib_id, left_sib_data, parent_page_id, parent_page_data, key_idx_left)
                return
        
        if right_sib_id is not None:
            self._merge_internal_nodes(page_id, page_data, right_sib_id, self.pager.get_page(right_sib_id), parent_page_id, parent_page_data, key_idx_right) 
            return 
                
        if left_sib_id is not None:
             self._merge_internal_nodes(left_sib_id, self.pager.get_page(left_sib_id), page_id, page_data, parent_page_id, parent_page_data, key_idx_left)

    def _borrow_from_right_internal(self, page_id, page_data, right_sib_id, right_sib_data, parent_page_id, parent_page_data, parent_key_index_RIGHT): 
        my_pointers = [(None, srl.get_left_most_child_id(page_data))]
        for i in range(srl.get_num_slots(page_data)): my_pointers.append((srl.read_data_from_slot(page_data, i)[0], int.from_bytes(srl.read_data_from_slot(page_data, i)[1], 'little')))
        right_pointers = [(None, srl.get_left_most_child_id(right_sib_data))]
        for i in range(srl.get_num_slots(right_sib_data)): right_pointers.append((srl.read_data_from_slot(right_sib_data, i)[0], int.from_bytes(srl.read_data_from_slot(right_sib_data, i)[1], 'little')))
            
        separator_key = srl.read_data_from_slot(parent_page_data, parent_key_index_RIGHT)[0]
        separator_child_id = int.from_bytes(srl.read_data_from_slot(parent_page_data, parent_key_index_RIGHT)[1], 'little')
        
        borrowed_child = right_pointers.pop(0)[1] 
        my_pointers.append((separator_key, borrowed_child))
        new_separator_key = right_pointers[0][0] 
        
        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        srl.set_num_slots(right_sib_data, 0); srl.set_free_space_pointer(right_sib_data, PAGE_SIZE)
        
        srl.set_left_most_child_id(page_data, my_pointers.pop(0)[1])
        for k, child_id in my_pointers: self._insert_into_internal_node(page_id, page_data, k, child_id)
        srl.set_left_most_child_id(right_sib_data, right_pointers.pop(0)[1])
        for k, child_id in right_pointers: self._insert_into_internal_node(right_sib_id, right_sib_data, k, child_id)

        self._delete_entry_from_internal_node(parent_page_id, parent_page_data, separator_key, skip_underflow_check=True)
        self._insert_into_internal_node(parent_page_id, parent_page_data, new_separator_key, separator_child_id)
        self.pager.mark_dirty(page_id); self.pager.mark_dirty(right_sib_id); self.pager.mark_dirty(parent_page_id)
        
    def _borrow_from_left_internal(self, page_id, page_data, left_sib_id, left_sib_data, parent_page_id, parent_page_data, parent_key_index_LEFT):
        my_pointers = [(None, srl.get_left_most_child_id(page_data))]
        for i in range(srl.get_num_slots(page_data)): my_pointers.append((srl.read_data_from_slot(page_data, i)[0], int.from_bytes(srl.read_data_from_slot(page_data, i)[1], 'little')))
        left_pointers = [(None, srl.get_left_most_child_id(left_sib_data))]
        for i in range(srl.get_num_slots(left_sib_data)): left_pointers.append((srl.read_data_from_slot(left_sib_data, i)[0], int.from_bytes(srl.read_data_from_slot(left_sib_data, i)[1], 'little')))
            
        separator_key = srl.read_data_from_slot(parent_page_data, parent_key_index_LEFT)[0]
        separator_child_id = int.from_bytes(srl.read_data_from_slot(parent_page_data, parent_key_index_LEFT)[1], 'little')
        
        borrowed_key, borrowed_child_id = left_pointers.pop() 
        my_pointers.insert(0, (separator_key, my_pointers.pop(0)[1]))
        srl.set_left_most_child_id(page_data, borrowed_child_id)
        
        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        srl.set_num_slots(left_sib_data, 0); srl.set_free_space_pointer(left_sib_data, PAGE_SIZE)
        
        srl.set_left_most_child_id(page_data, my_pointers.pop(0)[1])
        for k, child_id in my_pointers: self._insert_into_internal_node(page_id, page_data, k, child_id)
        srl.set_left_most_child_id(left_sib_data, left_pointers.pop(0)[1])
        for k, child_id in left_pointers: self._insert_into_internal_node(left_sib_id, left_sib_data, k, child_id)

        self._delete_entry_from_internal_node(parent_page_id, parent_page_data, separator_key, skip_underflow_check=True)
        self._insert_into_internal_node(parent_page_id, parent_page_data, borrowed_key, separator_child_id)
        self.pager.mark_dirty(page_id); self.pager.mark_dirty(left_sib_id); self.pager.mark_dirty(parent_page_id)

    def _merge_internal_nodes(self, page_id, page_data, right_sib_id, right_sib_data, parent_page_id, parent_page_data, parent_key_index_RIGHT): 
        key_to_pull_down = srl.read_data_from_slot(parent_page_data, parent_key_index_RIGHT)[0]
        all_data = [(None, srl.get_left_most_child_id(page_data))]
        for i in range(srl.get_num_slots(page_data)): all_data.append((srl.read_data_from_slot(page_data, i)[0], int.from_bytes(srl.read_data_from_slot(page_data, i)[1], 'little')))
        all_data.append((key_to_pull_down, srl.get_left_most_child_id(right_sib_data)))
        for i in range(srl.get_num_slots(right_sib_data)): all_data.append((srl.read_data_from_slot(right_sib_data, i)[0], int.from_bytes(srl.read_data_from_slot(right_sib_data, i)[1], 'little')))

        srl.set_num_slots(page_data, 0); srl.set_free_space_pointer(page_data, PAGE_SIZE)
        srl.set_left_most_child_id(page_data, all_data.pop(0)[1])
        for k, child_id in all_data:
            self._insert_into_internal_node(page_id, page_data, k, child_id)
            srl.set_parent_page_id(self.pager.get_page(child_id), page_id)
            self.pager.mark_dirty(child_id)

        self._delete_entry_from_internal_node(parent_page_id, parent_page_data, key_to_pull_down)
        self.pager.mark_dirty(page_id)
        
    def _shrink_root(self, root_page_data):
        if srl.get_node_type(root_page_data) == NODE_TYPE_LEAF: return 
        if srl.get_num_slots(root_page_data) == 0:
            new_root_id = srl.get_left_most_child_id(root_page_data)
            meta_page = self.pager.get_page(0)
            meta_page[17:21] = new_root_id.to_bytes(4, 'little')
            self.pager.mark_dirty(0)
            srl.set_parent_page_id(self.pager.get_page(new_root_id), 0)
            self.pager.mark_dirty(new_root_id)
            self.root_page_id = new_root_id