# Evaluator Test Instructions

Follow the steps below to verify grounding, accuracy, citations, and out-of-scope refusal behavior.

## Setup

1. Create `.env` from `.env.example` and add `OPENAI_API_KEY`.
2. Install and start the Streamlit app:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Open the local Streamlit URL.
4. Upload the provided **`sample.pdf`** file.
5. Wait for the success message showing the PDF has been loaded.

## Test Cases

Below are concrete queries specifically tailored to `sample.pdf`.

### Valid Queries

1. **Direct Fact Lookup**
   * **Query:** `What is the main topic of the document?`
   * **Expected:** Should mention Project Nexus as a next-generation distributed caching engine and include `(Page 1)`.

2. **Terminology & Definition**
   * **Query:** `How does the document define a Cache Node?`
   * **Expected:** Should mention a localized memory instance that holds frequently accessed queries and cite `(Page 2)`.

3. **Numeric Fact Retrieval**
   * **Query:** `What percentage does Project Nexus reduce database load by?`
   * **Expected:** Should answer `40%` with `(Page 1)`.

4. **Multi-page Synthesis**
   * **Query:** `Summarize what the document says about Project Nexus, its components, and its deployment strategy.`
   * **Expected:** Should mention content from pages 1, 2, and 3 with citations.

5. **Section Contents**
   * **Query:** `What topics are covered in the Methodology and Deployment section?`
   * **Expected:** Should list node clustering, distributed load balancing, and zero-downtime migrations with `(Page 3)`.

### Invalid Queries

Every invalid query must return exactly:

`This question is outside the scope of the provided PDF.`

1. `Who won the FIFA World Cup in 2022?`
2. `What's a good restaurant for dinner in Bangalore tonight?`
3. `What does the document say about the pricing structure for Project Nexus?`

## Evaluation Checklist

- [ ] Bot only answers using information present in the PDF.
- [ ] Every factual claim includes an inline `(Page N)` citation.
- [ ] Invalid questions return the exact refusal string.
- [ ] Optional multilingual valid questions preserve page citations.
