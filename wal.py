import os
import struct

OP_SET = 1
OP_DEL = 2
OP_UPDATE = 3

class WAL:
    def __init__(self, filename="marcodb.log"):
        self.filename = filename
        self.file = open(self.filename, 'a+b')

    def log_set(self, key, value):
        # AVISO VISUAL: Prova de que o WAL está agindo ANTES da B-Tree
        print(f"INFO (WAL): Salvando intenção de 'set {key}' fisicamente no log...")
        key_bytes = key.encode('utf-8')
        val_bytes = value.encode('utf-8')
        
        header = struct.pack('<B H', OP_SET, len(key_bytes))
        self.file.write(header + key_bytes)
        
        val_header = struct.pack('<H', len(val_bytes))
        self.file.write(val_header + val_bytes)
        
        self.file.flush()
        os.fsync(self.file.fileno()) 

    def log_del(self, key):
        print(f"INFO (WAL): Salvando intenção de 'del {key}' fisicamente no log...")
        key_bytes = key.encode('utf-8')
        
        header = struct.pack('<B H', OP_DEL, len(key_bytes))
        self.file.write(header + key_bytes)
        
        self.file.flush()
        os.fsync(self.file.fileno())

    def log_update(self, key, value):
        print(f"INFO (WAL): Salvando intenção de 'update {key}' fisicamente no log...")
        key_bytes = key.encode('utf-8')
        val_bytes = value.encode('utf-8')
        
        header = struct.pack('<B H', OP_UPDATE, len(key_bytes))
        self.file.write(header + key_bytes)
        
        val_header = struct.pack('<H', len(val_bytes))
        self.file.write(val_header + val_bytes)
        
        self.file.flush()
        os.fsync(self.file.fileno())

    def recover(self, tree):
        if os.path.getsize(self.filename) == 0:
            return 

        print("INFO (WAL): *** QUEDA DE ENERGIA DETECTADA! Iniciando recuperação pelo log... ***")
        self.file.seek(0) 
        
        operacoes_recuperadas = 0
        
        while True:
            op_byte = self.file.read(1)
            if not op_byte:
                break 
            
            op = op_byte[0]
            key_len_bytes = self.file.read(2)
            if not key_len_bytes: break
            key_len = struct.unpack('<H', key_len_bytes)[0]
            
            key = self.file.read(key_len).decode('utf-8')
            
            if op == OP_SET:
                val_len_bytes = self.file.read(2)
                if not val_len_bytes: break
                val_len = struct.unpack('<H', val_len_bytes)[0]
                value = self.file.read(val_len).decode('utf-8')
                
                try:
                    tree.insert(key, value)
                    operacoes_recuperadas += 1
                except Exception:
                    pass 
                    
            elif op == OP_DEL:
                try:
                    tree.delete(key)
                    operacoes_recuperadas += 1
                except Exception:
                    pass

            elif op == OP_UPDATE: # <-- ADICIONE ESTE BLOCO
                val_len_bytes = self.file.read(2)
                if not val_len_bytes: break
                val_len = struct.unpack('<H', val_len_bytes)[0]
                value = self.file.read(val_len).decode('utf-8')
                try:
                    tree.update(key, value) # Vamos criar essa função na BTree!
                    operacoes_recuperadas += 1
                except Exception:
                    pass
        
        print(f"INFO (WAL): Recuperação concluída. {operacoes_recuperadas} operações restauradas com sucesso.")

    def clear(self):
        self.file.close()
        self.file = open(self.filename, 'w+b')
        self.file.flush()
        os.fsync(self.file.fileno())