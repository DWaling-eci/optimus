"""ColBERT-truncation invariant for chunk_file.

This test pins the load-bearing relationship between DEFAULT_CHUNK_SIZE and
ColBERTv2's doc_maxlen. If chunks exceed doc_maxlen, ColBERT rerank silently
truncates and the dense stage ranks information ColBERT never sees -- the
46% truncation defect documented in spike/pre-m1-retrieval/README.md
"PRIORITY 1 next-session" section.

The invariant is empirical (depends on the tokenizer's chars-per-token ratio
for the test corpus shape) but the upper bound here is generous enough to
hold for any reasonable code text. Kotlin code in the live ms-superrepo
sample is ~3.5 chars/token; a 700-char chunk averages ~200 tokens, well
under the 220-token doc_maxlen.

WSL2 venv required (loads the ColBERT tokenizer).
"""

import pytest

pytest.importorskip("transformers")
pytest.importorskip("colbert")

from colbert.infra import ColBERTConfig
from transformers import AutoTokenizer

from indexer import DEFAULT_CHUNK_SIZE, chunk_file


# Margin under doc_maxlen to absorb tokenizer special tokens + worst-case
# chars-per-token variability across languages. ColBERT adds ~3-5 special
# tokens; the corpus might contain CJK or unusual punctuation that tokenizes
# denser than ~3.5 chars/token. 20-token margin is empirically sufficient
# and still leaves headroom over the 1500-char baseline that triggered this
# test.
MARGIN_TOKENS = 20


@pytest.fixture(scope="module")
def colbert_tokenizer():
    return AutoTokenizer.from_pretrained("colbert-ir/colbertv2.0")


@pytest.fixture(scope="module")
def doc_maxlen() -> int:
    return ColBERTConfig().doc_maxlen


def test_default_chunk_fits_colbert_doc_maxlen_for_dense_kotlin(
    colbert_tokenizer, doc_maxlen
):
    """A maximally-dense chunk at DEFAULT_CHUNK_SIZE must tokenize within doc_maxlen.

    Uses real Kotlin code as the worst-case sample because Kotlin is the
    dominant language in the spike's test corpus (583 / 819 files in
    ms-superrepo subset). If this passes for Kotlin, it passes for the
    sparser languages we also index.
    """
    kotlin_dense = (
        "package com.example.service\n"
        "import kotlinx.coroutines.flow.Flow\n"
        "import kotlinx.coroutines.flow.flowOf\n"
        "class OrderService(private val repo: OrderRepository) {\n"
        "    suspend fun findOrders(customerId: Long): Flow<Order> {\n"
        "        return repo.findByCustomerId(customerId)\n"
        "    }\n"
        "}\n"
    ) * 50  # Repeated to guarantee a full-size chunk worth of code

    chunks = list(chunk_file(kotlin_dense))
    assert chunks, "fixture must produce at least one chunk"

    for start, text in chunks:
        if len(text) < DEFAULT_CHUNK_SIZE:
            continue  # Tail chunk; not the invariant under test
        token_ids = colbert_tokenizer(text, add_special_tokens=True)["input_ids"]
        assert len(token_ids) + MARGIN_TOKENS <= doc_maxlen, (
            f"chunk at offset {start}: {len(token_ids)} tokens + "
            f"{MARGIN_TOKENS} margin exceeds ColBERT doc_maxlen={doc_maxlen}. "
            f"DEFAULT_CHUNK_SIZE={DEFAULT_CHUNK_SIZE} is too large; "
            f"ColBERT rerank will silently truncate."
        )
