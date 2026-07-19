# 🗄️ MarcoDB Enterprise

**Official Database Documentation | Version 1.1**  
*Copyright © 2026 QOrigin Technology Hub*

MarcoDB Enterprise is the native database engine of the QOrigin ecosystem. Designed for maximum performance and security, it uses a B+ Tree data structure, offering ultra-fast access to structured data and BLOBs through a Client-Server architecture via pure TCP protocol[cite: 1]. 

MarcoDB acts as the persistence backbone for projects developed in the Prism Engine[cite: 1], perfectly supporting the data workflows required by Lucida Flow and asset management from Paint Gen[cite: 1].

---

## 1. Core Architecture and Resilience[cite: 1]

Unlike simple file-based databases, MarcoDB was built with the same corporate systems engineering as PostgreSQL and Oracle[cite: 1].

*   **Write-Ahead Logging (WAL):** Absolute fault tolerance[cite: 1]. Before any byte is altered in memory, the intention is physically saved to disk[cite: 1]. In the event of a power outage (Hard Crash), the server perfectly recovers its state upon restarting[cite: 1].
*   **Overflow Pages (Big Data):** Breaks the B-Tree's physical 4KB page limit[cite: 1]. Giant texts or JSONs are automatically sliced into linked memory lists (Data Wagons)[cite: 1].
*   **Message Framing (TCP):** Uses the `<|EOM|>` marker to protect the network against packet fragmentation, ensuring transit integrity in critical integrations[cite: 1].
*   **SHA-256 Authentication:** Mandatory security handshake[cite: 1]. Passwords never travel in plain text[cite: 1].

---

## 2. MQL Language (Marco Query Language)[cite: 1]

Communication with the server is simple and direct, ideal for microservices and fast engine integrations[cite: 1].

| MQL Command | Expected Syntax | Action Description |
| :--- | :--- | :--- |
| `auth` | `auth <user> <password>` | Authenticates the current TCP socket. Required before any other operation.[cite: 1] |
| `set` | `set <key> <value>` | Inserts a new record. Returns an error if the key already exists.[cite: 1] |
| `get` | `get <key>` | Retrieves the stored value (text or JSON).[cite: 1] |
| `update` | `update <key> <new_val>` | Replaces the value of an existing key using a secure rewrite mechanism.[cite: 1] |
| `del` | `del <key>` | Permanently removes the key and frees up disk pages.[cite: 1] |
| `import` | `import <key> <file>` | *(Driver/CLI Only)* Uploads massive files via Overflow Pages.[cite: 1] |

---

## 3. Drivers and Integration[cite: 1]

MarcoDB was designed to run on **any hosting** (including VPS) through port `7300`[cite: 1].

### Python (Official SDK)[cite: 1]
Ideal for coupling backend services, integrating Prism Engine logic, or communicating with **Lucida Flow**[cite: 1].

```python
from marcodb_client import MarcoDBClient

# Initialize the driver with the authentication already configured[cite: 1]
db = MarcoDBClient(host='127.0.0.1', port=7300, user='root', password='your_password')

if db.connect():
    db.execute("set project Qorigin")
    response = db.execute("get project")
    print("Returned data:", response)
    db.close()
