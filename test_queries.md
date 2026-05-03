# Test Queries

These queries are written for the included `sample.pdf` about Project Nexus. For each valid query, the answer must use only the PDF and include page citations. For each invalid query, the answer must be exactly:

`This question is outside the scope of the provided PDF.`

## Sample PDF Reference

- Page 1: Project Nexus is a next-generation distributed caching engine for cloud infrastructure. Internal benchmarks show a 40% database-load reduction across high-traffic microservices.
- Page 2: A Cache Node is a localized memory instance that holds frequently accessed queries. Cache Nodes synchronize using a gossip protocol for eventual consistency without centralized coordination.
- Page 3: Deployment uses a phased approach with node clustering, distributed load balancing, zero-downtime migrations, blue-green deployment, and Nexus Dashboard monitoring.

## 5 Valid In-Scope Queries

### V1. Direct Fact Lookup
**Query:** What is the main topic of the document?

**Expected behavior:** Mentions Project Nexus and identifies it as a next-generation distributed caching engine. Must cite `(Page 1)`.

### V2. Definition / Terminology
**Query:** How does the document define a Cache Node?

**Expected behavior:** Defines it as a localized memory instance that holds frequently accessed queries. Must cite `(Page 2)`.

### V3. Specific Numeric Detail
**Query:** What percentage does Project Nexus reduce database load by?

**Expected behavior:** Answers `40%`. Must cite `(Page 1)`.

### V4. Multi-Page Synthesis
**Query:** Summarize what the document says about Project Nexus, its components, and its deployment strategy.

**Expected behavior:** Mentions the caching engine from page 1, Cache Nodes or gossip protocol from page 2, and deployment strategy from page 3. Must include citations for all used pages, such as `(Page 1)`, `(Page 2)`, and `(Page 3)`.

### V5. Section / Structure Question
**Query:** What topics are covered in the Methodology and Deployment section?

**Expected behavior:** Lists node clustering, distributed load balancing, and zero-downtime migrations. May also mention blue-green deployment and Nexus Dashboard monitoring. Must cite `(Page 3)`.

## 3 Invalid Out-of-Scope Queries

### I1. Unrelated General-Knowledge Question
**Query:** Who won the FIFA World Cup in 2022?

**Expected:** `This question is outside the scope of the provided PDF.`

### I2. Personal / Opinion Question
**Query:** What's a good restaurant for dinner in Bangalore tonight?

**Expected:** `This question is outside the scope of the provided PDF.`

### I3. Adjacent-But-Not-Present Detail
**Query:** What does the document say about the pricing structure for Project Nexus?

**Expected:** `This question is outside the scope of the provided PDF.`

## Optional Multilingual Checks

### M1. Valid Hindi Query
**Query:** Project Nexus database load kitne percent reduce karta hai?

**Expected behavior:** Answers in Hindi or Hinglish with `40%` and `(Page 1)`.

### M2. Invalid Hindi Query
**Query:** Bharat ka vartaman pradhan mantri kaun hai?

**Expected:** `This question is outside the scope of the provided PDF.`
