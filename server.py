import os
import socket
import threading
import hashlib # <-- NOVO IMPORT DE SEGURANÇA
from pager import Pager
from btree import BPlusTree
from wal import WAL

DB_FILENAME = "MarcoDB.db"
HOST = '0.0.0.0'
PORT = 7300

# CREDENCIAIS DO SISTEMA (Em um banco real, isso ficaria em um arquivo config.json ou em uma tabela de sistema)
ADMIN_USER = "root"
# O Hash SHA-256 da senha 'qorigin123'
ADMIN_PASS_HASH = hashlib.sha256(b"qorigin123").hexdigest() 

def handle_client(conn, addr, tree, wal):
    print(f"INFO: Nova conexão detectada de {addr}. Aguardando autenticação...")
    conn.sendall(b"MarcoDB Server conectado. Requer autenticacao (auth <usuario> <senha>).<|EOM|>")
    
    buffer = bytearray()
    is_authenticated = False # <-- A BARREIRA DE SEGURANÇA
    
    while True:
        try:
            chunk = conn.recv(4096)
            if not chunk: break 
            buffer.extend(chunk)
            
            while b"<|EOM|>" in buffer:
                msg_bytes, buffer = buffer.split(b"<|EOM|>", 1)
                full_command = msg_bytes.decode('utf-8').strip()
                if not full_command: continue

                parts = full_command.split(maxsplit=2)
                command = parts[0].lower()

                if command == "exit":
                    conn.sendall(b"Tchau.<|EOM|>")
                    return 
                
                # --- SISTEMA DE LOGIN (HANDSHAKE) ---
                if not is_authenticated:
                    if command == "auth":
                        if len(parts) < 3:
                            conn.sendall(b"Erro: Formato invalido. Use 'auth <usuario> <senha>'.<|EOM|>")
                            continue
                        
                        user = parts[1]
                        password = parts[2]
                        pass_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                        
                        if user == ADMIN_USER and pass_hash == ADMIN_PASS_HASH:
                            is_authenticated = True
                            conn.sendall(b"OK. Acesso Permitido. Bem-vindo ao MarcoDB!<|EOM|>")
                            print(f"INFO: {addr} autenticado como '{user}'.")
                        else:
                            conn.sendall(b"Erro: Credenciais invalidas. Acesso Negado.<|EOM|>")
                            print(f"AVISO: Tentativa de invasao falha de {addr}.")
                    else:
                        conn.sendall(b"Erro: Acesso Negado. Facilite o login com 'auth'.<|EOM|>")
                    continue # Impede que o código desça para o set/get

                # --- COMANDOS MQL (Só chega aqui se is_authenticated for True) ---
                elif command == "crash":
                    print(f"INFO: Recebido comando de CRASH!")
                    os._exit(1)

                elif command == "set":
                    if len(parts) < 3:
                        conn.sendall(b"Erro: 'set' requer chave e valor.<|EOM|>")
                        continue
                    key = parts[1]
                    value = parts[2] 
                    try:
                        wal.log_set(key, value) 
                        tree.insert(key, value) 
                        conn.sendall(b"OK.<|EOM|>")
                    except Exception as e:
                        conn.sendall(f"Erro Insercao: {e}<|EOM|>".encode('utf-8'))

                elif command == "update":
                    if len(parts) < 3:
                        conn.sendall(b"Erro: 'update' requer chave e novo valor.<|EOM|>")
                        continue
                    key = parts[1]
                    value = parts[2] 
                    try:
                        wal.log_update(key, value) 
                        tree.update(key, value)    
                        conn.sendall(b"OK Atualizado.<|EOM|>")
                    except Exception as e:
                        conn.sendall(f"Erro Atualizacao: {e}<|EOM|>".encode('utf-8'))

                elif command == "get":
                    if len(parts) != 2:
                        conn.sendall(b"Erro: 'get' requer uma chave.<|EOM|>")
                        continue
                    try:
                        value = tree.search(parts[1])
                        if value is not None:
                            conn.sendall(f"->\n{value}<|EOM|>".encode('utf-8'))
                        else:
                            conn.sendall(b"(Nulo)<|EOM|>")
                    except Exception as e:
                        conn.sendall(f"Erro Busca: {e}<|EOM|>".encode('utf-8'))

                elif command == "del":
                    if len(parts) != 2:
                        conn.sendall(b"Erro: 'del' requer uma chave.<|EOM|>")
                        continue
                    try:
                        if tree.search(parts[1]) is None:
                            conn.sendall(b"Erro: Chave nao encontrada.<|EOM|>")
                        else:
                            wal.log_del(parts[1])
                            tree.delete(parts[1])
                            conn.sendall(b"OK.<|EOM|>")
                    except Exception as e:
                        conn.sendall(f"Erro Delecao: {e}<|EOM|>".encode('utf-8'))
                else:
                    conn.sendall(f"Erro: Comando '{command}' desconhecido<|EOM|>".encode('utf-8'))

        except Exception as e:
            print(f"Erro na conexao com {addr}: {e}")
            break
            
    conn.close()
    print(f"INFO: Conexão encerrada com {addr}")

def main():
    if not os.path.exists(DB_FILENAME):
        print(f"INFO: Criando novo banco '{DB_FILENAME}'...")
        
    pager = Pager(DB_FILENAME)
    tree = BPlusTree(pager)
    
    wal = WAL()
    wal.recover(tree)
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    
    print(f"MarcoDB Server rodando na porta {PORT}...")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr, tree, wal))
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nDesligando servidor MarcoDB...")
    finally:
        server_socket.close()
        pager.close() 
        wal.clear()   
        print("Banco de dados salvo com segurança.")

if __name__ == "__main__":
    main()