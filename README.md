# 🗄️ MarcoDB Enterprise

**Documentação Oficial do Banco de Dados | Versão 1.1**  
*Copyright © 2026 QOrigin Hub Tecnológica*

O **MarcoDB Enterprise** é o motor de banco de dados nativo do ecossistema QOrigin. Projetado para máxima performance e segurança, ele utiliza uma estrutura de dados B+ Tree, oferecendo acesso ultrarrápido a dados estruturados e BLOBs através de uma arquitetura Cliente-Servidor via protocolo TCP puro. 

O MarcoDB atua como a espinha dorsal de persistência para os projetos desenvolvidos na **Prism Engine**, suportando perfeitamente os fluxos de trabalho de dados exigidos pelo **Lucida Flow** e gerenciamento de assets do **Paint Gen**.

---

## 1. Core Architecture e Resiliência

Diferente de bancos de dados simples baseados em arquivos, o MarcoDB foi construído com a mesma engenharia de sistemas corporativos como PostgreSQL e Oracle.

*   **Write-Ahead Logging (WAL):** Tolerância absoluta a falhas. Antes de qualquer byte ser alterado na memória, a intenção é salva fisicamente no disco. Em caso de queda de energia (Hard Crash), o servidor recupera perfeitamente o estado ao reiniciar.
*   **Overflow Pages (Big Data):** Quebra o limite físico da página de 4KB da B-Tree. Textos gigantes ou JSONs são automaticamente fatiados em listas de memória encadeadas (Data Wagons).
*   **Message Framing (TCP):** Utiliza o marcador `<|EOM|>` para proteger a rede contra fragmentação de pacotes, garantindo integridade de trânsito em integrações críticas.
*   **Autenticação SHA-256:** Handshake de segurança obrigatório. Senhas nunca trafegam em texto puro.

---

## 2. MQL Language (Marco Query Language)

A comunicação com o servidor é feita de forma simples e direta, ideal para microserviços e integrações rápidas em engines.

| Comando MQL | Sintaxe Esperada | Descrição da Ação |
| :--- | :--- | :--- |
| `auth` | `auth <user> <password>` | Autentica o socket TCP atual. Necessário antes de qualquer outra operação. |
| `set` | `set <key> <value>` | Insere um novo registro. Retorna erro se a chave já existir. |
| `get` | `get <key>` | Recupera o valor armazenado (texto ou JSON). |
| `update` | `update <key> <new_val>` | Substitui o valor de uma chave existente usando mecanismo de reescrita segura. |
| `del` | `del <key>` | Remove a chave permanentemente e libera as páginas no disco. |
| `import` | `import <key> <file>` | *(Apenas Driver/CLI)* Faz upload de arquivos massivos via Overflow Pages. |

---

## 3. Drivers e Integração

O MarcoDB foi desenhado para rodar em **qualquer hospedagem** (incluindo VPS) através da porta `7300`.

### Python (SDK Oficial)
Ideal para acoplar serviços backend, integrar a lógica da Prism Engine ou comunicar-se com o **Lucida Flow**.

```python
from marcodb_client import MarcoDBClient

# Inicializa o driver com a autenticação já configurada
db = MarcoDBClient(host='127.0.0.1', port=7300, user='root', password='your_password')

if db.connect():
    db.execute("set project Qorigin")
    response = db.execute("get project")
    print("Dados retornados:", response)
    db.close()
```

---

## 4. Exemplo Mestre (Web / Integração PHP)

Para desenvolvedores web ou painéis administrativos remotos, fornecemos a classe `MarcoDB.php`. Ela utiliza `fsockopen` para contornar bloqueios de provedores e conectar seu site diretamente ao banco de dados.

```php
<?php
require_once 'MarcoDB.php';

try {
    // 1. Conecta ao Servidor QOrigin
    $db = new MarcoDB('198.51.100.45', 7300, 'root', 'strong_password');
    $db->connect();
    
    // 2. Simulando salvamento de um JSON massivo
    $config_site = json_encode([
        "theme" => "dark",
        "maintenance" => false,
        "active_users" => 1542
    ]);
    
    // MarcoDB cria as Overflow Pages automaticamente
    $db->query("update general_settings " . $config_site);
    
    // 3. Recuperando para o Front-end
    $data = $db->query("get general_settings");
    echo "Configurações Atuais: " . $data;

    $db->close();

} catch (Exception $e) {
    echo "Erro Crítico de Banco de Dados: " . $e->getMessage();
}
?>
```

---
> **MarcoDB Enterprise** — O coração da infraestrutura QOrigin.
