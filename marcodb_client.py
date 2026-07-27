import socket
import threading

class MarcoDBClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 7300, user: str = 'root', password: str = 'qorigin123'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.conn = None
        self._buffer = bytearray()
        
        # O "Semáforo" do Cliente. Fundamental para a Prism Engine!
        self._lock = threading.Lock()

    def connect(self) -> bool:
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.settimeout(5.0) 
            self.conn.connect((self.host, self.port))
            
            self._recv_until_eom()
            
            auth_cmd = f"auth {self.user} {self.password}"
            self._send_cmd(auth_cmd)
            
            resposta = self._recv_until_eom()
            if "OK. Acesso Permitido" in resposta:
                self.conn.settimeout(None) 
                return True
            else:
                print(f"MarcoDB Erro de Autenticação: {resposta}")
                self.close()
                return False
                
        except Exception as e:
            print(f"MarcoDB Falha de Conexão: {e}")
            return False

    def execute(self, command: str) -> str:
        """Envia um comando MQL de forma Thread-Safe."""
        # A Trava: Garante que o envio e o recebimento sejam atômicos (indivisíveis)
        with self._lock:
            if not self.conn:
                return "Erro: Cliente não está conectado ao servidor."
            
            self._send_cmd(command)
            return self._recv_until_eom()

    def _send_cmd(self, cmd: str):
        msg = f"{cmd}<|EOM|>"
        self.conn.sendall(msg.encode('utf-8'))

    def _recv_until_eom(self) -> str:
        while b"<|EOM|>" not in self._buffer:
            chunk = self.conn.recv(4096)
            if not chunk:
                return "Erro: Conexão perdida com o servidor."
            self._buffer.extend(chunk)
        
        msg_bytes, remainder = self._buffer.split(b"<|EOM|>", 1)
        self._buffer = remainder 
        
        return msg_bytes.decode('utf-8').strip()

    def close(self):
        with self._lock:
            if self.conn:
                try:
                    self._send_cmd("exit")
                except:
                    pass
                self.conn.close()
                self.conn = None
                self._buffer.clear()

# ==========================================
# TERMINAL INTERATIVO NATIVO
# ==========================================
if __name__ == "__main__":
    print("Iniciando MarcoDB Terminal Client...")
    
    # Inicia o cliente com as configurações padrão
    client = MarcoDBClient() 
    
    if client.connect():
        print(f"✅ Conectado ao MarcoDB em {client.host}:{client.port}!")
        print("Digite seus comandos MQL (ou 'exit' para sair):")
        print("-" * 50)
        
        while True:
            try:
                cmd = input("MarcoDB> ")
                if not cmd.strip():
                    continue
                
                if cmd.strip().lower() == 'exit':
                    print("Encerrando conexão...")
                    client.close()
                    break
                    
                resposta = client.execute(cmd)
                print(resposta)
                
            except KeyboardInterrupt:
                print("\nEncerrando conexão...")
                client.close()
                break
    else:
        print("❌ Falha ao iniciar o cliente via terminal.")