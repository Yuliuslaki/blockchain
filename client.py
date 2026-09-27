import json
import sys
import urllib.error
import urllib.request
import time

def panggil(url, data=None):
    if data is None:
        permintaan = urllib.request.Request(url)
    else:
        permintaan = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers={"Content-Type": "application/json"}, 
            method="POST"
        )
    with urllib.request.urlopen(permintaan, timeout=30) as balasan:
        return json.loads(balasan.read().decode("utf-8"))

def ringkas(chain):
    for block in chain:
        induk = block.get("parent_hash")
        induk = induk[:15] + "..." if induk else "None"
        tx = block.get("transaction", {})
        
        print(f"--------------------------------------------------")
        print(f" Block ID          : {block['id']}")
        print(f" Nonce             : {str(block['nonce']).ljust(8)}")
        print(f" Fibonacci Modifier: {block.get('fibonacci_modifier', 'N/A')}")
        print(f" Parent Hash       : {induk}")
        
        # Format cetakan khusus untuk data kasir
        if "keterangan" in tx:
            print(f" Transaction       : {tx['keterangan']}")
        else:
            print(f" Branch ID         : {tx.get('branch_id', 'N/A')}")
            print(f" Receipt ID        : {tx.get('receipt_id', 'N/A')}")
            print(f" Amount            : Rp {tx.get('amount', 0)}")
            print(f" Payment Method    : {tx.get('payment_method', 'N/A')}")
            sig = tx.get('signature', '')
            print(f" RSA Signature     : {sig[:15]}... (Valid)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Gunakan format:")
        print("  python client.py mine <alamat:port> '<json_data>'")
        print("  python client.py chain <alamat:port>")
        print("  python client.py resolve <alamat:port>")
        print("  python client.py add_peer <alamat:port> <peer_baru:port>")
        print("  python client.py palsu <alamat:port>")
        sys.exit(1)

    perintah = sys.argv[1]
    alamat = sys.argv[2]

    if perintah == "mine":
        raw_data = sys.argv[3] if len(sys.argv) > 3 else "{}"
        try:
            tx_data = json.loads(raw_data)
        except Exception:
            print("Error: Format data harus JSON yang valid! Gunakan tanda kutip ganda.")
            sys.exit(1)
            
        hasil = panggil(f"http://{alamat}/mine", tx_data)
        print(f"Berhasil: {hasil['pesan']} (Block ID {hasil['block']['id']})")

    elif perintah == "chain":
        hasil = panggil(f"http://{alamat}/chain")
        print(f"Panjang rantai di {alamat}: {hasil['panjang']} block")
        ringkas(hasil["chain"])

    elif perintah == "resolve":
        hasil = panggil(f"http://{alamat}/resolve")
        if hasil["rantai_diganti"]:
            print(f"Rantai berhasil disinkronkan! Panjang sekarang: {hasil['panjang']} block")
        else:
            print(f"Rantai sudah yang terpanjang. Panjang: {hasil['panjang']} block")

    elif perintah == "add_peer":
        target_peer = sys.argv[3] if len(sys.argv) > 3 else ""
        if not target_peer:
            print("Error: Masukkan alamat peer yang ingin ditambahkan! Cth: localhost:5002")
            sys.exit(1)
        hasil = panggil(f"http://{alamat}/peers", {"peer": target_peer})
        print(hasil['pesan'])
        print(f"Daftar Peers Aktif: {hasil['peers']}")

    elif perintah == "palsu":
        terakhir = panggil(f"http://{alamat}/chain")["chain"][-1]
        block_palsu = {
            "id": terakhir["id"] + 1,
            "timestamp": time.time(),
            "transaction": {"keterangan": "Block manipulasi oknum kasir"},
            "parent_id": terakhir["id"],
            "parent_hash": "0" * 64,
            "fibonacci_modifier": 999,
            "nonce": 1
        }
        try:
            panggil(f"http://{alamat}/block", block_palsu)
            print("❌ Block palsu DITERIMA (Validasi node gagal!).")
        except urllib.error.HTTPError as e:
            print(f"✔ Block palsu DITOLAK oleh node. Status HTTP: {e.code}")

    else:
        print(f"Perintah tidak dikenal: {perintah}")