import hashlib
import json
import sys
import urllib.request
import rsa
import time
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ==========================================
# KONFIGURASI AWAL NODE
# ==========================================
DIFFICULTY = "0000"
PORT = 0
PEERS = set()
CHAIN = []

# Membuat Key Pair RSA untuk node/cabang ini secara otomatis saat dijalankan
print("Membuat Public & Private Key RSA untuk Node ini...")
PUBLIC_KEY, PRIVATE_KEY = rsa.newkeys(512)
# Simpan Public Key dalam format string PEM agar bisa dikirim lewat JSON
PUB_KEY_PEM = PUBLIC_KEY.save_pkcs1().decode('utf-8')

# ==========================================
# 1. LOGIKA BLOCKCHAIN, FIBONACCI, & RSA
# ==========================================
def get_fibonacci(n):
    if n <= 0: return 0
    elif n == 1: return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def verify_rsa_signature(tx_string, signature_hex, pub_key_pem):
    """Fungsi verifikasi RSA hasil adaptasi dari Praktikum 1"""
    try:
        signature = binascii.unhexlify(signature_hex.encode('utf-8'))
        pub_key = rsa.PublicKey.load_pkcs1(pub_key_pem.encode('utf-8'))
        rsa.verify(tx_string.encode(), signature, pub_key)
        return True
    except Exception:
        return False

def new_block(id, tx_data, parent_id=None, parent_hash=None):
    return {
        "id": id,
        "timestamp": time.time(),
        "transaction": tx_data, # Berisi data transaksi kasir + RSA Signature
        "parent_id": parent_id,
        "parent_hash": parent_hash,
        "fibonacci_modifier": get_fibonacci(id),
        "nonce": None,
    }

def compute_hash(block):
    payload = json.dumps(block, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def mine_block(block, difficulty=DIFFICULTY, max_try=2000000):
    for i in range(max_try):
        block["nonce"] = i
        hasil = compute_hash(block)
        if hasil.startswith(difficulty):
            return i, hasil
    block["nonce"] = None
    return None, None

def genesis_block():
    block = new_block(1, {"keterangan": "Genesis Block - Sistem Kasir Franchise"})
    # Wajib statis agar Hash Genesis identik di semua node saat dijalankan pada waktu berbeda
    block["timestamp"] = 0 
    block["nonce"] = 0
    return block

def is_chain_valid(chain, difficulty=DIFFICULTY):
    if not chain or chain[0]["parent_hash"] is not None:
        return False
    for i in range(1, len(chain)):
        induk = chain[i - 1]
        blok = chain[i]
        
        # 1. Validasi Hash dan Kaitan Rantai
        if blok["parent_id"] != induk["id"]: return False
        if blok["parent_hash"] != compute_hash(induk): return False
        if blok["nonce"] is None: return False
        if not compute_hash(blok).startswith(difficulty): return False
        
        # 2. Validasi Tanda Tangan Digital RSA (Cegah Manipulasi Transaksi)
        tx = blok.get("transaction", {})
        if "signature" in tx:
            tx_string = f"{tx['branch_id']}{tx['receipt_id']}{tx['amount']}{tx['payment_method']}"
            if not verify_rsa_signature(tx_string, tx['signature'], tx['public_key']):
                print(f"--> [BAHAYA] Tanda Tangan RSA pada Block {blok['id']} TIDAK VALID!")
                return False
    return True


# ==========================================
# 2. KOMUNIKASI JARINGAN (P2P)
# ==========================================
def kirim_json(url, isi):
    data = json.dumps(isi).encode("utf-8")
    permintaan = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(permintaan, timeout=5) as balasan:
        return json.loads(balasan.read().decode("utf-8"))

def ambil_json(url):
    with urllib.request.urlopen(url, timeout=5) as balasan:
        return json.loads(balasan.read().decode("utf-8"))

def broadcast_block(block):
    for peer in PEERS:
        try:
            kirim_json(f"http://{peer}/block", block)
            print(f" -> Block {block['id']} disebar ke peer {peer}")
        except Exception:
            pass

def resolve_conflicts():
    terpanjang = CHAIN
    for peer in PEERS:
        try:
            kandidat = ambil_json(f"http://{peer}/chain")["chain"]
            if len(kandidat) > len(terpanjang) and is_chain_valid(kandidat):
                terpanjang = kandidat
        except Exception:
            pass
    if terpanjang is not CHAIN:
        CHAIN[:] = terpanjang
        return True
    return False


# ==========================================
# 3. ANTARMUKA HTTP (SERVER NODE)
# ==========================================
class NodeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def _balas(self, kode, isi):
        badan = json.dumps(isi, indent=2).encode("utf-8")
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(badan)))
        self.end_headers()
        self.wfile.write(badan)

    def do_GET(self):
        if self.path == "/chain":
            self._balas(200, {"panjang": len(CHAIN), "chain": CHAIN})
        elif self.path == "/resolve":
            berubah = resolve_conflicts()
            self._balas(200, {"rantai_diganti": berubah, "panjang": len(CHAIN)})
        else:
            self._balas(404, {"error": "endpoint tidak dikenal"})

    def do_POST(self):
        panjang = int(self.headers.get("Content-Length", 0))
        isi = json.loads(self.rfile.read(panjang) or "{}")

        if self.path == "/peers":
            peer_baru = isi.get("peer")
            if peer_baru and peer_baru not in PEERS:
                PEERS.add(peer_baru)
                self._balas(201, {"pesan": f"Peer {peer_baru} ditambahkan", "peers": list(PEERS)})
            else:
                self._balas(400, {"error": "Peer tidak valid"})

        elif self.path == "/mine":
            induk = CHAIN[-1]
            
            # Menerima input data transaksi kasir
            branch_id = isi.get("branch_id", f"CAB-{PORT}")
            receipt_id = isi.get("receipt_id", f"INV-{int(time.time())}")
            amount = isi.get("amount", 0)
            payment_method = isi.get("payment_method", "CASH")
            
            # Node kasir menandatangani transaksi (RSA Sign)
            tx_string = f"{branch_id}{receipt_id}{amount}{payment_method}"
            signature_bytes = rsa.sign(tx_string.encode(), PRIVATE_KEY, 'SHA-256')
            signature_hex = binascii.hexlify(signature_bytes).decode('utf-8')
            
            tx_data = {
                "branch_id": branch_id,
                "receipt_id": receipt_id,
                "amount": amount,
                "payment_method": payment_method,
                "signature": signature_hex,
                "public_key": PUB_KEY_PEM
            }

            block = new_block(induk["id"] + 1, tx_data, induk["id"], compute_hash(induk))
            nonce, hasil = mine_block(block)
            
            if nonce is None:
                self._balas(500, {"error": "gagal menambang block"})
                return

            CHAIN.append(block)
            print(f"[{PORT}] Block {block['id']} (Struk {receipt_id}) ditambang! Hash: {hasil[:15]}...")
            broadcast_block(block)
            self._balas(201, {"pesan": "block ditambang", "block": block})

        elif self.path == "/block":
            block = isi
            induk = CHAIN[-1]
            # Validasi Block Masuk + RSA
            sah = (
                block.get("parent_id") == induk["id"]
                and block.get("parent_hash") == compute_hash(induk)
                and block.get("nonce") is not None
                and compute_hash(block).startswith(DIFFICULTY)
            )

            # Validasi tambahan RSA Signature jika ada data transaksi
            tx = block.get("transaction", {})
            if sah and "signature" in tx:
                tx_string = f"{tx['branch_id']}{tx['receipt_id']}{tx['amount']}{tx['payment_method']}"
                sah = verify_rsa_signature(tx_string, tx['signature'], tx['public_key'])

            if sah:
                CHAIN.append(block)
                print(f"[{PORT}] Block {block['id']} diterima dari peer.")
                self._balas(200, {"pesan": "block diterima"})
            else:
                print(f"[{PORT}] ❌ Block DITOLAK! Manipulasi / RSA Tidak Valid.")
                self._balas(409, {"pesan": "block ditolak"})
        else:
            self._balas(404, {"error": "endpoint tidak dikenal"})

# ==========================================
# 4. MAIN PROGRAM
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Gunakan format: python node.py <PORT> [peer1,peer2,...]")
        sys.exit(1)

    PORT = int(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2]:
        for p in sys.argv[2].split(","):
            PEERS.add(p.strip())

    CHAIN.append(genesis_block())
    print(f"Node Aktif di Port : {PORT} | Daftar Peers: {list(PEERS)}")
    ThreadingHTTPServer(("0.0.0.0", PORT), NodeHandler).serve_forever()