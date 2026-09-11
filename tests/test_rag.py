import tempfile
import unittest
from pathlib import Path

from rag.chunker import Chunk, chunk
from rag.embeddings import HashingEmbedder, cosine, get_embedder
from rag.extractors import Block, ExtractionError, extract
from rag.ingest import clean_title, guess_kind, guess_week, ingest_file
from rag.normalize import clean, repair
from rag.retriever import Filters, Retriever, build_fts_query
from rag.store import Store, pack_vector, unpack_vector


class NormalizeTests(unittest.TestCase):
    def test_repairs_ligatures_inside_words(self):
        self.assertEqual(clean("an e\xa2 cient outcome"), "an efficient outcome")
        self.assertEqual(clean("A \x85 rm has \x85 xed costs"), "A firm has fixed costs")
        self.assertEqual(clean("the di⁄ erence in e⁄ ort"), "the difference in effort")

    def test_keeps_word_boundary_when_ligature_ends_a_word(self):
        # "payoff of" must not collapse into "payoffof".
        self.assertEqual(clean("payo⁄ of staying"), "payoff of staying")
        self.assertEqual(clean("sta⁄ and the \x85 rms"), "staff and the firms")

    def test_collapses_doubled_math_glyphs(self):
        # PowerPoint equation export emits every math glyph twice.
        self.assertEqual(clean("\U0001d449\U0001d449 ln \U0001d43a\U0001d43a"), "V ln G")

    def test_normalises_smart_punctuation_and_arrows(self):
        self.assertEqual(clean("Anne\x92 s payoff"), "Anne’s payoff")
        self.assertIn("\u2192", clean("exploited \uf0e0 Adam Smith"))

    def test_is_idempotent_on_clean_text(self):
        text = "The Pigouvian tax equals marginal external damage."
        self.assertEqual(clean(text), text)
        self.assertEqual(clean(clean(text)), clean(text))

    def test_handles_empty_input(self):
        self.assertEqual(repair(""), "")
        self.assertEqual(clean(""), "")


class ChunkerTests(unittest.TestCase):
    def test_starts_a_new_chunk_at_each_exercise(self):
        blocks = [Block(text="Exercises\n\n" + "\n\n".join(
            f"{i}.1 A firm produces Q units of output at cost C." for i in range(1, 4)
        ), page=1, label="page")]
        chunks = chunk(blocks)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertTrue(any("2.1" in c.text for c in chunks))

    def test_labels_chunks_with_exercise_numbers(self):
        blocks = [Block(text="Intro text here.\n\nExercise 2.3 A firm on a riverbank.",
                        page=4, label="page")]
        sections = [c.section for c in chunk(blocks)]
        self.assertIn("Exercise 2.3", sections)

    def test_records_page_range(self):
        blocks = [Block(text="short one", page=3, label="slide"),
                  Block(text="short two", page=4, label="slide")]
        chunks = chunk(blocks)
        self.assertEqual(chunks[0].page_start, 3)
        self.assertEqual(chunks[-1].page_end, 4)

    def test_splits_oversized_blocks(self):
        blocks = [Block(text="Sentence about welfare. " * 600, page=1)]
        chunks = chunk(blocks)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.text) <= 2600 for c in chunks))

    def test_empty_input_yields_no_chunks(self):
        self.assertEqual(chunk([]), [])


class EmbeddingTests(unittest.TestCase):
    def test_scores_related_text_above_unrelated(self):
        e = HashingEmbedder()
        a, b, c = e.embed([
            "Pigouvian tax on a negative externality",
            "Pigovian taxes and externalities",
            "the worker exerts effort and the firm sets a bonus",
        ])
        self.assertGreater(cosine(a, b), cosine(a, c))

    def test_vectors_are_unit_length(self):
        (vec,) = HashingEmbedder().embed(["marginal social cost"])
        self.assertAlmostEqual(sum(v * v for v in vec) ** 0.5, 1.0, places=5)

    def test_weights_are_never_negative(self):
        # log() of a fractional n-gram weight would go negative and cancel overlap.
        (vec,) = HashingEmbedder().embed(["Coase theorem bargaining"])
        self.assertTrue(all(v >= 0 for v in vec))

    def test_backend_can_be_disabled(self):
        self.assertIsNone(get_embedder("none"))

    def test_unknown_backend_raises(self):
        with self.assertRaises(ValueError):
            get_embedder("banana")

    def test_vector_blob_roundtrip(self):
        values = [0.5, -0.25, 0.125]
        restored = unpack_vector(pack_vector(values))
        for original, got in zip(values, restored):
            self.assertAlmostEqual(original, got, places=6)


class FTSQueryTests(unittest.TestCase):
    def test_drops_stopwords_and_quotes_terms(self):
        query = build_fts_query("What is the Coase theorem?")
        self.assertIn('"coase"', query)
        self.assertIn('"theorem"', query)
        self.assertNotIn('"the"', query)

    def test_survives_punctuation_that_would_break_fts_syntax(self):
        self.assertNotIn("(", build_fts_query('tax "AND" OR (NOT) *'))

    def test_empty_question_gives_empty_query(self):
        self.assertEqual(build_fts_query("   "), "")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "library.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _add(self, doc_key="doc", title="Doc", text="The Coase theorem concerns bargaining."):
        doc_id = self.store.upsert_document(
            doc_key=doc_key, title=title, source_path="/tmp/x.pdf", kind="lecture",
            course="Micro", week="2", tags="", sha256="abc", page_label="slide",
            n_pages=1, added_at="2026-01-01T00:00:00", meta={},
        )
        self.store.add_chunks(doc_id, [Chunk(text=text, page_start=1, page_end=1, section="S")])
        return doc_id

    def test_keyword_search_finds_indexed_text(self):
        self._add()
        hits = self.store.keyword_search('"coase"', 5)
        self.assertEqual(len(hits), 1)

    def test_stemming_matches_word_forms(self):
        self._add(text="Efficient provision requires bargaining between parties.")
        self.assertTrue(self.store.keyword_search('"bargain"', 5))

    def test_malformed_query_returns_no_hits_instead_of_raising(self):
        self._add()
        self.assertEqual(self.store.keyword_search('"unclosed AND (', 5), [])

    def test_reingest_replaces_chunks_rather_than_duplicating(self):
        self._add()
        self._add()
        self.assertEqual(self.store.stats()["chunks"], 1)
        self.assertEqual(self.store.stats()["documents"], 1)

    def test_delete_removes_chunks_and_fts_entries(self):
        self._add()
        self.assertTrue(self.store.delete_document("doc"))
        self.assertEqual(self.store.stats()["chunks"], 0)
        self.assertEqual(self.store.keyword_search('"coase"', 5), [])

    def test_citation_reads_as_a_source_reference(self):
        self._add()
        (hit,) = self.store.hydrate([1]).values()
        self.assertEqual(hit.citation(), "Doc — slide 1 — S")


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.store = Store(self.dir / "library.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _write(self, name, text="Marginal social cost equals marginal private cost plus damage."):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_ingests_a_text_file(self):
        result = ingest_file(self.store, self._write("notes.txt"), copy_source=False)
        self.assertEqual(result.status, "added")
        self.assertEqual(self.store.stats()["documents"], 1)

    def test_unchanged_file_is_skipped_on_reingest(self):
        path = self._write("notes.txt")
        ingest_file(self.store, path, copy_source=False)
        again = ingest_file(self.store, path, copy_source=False)
        self.assertEqual(again.status, "skipped")

    def test_force_reindexes_unchanged_file(self):
        path = self._write("notes.txt")
        ingest_file(self.store, path, copy_source=False)
        forced = ingest_file(self.store, path, copy_source=False, force=True)
        self.assertEqual(forced.status, "updated")

    def test_edited_file_is_reindexed_without_force(self):
        path = self._write("notes.txt")
        ingest_file(self.store, path, copy_source=False)
        path.write_text("Completely different content about Coase.", encoding="utf-8")
        self.assertEqual(ingest_file(self.store, path, copy_source=False).status, "updated")

    def test_missing_file_reports_failure(self):
        result = ingest_file(self.store, self.dir / "nope.pdf", copy_source=False)
        self.assertEqual(result.status, "failed")

    def test_unsupported_type_reports_failure(self):
        result = ingest_file(self.store, self._write("thing.xyz"), copy_source=False)
        self.assertEqual(result.status, "failed")
        self.assertIn("Unsupported", result.detail)

    def test_metadata_is_inferred_from_filename(self):
        self.assertEqual(clean_title("40c0a958-Lecture_2_.pptx"), "Lecture 2")
        self.assertEqual(guess_week("Lecture 2"), "2")
        self.assertEqual(guess_kind("exercises week 2", ""), "exercises")
        self.assertEqual(guess_kind("Lecture 2", "slides about externalities"), "lecture")


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.store = Store(self.dir / "library.db")
        for key, title, week, kind, text in [
            ("l1", "Lecture 1", "1", "lecture",
             "Public goods are non-rival and non-excludable, causing free riding."),
            ("l2", "Lecture 2", "2", "lecture",
             "A Pigouvian tax equal to marginal external damage restores efficiency."),
            ("e2", "Exercises 2", "2", "exercises",
             "Exercise 2.3 A firm on a riverbank pollutes; find the Pigouvian tax."),
        ]:
            path = self.dir / f"{key}.txt"
            path.write_text(text, encoding="utf-8")
            ingest_file(self.store, path, doc_key=key, week=week, kind=kind, copy_source=False)
        # ingest_file derives the title from the filename; set the readable one.
        for key, title in [("l1", "Lecture 1"), ("l2", "Lecture 2"), ("e2", "Exercises 2")]:
            self.store.conn.execute("UPDATE documents SET title=? WHERE doc_key=?", (title, key))
        self.store.conn.commit()
        self.retriever = Retriever(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_finds_the_relevant_document(self):
        hits = self.retriever.search("Pigouvian tax", k=3)
        self.assertTrue(hits)
        self.assertIn("Pigouvian", hits[0].text)

    def test_filters_restrict_results(self):
        hits = self.retriever.search("Pigouvian tax", k=5, filters=Filters(kind="exercises"))
        self.assertTrue(hits)
        self.assertTrue(all(h.kind == "exercises" for h in hits))

    def test_week_filter_excludes_other_weeks(self):
        hits = self.retriever.search("public goods free riding", k=5, filters=Filters(week="2"))
        self.assertTrue(all(h.week == "2" for h in hits))

    def test_blank_question_returns_nothing(self):
        self.assertEqual(self.retriever.search("   "), [])

    def test_nonsense_query_does_not_crash(self):
        self.assertIsInstance(self.retriever.search("zzzzqqq"), list)

    def test_returns_nothing_for_a_topic_the_library_does_not_cover(self):
        self.assertEqual(self.retriever.search("quantum chromodynamics"), [])

    def test_works_without_an_embedding_backend(self):
        keyword_only = Retriever(self.store, backend="none")
        self.assertTrue(keyword_only.search("Pigouvian tax", k=3))


class ExtractorTests(unittest.TestCase):
    def test_rejects_unknown_extension(self):
        with self.assertRaises(ExtractionError):
            extract(Path("/tmp/whatever.xyz"))


class CaptionTests(unittest.TestCase):
    """Lecture recordings arrive as WebVTT/SubRip caption files."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name, body):
        path = self.dir / name
        path.write_text(body, encoding="utf-8")
        return path

    VTT = """WEBVTT

NOTE auto-generated

1
00:00:02.100 --> 00:00:06.400
Today we continue with externalities

2
00:01:45.000 --> 00:01:51.200
<v Instructor>The key condition is that property rights are well defined

3
00:01:51.200 --> 00:01:58.000
and transaction costs are low enough for bargaining.

4
00:03:12.000 --> 00:03:19.500
and transaction costs are low enough for bargaining.
"""

    SRT = """1
00:00:01,000 --> 00:00:05,000
Public goods are non-rival and non-excludable.

2
00:01:40,000 --> 00:01:47,500
That gives us the Samuelson condition.
"""

    def test_parses_webvtt_into_timestamped_blocks(self):
        blocks = extract(self._write("lec.vtt", self.VTT))
        self.assertEqual([b.section for b in blocks], ["0:02", "1:45"])

    def test_parses_subrip(self):
        blocks = extract(self._write("lec.srt", self.SRT))
        self.assertTrue(blocks)
        self.assertIn("Samuelson", " ".join(b.text for b in blocks))

    def test_cue_starting_a_window_is_not_absorbed_into_the_previous_one(self):
        # The 1:45 block must begin with what was said at 1:45.
        blocks = extract(self._write("lec.vtt", self.VTT))
        second = next(b for b in blocks if b.section == "1:45")
        self.assertTrue(second.text.startswith("The key condition"))

    def test_strips_caption_markup_and_headers(self):
        text = " ".join(b.text for b in extract(self._write("lec.vtt", self.VTT)))
        self.assertNotIn("<v", text)
        self.assertNotIn("WEBVTT", text)
        self.assertNotIn("NOTE", text)

    def test_drops_repeated_rolling_caption_lines(self):
        text = " ".join(b.text for b in extract(self._write("lec.vtt", self.VTT)))
        self.assertEqual(text.count("transaction costs are low enough"), 1)

    def test_timestamp_label_survives_chunking(self):
        sections = [c.section for c in chunk(extract(self._write("lec.vtt", self.VTT)))]
        self.assertIn("0:02", sections)

    def test_hours_appear_in_long_recordings(self):
        body = "WEBVTT\n\n1\n01:05:00.000 --> 01:05:04.000\nAn hour into the lecture.\n"
        self.assertEqual(extract(self._write("long.vtt", body))[0].section, "1:05:00")

    def test_file_without_cues_is_rejected(self):
        with self.assertRaises(ExtractionError):
            extract(self._write("empty.vtt", "WEBVTT\n\njust prose, no cues\n"))

    def test_transcripts_are_labelled_as_their_own_kind(self):
        self.assertEqual(guess_kind("Lecture 3 recording", "", ".vtt"), "transcript")


if __name__ == "__main__":
    unittest.main()
