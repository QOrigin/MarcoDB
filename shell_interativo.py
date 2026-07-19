# shell_interativo.py (Atualizado com MarcoDB)

import os
from pager import Pager
from btree import BPlusTree
import sys

# --- MUDANÇA 1 ---
DB_FILENAME = "MarcoDB.db" # Novo nome do arquivo do banco

def main():
    # --- Inicialização ---
    if not os.path.exists(DB_FILENAME):
        print(f"INFO: Criando novo banco de dados '{DB_FILENAME}'...")
    
    pager = Pager(DB_FILENAME)
    tree = BPlusTree(pager)
    
    # --- MUDANÇA 2 ---
    print(f"Bem-vindo ao MarcoDB. Banco '{DB_FILENAME}' aberto.")
    print("Use a linguagem MQL (set, get, del) ou 'exit' para sair.")

    # --- O Loop REPL ---
    while True:
        try:
            # 1. READ (Ler)
            # --- MUDANÇA 3 ---
            full_command = input("MarcoDB> ") 
            if not full_command:
                continue

            # 2. EVAL (Avaliar/Parsear)
            parts = full_command.split()
            command = parts[0].lower()

            if command == "exit":
                break
            
            elif command == "set":
                if len(parts) < 3:
                    print("Erro MQL: 'set' requer uma chave e um valor.")
                    continue
                
                key = parts[1]
                value = " ".join(parts[2:]) 
                
                try:
                    tree.insert(key, value)
                    print("OK.")
                except Exception as e:
                    print(f"Erro de Inserção: {e}")

            elif command == "get":
                if len(parts) != 2:
                    print("Erro MQL: 'get' requer exatamente uma chave.")
                    continue
                
                key = parts[1]
                try:
                    value = tree.search(key)
                    # 3. PRINT (Imprimir)
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

    # --- Desligamento ---
    print("\nSalvando MarcoDB e saindo...")
    pager.close()
    print("Feito.")

if __name__ == "__main__":
    main()