# LMS Advisory — New Client Questionnaire (Tax Preparation)

*Export of the complete questionnaire content and logic. Version v2026.01.25. Source of truth: `tax_questionnaire/schema.js` (plus validation rules and the consent gate from the form engine), consolidated here.*

---

**Summary.** This questionnaire is for **new clients of LMS Advisory** engaging the firm to prepare their **Australian income tax return(s)**. It collects identity and contact details, refund/banking preferences, the client's tax situation for the year, document uploads and service interests, then requires several acknowledgements and a privacy consent before submission. There are **28 client-facing questions** across **7 sections**, plus **4 mandatory acknowledgements** and **1 consent tick** (33 required/optional items in total). It uses light branching rather than separate paths: follow-up questions appear based on earlier answers — e.g. the multi-select "significant items" reveals an ABN field (sole trader), a rental-readiness question (investment property) and a crypto detail box; any "Other" choice reveals a "please specify" field; a "Referral" source reveals a thank-you name; and "other entities = Yes" reveals a detail box. Progress is saved locally so clients can resume, and the four acknowledgements plus consent must be completed to submit.

---

## Section: About you
*So we know who we're acting for and can meet our verification obligations.*

**Q1. What is your full name including any middle names?**  *(required)*
- Type: Short text
- Help text: Please ensure this matches your drivers licence or passport. We will need to contact you to verify these details as per our AML/CTF obligations.

**Q2. What is your Date of Birth?**  *(required)*
- Type: Date

**Q3. Please confirm your current residential address to include in the return.**  *(required)*
- Type: Long text
- Help text: We will also treat this as your postal address.

**Q4. Confirm Mobile Phone number to access secure documents and complete electronic signature verification?**  *(required)*
- Type: Phone number
- Help text: We use Fusesign for digital signatures. The added layer of SMS authentication ensures that your Tax File Number will always be secure to you. Every individual return lodged needs its own unique email address and unique mobile phone number.
- Validation: Must be a valid Australian mobile number (format 04xx xxx xxx)

**Q5. What would you describe as your Primary Occupation?**  *(required)*
- Type: Short text
- Help text: It is important we select the right occupation code in your return, as the ATO will benchmark the usual deductions claimed in different industries against your peers.

**Q6. Preferred email address for electronic signing of documents?**  *(required)*
- Type: Email
- Help text: Every return lodged for each taxpayer needs its own unique email address and mobile phone number.
- Validation: Must be a valid email address

---

## Section: Tax year & refund
*The year(s) we're lodging and where any refund should go.*

**Q7. What Tax Year are we completing for you?**  *(required)*
- Type: Multi-select (checkboxes)
- Help text: Select all that apply.
- Options: 2026 · 2025 · 2024 · 2023 · 2022 · Multiple Years · Other

**Q8. Which other year(s) should we complete?**  *(optional)*
- Type: Short text
- Conditional: Show only if Q7 (Tax Year) includes "Other"

**Q9. What is your preferred Bank Account for your refund? Please provide even if you anticipate your return being payable this year.**  *(required)*
- Type: Structured bank details — three fields: Account name (short text), BSB (number), Account number (number)
- Help text: Please provide Account Name, BSB and Account Number.
- Validation: BSB must be 6 digits; account number must be 5–12 digits

**Q10. If your return is refundable, do you intend to use the LMS Trust Account service to pay your tax return fee from your refund?**  *(required)*
- Type: Yes/No
- Help text: Our fees will be quoted in advance wherever possible. If your return is refundable and you wish to use the Trust Account Service, the ATO will pay your refund into our Trust Account first. Your agreed fee is then transferred to LMS and the balance returned to you. This may delay receipt of your refund by up to 1 week. There is no charge for using the Trust Account service. We will send you a Trust Authority document to complete with your tax paperwork.

---

## Section: Getting started
*A couple of quick questions before we dig in.*

**Q11. Have you received a copy of our Tax Checklist for completion to assist you in providing us with the documents we'll need to complete your return?**  *(optional)*
- Type: Yes/No
- Help text: Copies can also be downloaded from the LMS website: https://www.lmsadvisory.com.au/knowledge/taxpreparation/

**Q12. Do you require a consultation with an accountant in relation to your tax affairs?**  *(required)*
- Type: Single-select (radio)
- Help text: In-person appointments are not necessary to progress tax return preparation. If you are looking to book an in-person advice consultation with one of our accountants, you can schedule once your returns are complete. Appointments outside of office hours and on Saturdays are available by Zoom only. Please note additional fees may apply for consultations.
- Options: Yes · No · Unsure, I'd like a phone call to discuss

---

## Section: About your return
*This helps us tailor our advice to your circumstances.*

**Q13. Do any of these significant items apply to you?**  *(required)*
- Type: Multi-select (checkboxes)
- Help text: Multiple answers could apply — this will help guide us in advising you on your tax affairs.
- Options:
  1. I am a sole trader
  2. Bought/Sold a Significant Asset required a Capital Gains Tax calculation (investment property/shares)
  3. Own 1 or more investment properties
  4. Got Married in the financial year
  5. Separated from your spouse in the financial year
  6. Welcomed a new child into the world
  7. Moved House (changed my main residence)
  8. Started a new job / Retired
  9. Started my own business
  10. Commenced new studies / Finalised my studies
  11. Paid out my HECS Debt
  12. Refinanced a home loan or investment loan
  13. Invest or Trade in Crypto
  14. Make additional contributions to super
  15. Unsure
  16. Other

**Q14. As a sole trader, what is your ABN?**  *(optional)*
- Type: Short text
- Conditional: Show only if Q13 (significant items) includes "I am a sole trader"
- Validation: Must be a valid ABN (11 digits)

**Q15. Do you have your agent's Annual Rental Summary, loan statements and out-of-pocket expenses ready to provide?**  *(optional)*
- Type: Yes/No
- Help text: Our checklist has a detailed rental schedule you can complete.
- Conditional: Show only if Q13 (significant items) includes "Own 1 or more investment properties"

**Q16. Tell us briefly about your crypto activity.**  *(optional)*
- Type: Long text
- Help text: Which exchanges you used and roughly how many transactions — we'll follow up for detail.
- Conditional: Show only if Q13 (significant items) includes "Invest or Trade in Crypto"

**Q17. Please tell us about the other significant item.**  *(optional)*
- Type: Short text
- Conditional: Show only if Q13 (significant items) includes "Other"

**Q18. Do you have any questions in particular related to this year's return or your tax affairs in general?**  *(optional)*
- Type: Long text
- Help text: Please list your questions separated by a comma, e.g. (1. Can I claim this? 2. What are the 2 alternate work-from-home claim methods?). It's OK if you have no questions!

---

## Section: Documents & services
*Share anything useful and tell us where else we can help.*

**Q19. Would you like to upload any documents linked to the questions above for us to consider?**  *(optional)*
- Type: File upload (multiple files allowed)
- Help text: You are welcome to upload any documentation referred to in the checklist. We'd also love a copy of last year's tax return lodged.

**Q20. Do you have a copy of last year's tax return on hand in case we need it?**  *(required)*
- Type: Yes/No
- Help text: Providing last year's return helps us ensure we address all applicable aspects of your return. Email us or upload it using the link above.

**Q21. Are you interested in any of the other services LMS can provide?**  *(required)*
- Type: Multi-select (checkboxes)
- Help text: If you do not require any additional services, please select 'No Thanks'. You may select as many services as you need — we'll be in touch!
- Options:
  1. No Thanks
  2. Financial Planning
  3. Budgeting / Cashflow Forecasting
  4. Asset purchase structuring and entity formations
  5. Referral to Mortgage Brokers in our network
  6. Referral to Solicitors
  7. Bookkeeping Services
  8. Self Managed Superannuation Creation and Advice
  9. Wealth Creation Strategies
  10. Property Portfolio Review and Growth Strategies
  11. Starting a new business or side hustle
  12. Other

**Q22. Which other service are you interested in?**  *(optional)*
- Type: Short text
- Conditional: Show only if Q21 (other services) includes "Other"

---

## Section: A few last things
*Almost done.*

**Q23. How did you hear about us?**  *(required)*
- Type: Single-select (radio)
- Help text: If you were referred to LMS, we would love to thank the person who passed on our details.
- Options: Referral · LMS Website · LinkedIn · Facebook · Instagram · Saw us in a magazine or online publication · Other

**Q24. Who can we thank for referring you?**  *(optional)*
- Type: Short text
- Conditional: Show only if Q23 (how heard) is "Referral"

**Q25. Please tell us how you heard about us.**  *(optional)*
- Type: Short text
- Conditional: Show only if Q23 (how heard) is "Other"

**Q26. If we provide you an outstanding service, would you be willing to leave us a Google review?**  *(optional)*
- Type: Yes/No
- Help text: Our business grows when our valued customers share their positive experience with us. We look forward to working with you!

**Q27. Do you have any other entities that you would like us to look after?**  *(required)*
- Type: Yes/No
- Help text: You may have associated companies, trusts or an SMSF. We have expertise in all of the above and would love to help.

**Q28. Tell us about the entities you'd like us to look after.**  *(optional)*
- Type: Long text
- Conditional: Show only if Q27 (other entities) is "Yes"

---

## Section: Acknowledgements
*Please read and confirm each of the following to continue. Each is a required tick-to-confirm.*

**Q29. I understand that LMS cannot commence working on my return until my Income Tax Finalisation for the year is noted as 'Tax Ready' in myGov or on the ATO Prefill report.**  *(required)*
- Type: Acknowledgement (tick to confirm)

**Q30. I understand that LMS will start working on my return when all of the information requested from me has been received.**  *(required)*
- Type: Acknowledgement (tick to confirm)

**Q31. Where source documents have not been provided (for example, items listed on a spreadsheet without a receipt), I confirm the source documents are in my possession and can be provided on request by LMS Advisory Pty Limited, the Australian Taxation Office, or any other party with authority to request them.**  *(required)*
- Type: Acknowledgement (tick to confirm)

**Q32. I understand LMS Advisory reserves the right to withhold lodgement of my return until any outstanding invoice(s) for the preparation of that return have been paid.**  *(required)*
- Type: Acknowledgement (tick to confirm)

---

## Section: Consent (final step before submit)

**Q33. I consent to LMS Advisory collecting and handling the information in this form to prepare my tax return, in line with the Privacy Policy.**  *(required)*
- Type: Acknowledgement (tick to confirm)
- Help text: Links to the LMS Advisory Privacy Policy. Submission is blocked until this is ticked.

---

*Note: the live form also includes a hidden anti-spam honeypot field and a submission-timing check. These are not questions shown to clients and collect no client information; they are listed here only for completeness.*
