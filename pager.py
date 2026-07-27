import os
import threading
from collections import OrderedDict
# Trazendo o seu sistema de segurança anti-corrupção!
from serialization import update_page_checksum, verify_page_integrity 

PAGE_SIZE = 4096 # 4KB
# Aumentado para ~200MB de RAM. 
# Garante cache massivo para gerenciar perfeitamente os nós do Lucida Flow 
# e descritores estruturais de textura do Paint Gen sem travar a Prism Engine no disco.
MAX_CACHE_PAGES = 50000 

class Pager:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        
        file_exists = os.path.exists(db_filename)
        if not file_exists:
            with open(db_filename, 'w+b') as f:
                f.write(b'\x00' * PAGE_SIZE)
        
        self.db_file = open(db_filename, 'r+b')
        
        self.cache = OrderedDict() 
        self.dirty_pages = set()
        
        self.lock = threading.RLock()

    def get_page(self, page_id):
        with self.lock:
            if page_id in self.cache:
                self.cache.move_to_end(page_id)
                return self.cache[page_id]

            if len(self.cache) >= MAX_CACHE_PAGES:
                self._evict_page()

            offset = page_id * PAGE_SIZE
            self.db_file.seek(offset)
            page_data = self.db_file.read(PAGE_SIZE)

            if not page_data:
                # Página nova (final do arquivo)
                page_data = bytearray(b'\x00' * PAGE_SIZE)
            else:
                page_data = bytearray(page_data)
                # --- A BARREIRA DE INTEGRIDADE (Zero Trust) ---
                if not verify_page_integrity(page_data):
                    print(f"CRÍTICO: Corrupção detectada na página {page_id}!")
                    # Interrompe imediatamente para a corrupção do HD não infectar a árvore na RAM
                    raise Exception(f"Erro Fatal de Disco: Assinatura CRC32 inválida na Página {page_id}.")

            self.cache[page_id] = page_data
            return self.cache[page_id]

    def _evict_page(self):
        """Remove a página menos usada recentemente do cache para liberar memória."""
        oldest_page_id, page_data = self.cache.popitem(last=False)
        
        if oldest_page_id in self.dirty_pages:
            # --- ASSINATURA ANTES DO DISCO ---
            update_page_checksum(page_data)
            
            offset = oldest_page_id * PAGE_SIZE
            self.db_file.seek(offset)
            self.db_file.write(page_data)
            self.dirty_pages.remove(oldest_page_id)

    def new_page(self):
        with self.lock:
            self.db_file.seek(0, 2)
            file_size = self.db_file.tell()
            new_page_id = file_size // PAGE_SIZE
            
            # Aloca fisicamente o espaço
            self.db_file.write(b'\x00' * PAGE_SIZE)
            
            page_data = self.get_page(new_page_id)
            return new_page_id, page_data

    def mark_dirty(self, page_id):
        with self.lock:
            self.dirty_pages.add(page_id)

    def flush_all(self):
        with self.lock:
            if not self.dirty_pages:
                return 

            for page_id in list(self.dirty_pages): 
                if page_id in self.cache:
                    page_data = self.cache[page_id]
                    
                    # --- GARANTINDO QUE TUDO TENHA CHECKSUM AO FECHAR O SERVIDOR ---
                    update_page_checksum(page_data)
                    
                    offset = page_id * PAGE_SIZE
                    self.db_file.seek(offset)
                    self.db_file.write(page_data)
            
            self.db_file.flush()
            os.fsync(self.db_file.fileno()) 
            self.dirty_pages.clear()

    def close(self):
        with self.lock:
            self.flush_all()
            self.db_file.close()