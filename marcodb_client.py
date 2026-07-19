import socket

class MarcoDBClient:
    def __init__(self, host='127.0.0.1', port=7300, user='root', password='qorigin123'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.conn = None
        # CORREÇÃO 1: Buffer persistente para a classe inteira não perder pacotes
        self._buffer = bytearray()

    def connect(self):
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.settimeout(5.0) # Espera no máximo 5 segundos para conectar
            self.conn.connect((self.host, self.port))
            
            # 1. Lê a mensagem de boas-vindas do servidor
            self._recv_until_eom()
            
            # 2. Envia a credencial de segurança (Handshake)
            auth_cmd = f"auth {self.user} {self.password}"
            self._send_cmd(auth_cmd)
            
            # 3. Analisa a resposta do servidor
            resposta = self._recv_until_eom()
            if "OK. Acesso Permitido" in resposta:
                self.conn.settimeout(None) # Libera o timeout para queries longas
                return True
            else:
                print(f"MarcoDB Erro de Autenticação: {resposta}")
                self.close()
                return False
                
        except Exception as e:
            print(f"MarcoDB Falha de Conexão: {e}")
            return False

    def execute(self, command):
        """Envia um comando MQL para o servidor e retorna a resposta."""
        if not self.conn:
            return "Erro: Cliente não está conectado ao servidor."
        
        self._send_cmd(command)
        return self._recv_until_eom()

    def _send_cmd(self, cmd):
        """Empacota a string com a tag de fim de mensagem <|EOM|>"""
        msg = f"{cmd}<|EOM|>"
        self.conn.sendall(msg.encode('utf-8'))

    def _recv_until_eom(self):
        """Lê os pacotes da rede até encontrar a tag <|EOM|> sem perder sobras"""
        # CORREÇÃO 2: Usa o buffer persistente, não zera a cada chamada
        while b"<|EOM|>" not in self._buffer:
            chunk = self.conn.recv(4096)
            if not chunk:
                return "Erro: Conexão perdida com o servidor."
            self._buffer.extend(chunk)
        
        # Separa a primeira mensagem completa e GUARDA o resto para a próxima chamada!
        msg_bytes, remainder = self._buffer.split(b"<|EOM|>", 1)
        self._buffer = remainder 
        
        return msg_bytes.decode('utf-8').strip()

    def close(self):
        if self.conn:
            try:
                self._send_cmd("exit")
            except:
                pass
            self.conn.close()
            self.conn = None
            self._buffer.clear()

# ==========================================
# CORREÇÃO 3: TERMINAL INTERATIVO NATIVO
# ==========================================
if __name__ == "__main__":
    print("Iniciando MarcoDB Terminal Client...")
    
    # Você pode passar os parâmetros aqui se estiver testando remoto
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