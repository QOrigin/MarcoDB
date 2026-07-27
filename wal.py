import os
import struct

OP_SET = 1
OP_DEL = 2
OP_UPDATE = 3

class WAL:
    def __init__(self, filename="marcodb.log"):
        self.filename = filename
        self.file = open(self.filename, 'a+b')
        self.unflushed_ops = 0
        self.flush_threshold = 100 # Faz o fsync a cada 100 operações para voar na performance!

    def _escrever_e_sincronizar(self, dados, force_sync=False):
        """Função interna para unificar a lógica de gravação e buffer"""
        self.file.write(dados)
        self.unflushed_ops += 1
        
        # Só força a gravação física no disco se atingir o limite ou se forçado
        if force_sync or self.unflushed_ops >= self.flush_threshold:
            self.file.flush()
            os.fsync(self.file.fileno()) 
            self.unflushed_ops = 0

    def log_set(self, key, value, force_sync=False):
        # print(f"INFO (WAL): Salvando intenção de 'set {key}' fisicamente no log...")
        key_bytes = key.encode('utf-8')
        val_bytes = value.encode('utf-8')
        
        header = struct.pack('<B H', OP_SET, len(key_bytes))
        val_header = struct.pack('<H', len(val_bytes))
        
        # Agrupa tudo em um único pacote binário antes de escrever
        pacote = header + key_bytes + val_header + val_bytes
        self._escrever_e_sincronizar(pacote, force_sync)

    def log_del(self, key, force_sync=False):
        # print(f"INFO (WAL): Salvando intenção de 'del {key}' fisicamente no log...")
        key_bytes = key.encode('utf-8')
        
        header = struct.pack('<B H', OP_DEL, len(key_bytes))
        pacote = header + key_bytes
        
        self._escrever_e_sincronizar(pacote, force_sync)

    def log_update(self, key, value, force_sync=False):
        # print(f"INFO (WAL): Salvando intenção de 'update {key}' fisicamente no log...")
        key_bytes = key.encode('utf-8')
        val_bytes = value.encode('utf-8')
        
        header = struct.pack('<B H', OP_UPDATE, len(key_bytes))
        val_header = struct.pack('<H', len(val_bytes))
        
        pacote = header + key_bytes + val_header + val_bytes
        self._escrever_e_sincronizar(pacote, force_sync)

    def recover(self, tree):
        if not os.path.exists(self.filename) or os.path.getsize(self.filename) == 0:
            return 

        print("INFO (WAL): *** Iniciando verificação de recuperação pelo log... ***")
        self.file.seek(0) 
        
        operacoes_recuperadas = 0
        
        while True:
            op_byte = self.file.read(1)
            if not op_byte:
                break 
            
            op = op_byte[0]
            
            key_len_bytes = self.file.read(2)
            if len(key_len_bytes) < 2: break # Previne corrupção parcial
            key_len = struct.unpack('<H', key_len_bytes)[0]
            
            key_bytes = self.file.read(key_len)
            if len(key_bytes) < key_len: break
            key = key_bytes.decode('utf-8')
            
            if op == OP_SET or op == OP_UPDATE:
                val_len_bytes = self.file.read(2)
                if len(val_len_bytes) < 2: break
                val_len = struct.unpack('<H', val_len_bytes)[0]
                
                val_bytes = self.file.read(val_len)
                if len(val_bytes) < val_len: break
                value = val_bytes.decode('utf-8')
                
                try:
                    if op == OP_SET:
                        tree.insert(key, value)
                    else:
                        tree.update(key, value)
                    operacoes_recuperadas += 1
                except Exception:
                    pass 
                    
            elif op == OP_DEL:
                try:
                    tree.delete(key)
                    operacoes_recuperadas += 1
                except Exception:
                    pass
        
        if operacoes_recuperadas > 0:
            print(f"INFO (WAL): Recuperação concluída. {operacoes_recuperadas} operações restauradas com sucesso.")

    def clear(self):
        self.file.close()
        self.file = open(self.filename, 'w+b')
        self.unflushed_ops = 0
        self.file.flush()
        os.fsync(self.file.fileno())