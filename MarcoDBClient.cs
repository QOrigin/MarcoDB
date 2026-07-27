using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace QOrigin.MarcoDB
{
    public class MarcoDBClient : IDisposable
    {
        private readonly string host;
        private readonly int port;
        private readonly string user;
        private readonly string password;
        
        private TcpClient client;
        private NetworkStream stream;
        private StringBuilder buffer;
        
        // O "Semáforo" do C#. Fundamental para engines multithread!
        private readonly object dbLock = new object();

        public MarcoDBClient(string host = "127.0.0.1", int port = 7300, string user = "root", string password = "qorigin123")
        {
            this.host = host;
            this.port = port;
            this.user = user;
            this.password = password;
            this.buffer = new StringBuilder();
        }

        public bool Connect()
        {
            try
            {
                client = new TcpClient();
                client.Connect(host, port);
                stream = client.GetStream();
                stream.ReadTimeout = 5000;
                stream.WriteTimeout = 5000;

                // 1. Lê a mensagem de boas-vindas do servidor
                ReadUntilEOM();

                // 2. Envia a credencial de segurança (Handshake)
                SendCmd($"auth {user} {password}");

                // 3. Analisa a resposta do servidor
                string resposta = ReadUntilEOM();
                if (resposta.Contains("OK. Acesso Permitido"))
                {
                    stream.ReadTimeout = Timeout.Infinite; // Libera o timeout para queries MQL pesadas
                    return true;
                }
                
                Console.WriteLine($"MarcoDB Erro de Autenticação: {resposta}");
                Close();
                return false;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"MarcoDB Falha de Conexão: {ex.Message}");
                return false;
            }
        }

        public string Query(string command)
        {
            // Bloqueio Thread-Safe: Fila automática de comandos no socket
            lock (dbLock)
            {
                if (client == null || !client.Connected)
                    return "Erro: Cliente não está conectado ao servidor.";

                SendCmd(command);
                return ReadUntilEOM();
            }
        }

        private void SendCmd(string cmd)
        {
            byte[] data = Encoding.UTF8.GetBytes($"{cmd}<|EOM|>");
            stream.Write(data, 0, data.Length);
        }

        private string ReadUntilEOM()
        {
            byte[] readBuffer = new byte[4096];
            
            while (!buffer.ToString().Contains("<|EOM|>"))
            {
                int bytesRead = stream.Read(readBuffer, 0, readBuffer.Length);
                if (bytesRead == 0)
                    return "Erro: Conexão perdida com o servidor.";
                    
                buffer.Append(Encoding.UTF8.GetString(readBuffer, 0, bytesRead));
            }

            string fullBuffer = buffer.ToString();
            string[] parts = fullBuffer.Split(new[] { "<|EOM|>" }, 2, StringSplitOptions.None);
            
            string msg = parts[0];
            
            buffer.Clear(); // Limpa e guarda apenas as sobras do pacote
            if (parts.Length > 1)
                buffer.Append(parts[1]);

            return msg.Trim();
        }

        public void Close()
        {
            lock (dbLock)
            {
                if (client != null)
                {
                    try { SendCmd("exit"); } catch { }
                    stream?.Close();
                    client?.Close();
                    client = null;
                    buffer.Clear();
                }
            }
        }

        public void Dispose() => Close();
    }
}