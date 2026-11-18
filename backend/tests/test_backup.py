import pytest
from sqlalchemy import create_engine, func, select

from app.core.database import Base
from app.models import Document, Invoice
from app.ops import backup
from app.services import storage as storage_mod
from tests.conftest import doc


@pytest.fixture
def key(monkeypatch):
    k = backup.Fernet.generate_key().decode()
    monkeypatch.setattr(backup.settings, "BACKUP_ENCRYPTION_KEY", k)
    return k


@pytest.fixture
def populated(org):
    acc = org["acc"]
    for k in ("01_valid", "04_missing_fields"):
        d = acc.upload(doc(k)).json()
        acc.post("/invoices/extract", json={"document_id": d["id"]})
    return org


def _fresh_engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'restore.db'}")
    Base.metadata.create_all(eng)
    return eng


def test_round_trip_backup_and_restore(populated, key, tmp_path, db, monkeypatch):
    dest = backup.LocalDestination(tmp_path / "bk")
    snap = backup.create(dest)
    assert snap.manifest["tables"]["invoices"] == db.scalar(select(func.count()).select_from(Invoice))
    assert snap.manifest["documents_uploaded"] == 2
    v = backup.verify(dest, deep=True)
    assert v["ok"], v["problems"]
    # files on disk are encrypted (no PDF header, no plaintext company names)
    blob = (tmp_path / "bk" / "snapshots" / snap.id / "db.jsonl.gz.enc").read_bytes()
    assert b"Acme" not in blob and not any(p.read_bytes().startswith(b"%PDF") for p in (tmp_path / "bk" / "documents").iterdir())

    # restore into a brand-new database + empty storage
    new_storage = storage_mod.LocalStorage(tmp_path / "restored-docs")
    monkeypatch.setattr(backup, "get_storage", lambda: new_storage)
    eng = _fresh_engine(tmp_path)
    res = backup.restore(dest, snap.id, eng=eng)
    assert res["documents"] == 2
    with eng.connect() as c:
        assert c.execute(select(func.count()).select_from(Invoice.__table__)).scalar() == snap.manifest["tables"]["invoices"]
        totals = sorted(str(t) for t in c.execute(select(Invoice.__table__.c.grand_total)).scalars() if t is not None)
    originals = sorted(str(i.grand_total) for i in db.query(Invoice).all() if i.grand_total is not None)
    assert totals == originals  # exact Decimal values survive
    key_ = db.query(Document).first().storage_key
    with new_storage.local_path(key_) as p:
        assert p.read_bytes()[:4] in (b"%PDF", b"\x89PNG")

    # refuses to overwrite a non-empty database unless --wipe
    with pytest.raises(backup.BackupError):
        backup.restore(dest, snap.id, eng=eng, restore_documents=False)
    assert backup.restore(dest, snap.id, eng=eng, wipe=True, restore_documents=False)["rows"] > 0


def test_documents_are_deduplicated_and_pruned(populated, key, tmp_path):
    dest = backup.LocalDestination(tmp_path / "bk")
    first = backup.create(dest)
    second = backup.create(dest)
    assert first.manifest["documents_uploaded"] == 2 and second.manifest["documents_uploaded"] == 0
    backup.create(dest)
    out = backup.prune(dest, keep=1)
    assert len(out["deleted_snapshots"]) == 2 and len(backup.list_snapshots(dest)) == 1
    assert backup.verify(dest)["ok"]


def test_tampering_and_wrong_key_are_detected(populated, key, tmp_path, monkeypatch):
    dest = backup.LocalDestination(tmp_path / "bk")
    snap = backup.create(dest)
    p = tmp_path / "bk" / "snapshots" / snap.id / "db.jsonl.gz.enc"
    data = bytearray(p.read_bytes())
    data[100] ^= 0xFF
    p.write_bytes(bytes(data))
    with pytest.raises(backup.BackupError, match="decrypt"):
        backup.verify(dest)
    monkeypatch.setattr(backup.settings, "BACKUP_ENCRYPTION_KEY", backup.Fernet.generate_key().decode())
    with pytest.raises(backup.BackupError, match="decrypt"):
        backup.verify(dest, snapshot=snap.id)


def test_missing_key_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(backup.settings, "BACKUP_ENCRYPTION_KEY", "")
    with pytest.raises(backup.BackupError, match="keygen"):
        backup.create(backup.LocalDestination(tmp_path))


def test_cli(populated, key, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(backup.settings, "BACKUP_LOCAL_PATH", str(tmp_path / "cli"))
    assert backup.main(["create", "--keep", "3"]) == 0
    assert '"documents": 2' in capsys.readouterr().out
    assert backup.main(["verify", "--deep"]) == 0
    assert backup.main(["restore", "--snapshot", "latest"]) == 1  # requires --yes
