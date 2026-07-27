import os
import socket
import threading
import hashlib
from pager import Pager
from btree import BPlusTree
from wal import WAL

DB_FILENAME = "MarcoDB.db"
HOST = '0.0.0.0'
PORT = 7300

ADMIN_USER = "root"
ADMIN_PASS_HASH = hashlib.sha256(b"qorigin123").hexdigest() 

def handle_client(conn, addr, tree, wal, db_lock):
    print(f"INFO: Nova conexão detectada de {addr}. Aguardando autenticação...")
    
    # TIMEOUT DE SEGURANÇA: Desconecta clientes ociosos após 5 minutos para liberar RAM
    conn.settimeout(300.0) 
    
    try:
        conn.sendall(b"MarcoDB Server conectado. Requer autenticacao (auth <usuario> <senha>).<|EOM|>")
    except Exception as e:
        print(f"Erro ao enviar boas-vindas para {addr}: {e}")
        conn.close()
        return

    buffer = bytearray()
    is_authenticated = False 
    
    while True:
        try:
            chunk = conn.recv(4096)
            if not chunk: break 
            buffer.extend(chunk)
            
            while b"<|EOM|>" in buffer:
                msg_bytes, buffer = buffer.split(b"<|EOM|>", 1)
                
                try:
                    full_command = msg_bytes.decode('utf-8').strip()
                except UnicodeDecodeError:
                    conn.sendall(b"Erro: Payload invalido. Use UTF-8.<|EOM|>")
                    continue
                    
                if not full_command: continue

                parts = full_command.split(maxsplit=2)
                command = parts[0].lower()

                if command == "exit":
                    conn.sendall(b"Tchau.<|EOM|>")
                    return 
                
                # --- SISTEMA DE LOGIN ---
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
                    continue 

                # --- COMANDOS MQL (Somente Autenticados) ---
                if command == "crash":
                    print(f"CRÍTICO: Recebido comando de CRASH de {addr}!")
                    os._exit(1)

                elif command == "set":
                    if len(parts) < 3:
                        conn.sendall(b"Erro: 'set' requer chave e valor.<|EOM|>")
                        continue
                    
                    # O SEMÁFORO: Só uma thread escreve por vez
                    with db_lock:
                        try:
                            # Agora as operações WAL e Tree são Atômicas (indivisíveis)
                            wal.log_set(parts[1], parts[2]) 
                            tree.insert(parts[1], parts[2]) 
                            conn.sendall(b"OK.<|EOM|>")
                        except Exception as e:
                            conn.sendall(f"Erro Insercao: {e}<|EOM|>".encode('utf-8'))

                elif command == "update":
                    if len(parts) < 3:
                        conn.sendall(b"Erro: 'update' requer chave e novo valor.<|EOM|>")
                        continue
                    
                    with db_lock:
                        try:
                            wal.log_update(parts[1], parts[2]) 
                            tree.update(parts[1], parts[2])    
                            conn.sendall(b"OK Atualizado.<|EOM|>")
                        except Exception as e:
                            conn.sendall(f"Erro Atualizacao: {e}<|EOM|>".encode('utf-8'))

                elif command == "get":
                    if len(parts) != 2:
                        conn.sendall(b"Erro: 'get' requer uma chave.<|EOM|>")
                        continue
                    
                    # Leitura também leva trava para evitar "leitura suja" se a B-Tree estiver se dividindo
                    with db_lock:
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
                    
                    with db_lock:
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

        except socket.timeout:
            print(f"AVISO: Conexao com {addr} encerrada por inatividade (timeout).")
            break
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
    
    # --- O CORAÇÃO DA CONCORRÊNCIA SEGURA ---
    db_lock = threading.Lock()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    server_socket.bind((HOST, PORT))
    server_socket.listen(50) # Aumentei a fila de espera (backlog) de 5 para 50 para suportar picos de tráfego web
    
    print(f"MarcoDB Server rodando na porta {PORT}...")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            # Passamos o db_lock para que todos os clientes compartilhem o mesmo semáforo
            client_thread = threading.Thread(target=handle_client, args=(conn, addr, tree, wal, db_lock))
            # Torna as threads em Daemon. Se o servidor principal desligar, elas param imediatamente
            client_thread.daemon = True 
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\nDesligando servidor MarcoDB...")
    finally:
        server_socket.close()
        # O lock final garante que nenhuma thread está no meio de uma gravação quando desligamos
        with db_lock:
            pager.close() 
            wal.clear()   
        print("Banco de dados salvo com segurança.")

if __name__ == "__main__":
    main()