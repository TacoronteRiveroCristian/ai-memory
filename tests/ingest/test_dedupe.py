from ingest_dedupe import normalize_for_hash, is_duplicate


def test_normalization_collapses_case_punctuation_whitespace():
    assert normalize_for_hash("MIGRACION A pgvector") == normalize_for_hash("migracion a   pgvector!!!")


def test_normalization_strips_accents():
    assert normalize_for_hash("Migración a pgvector") == normalize_for_hash("migracion a pgvector")


def test_different_content_different_hash():
    assert normalize_for_hash("Decision about caching") != normalize_for_hash("Decision about routing")


def test_truncation_at_200_chars_makes_long_texts_collide_if_prefix_matches():
    prefix = "a" * 200
    assert normalize_for_hash(prefix + "suffix1") == normalize_for_hash(prefix + "suffix2")


def test_is_duplicate_detects_match_in_recent_list():
    recent = [
        {"title": "Decision: use pgvector", "content": "We chose pgvector over pinecone for cost"},
        {"title": "Error: oauth flow", "content": "The login failed because..."},
    ]
    action = {"title": "decision use pgvector", "content": "We chose pgvector over pinecone for cost"}
    assert is_duplicate(action, recent) is True


def test_is_duplicate_returns_false_when_no_match():
    recent = [{"title": "Something else", "content": "totally different content"}]
    action = {"title": "New insight", "content": "novel observation here"}
    assert is_duplicate(action, recent) is False


def test_empty_text_hashes_safely():
    assert normalize_for_hash("") == normalize_for_hash("")
    assert len(normalize_for_hash("")) == 16
