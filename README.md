# 🗄️ MarcoDB Enterprise

**Official Database Documentation | Version 1.1**  
*Copyright © 2026 QOrigin Technology Hub*

MarcoDB Enterprise is the native database engine of the QOrigin ecosystem. Designed for maximum performance and security, it uses a B+ Tree data structure, offering ultra-fast access to structured data and BLOBs through a Client-Server architecture via pure TCP protocol. 

MarcoDB acts as the persistence backbone for projects developed in the Prism Engine, perfectly supporting the data workflows required by Lucida Flow and asset management from Paint Gen.

---

## 1. Core Architecture and Resilience

Unlike simple file-based databases, MarcoDB was built with the same corporate systems engineering as PostgreSQL and Oracle.

*   **Write-Ahead Logging (WAL):** Absolute fault tolerance. Before any byte is altered in memory, the intention is physically saved to disk. In the event of a power outage (Hard Crash), the server perfectly recovers its state upon restarting.
*   **Overflow Pages (Big Data):** Breaks the B-Tree's physical 4KB page limit. Giant texts or JSONs are automatically sliced into linked memory lists (Data Wagons).
*   **Message Framing (TCP):** Uses the `<|EOM|>` marker to protect the network against packet fragmentation, ensuring transit integrity in critical integrations.
*   **SHA-256 Authentication:** Mandatory security handshake. Passwords never travel in plain text.

---

## 2. MQL Language (Marco Query Language)

Communication with the server is simple and direct, ideal for microservices and fast engine integrations.

| MQL Command | Expected Syntax | Action Description |
| :--- | :--- | :--- |
| `auth` | `auth <user> <password>` | Authenticates the current TCP socket. Required before any other operation. |
| `set` | `set <key> <value>` | Inserts a new record. Returns an error if the key already exists. |
| `get` | `get <key>` | Retrieves the stored value (text or JSON). |
| `update` | `update <key> <new_val>` | Replaces the value of an existing key using a secure rewrite mechanism. |
| `del` | `del <key>` | Permanently removes the key and frees up disk pages. |
| `import` | `import <key> <file>` | *(Driver/CLI Only)* Uploads massive files via Overflow Pages. |

---

## 3. Drivers and Integration

MarcoDB was designed to run on **any hosting** (including VPS) through port `7300`.

### Python (Official SDK)
Ideal for coupling backend services, integrating Prism Engine logic, or communicating with **Lucida Flow**.

```python
from marcodb_client import MarcoDBClient

# Initialize the driver with the authentication already configured
db = MarcoDBClient(host='127.0.0.1', port=7300, user='root', password='your_password')

if db.connect():
    db.execute("set project Qorigin")
    response = db.execute("get project")
    print("Returned data:", response)
    db.close()
```

---

## 4. Master Example (Web / PHP Integration)

For web developers or remote administrative panels, we provide the `MarcoDB.php` class. It uses `fsockopen` to bypass provider blocks and connect your site directly to the database.

```php
<?php
require_once 'MarcoDB.php';

try {
    // 1. Connect to the QOrigin Server
    $db = new MarcoDB('198.51.100.45', 7300, 'root', 'strong_password');
    $db->connect();
    
    // 2. Simulating the saving of a massive JSON
    $config_site = json_encode([
        "theme" => "dark",
        "maintenance" => false,
        "active_users" => 1542
    ]);
    
    // MarcoDB creates the Overflow Pages automatically
    $db->query("update general_settings " . $config_site);
    
    // 3. Retrieving for the Front-end
    $data = $db->query("get general_settings");
    echo "Current Settings: " . $data;

    $db->close();

} catch (Exception $e) {
    echo "Critical Database Error: " . $e->getMessage();
}
?>
```

---
> **MarcoDB Enterprise** — The heart of the QOrigin infrastructure.
