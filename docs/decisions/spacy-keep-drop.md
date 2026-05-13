# Decision Record: spaCy Preprocessing -- Keep / Drop

**Status:** Decided -- locked. **DROP** spaCy from the optimus v2 retrieval query path. v2 GA gate decision; revisable post-GA via standard decision-record revision if dogfood-eval surfaces contradictory evidence.
**Owner:** Dustin (in-place call 2026-05-13). Research review delegated to a same-session subagent and synthesized into the verdict + sources below.

## Why this record exists

`docs/decomp/pre-M1-spikes.md` originally framed the spaCy keep/drop call as the verdict of spike-1 hypothesis H4 -- an empirical Recall@10 / nDCG@10 measurement of "spaCy preprocessing on vs off" against the spike-1 task corpus.

That framing has two structural problems the chat-report sibling project surfaced when spike-2 wrapped:

1. **Corpus-availability mismatch.** H4 needs labeled relevance to compute Recall@10 / nDCG@10. The graded 50+ query corpus is owned by `docs/decisions/eval-corpus-methodology.md` and is **deliberately deferred to Phase 1.0 prep** (after spike-1) -- to avoid contamination of the corpus by the implementer who would also be running spike-1. So H4-as-empirical-measurement either needs (a) a small shadow corpus authored just for the spike (defeating the contamination guard), (b) reframing as a non-graded comparison (weaker rigor), or (c) a charter-level revisit.
2. **The empirical test is unnecessary** when the literature already provides a strong, mechanism-grounded answer for the specific pipeline shape v2 has locked in (Nomic CodeRankEmbed dense retrieval + ColBERTv2 late-interaction reranker via RAGatouille). Spinning our own empirical case is "salvage by nostalgia, not by evidence" inverted -- we'd be measuring something the literature has already measured at much greater rigor than a 1-2 session spike could match.

This record retires H4 from spike-1 and lands the spaCy verdict here, sourced from the literature.

## Locked design call

### 1. Verdict: DROP spaCy from the retrieval query path

The query path is:

```
user query (natural language)
  -> [REMOVED: spaCy preprocessing]
  -> Nomic CodeRankEmbed (with prescribed task-instruction prefix)
  -> top-100 dense candidates
  -> ColBERTv2 reranker via RAGatouille
  -> top-5 returned to agent
```

**No spaCy in the production retrieval pipeline.** The only required query transformation is the **Nomic CodeRankEmbed task-instruction prefix** (`"Represent this query for searching relevant code"` per the model card). That is not spaCy; that is a fixed string concatenation and lives wherever the embedder is invoked.

Confidence: **HIGH**. The mechanism is clean, the model card is unambiguous, the closest direct ablation in the code-retrieval literature shows ~50% relative MRR loss from the kind of normalization spaCy performs, and the general transformer-IR literature agrees that classic preprocessing is at best neutral and often harmful for modern dense retrievers.

### 2. What "drop" means operationally

- `src/optimus/spacy_pipeline.py` is **NOT BUILT** under M1 Phase 1.1. It is dropped from the module list before the module list is authored in the M1.0 Architecture Spike (per the propagation in `docs/decomp/M1-tasks.md` Phase 1.1 below).
- The v1 spaCy preprocessing code is **not salvaged**. CHARTER Decision 5's "salvage-driven, not nostalgia-driven" principle applies: the only reason to bring v1's spaCy work forward would be sentiment, and the literature says sentiment is wrong here.
- Optimus v2 does NOT depend on `spacy` (or `spacy[cpu]`, or any spaCy model artifact like `en_core_web_sm`) at runtime, build time, or install time. The dependency is cut at the requirements/manifest level.
- `docs/glossary.md`'s spaCy entry is updated to reflect the dropped status (with a back-reference to this record); it is not deleted, because the term remains useful for context when reading older docs.
- The illustrative `server.py` in `docs/decisions/secure-singleton-mcp-baseline.md` does not need to change -- it already does not include spaCy in the retrieval pipeline.

### 3. What "drop" does NOT preclude

- **A future query-rewriting / query-expansion layer** is a separate decision (and a separate record). The 2025-2026 LLM-driven query-expansion literature (LameR, CHIQ, ExpandR) shows real gains in some retrieval settings and real losses in others ("Not All Queries Need Rewriting" -- arXiv 2603.13301 reports nDCG@10 dropped 9% on FiQA from rewriting). If optimus v2.x considers query expansion, it gets its own decision record and its own dogfood-eval gate. It does NOT come in through the back door as "we kept spaCy after all."
- **A future domain-tuned SE-stopword pass** is also separate. The SE-stopwords paper shows hand-curated lists yield ~1pp gains on specific SE tools where generic lists hurt. If optimus v2.x ever wants this, it gets its own record. spaCy ships generic lists -- that's the version this record drops. Domain-tuned is a different intervention.
- **Document-side preprocessing** during indexing is a different problem. v2's document-side strategy (chunking, AST-awareness, garp-driven candidates) is owned by M1 Phase 1.3 + the secure-singleton-mcp-baseline decision record. This record is about the **query path only**.

### 4. Roadblock-revision rule

This decision is revisable post-GA via standard decision-record revision (PR + sign-off + cross-doc propagation) under the same "evidence-backed roadblock" bar as `docs/decisions/secure-singleton-mcp-baseline.md`:

- "Evidence-backed" means **measurement against a real corpus** -- e.g., M6 dogfood-eval surfacing a clear retrieval-quality regression that maps to query-side preprocessing absence, or the M1.3 graded retrieval-quality corpus showing a Recall@10 / nDCG@10 lift from a spaCy-equivalent preprocessing pass.
- "Soft preference shift" -- "what if we just added spaCy back to see" -- is **not** sufficient. The literature is strong enough that the burden of proof is on putting spaCy back, not on keeping it out.
- The cheap conditional revision is "drop unless query length < N tokens" if very short queries underperform in practice. The literature gives no current reason to ship that conditional on day one.

## Research review -- evidence behind the verdict

### Q1: Has the field moved away from explicit query preprocessing for dense retrieval (general / non-code)?

**Yes.** The 2024 EMNLP Findings paper *Revisiting Query Variation Robustness of Transformer-based Information Retrieval Systems* finds classic preprocessing such as stopword removal and lemmatization "generally hurt rather than help dense retriever performance" because dense retrievers "learn to handle linguistic variations implicitly through their training process" and "actually benefit from surface-form information." The 2024 survey *Is text preprocessing still worth the time? A comparative survey* reaches the same direction for transformer pipelines: stopword removal, stemming, and lemmatization "do not significantly improve the performance of classification models, and results indicate that the use of stemming tends to decrease performance." Note: the survey distinguishes rule-based preprocessing (spaCy's territory -- shown to hurt or be neutral) from context-aware LLM-driven preprocessing (sometimes helps). spaCy is the former.

### Q2: Is there code-retrieval-specific evidence?

**Yes, and it is decisive in the direction of DROP.** The CodeSearchNet line of work shows that identifier-normalizing preprocessing destroys code-retrieval quality: normalizing function and variable names "significantly reduces Mean Reciprocal Rank (MRR) scores, dropping from 0.809 to 0.419 for RoBERTa and 0.869 to 0.507 for CodeBERT." That is a ~50% relative MRR loss from the kind of normalization spaCy performs by default. The mechanism is straightforward: a code query like `"find auth_middleware caller"` gets mangled because `auth_middleware` is the highest-signal token in the query and spaCy's English-trained lemmatizer was never built to preserve it.

The dedicated SE-stopwords paper *Stop Words for Processing Software Engineering Documents: Do they Matter?* concludes that **generic stopword lists hurt SE tasks** and only carefully hand-tuned domain-specific lists help marginally (e.g., +0.91pp Top-10 accuracy on RACK with a domain TF-IDF list, while the generic 1,298-word list dropped accuracy to 80.57%). Their explicit warning: "blind use of a stop list may have a negative impact on the results of the algorithm." spaCy's default English stopword list is exactly the generic-list shape this paper warns against.

### Q3: What does the Nomic CodeRankEmbed model card say about query preprocessing?

The model card prescribes **exactly one** input transformation:

> "the query prompt **must** include the following task instruction prefix: 'Represent this query for searching relevant code'"

The example in the card embeds raw natural-language queries (e.g., `"Calculate the n-th factorial"`) with no lemmatization, lowercasing, or stopword stripping. The same pattern holds for the parent `nomic-embed-text-v1.5` family, which mandates a `search_query:` / `search_document:` prefix and is otherwise silent on preprocessing. **Model-card silence on a transformation when the card teaches another transformation by example is the implicit contract: feed it raw text after the prefix.** Nomic actively maintains these cards; silence is signal, not oversight.

### Q4: Does ColBERTv2 / late-interaction reranking care about query preprocessing?

**No -- and stripping upstream actively hurts it.** ColBERTv2 does its own input preparation at the model layer. Per the ColBERT and ColBERTv2 papers, "a textual query is tokenized into BERT-based WordPiece tokens, with a special `[Q]` token prepended ... If the query has fewer than a pre-defined number of tokens, it is padded with BERT's special `[mask]` tokens up to length Nq." The MaxSim late-interaction operator then attends over the full token matrix including those mask-padded slots, which act as **learned query-expansion positions**. Stripping stopwords upstream **shortens the query token sequence**, which means more `[mask]` slots ColBERT must hallucinate context into -- strictly worse signal. RAGatouille's documented usage pattern simply passes the raw query string into `RAG.search(query=...)` with no preprocessing layer in any official example.

### Q5: Counter-evidence (honest accounting)

The strongest counter-cases do not actually counter the verdict:

- **LLM-driven query expansion** (LameR, CHIQ, ExpandR 2025) can lift dense retrieval -- but this is *adding* signal, not stripping it, and "Not All Queries Need Rewriting" (arXiv 2603.13301) shows the effect is "strongly domain-dependent": it "degrades nDCG@10 by 9.0% on FiQA" while helping on TREC-COVID. Code is a domain with specific vocabulary; aggressive query-side rewriting in such domains is a known footgun. This is an adjacent intervention -- if optimus v2.x ever adds query expansion it gets its own decision record (per section 3 above).
- **Domain-tuned SE stopwords** can yield ~1pp gains on specific SE tools -- but require hand-curation per task and explicitly outperform generic lists. spaCy ships generic lists; the SE-stopwords paper warns against exactly this.
- **Context-aware LLM preprocessing** (e.g., Gemma-2 +6.16% on AG News classification) -- but this is an LLM doing context-sensitive normalization, not a rule-based pipeline, and the gain is on classification, not retrieval. spaCy is rule-based.

None of this rescues a generic spaCy lemmatize+stopword pass on code queries.

## Sources

1. *Revisiting Query Variation Robustness of Transformer-based Information Retrieval Systems* (EMNLP Findings 2024) -- https://aclanthology.org/2024.findings-emnlp.248.pdf
2. *Is text preprocessing still worth the time? A comparative survey* (ScienceDirect 2024) -- https://www.sciencedirect.com/science/article/pii/S0306437923001783
3. *Not All Queries Need Rewriting: When Prompt-Only LLM Refinement Helps and Hurts Dense Retrieval* (arXiv 2603.13301) -- https://arxiv.org/abs/2603.13301
4. *CodeSearchNet Challenge: Evaluating the State of Semantic Code Search* -- https://arxiv.org/abs/1909.09436
5. *CoIR: A Comprehensive Benchmark for Code Information Retrieval Models* -- https://arxiv.org/html/2407.02883v1
6. *Stop Words for Processing Software Engineering Documents: Do they Matter?* -- https://arxiv.org/html/2303.10439v2
7. Nomic CodeRankEmbed model card -- https://huggingface.co/nomic-ai/CodeRankEmbed
8. Nomic Embed Text v1.5 model card -- https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
9. *ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT* (SIGIR 2020) -- https://people.eecs.berkeley.edu/~matei/papers/2020/sigir_colbert.pdf
10. *ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction* (NAACL 2022) -- https://aclanthology.org/2022.naacl-main.272/
11. RAGatouille (AnswerDotAI) usage docs -- https://github.com/AnswerDotAI/RAGatouille

## Open evidence gaps (honest)

- **No published ablation that runs spaCy specifically against CodeRankEmbed -> ColBERTv2.** This verdict is built from (a) the model card's prescribed contract, (b) general transformer-IR preprocessing literature, (c) CodeSearchNet's identifier-normalization ablation as the closest proxy, and (d) ColBERT's documented internal tokenization. No one has published "spaCy vs raw, CodeRankEmbed pipeline." This is a literature gap, not a contradiction.
- **No direct study isolating query-side vs document-side preprocessing for code retrievers.** Most code-retrieval ablations vary the *document* side (identifier splitting, AST normalization). Query-side preprocessing studies are rarer and almost always report neutral-to-negative results.
- **Domain-tuned SE stopword lists could in principle help marginally** per the SE-stopwords paper, but constructing one validated for an agent-RAG use case is its own research project. Out of scope here.

These gaps are why this record's revision bar is "evidence-backed roadblock" and not "this is final forever." If M6 dogfood-eval or the M1.3 graded-corpus baseline surfaces contradictory evidence, this record gets revisited via standard PR + sign-off.

## Consumers (cross-reference)

- `CHARTER.md` Founding Decision 5 ("salvage-driven, not nostalgia-driven") -- this record is the canonical application of that principle to spaCy. Salvage by evidence; v1's spaCy work does not come forward.
- `docs/decomp/pre-M1-spikes.md` -- spike-1 H4 is **retired** by this record. spike-1 hypothesis list reduces to H1 + H2 + H3. Gate logic loses the H4 branch.
- `docs/decomp/M1-tasks.md` Phase 1.1 -- `spacy_pipeline.py` is **NOT BUILT** under Phase 1.1. The conditional gating language ("gated on spike-1 H4 evidence") is replaced with "DROPPED per `docs/decisions/spacy-keep-drop.md`."
- `docs/decisions/secure-singleton-mcp-baseline.md` -- the locked retrieval stack (Nomic CodeRankEmbed + ColBERTv2 via RAGatouille) is the pipeline this record optimizes the query path for. No content change there; this record is downstream.
- `docs/decisions/eval-corpus-methodology.md` -- relates; that record owns the M1.3 graded corpus that, post-GA, may produce evidence sufficient to revisit this verdict. Not a current obligation.
- `docs/glossary.md` -- spaCy entry updated to reflect DROPPED status with back-ref to this record.
- `docs/spikes/spike-1-prep-brief.md` -- consumes this record's verdict (spike-1 prep no longer needs to plan an H4 measurement).

## Status note

Locked at refactor time 2026-05-13. Verdict is DROP, confidence HIGH, sourced from:

- General transformer-IR preprocessing literature (EMNLP 2024 + ScienceDirect 2024 survey).
- Code-retrieval-specific identifier-normalization ablation (CodeSearchNet on RoBERTa + CodeBERT, ~50% MRR loss).
- Nomic CodeRankEmbed model-card prescribed contract (raw query + fixed task prefix; silence on further preprocessing).
- ColBERTv2 internal tokenization mechanism (`[Q]` + WordPiece + `[mask]` padding -- upstream stripping mechanically harmful).

The decision retires spike-1 H4 and re-gates M1 Phase 1.1's `spacy_pipeline.py` to "not built." Revision bar: evidence-backed roadblock surfaced by M6 dogfood-eval or the M1.3 graded corpus.
