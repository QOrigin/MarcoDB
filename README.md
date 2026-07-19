# MarcoDB
Native fault tolerance (WAL) and corporate Big Data support. Client-Server architecture operating 100% offline.

MarcoDB Enterprise
Official Database Documentation | Version 1.1
Copyright © 2026 QOrigin Technology Hub

MarcoDB Enterprise is the native database engine of the QOrigin ecosystem. Designed for maximum performance and security, it uses a B+ Tree data structure, offering ultra-fast access to structured data and BLOBs through a Client-Server architecture via pure TCP protocol.

1. Core Architecture and Resilience
Unlike simple file-based databases, MarcoDB was built with the same systems engineering as enterprise databases like PostgreSQL and Oracle.

Industrial Grade Features
Write-Ahead Logging (WAL): Absolute fault tolerance. Before any byte is changed in memory, the intent is physically saved to disk. In the event of a power outage (Hard Crash), the server perfectly recovers the state upon restart.
Overflow Pages (Big Data): Breaks the physical 4KB page limit of the B-Tree. Giant texts or JSONs are automatically sliced into linked memory lists (Data Wagons).
Message Framing (TCP): Uses the <|EOM|> marker to protect the network against packet fragmentation, ensuring transit integrity.
SHA-256 Authentication: Mandatory security handshake. Passwords never travel in plain text.
2. MQL Language (Marco Query Language)
Communication with the server is simple and direct, ideal for microservices and quick integrations.

MQL Command	Expected Syntax	Action Description
auth	auth <user> <password>	Authenticates the current TCP socket. Required before any other operation.
set	set <key> <value>	Inserts a new record. Returns an error if the key already exists.
get	get <key>	Retrieves the stored value (text or JSON).
update	update <key> <new_val>	Replaces the value of an existing key using a safe rewrite mechanism.
del	del <key>	Permanently removes the key and frees the pages on the disk.
import	import <key> <file>	(Driver/CLI Only) Uploads massive files via Overflow Pages.
3. Drivers and Integration
MarcoDB was designed to run on any hosting (including VPS) through port 7300.

Python (Official SDK)
Ideal for integrating with Lucida-Flow Studio or robust back-ends.

from marcodb_client import MarcoDBClient

# Inicializa o driver com a autenticação já configurada
db = MarcoDBClient(host='127.0.0.1', port=7300, user='root', password='your_password')

if db.connect():
    db.execute("set project Qorigin")
    response = db.execute("get project")
    print("Dados retornados:", response)
    db.close()
4. Main Example (Web / PHP Integration)
For web developers, we provide the MarcoDB.php class, which uses fsockopen to bypass provider blocks and connect your site directly to the database.

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
MarcoDB Enterprise — The heart of the QOrigin infrastructure.
