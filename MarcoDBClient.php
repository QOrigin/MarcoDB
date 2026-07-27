<?php

class MarcoDB {
    private $host;
    private $port;
    private $user;
    private $password;
    private $socket;
    // CORREÇÃO: O buffer agora é persistente e sobrevive entre as chamadas!
    private $buffer = ""; 

    public function __construct($host = '127.0.0.1', $port = 7300, $user = 'root', $password = 'qorigin123') {
        $this->host = $host;
        $this->port = $port;
        $this->user = $user;
        $this->password = $password;
    }

    public function connect() {
        $this->socket = @fsockopen($this->host, $this->port, $errno, $errstr, 5);
        
        if (!$this->socket) {
            throw new Exception("Falha na conexão MarcoDB: $errstr ($errno)");
        }

        // 1. Ignora a mensagem inicial do servidor
        $this->read_until_eom();

        // 2. Envia credenciais de acesso
        $this->send_cmd("auth " . $this->user . " " . $this->password);

        // 3. Verifica se a senha foi aceita
        $resposta = $this->read_until_eom();
        if (strpos($resposta, "OK. Acesso Permitido") === false) {
            $this->close();
            throw new Exception("Falha de Autenticação MarcoDB: " . $resposta);
        }
        
        return true;
    }

    public function query($command) {
        if (!$this->socket) {
            return "Erro: Cliente não está conectado.";
        }
        $this->send_cmd($command);
        return $this->read_until_eom();
    }

    private function send_cmd($cmd) {
        fwrite($this->socket, $cmd . "<|EOM|>");
    }

    private function read_until_eom() {
        // CORREÇÃO: Continua lendo a rede apenas se a tag não estiver no buffer guardado
        while (strpos($this->buffer, "<|EOM|>") === false) {
            $chunk = fread($this->socket, 4096);
            if ($chunk === false || feof($this->socket)) {
                return "Erro: Conexão perdida com o servidor.";
            }
            $this->buffer .= $chunk;
        }
        
        // Separa a primeira mensagem e GUARDA o resto no buffer
        $parts = explode("<|EOM|>", $this->buffer, 2);
        $msg = $parts[0];
        $this->buffer = isset($parts[1]) ? $parts[1] : ""; 
        
        return trim($msg);
    }

    public function close() {
        if ($this->socket) {
            @$this->send_cmd("exit");
            fclose($this->socket);
            $this->socket = null;
            $this->buffer = ""; // Limpa a memória ao fechar
        }
    }
}
?>