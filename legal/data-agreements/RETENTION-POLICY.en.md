> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Data Retention and Deletion Policy

Version [0.1] · 2026-09-26 · Owner: Marius Carlsson · [NeuroForge Bio AS] (ASSUMPTION: Norwegian AS, **not yet incorporated**)
Prevailing language: Norwegian [advokat choice] · Norwegian version: RETENTION-POLICY.no.md
Status: **policy for designed/planned systems**. No system described here is live.

## 1. Principles
1. **Storage limitation.** Personal data is "kept in a form which permits identification … for no longer than is necessary". Longer storage is allowed only where it "will be processed **solely** for … scientific … research purposes" with Art. 89(1) safeguards (GDPR Art. 5(1)(e)).
2. **Two roles, two rule sets.**
   - For **customer data**, NeuroForge is a **processor**. The customer sets retention, and NeuroForge deletes on instruction and at contract end (DPA § 11; MSA § 15.2).
   - For **pool data** (consent boxes (ii)–(viii)), NeuroForge is a **controller** and this policy governs.
3. **Pseudonymised data is personal data.** "Personal data which have undergone pseudonymisation … should be considered to be information on an identifiable natural person" (Recital 26). Only data that passes a documented anonymisation test (§ 4) leaves this policy.
4. **Deletion is honest.**
   - Crypto-shredding makes copies unreadable.
   - Models are **retrained**, not "unlearned".
   - Exports already sent outside the platform cannot be recalled by us. They are chased by contract (BLUEPRINT §8.4).

## 2. Retention schedule

| # | Data category | Role | Retention period | End-of-period action | Basis / note |
|---|---|---|---|---|---|
| 1 | **Raw neural signals and recordings: customer tenants** | Processor | As configured by the customer. At contract end: [30]-day retrieval period, deletion from production within [30] further days, backups unreadable via key destruction and expired within [35] days (ESTIMATE) | Delete + crypto-shred tenant and subject keys; certificate on request | DPA § 11; MSA § 15.2 |
| 2 | **Raw neural signals: NeuroForge pool** (box ii) | Controller | Until the subject withdraws (ii), or at most **[10] years after the subject's last session** [owner/REK to set]. Reviewed every [2] years for continued research need | Delete + destroy the pool subject key | Art. 5(1)(e): research-only. Kept only while a research scope ((ii)/(iv)) is live |
| 3 | **Derived features, embeddings, annotations** | Same as their source | **Never longer than their source** (inheritance rule, BLUEPRINT §8.2) | Deleted by the same DeletionJob | Linkable features are personal data (Recital 26) |
| 4 | **Aggregates mixing several subjects** (group statistics) | Same as source | While the source is kept. On a subject's withdrawal: marked stale and **re-run without the subject**, or tombstoned (tenant/pool policy) | Re-run / tombstone | BLUEPRINT §8.4 |
| 5 | **Anonymised data** (passed the § 4 test) | Outside GDPR | No limit | Keep the test report with it | Recital 26. Neural data is rarely anonymisable (§ 4) |
| 6 | **Consent-ledger records** (grants, withdrawals, form version/hash, evidence reference) | Controller (pool) / processor (tenants) | While any processing under the consent continues, **plus [5] years** [advokat: limitation period; foreldelsesloven **UNVERIFIED**]. After a withdrawal only a minimal record is kept (pseudonym, scope, time, deletion-certificate hash) | Delete, or reduce to minimal proof | Art. 7(1): the controller "shall be able to demonstrate that the data subject has consented". Art. 17(3)(e) legal claims |
| 7 | **Audit logs** (WORM, hash-chained) | Controller of its own logs | **[3] years** default; **[≥ 6] years** for tenants under a BAA (MSA Schedule 2 S6) [HIPAA documentation period **UNVERIFIED**] | Expire by object-lock lifecycle | Security (Art. 32); accountability. **No signal data or direct identifiers in logs** |
| 8 | **Application / operational logs** | Controller | [90] days (ESTIMATE) | Delete | Log fields allow-listed; no signal data (BLUEPRINT §8.1) |
| 9 | **Backups** | Same as source | Rotation ≤ [35] days (ESTIMATE). A withdrawn subject's data in backups becomes **unreadable immediately** once their key is destroyed. No restore of that subject's data is possible | Crypto-shredding; natural expiry | BLUEPRINT §8.4; DPA § 11.1 |
| 10 | **Trained models** (see § 5) | Controller (pool) / customer (tenant) | While in use and while every training subject's scope ((iii) or (vi)) remains live | `retrain_required` → retrain → retire the old version within [90] days | No certified unlearning |
| 11 | **Copies held by licensees and partners** | Recipients (their own controllers) | Deleted **within [30] days** of a Withdrawal Notice, and at licence/DSA end | Deletion certificate to NeuroForge | Art. 19 notice to recipients; data-licence § 6; DSA § 5 |
| 12 | **Contact details for recontact** (box viii) | Controller | Until withdrawal, or [5] years without contact | Delete | Consent |
| 13 | **Contract and billing records** | Controller (own records) | **Bokføringsloven § 13:** annual accounts, specifications, documentation of entries and auditor letters: **5 years after the end of the financial year**. Business contracts, correspondence with material information, shipping documents and price lists: **3 years and 6 months after year end** | Delete | Law requires these to be kept "i Norge". The rules for storage abroad (bokføringsforskriften) are **UNVERIFIED**. Hosting in AWS US conflicts unless an exception applies |
| 14 | **Website data** | Controller | Per privacy policy: request logs [30] days; early-access list until unsubscribe or [24] months | Delete | legal\website\privacy-policy.* |

## 3. Pseudonymised vs anonymised
- **Pseudonymised:** direct identifiers are removed and a code key is kept separately (Art. 4(5)). **Still personal data. All of GDPR applies**, including withdrawal and deletion.
- **Anonymised:** the person is "not or no longer identifiable", judged by "all the means reasonably likely to be used, such as singling out" (Recital 26). Only then does GDPR stop applying.
- **Destroying the pseudonym key alone is not anonymisation.** Neural signals can themselves identify a person (EEG is used as a biometric, doi:10.1155/2021/5229576). Plaintext features left behind may still single someone out. Destroying the **encryption** key (crypto-shredding) is a different thing: it makes the ciphertext unreadable, which is effectively deletion.

## 4. Anonymisation test (before any category moves to row 5)
A documented Recital 26 assessment is required. It must include:
- (a) a singling-out and linkage test, including an EEG biometric matcher run against other recordings of the same people;
- (b) for synthetic data, membership-inference and nearest-record tests;
- (c) attribute-inference checks.

Thresholds are set in the DPIA. The report is kept with the data and re-run when attack methods change materially. If in doubt, the data stays pseudonymised.

## 5. AI models trained on data that is later withdrawn
1. **Record.** The provenance graph records which model versions included which subject pseudonyms.
2. **Flag.** Withdrawal of (ii), (iii) or (vi) marks every affected version `retrain_required` and notifies the model owners by webhook.
3. **Deployment block.** New deployments of flagged versions are blocked (configurable per tenant; **on by default for the pool**). Existing deployments stay in use until the retrained version is available, and for at most [90] days.
4. **Retrain.** The model is retrained without the subject. With **SISA sharded training** (opt-in mode), only the affected shard is retrained. SISA "strategically limits the influence of a data point" (arXiv:1912.03817), but it is **not certified unlearning**.
5. **Retire.** Old versions that contained the subject are deleted from the registry within [90] days of the replacement, and licensees must switch versions (model-licence terms).
6. **No promise of certified unlearning.** The guarantee is: "retrained without the subject; here is the provenance proof and deletion certificate".
7. **Models already licensed out:** NeuroForge sends a withdrawal notice and a replacement version. The licensee must stop using the old version within [90] days. We cannot technically recall copies.

## 6. Responsibilities and review
- **Data steward** [role]: runs the DeletionJob, signs certificates, and reviews this policy **yearly**.
- **DPIA:** each pool purpose. The advokat approves the periods in brackets.
- **Exceptions:** a legal hold (litigation or authority order) suspends deletion for the data concerned only, is logged, and is reviewed every [3] months.

## Hjemmel / Legal basis
- **GDPR official text** (Publications Office, http://publications.europa.eu/resource/celex/32016R0679, opened 2026-09-26): Recital 26; Art. 5(1)(e); Art. 7(1); Art. 17(3)(e); Art. 33(1); Art. 89(1).
- **GDPR Norwegian text on Lovdata** (opened 2026-09-26):
  - Art. 4(5): https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - Art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - Art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
- **Bokføringsloven § 13:** https://lovdata.no/lov/2004-11-19-73/§13 (opened 2026-09-26). Bokføringsforskriften (storage abroad) **UNVERIFIED**.
- **Not opened, UNVERIFIED:** foreldelsesloven (limitation periods) and the HIPAA documentation retention period.
- **Product facts:**
  - BLUEPRINT.md §8.1 (logging hygiene), §8.2 (inheritance), §8.4 (DeletionJob, crypto-shredding, `retrain_required`, SISA, no certified unlearning, exports not recallable);
  - DPA § 11; MSA § 15.2 and Schedule 2 S6.
- **SISA:** Bourtoule et al., arXiv:1912.03817 (as opened for BLUEPRINT).
