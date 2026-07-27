import os
import sys
from pager import Pager
from btree import BPlusTree
from wal import WAL # <-- IMPORTANTE: Trazendo nosso sistema de segurança

DB_FILENAME = "MarcoDB.db"

def main():
    if not os.path.exists(DB_FILENAME):
        print(f"INFO: Criando novo banco de dados '{DB_FILENAME}'...")
    
    pager = Pager(DB_FILENAME)
    tree = BPlusTree(pager)
    
    # --- INTEGRAÇÃO DO WAL (Recuperação de Desastres Local) ---
    wal = WAL()
    print("Verificando integridade dos dados...")
    wal.recover(tree)
    
    print(f"\n✅ Bem-vindo ao MarcoDB Admin Shell. Banco '{DB_FILENAME}' aberto.")
    print("Comandos MQL suportados: set, get, update, del, clear, exit")
    print("-" * 60)

    while True:
        try:
            full_command = input("MarcoDB> ") 
            if not full_command.strip():
                continue

            parts = full_command.split()
            command = parts[0].lower()

            if command == "exit":
                break
                
            elif command == "clear":
                # Limpa a tela do terminal (Windows ou Linux/Mac)
                os.system('cls' if os.name == 'nt' else 'clear')
            
            elif command == "set":
                if len(parts) < 3:
                    print("Erro MQL: 'set' requer uma chave e um valor.")
                    continue
                
                key = parts[1]
                value = " ".join(parts[2:]) 
                
                try:
                    wal.log_set(key, value, force_sync=True) # Força o sync no shell local
                    tree.insert(key, value)
                    print("OK.")
                except Exception as e:
                    print(f"Erro de Inserção: {e}")

            elif command == "update":
                if len(parts) < 3:
                    print("Erro MQL: 'update' requer uma chave e o novo valor.")
                    continue
                
                key = parts[1]
                value = " ".join(parts[2:]) 
                
                try:
                    # Verifica se a chave existe antes de atualizar
                    if tree.search(key) is None:
                        print(f"Erro MQL: Chave '{key}' não existe. Use 'set' para criar.")
                    else:
                        wal.log_update(key, value, force_sync=True)
                        tree.update(key, value)
                        print("OK Atualizado.")
                except Exception as e:
                    print(f"Erro de Atualização: {e}")

            elif command == "get":
                if len(parts) != 2:
                    print("Erro MQL: 'get' requer exatamente uma chave.")
                    continue
                
                key = parts[1]
                try:
                    value = tree.search(key)
                    if value is not None:
                        print(f"-> {value}")
                    else:
                        print("(Nulo)")
                except Exception as e:
                    print(f"Erro de Busca: {e}")

            elif command == "del":
                if len(parts) != 2:
                    print("Erro MQL: 'del' requer exatamente uma chave.")
                    continue
                
                key = parts[1]
                try:
                    if tree.search(key) is None:
                        print(f"Erro MQL: Chave '{key}' não encontrada.")
                    else:
                        wal.log_del(key, force_sync=True)
                        tree.delete(key)
                        print("OK.")
                except Exception as e:
                    print(f"Erro de Deleção: {e}")

            else:
                print(f"Erro MQL: Comando desconhecido '{command}'")

        except KeyboardInterrupt: 
            break
        except EOFError: 
            break

    # --- Desligamento Seguro ---
    print("\nSalvando MarcoDB e sincronizando disco...")
    pager.close()
    
    # Como o pager.close() salvou tudo fisicamente na B-Tree, podemos limpar o WAL!
    wal.clear() 
    print("Feito. Até logo!")

if __name__ == "__main__":
    main()