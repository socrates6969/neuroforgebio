> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Data Contributor Consent Form

Version [0.2] · [DATE] · Consent document hash: [recorded in the consent ledger] · Prevailing language: [Norwegian for Norwegian participants – advokat choice]

**Ethics approval:** [REK ref. ●] / [IRB ref. ●]. *Do not use this form until the approval exists and its number is filled in.*

**Two separate organisations may use your data. Each is responsible (a "controller") only for its own part:**
- **The study organiser:** [Customer / study organiser name], org.nr. [●], [address], contact [●]. It is responsible for box (i).
- **NeuroForge Bio:** [NeuroForge Bio AS] (ASSUMPTION: Norwegian AS, not yet incorporated), org.nr. [●], [address], contact [privacy@neuroforge.bio], [phone]. It is responsible for boxes (ii)–(viii).

[Data protection officer(s): [name, email] / none appointed – advokat to confirm]

> **Note for the organiser (delete before use).**
> - Boxes (ii)–(viii) create a **new, separate controller role for NeuroForge**. They may only be offered if all of these are true:
>   - (a) the study organiser has signed the **Research Pool Addendum** (MSA § 4.3 written opt-in);
>   - (b) NeuroForge has done a DPIA for the pool (RISK-MEMO § 9);
>   - (c) REK/IRB approval covers the pool, where the research is health research.
> - Otherwise delete boxes (ii)–(viii), and the form covers only the organiser's study.
> - The ledger stores each box as its own scope. Each box can be withdrawn on its own. Scope IDs are in CONSENT-SCOPES.en.md: (i) `study.*`, (ii) `nf.pool` + `nf.internal_rnd`, (iii) `nf.model_training.internal`, (iv) `nf.research.future_neuro`, (v) `nf.share.research_partner`, (vi) `nf.model_training.licensed`, (vii) `nf.data_licence.commercial`, (viii) `nf.recontact`. The customer's side is legal\commercial\research-pool-addendum.en.md.
> - **Adults only (18+).** Under helseforskningsloven § 17, people aged 16–18 can sometimes consent themselves. We still exclude everyone under 18 unless a separate process is approved by REK/IRB.
> - Reading level target: lower secondary school. Test the form with lay readers.
> - Limits of broad consent: see BROAD-CONSENT-ASSESSMENT.md.

---

## Part 1 – The short version (please read this first)

- We ask to **record signals from your nervous system**, for example brain waves (EEG) or muscle signals (EMG), for [the study organiser]'s study.
- **Taking part is voluntary.** You can say no, or stop later, without giving a reason. It does not affect [your treatment / job / studies].
- We remove your name and other details that say who you are. **But brain and nerve signals can be as personal as a fingerprint.** We cannot promise that nobody could ever find out the data is yours.
- **You decide each use separately in Part 3.** All boxes start empty. If you leave a box empty, that use does **not** happen.
- You can **take back any box at any time**, one box or all of them. We will then delete the data used for that purpose. We **cannot** take back copies already shared, or results already published (Part 2, section 7).
- **Nobody sells your data to ordinary consumers, advertisers or data brokers.**

## Part 2 – More detail

### 1. What is collected
- **Signals:** [EEG / EMG / other], about [●] minutes per session, [●] sessions.
- **About the recording:** date, device, settings, and the tasks you did.
- **About you:** age group, [sex], [handedness], [health information you choose to give – only if the study needs it].
- **Contact details** (name, email/phone): kept **apart** from the signals and used only to reach you.
- **Your choices:** which boxes you ticked, the date and the form version. They are stored in a consent ledger, a record that cannot be secretly changed.

### 2. What each box means

| Box | Who is responsible | What it allows | What it does NOT allow |
|---|---|---|---|
| **(i) The study** | Study organiser | Recording and using your data for [study title and question, in 1–2 plain sentences]. NeuroForge only stores and processes it for the organiser, as its supplier. | Any use by NeuroForge for its own purposes |
| **(ii) NeuroForge research pool** | NeuroForge | A **copy** of your de-identified data goes into NeuroForge's research collection. It is used to study brain and nerve signals and to test and improve NeuroForge's analysis software. | Sharing with anyone outside NeuroForge (that needs (v), (vi) or (vii)) |
| **(iii) Training NeuroForge AI models (internal)** | NeuroForge | Using pool data to train computer models (AI) that NeuroForge uses itself | Licensing those models to other companies (that needs (vi)) |
| **(iv) Future brain research by NeuroForge** | NeuroForge | Future research by NeuroForge on **how the nervous system works and on neurological conditions**. Each new project must first get ethics approval where the law requires it. We will tell you about new projects on [web page / by email], and you can say no to any area at any time. | Research outside that area, for example genetics, drugs or anything not about the nervous system. For those we will ask you again. |
| **(v) Sharing with vetted research partners** | NeuroForge | Sharing de-identified data with universities and hospitals that sign a contract. The contract forbids trying to identify you and forbids passing the data on. | Companies that pay (that needs (vi) or (vii)) |
| **(vi) AI models licensed to companies** | NeuroForge | Training AI models on pool data and **licensing the models** to companies that pay a fee. The companies get the model, not your data. | Advertising, data brokers, insurance, jobs, credit, or reading emotions at work or school. These are never allowed. |
| **(vii) Data licensed to companies** | NeuroForge | Sharing de-identified **data** with **companies that pay a licence fee** to use it for research or product development | The same uses as in (vi) are never allowed |
| **(viii) Contact about future studies** | NeuroForge | Asking you about new studies. You can say no each time. | – |

**How the boxes fit together:**
- Boxes **(iii)–(vii)** only work if you also tick **(ii)**, because they use the copy in the pool.
- If you take back (ii), all NeuroForge uses stop. (viii) is the only exception, and only if you keep it.

### 3. Legal basis
Your **explicit consent**, given separately for each box (GDPR Art. 6(1)(a) and Art. 9(2)(a)). For health research, the Norwegian Health Research Act also applies, and an ethics committee must approve the project ([REK]).

### 4. Who gets the data
| Recipient | When |
|---|---|
| The study organiser's named team | Box (i) |
| NeuroForge's IT suppliers (e.g. cloud hosting [AWS, US region at launch; EU region planned]) | Always. They work for us under contract and may not use the data for themselves |
| NeuroForge research staff | Boxes (ii)–(iv) |
| University or hospital researchers [named or vetted] | Box (v) |
| Companies that pay a licence fee | Boxes (vi) and (vii) only |
| Authorities | Only if the law requires it |

Everyone who receives the data signs a contract. The contract forbids them to try to find out who you are, to sell the data on, or to use it for advertising, decisions about your job, insurance or credit, or reading emotions at work or school.

**Data outside Norway / the EU/EEA:** [At launch data is stored in the USA (Amazon Web Services).] Data is only transferred with a legal safeguard, such as the EU standard contractual clauses. You can ask for a copy.

### 5. How the data is protected
- Your name is replaced by a code, and the code key is stored apart from the data.
- The data is encrypted, only named staff can open it, and every access is logged.
- **Honest limit:** removing your name lowers the risk, but does not remove it. Brain signals can sometimes be matched to a person. The risk is checked before any sharing, and trying to identify you is forbidden by contract.

### 6. How long the data is kept
- **Box (i):** until [end of study + ● years], set by the organiser.
- **Boxes (ii)–(vii):** until you withdraw, or at most [●] years after your last session (see RETENTION-POLICY).
- After that the data is deleted, or made truly anonymous if that is possible and approved.

### 7. Taking back your consent – what can and cannot be undone
You can withdraw any box at any time: email [privacy@neuroforge.bio], call [phone] or use [link]. It is as easy as saying yes. If you withdraw from the study itself (box (i)), contact [the organiser]; we will pass it on.

**What will be done:**
- your data for that purpose is deleted. Backups become unreadable because the encryption key for your data is destroyed;
- everyone who received your data for that purpose is told to delete it within [30] days and to confirm it;
- computer models trained with your data are **retrained without it**, or taken out of use;
- you get confirmation if you ask.

**What cannot be undone:**
- results that are already **published** (they only show group results, never your name);
- copies other organisations made **before** you withdrew, if they fail to delete them. Deletion is required by contract, but we cannot physically reach into their systems;
- exact "forgetting" by an AI model. There is **no proven method** for that. Models are retrained without your data instead.

Anything done before you withdrew stays lawful.

### 8. Your rights
You can ask to see your data, correct it, delete it, limit its use, or get a copy to take elsewhere. You can also object. Contact the organiser for box (i) and NeuroForge for boxes (ii)–(viii). Answers come within one month.

**Complaints:** you can complain to **Datatilsynet**, the Norwegian Data Protection Authority (www.datatilsynet.no), or to the authority where you live.

### 9. Payment
[You receive [amount/gift card] for your time. / There is no payment.] **You get the same payment whatever you choose in boxes (ii)–(viii)**, and you keep it if you withdraw later. Nobody pays extra for ticking any box.

### 10. Risks and benefits
Recording is [non-invasive; describe discomfort]. Your main risk is the privacy risk above. There is no direct benefit to you. You receive no medical results and no diagnosis.

### 11. US residents
In some US states (e.g. Connecticut, California, Colorado) neural data is "sensitive data". Sharing it with companies for a fee can count as a "sale". **Boxes (vi) and (vii) are your consent to that.** You can take it back at any time, and we will stop within [15] days. [US counsel to confirm the state wording. **UNVERIFIED** for Colorado and Montana.]

## Part 3 – Your choices (each box is separate; all start empty; each can be withdrawn on its own)

To take part in the study you must tick **(i)**. Everything else is optional.

☐ **(i) The study.** I agree that [the study organiser] may record, store and use my data for the study described above.

☐ **(ii) NeuroForge research pool.** I agree that NeuroForge Bio may keep a de-identified copy of my data in its research pool, to study brain and nerve signals and to test and improve its analysis software.

☐ **(iii) Training NeuroForge AI models.** I agree that NeuroForge Bio may use my de-identified data to train AI models that it uses itself. I understand that if I withdraw, the models are retrained without my data, not exactly "unlearned".

☐ **(iv) Future brain research by NeuroForge.** I agree that NeuroForge Bio may use my de-identified data in future research on how the nervous system works and on neurological conditions, with ethics approval where required. I will be told about new projects and can say no at any time.

☐ **(v) Research partners.** I agree that NeuroForge Bio may share my de-identified data with vetted universities and hospitals for research, under a contract that bans identifying me and passing the data on.

☐ **(vi) AI models licensed to companies.** I agree that NeuroForge Bio may use my de-identified data to train AI models that it **licenses to companies** for a fee. The licence bans trying to identify me and the uses listed in section 4. If I withdraw, new versions of the models are trained without my data.

☐ **(vii) Data licensed to companies.** I agree that NeuroForge Bio may share my de-identified **data** with companies that pay a licence fee to use it for research or product development. The contract bans identifying me, reselling, and the uses listed in section 4. *(Under some US laws this is a "sale".)*

☐ **(viii) Contact.** I agree that NeuroForge Bio may contact me about future studies.

I have read Part 1 and Part 2, or had them read to me. I was able to ask questions. I am 18 or older.

Name: ______________ Signature / e-signature: ______________ Date: ________
Person explaining the study: ______________ Signature: ______________

*You receive a copy of this signed form.*

## Hjemmel / Legal basis
- **GDPR, official English text.** Publications Office, http://publications.europa.eu/resource/celex/32016R0679 (content-negotiated XHTML, opened 2026-09-26):
  - Recital 26 (pseudonymised data = identifiable; "singling out");
  - Recital 33 (consent "to certain areas of scientific research");
  - Recital 42 (identity of controller; no detriment on refusal or withdrawal);
  - Art. 5(1)(b), (e); Art. 12(3).
- **GDPR, Norwegian text on Lovdata** (opened 2026-09-26):
  - Art. 4(11): https://lovdata.no/lov/2018-06-15-38/gdpr/a4
  - Art. 7(3)–(4): https://lovdata.no/lov/2018-06-15-38/gdpr/a7
  - Art. 9(2)(a): https://lovdata.no/lov/2018-06-15-38/gdpr/a9
  - Art. 17: https://lovdata.no/lov/2018-06-15-38/gdpr/a17
  - Art. 19: https://lovdata.no/lov/2018-06-15-38/gdpr/a19
  - Art. 46: https://lovdata.no/lov/2018-06-15-38/gdpr/a46
- **Personopplysningsloven § 10:** https://lovdata.no/lov/2018-06-15-38/§10 (opened 2026-09-26).
- **Helseforskningsloven** (opened 2026-09-26):
  - § 9, § 13, § 14 (broad consent; REK conditions; regular information), § 16 (withdrawal; 30-day deletion demand), § 17 (consent capacity 18+, 16–18 in some cases): https://lovdata.no/lov/2008-06-20-44/§14 and https://lovdata.no/dokument/NL/lov/2008-06-20-44
- **US state law** (opened 2026-09-26):
  - Connecticut PA 25-113: https://www.cga.ct.gov/2025/ACT/PA/PDF/2025PA-00113-R00SB-01295-PA.PDF
  - California SB 1223: https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223
  - Colorado HB24-1058: https://leg.colorado.gov/bills/hb24-1058 (consent wording **UNVERIFIED**)
  - Montana SB 163: **UNVERIFIED**
- **EEG as a biometric:** doi:10.1155/2021/5229576; doi:10.1155/ijta/3946740 (PubMed abstracts, opened 2026-09-26).
- **Product and contract facts:**
  - BLUEPRINT.md §8.3–8.4 (ledger scopes, crypto-shredding, retraining, no certified unlearning);
  - MSA § 4.3 (written opt-in);
  - DECISIONS.md D4.
