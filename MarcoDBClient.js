const net = require('net');

class MarcoDBClient {
    constructor(host = '127.0.0.1', port = 7300, user = 'root', password = 'qorigin123') {
        this.host = host;
        this.port = port;
        this.user = user;
        this.password = password;
        this.client = null;
        this.buffer = "";
        
        // Fila de execução para lidar com o ambiente assíncrono do Node.js
        this.responseQueue = []; 
    }

    connect() {
        return new Promise((resolve, reject) => {
            this.client = new net.Socket();
            
            this.client.connect(this.port, this.host, () => {
                // Aguarda a mensagem de boas-vindas do servidor
                this._enqueueResponse().then(() => {
                    // Handshake de Autenticação
                    this.client.write(`auth ${this.user} ${this.password}<|EOM|>`);
                    return this._enqueueResponse();
                }).then((resposta) => {
                    if (resposta.includes("OK. Acesso Permitido")) {
                        resolve(true);
                    } else {
                        reject(new Error("MarcoDB: Acesso Negado -> " + resposta));
                    }
                }).catch(reject);
            });

            // Listener passivo: sempre que dados chegam pela rede, ele alimenta o buffer
            this.client.on('data', (data) => {
                this.buffer += data.toString('utf-8');
                this._processBuffer();
            });

            this.client.on('error', (err) => {
                reject(err);
            });
            
            this.client.on('close', () => {
                this.client = null;
            });
        });
    }

    async query(command) {
        if (!this.client) throw new Error("Erro: Cliente não está conectado ao MarcoDB.");
        
        this.client.write(`${command}<|EOM|>`);
        return this._enqueueResponse();
    }

    _enqueueResponse() {
        // Cria uma promessa que ficará aguardando o servidor responder
        return new Promise((resolve) => {
            this.responseQueue.push(resolve);
        });
    }

    _processBuffer() {
        // Verifica se há uma mensagem completa no buffer
        while (this.buffer.includes("<|EOM|>")) {
            let parts = this.buffer.split("<|EOM|>");
            let msg = parts.shift(); // Remove e captura a primeira mensagem completa
            
            this.buffer = parts.join("<|EOM|>"); // Guarda o resto no buffer

            // Se houver alguém esperando resposta na fila, entrega a mensagem
            if (this.responseQueue.length > 0) {
                let resolve = this.responseQueue.shift();
                resolve(msg.trim());
            }
        }
    }

    close() {
        if (this.client) {
            this.client.write("exit<|EOM|>");
            this.client.destroy();
            this.client = null;
        }
    }
}

module.exports = MarcoDBClient;