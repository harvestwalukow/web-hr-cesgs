def generate_default_password(nama, tgl_lahir):
    nama_depan = nama.split()[0].lower()
    tanggal = tgl_lahir.strftime('%d%m%Y')
    return f"{nama_depan}{tanggal}"