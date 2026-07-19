import os
import threading
from collections import OrderedDict

PAGE_SIZE = 4096 # 4KB
MAX_CACHE_PAGES = 10000 # ~40MB de RAM máxima para o Buffer Pool

class Pager:
    def __init__(self, db_filename):
        self.db_filename = db_filename
        
        file_exists = os.path.exists(db_filename)
        if not file_exists:
            with open(db_filename, 'w+b') as f:
                f.write(b'\x00' * PAGE_SIZE)
        
        self.db_file = open(db_filename, 'r+b')
        
        # OrderedDict funciona perfeitamente como um cache LRU em Python
        self.cache = OrderedDict() 
        self.dirty_pages = set()
        
        # Trava (Lock) para garantir segurança com múltiplas conexões de rede
        self.lock = threading.RLock()

    def get_page(self, page_id):
        with self.lock:
            if page_id in self.cache:
                # Move a página para o final (marca como a mais recentemente usada)
                self.cache.move_to_end(page_id)
                return self.cache[page_id]

            # Se o cache estiver cheio, expulsa a página mais antiga
            if len(self.cache) >= MAX_CACHE_PAGES:
                self._evict_page()

            offset = page_id * PAGE_SIZE
            self.db_file.seek(offset)
            page_data = self.db_file.read(PAGE_SIZE)

            if not page_data:
                page_data = b'\x00' * PAGE_SIZE

            self.cache[page_id] = bytearray(page_data)
            return self.cache[page_id]

    def _evict_page(self):
        """Remove a página menos usada recentemente do cache para liberar memória."""
        # popitem(last=False) remove o primeiro item inserido (o mais antigo)
        oldest_page_id, page_data = self.cache.popitem(last=False)
        
        if oldest_page_id in self.dirty_pages:
            # Se a página estava modificada, salva no disco antes de expulsar da RAM
            offset = oldest_page_id * PAGE_SIZE
            self.db_file.seek(offset)
            self.db_file.write(page_data)
            self.dirty_pages.remove(oldest_page_id)

    def new_page(self):
        with self.lock:
            self.db_file.seek(0, 2)
            file_size = self.db_file.tell()
            new_page_id = file_size // PAGE_SIZE
            
            self.db_file.write(b'\x00' * PAGE_SIZE)
            
            # Chama o get_page, que agora gerencia o limite de memória automaticamente
            page_data = self.get_page(new_page_id)
            return new_page_id, page_data

    def mark_dirty(self, page_id):
        with self.lock:
            self.dirty_pages.add(page_id)

    def flush_all(self):
        with self.lock:
            if not self.dirty_pages:
                return 

            for page_id in list(self.dirty_pages): # Usa list() para evitar erro ao modificar o set durante a iteração
                if page_id in self.cache:
                    offset = page_id * PAGE_SIZE
                    self.db_file.seek(offset)
                    self.db_file.write(self.cache[page_id])
            
            self.db_file.flush()
            os.fsync(self.db_file.fileno()) 
            self.dirty_pages.clear()

    def close(self):
        with self.lock:
            self.flush_all()
            self.db_file.close()