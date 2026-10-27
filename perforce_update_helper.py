#!/usr/bin/env python3
"""
Perforce Update Helper
======================
Ambil revisi terbaru dari folder Perforce mana pun dengan satu perintah,
tanpa perlu klik-klik manual di P4V.

Developed by ardi.putra with full AI coding assistance.

Contoh:
  python perforce_update_helper.py                                  # pakai semua setting di blok SETTING DEFAULT
  python perforce_update_helper.py -d //depot/project/folder        # timpa depot path
  python perforce_update_helper.py -n                               # preview saja
  python perforce_update_helper.py -m                               # download ulang file yang terhapus di lokal
  python perforce_update_helper.py --no-force                       # matikan opsi yang di-set True di script
  python perforce_update_helper.py -r @12345                        # sync ke changelist tertentu
"""

import argparse
import subprocess
import sys

# ============================================================
# SETTING DEFAULT
#
# Nilai di bawah adalah nilai cadangan (default). Ada 2 cara memakainya:
#   1) Isi di sini, lalu jalankan tanpa argumen:   python perforce_update_helper.py
#   2) Kosongkan di sini, lalu kirim lewat argumen: python perforce_update_helper.py -d //depot/folder -c workspace
#      (argumen selalu menimpa nilai di sini)
#
# WAJIB diisi (di script atau lewat argumen):
#   - DEFAULT_DEPOT_PATH / -d
#   - DEFAULT_CLIENT / -c   (kecuali P4CLIENT sudah ter-set di sistem, cek: p4 set P4CLIENT)
#     Kalau kosong dan P4CLIENT tidak ter-set, p4 memakai nama komputer sebagai nama
#     workspace dan akan error "Client 'NAMA-PC' unknown".
# Boleh kosong: USER dan PORT, kalau sudah ter-set di sistem (cek: p4 set).
# ============================================================

# ---------------- KONEKSI & LOKASI ----------------

# DEFAULT_DEPOT_PATH = path folder DI SERVER Perforce (diawali //), bukan path di komputer.
#   Contoh: "//depot/project/folder"
#   Cara cari:
#     a) P4V: klik kanan folder di tab "Depot" > Properties (atau lihat path di bagian atas
#        tree), lalu salin path yang diawali "//".
#     b) Terminal: lihat daftar depot dengan   p4 depots
#        lalu telusuri folder dengan          p4 dirs "//namadepot/*"
#                                              p4 dirs "//namadepot/folder/*"
#     c) Kalau sudah tahu path lokalnya (di komputer), tanya server:
#          p4 where "D:\path\lokal\folder\..."
#        Kolom pertama hasilnya adalah depot path-nya.
#   Jangan sertakan "/..." di belakang, script menambahkannya sendiri.
DEFAULT_DEPOT_PATH = ""

# DEFAULT_USER = username Perforce.
#   Cara cari: p4 info   (baris "User name"), atau P4V > Connection > Connection Info.
#   Kosong = pakai P4USER yang sudah ter-set (cek: p4 set).
DEFAULT_USER = ""

# DEFAULT_CLIENT = nama workspace (client) Perforce kamu.
#   Cara cari:
#     a) P4V: lihat dropdown "Workspace" di pojok kanan atas, atau tab Workspaces.
#     b) Terminal: p4 clients -u USERNAME_KAMU
#        Pilih yang kolom "root"-nya sama dengan folder lokal tempat file mau diunduh.
#        (Kalau ada beberapa PC, pilih yang namanya sesuai PC yang sedang dipakai.)
#     c) Lihat yang sedang aktif sekarang: p4 info   (baris "Client name")
#   Kosong = pakai P4CLIENT yang sudah ter-set (cek: p4 set). Kalau muncul error
#   "Client 'xxx' unknown", artinya nama default dari hostname tidak ada di server,
#   jadi isi nilai ini.
DEFAULT_CLIENT = ""

# DEFAULT_PORT = alamat server Perforce. REKOMENDASI: BIARKAN KOSONG.
#   Kosong = pakai P4PORT yang sudah ter-set di sistem (cek: p4 set P4PORT), sama seperti
#   yang dipakai P4V dan perintah p4 lainnya di terminal.
#   Kalau P4PORT belum ter-set, atur sekali secara permanen (tidak perlu isi di script):
#       p4 set P4PORT=ssl:namaserver.perusahaan.com:1667
#   Info penting kalau mau mengisinya di sini:
#     - Formatnya harus lengkap: host:port, bukan port saja. Port saja (misal "1667")
#       dianggap localhost dan akan error "connection refused".
#     - Kalau server memakai SSL, WAJIB pakai prefix "ssl:", contoh
#       "ssl:namaserver.perusahaan.com:1667". Tanpa itu muncul error
#       "Failed client connect, server using SSL".
#     - Cek alamat server dengan: p4 info (baris "Server address"), atau
#       P4V > Connection > Connection Info.
#     - Pertama kali konek lewat SSL, mungkin perlu: p4 trust -y
#     - Kalau muncul error soal password/sesi: p4 login
DEFAULT_PORT = ""

# DEFAULT_REVISION = revisi yang diambil.
#   "#head" = terbaru (default), "@12345" = sampai changelist 12345,
#   "@2026/10/27" = kondisi pada tanggal tersebut.
DEFAULT_REVISION = "#head"

# ---------------- OPSI (True = aktif, False = nonaktif) ----------------
# Bisa ditimpa dari command line: pakai --nama-opsi untuk mengaktifkan,
# atau --no-nama-opsi untuk menonaktifkan (contoh: --no-force, --no-preview).

# DEFAULT_PREVIEW = hanya tampilkan apa yang AKAN dilakukan, tanpa download apa pun.
#   Aman untuk coba-coba. (argumen: -n / --preview / --no-preview)
DEFAULT_PREVIEW = False

# DEFAULT_RESTORE_MISSING = download ulang file yang terhapus di lokal.
#   Perlu karena kalau file dihapus manual (bukan lewat p4), server tetap mengira kamu masih
#   punya file itu, jadi sync biasa bilang "up-to-date".
#   (argumen: -m / --restore-missing / --no-restore-missing)
DEFAULT_RESTORE_MISSING = False

# DEFAULT_FORCE = paksa download ulang SEMUA file di folder, termasuk yang masih ada dan
#   tidak berubah, lalu menimpanya tanpa pengecekan. Bisa lama di folder besar, dan file
#   yang diubah lokal tanpa "p4 edit" akan tertimpa.
#   HATI-HATI: sebaiknya biarkan False kecuali memang perlu.
#   (argumen: -f / --force / --no-force)
DEFAULT_FORCE = False

# DEFAULT_QUIET = kurangi output saat sync (p4 sync -q).
#   (argumen: -q / --quiet / --no-quiet)
DEFAULT_QUIET = False

# DEFAULT_EDIT = setelah sync, checkout (p4 edit) SEMUA file di folder untuk diedit.
#   Biasanya tidak perlu untuk sekadar "ambil latest".
#   (argumen: --edit / --no-edit)
DEFAULT_EDIT = False

# ============================================================


def build_base_cmd(args):
    cmd = ["p4"]
    if args.port:
        cmd += ["-p", args.port]
    if args.user:
        cmd += ["-u", args.user]
    if args.client:
        cmd += ["-c", args.client]
    return cmd


def run(cmd, check=True):
    print(f"> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        print(f"[ERROR] {err}")
        low = err.lower()
        if "password" in low or "login" in low:
            print("[HINT] Sesi login habis. Jalankan: p4 login")
        if "unknown" in low and "client" in low:
            print("[HINT] Nama workspace salah. Cek dengan: p4 clients -u <username>")
        if "ssl" in low:
            print("[HINT] Server pakai SSL. Pakai prefix 'ssl:' di P4PORT, atau set: p4 set P4PORT=ssl:host:port")
        if "trust" in low:
            print("[HINT] Jalankan sekali: p4 trust -y")
        if "connect" in low and ("refused" in low or "failed" in low):
            print("[HINT] Cek P4PORT (p4 set P4PORT). Format harus host:port, bukan port saja.")
        sys.exit(result.returncode)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Perforce Update Helper: sync revisi terbaru folder Perforce. "
                    "Developed by ardi.putra with full AI coding assistance.")
    parser.add_argument("-d", "--depot", default=DEFAULT_DEPOT_PATH, help="Depot path folder, contoh: //depot/proj/folder")
    parser.add_argument("-u", "--user", default=DEFAULT_USER, help="Username Perforce")
    parser.add_argument("-c", "--client", default=DEFAULT_CLIENT, help="Nama workspace/client")
    parser.add_argument("-p", "--port", default=DEFAULT_PORT, help="P4PORT (server), kosong = pakai setting sistem")
    parser.add_argument("-r", "--rev", default=DEFAULT_REVISION, help="Revision spec (#head, @CL, @tanggal)")

    flag = argparse.BooleanOptionalAction
    parser.add_argument("-n", "--preview", action=flag, default=DEFAULT_PREVIEW,
                        help="Preview saja, tanpa download")
    parser.add_argument("-m", "--restore-missing", action=flag, default=DEFAULT_RESTORE_MISSING,
                        help="Download ulang file yang terhapus di lokal")
    parser.add_argument("-f", "--force", action=flag, default=DEFAULT_FORCE,
                        help="Force resync semua file (p4 sync -f)")
    parser.add_argument("-q", "--quiet", action=flag, default=DEFAULT_QUIET,
                        help="Kurangi output (p4 sync -q)")
    parser.add_argument("--edit", action=flag, default=DEFAULT_EDIT,
                        help="Setelah sync, p4 edit semua file di folder")
    args = parser.parse_args()

    if not args.depot:
        parser.error("Depot path wajib diisi: pakai -d //depot/path atau set DEFAULT_DEPOT_PATH di script.")

    depot = args.depot.rstrip("/")
    base = build_base_cmd(args)

    print("=" * 50)
    print(" Perforce Update Helper")
    print(" Developed by ardi.putra with full AI coding assistance")
    print("=" * 50)

    # Tampilkan opsi yang aktif
    active = [name for name, on in [
        ("preview", args.preview), ("restore-missing", args.restore_missing),
        ("force", args.force), ("quiet", args.quiet), ("edit", args.edit)] if on]
    print(f"[INFO] Opsi aktif: {', '.join(active) if active else '(tidak ada)'}")

    # Cek koneksi & login
    run(base + ["login", "-s"])

    # Cek workspace/client valid sebelum sync
    info = run(base + ["info"], check=False).stdout
    if "client unknown" in info.lower():
        user = args.user
        for line in info.splitlines():
            if line.startswith("User name:") and not user:
                user = line.split(":", 1)[1].strip()
        print("[ERROR] Workspace/client belum diisi atau tidak dikenal oleh server.")
        print("        Isi DEFAULT_CLIENT di script, atau jalankan dengan -c NAMA_WORKSPACE.")
        print("        Workspace yang tersedia untuk user kamu (pilih yang root-nya sesuai folder lokal):")
        clients = run(["p4"] + (["-p", args.port] if args.port else []) + ["clients", "-u", user], check=False)
        print(clients.stdout.strip() or "        (tidak ada hasil, cek username dengan: p4 info)")
        sys.exit(1)

    # Tampilkan lokasi lokal tujuan
    where = run(base + ["where", f"{depot}/..."], check=False)
    if where.stdout.strip():
        print(f"[INFO] Mapping: {where.stdout.strip()}")

    # Sync
    sync_cmd = base + ["sync"]
    if args.preview:
        sync_cmd.append("-n")
    if args.force:
        sync_cmd.append("-f")
    if args.quiet:
        sync_cmd.append("-q")
    sync_cmd.append(f"{depot}/...{args.rev}")

    result = run(sync_cmd, check=False)
    out = result.stdout.strip()
    err = result.stderr.strip()

    if result.returncode != 0 and "up-to-date" not in err:
        print(f"[ERROR] {err}")
        sys.exit(result.returncode)

    print(out or err or "[INFO] Sudah up-to-date.")

    # Restore file yang terhapus di lokal.
    # Penyebab: kalau file dihapus manual (bukan lewat p4), server tetap mengira kamu
    # masih punya file itu, jadi "p4 sync" biasa bilang up-to-date.
    if args.restore_missing:
        missing_res = run(base + ["diff", "-sd", f"{depot}/..."], check=False)
        missing = []
        for line in missing_res.stdout.splitlines():
            path = line.strip().split("#")[0].strip()
            if path:
                missing.append(path)
        if not missing:
            print("[INFO] Tidak ada file yang hilang di lokal.")
        else:
            print(f"[INFO] {len(missing)} file hilang di lokal, download ulang...")
            for i in range(0, len(missing), 100):
                batch = missing[i:i + 100]
                cmd = base + ["sync", "-f"] + (["-n"] if args.preview else []) + batch
                res = run(cmd, check=False)
                print(res.stdout.strip() or res.stderr.strip())

    # Checkout untuk edit (opsional)
    if args.edit and not args.preview:
        edit_result = run(base + ["edit", f"{depot}/..."], check=False)
        print(edit_result.stdout.strip() or edit_result.stderr.strip())

    print("[DONE]")


if __name__ == "__main__":
    main()
