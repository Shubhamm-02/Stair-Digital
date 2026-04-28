# Test Queries

These queries are used to evaluate the bot against the assignment's evaluation criteria: accuracy, robustness against hallucination, refusal quality, and grounding.

> **Note:** The specific queries below assume `sample.pdf` is a typical informational/technical document. Replace the *italicized placeholders* with details actually present in the PDF you supply. For each valid query the answer should cite the page number(s) inline; for each invalid query the bot must respond verbatim with:
>
> `This question is outside the scope of the provided PDF.`

---

## 5 Valid (in-scope) queries

### V1. Direct fact lookup
**Query:** What is the *title / main topic* of the document?
**Expected:** A one-line answer that matches the title page or abstract, with a `(Page 1)` citation.

### V2. Definition / terminology
**Query:** How does the document define *<a key term that appears in the PDF>*?
**Expected:** A definition quoted or paraphrased from the PDF, citing the page where the term is introduced, e.g. `(Page 3)`.

### V3. Specific numeric / factual detail
**Query:** What *<specific number, date, percentage, or named entity>* does the document mention regarding *<topic>*?
**Expected:** The exact figure or name from the PDF with a page citation. The bot must not round or approximate.

### V4. Multi-page synthesis
**Query:** Summarize what the document says about *<a theme that spans multiple sections>*.
**Expected:** A short synthesis grounded only in the PDF, with citations to **every** page used, e.g. `(Pages 4, 7, 12)`.

### V5. Section / structure question
**Query:** What topics are covered in the *<named section, e.g. "Methodology" / "Conclusion">* section?
**Expected:** A bulleted or one-paragraph list reflecting the actual contents of that section, citing its page(s).

---

## 3 Invalid (out-of-scope) queries

These should each return **exactly**: `This question is outside the scope of the provided PDF.`

### I1. Unrelated general-knowledge question
**Query:** Who won the FIFA World Cup in 2022?
**Expected:** `This question is outside the scope of the provided PDF.`

### I2. Personal / opinion question the PDF cannot answer
**Query:** What's a good restaurant for dinner in Bangalore tonight?
**Expected:** `This question is outside the scope of the provided PDF.`

### I3. Adjacent-but-not-present detail
**Query:** What does the document say about *<a plausible-sounding topic that is NOT actually in the PDF>*?
**Expected:** `This question is outside the scope of the provided PDF.` — this specifically tests that the bot does not hallucinate when a question *sounds* on-topic but the answer isn't in the PDF.

---

## Evaluation checklist

For each run, confirm:

- [ ] V1–V5 all answered using PDF content only.
- [ ] V1–V5 each include at least one `(Page N)` citation matching the actual location of the fact.
- [ ] I1–I3 each respond with the exact refusal string above (no paraphrase, no extra text).
- [ ] No answer references information that does not appear in the PDF.
