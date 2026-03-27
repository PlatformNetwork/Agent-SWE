import pytest

import audformat
import audformat.testing

import audb


DB_NAME = "test_load_media_missing"


@pytest.fixture(scope="module", autouse=True)
def db(tmpdir_factory, persistent_repository):
    """Publish a database with known media files."""
    version = "1.0.0"
    db_root = tmpdir_factory.mktemp(version)

    database = audformat.testing.create_db(minimal=True)
    database.name = DB_NAME
    audformat.testing.add_table(
        database,
        "items",
        audformat.define.IndexType.FILEWISE,
        num_files=2,
    )
    database.save(db_root)
    audformat.testing.create_audio_files(database)

    audb.publish(
        db_root,
        version,
        persistent_repository,
        verbose=False,
    )



def test_load_media_error_sorted_missing():
    """Missing media error should report sorted missing file."""
    missing = ["audio/100.wav", "audio/005.wav"]
    with pytest.raises(ValueError) as excinfo:
        audb.load_media(DB_NAME, missing, version="1.0.0", verbose=False)

    message = str(excinfo.value)
    assert "audio/005.wav" in message
    assert "audio/100.wav" not in message
