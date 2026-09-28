> DRAFT – not legal advice. Must be reviewed by a Norwegian lawyer (advokat) before use.

# Convertible loan agreement (asl kap. 11)

**ASSUMPTION:** [NeuroForge Bio AS] will be a Norwegian AS under aksjeloven. It is not yet incorporated; all company data
are placeholders. **Language:** the Norwegian version (konvertibelt-laan.no.md) prevails.

Parties: [NeuroForge Bio AS], org.nr. [___] (the "Company"); [Lender], [id], [address] (the "Lender"); and Marius
Carlsson (the "Founder", as shareholder for clause 2).

## 1. Loan
1.1 The Lender lends the Company NOK [1,000,000] (the "Loan"). It is paid out to account [___] within [__] days after the
Company has registered the general meeting resolution under clause 2 [or: after the resolution; advokat to confirm the
order].
1.2 Interest: [5] % p.a. simple, calculated on a 365-day basis. It accrues and is not paid in cash unless the Loan is
repaid. Over the full 24-month maturity, the accrued interest is NOK [100,000] (NOK [1,100,000] in total).
1.3 The Loan is unsecured [and subordinated to [bank debt]].

## 2. Corporate formalities (conditions)
2.1 The Loan is a konvertibelt lån under aksjeloven §11-1: the Lender may demand that new shares are issued against
set-off of the claim (motregning).
2.2 The general meeting resolves to take up the Loan with the majority required to amend the articles (§11-2 with §5-18).
The resolution contains the items listed in §11-2 (see generalforsamlingsprotokoll, part B), including the conversion
deadline, which may be no later than **five years** from the resolution.
2.3 The shareholders' pre-emption right is waived (§11-4 with §§10-4 and 10-5). The Founder undertakes to vote in favour.
2.4 The Company reports the resolution to Foretaksregisteret (§11-6). Conversion shares are registered under §11-7
[advokat: timing and whether each conversion must be reported separately; **UNVERIFIED** detail].

## 3. Conversion
3.1 **Qualified Financing:** an equity issue with at least NOK [5,000,000] of new money before the Maturity Date. The Loan
+ accrued interest converts automatically at the Conversion Price. [Advokat: whether "automatic" conversion is
compatible with §11-1's "right to demand"; if not, the Lender undertakes to demand conversion.]
3.2 **Conversion Price** = the lower of (a) NOK [12,000,000] ÷ number of shares outstanding before the Qualified
Financing, excluding shares issued in it and excluding the [10] % option pool created pre-money in it (the "Cap Price"), and (b) the price per share in the
Qualified Financing × (1 − [0.20]) (the "Discount Price").
3.3 Number of conversion shares = (principal + accrued interest) ÷ Conversion Price, rounded down. The remainder is paid in
cash [or waived].
3.4 The conversion shares have the same class and rights as those issued in the Qualified Financing [owner-friendly
alternative: ordinary shares].
3.5 Voluntary conversion: the Lender may demand conversion at the Cap Price at any time before the Maturity Date.

## 4. Maturity
4.1 Maturity Date: [24] months after payout (and in any case before the conversion deadline in the GF resolution).
4.2 At the Maturity Date without a Qualified Financing, the Loan + interest **converts at the Cap Price** [alternative:
the Company chooses between repayment and conversion]. The Company shall not be required to repay in cash if that would
breach asl §3-4 (proper equity and liquidity; **UNVERIFIED**, not opened).

## 5. Sale of the Company
If more than 50 % of the shares or substantially all assets are sold before conversion, the Lender chooses between
(a) repayment of principal + interest and (b) conversion at the Cap Price immediately before the sale.

## 6. Events of default
Insolvency, bankruptcy or winding-up proceedings: the Loan falls due. [Advokat: interaction with konkursloven;
**UNVERIFIED**.]

## 7. Information and pro-rata
Information rights and pro-rata right as in the shareholders' agreement. The Lender adheres to the SHA upon conversion.

## 8. Transfer
The Lender may not assign the Loan without the Company's written consent.

## 9. Governing law
Norwegian law, [Oslo tingrett].

## Signatures (leave blank)
Company: ________ Lender: ________ Founder: ________ Date: [ ]

Worked example (ESTIMATE; dilution.py = investor\dilution.csv; inputs from investor\ROUND-ASSUMPTIONS.md): NOK 1,100,000 at
the NOK 12M cap = 8.40 % just before the seed. Owner after the seed: 64.12 % (NOK 10M at NOK 40M pre) or 60.40 %
(NOK 38.0M at NOK 120M pre, alone), including the 10 % pool; in sequence N1 → N2: 48.69 %. With a seed at NOK 10M pre-money, the discount gives 17.19 %.

## Hjemmel / Legal basis
- Aksjeloven §11-1 (conversion right; cash or set-off), §11-2 (GF resolution, required items, conversion deadline ≤ 5
  years), §11-4 (pre-emption with §§10-4, 10-5), §11-6 (registration), §11-7 (registration of the capital increase;
  articles amended without a new GF), §11-8 (board authorisation ≤ half the share capital, ≤ 2 years):
  https://lovdata.no/lov/1997-06-13-44/§11-1 (opened 2026-09-26)
- §5-18: https://lovdata.no/lov/1997-06-13-44/§5-18 (opened 2026-09-26)
- §3-4, konkursloven, tax on interest and conversion: **UNVERIFIED** (not opened).
