import hashlib
import time
import rsa # Untuk Public/Private Key dan Digital Signature

# ==========================================
# 1. CLASS TRANSAKSI (Payload / Data Kasir)
# ==========================================
class Transaction:
    def __init__(self, branch_id, receipt_id, amount, payment_method):
        self.branch_id = branch_id
        self.receipt_id = receipt_id
        self.amount = amount
        self.payment_method = payment_method
        self.signature = None # Akan diisi setelah di-sign oleh kasir

    # Menghasilkan hash unik dari isi transaksi
    def calculate_hash(self):
        tx_string = f"{self.branch_id}{self.receipt_id}{self.amount}{self.payment_method}"
        return hashlib.sha256(tx_string.encode()).hexdigest()

    # Kasir menandatangani transaksi menggunakan Private Key cabang
    def sign_transaction(self, private_key):
        tx_hash = self.calculate_hash()
        self.signature = rsa.sign(tx_hash.encode(), private_key, 'SHA-256')

    # Sistem memverifikasi apakah transaksi benar dari cabang yang sah
    def is_valid(self, public_key):
        if self.signature is None:
            return False
        tx_hash = self.calculate_hash()
        try:
            rsa.verify(tx_hash.encode(), self.signature, public_key)
            return True
        except rsa.VerificationError:
            return False

# ==========================================
# 2. CLASS BLOCK (Struktur Data & Proof of Work)
# ==========================================
class Block:
    def __init__(self, index, transactions, previous_hash):
        self.index = index
        self.timestamp = time.time()
        self.transactions = transactions # Berisi list objek Transaction
        self.previous_hash = previous_hash
        self.nonce = 0 # Angka acak untuk ditambang
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        # Gabungkan hash semua transaksi di block ini
        tx_hashes = "".join([tx.calculate_hash() for tx in self.transactions])
        # Gabungkan seluruh header block
        block_string = f"{self.index}{self.timestamp}{tx_hashes}{self.previous_hash}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    # Proof of Work: Mencari hash yang diawali dengan '0' sebanyak difficulty
    def mine_block(self, difficulty):
        target = "0" * difficulty
        print(f"Menambang block {self.index}...")
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Block berhasil ditambang! Hash: {self.hash}")

# ==========================================
# 3. CLASS BLOCKCHAIN (Mesin Utama & Validator)
# ==========================================
class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]
        self.difficulty = 3 # Tingkat kesulitan Proof of Work
        self.pending_transactions = []

    def create_genesis_block(self):
        return Block(0, [], "0") # Block pertama (Index 0), prev_hash = "0"

    def get_latest_block(self):
        return self.chain[-1]

    def add_transaction(self, transaction, public_key):
        # Tolak jika tanda tangan digital palsu
        if not transaction.is_valid(public_key):
            raise Exception("ERROR: Transaksi tidak valid! Signature salah/dipalsukan.")
        self.pending_transactions.append(transaction)

    def mine_pending_transactions(self):
        new_block = Block(
            index=len(self.chain),
            transactions=self.pending_transactions,
            previous_hash=self.get_latest_block().hash
        )
        new_block.mine_block(self.difficulty)
        self.chain.append(new_block)
        self.pending_transactions = [] # Kosongkan antrean

    # Fungsi Deteksi Manipulasi (Syarat Rubrik)
    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # Cek apakah ada data dalam block yang diam-diam diubah
            if current_block.hash != current_block.calculate_hash():
                print(f"--> [BAHAYA] Data pada Block {i} telah dimanipulasi!")
                return False

            # Cek apakah rantai terputus
            if current_block.previous_hash != previous_block.hash:
                print(f"--> [BAHAYA] Rantai terputus pada Block {i}!")
                return False

        return True


    # ==========================================
# SKENARIO DEMO PRAKTIKUM 1 (Jalankan file ini)
# ==========================================
if __name__ == "__main__":
    print("--- INISIALISASI SISTEM ---")
    # 1. Buat pasangan kunci untuk Cabang Jakarta-01
    print("Membuat Public & Private Key untuk Cabang JKT-01...")
    pub_key_jkt, priv_key_jkt = rsa.newkeys(512)
    
    # Inisiasi Blockchain
    kopi_chain = Blockchain()

    print("\n--- TRANSAKSI KASIR HARI INI ---")
    # 2. Kasir input transaksi pelanggan 1
    tx1 = Transaction("JKT-01", "INV-001", 50000, "QRIS")
    tx1.sign_transaction(priv_key_jkt) # Kasir Tanda Tangan
    kopi_chain.add_transaction(tx1, pub_key_jkt)
    print("Struk INV-001 ditambahkan ke antrean.")

    # 3. Kasir input transaksi pelanggan 2
    tx2 = Transaction("JKT-01", "INV-002", 75000, "CASH")
    tx2.sign_transaction(priv_key_jkt) # Kasir Tanda Tangan
    kopi_chain.add_transaction(tx2, pub_key_jkt)
    print("Struk INV-002 ditambahkan ke antrean.")

    # 4. Memasukkan transaksi ke dalam Block (Mining)
    print("\nServer pusat memasukkan transaksi ke dalam block...")
    kopi_chain.mine_pending_transactions()

    # 5. Cek validitas awal
    print(f"\nStatus Validitas Blockchain: {kopi_chain.is_chain_valid()}")

    print("\n--- SIMULASI SERANGAN (PENGGELAPAN DANA) ---")
    print("Kasir mencoba mengubah data struk INV-002 (75000) menjadi (10000) di database...")
    
    # Oknum mengubah data transaksi pada block yang sudah dicetak
    kopi_chain.chain[1].transactions[1].amount = 10000 
    
    # 6. Sistem mengecek ulang integritas
    print("\nSistem pusat mengecek integritas data:")
    is_valid = kopi_chain.is_chain_valid()
    print(f"Status Validitas Blockchain sekarang: {is_valid}")
    if not is_valid:
         print("TINDAKAN: Sistem menolak database! Terdeteksi adanya manipulasi (cooking the books).")