package marcodb

import (
	"errors"
	"fmt"
	"net"
	"strings"
	"sync"
	"time"
)

type Client struct {
	host     string
	port     int
	user     string
	password string
	conn     net.Conn
	buffer   string
	mu       sync.Mutex // O Semáforo do Go para goroutines seguras!
}

// Inicializador padrão
func NewClient(host string, port int, user, password string) *Client {
	return &Client{
		host:     host,
		port:     port,
		user:     user,
		password: password,
	}
}

func (c *Client) Connect() error {
	address := fmt.Sprintf("%s:%d", c.host, c.port)
	// Timeout rigoroso para não travar a aplicação web
	conn, err := net.DialTimeout("tcp", address, 5*time.Second)
	if err != nil {
		return fmt.Errorf("MarcoDB Falha de Conexão: %v", err)
	}
	c.conn = conn

	// 1. Lê a mensagem de boas-vindas
	_, err = c.readUntilEOM()
	if err != nil {
		return err
	}

	// 2. Envia credencial de segurança
	authCmd := fmt.Sprintf("auth %s %s", c.user, c.password)
	c.sendCmd(authCmd)

	// 3. Analisa a resposta do servidor
	resposta, err := c.readUntilEOM()
	if err != nil {
		return err
	}

	if !strings.Contains(resposta, "OK. Acesso Permitido") {
		c.Close()
		return fmt.Errorf("MarcoDB Erro de Autenticação: %s", resposta)
	}

	return nil
}

// Executa comandos MQL (Thread-Safe para milhares de goroutines simultâneas)
func (c *Client) Query(command string) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn == nil {
		return "", errors.New("Erro: Cliente não está conectado ao MarcoDB")
	}

	c.sendCmd(command)
	return c.readUntilEOM()
}

func (c *Client) sendCmd(cmd string) {
	msg := fmt.Sprintf("%s<|EOM|>", cmd)
	c.conn.Write([]byte(msg))
}

func (c *Client) readUntilEOM() (string, error) {
	readBuffer := make([]byte, 4096)

	// Continua buscando na rede até o EOM estar montado no buffer
	for !strings.Contains(c.buffer, "<|EOM|>") {
		n, err := c.conn.Read(readBuffer)
		if err != nil {
			return "", fmt.Errorf("Erro: Conexão perdida com o servidor (%v)", err)
		}
		c.buffer += string(readBuffer[:n])
	}

	parts := strings.SplitN(c.buffer, "<|EOM|>", 2)
	msg := parts[0]
	
	// Preserva o que sobrou do pacote TCP
	if len(parts) > 1 {
		c.buffer = parts[1]
	} else {
		c.buffer = ""
	}

	return strings.TrimSpace(msg), nil
}

func (c *Client) Close() {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.conn != nil {
		c.sendCmd("exit")
		c.conn.Close()
		c.conn = nil
		c.buffer = ""
	}
}