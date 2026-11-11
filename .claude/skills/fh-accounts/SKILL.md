---
name: fh-accounts
description: >
  My Function Health user and Dev QA account identifiers: email, UUID,
  patient ID and Firebase UID per environment, plus the Dev member app
  `/devtools` page for setting member values. TRIGGER when: a task needs
  my FH user or patient ID, a Dev QA or test account to act as, QA account
  setup or rediscovery, or member state manipulation in Dev.
disable-model-invocation: false
allowed-tools: Bash, Read
---

# Function Health Accounts

## My User

Identifiers for my personal Function Health user, per environment. The
email is the same across environments; the UUID and patient ID differ.

### Dev

- **Email**: `nickolas.kraus@functionhealth.com`
- **UUID**: `d089c262-1870-4ba1-a27e-cd143ebf7ffb`
- **Patient ID**: `QFnSbFxRxrYCHKJ3`

### Prod

- **Email**: `nickolas.kraus@functionhealth.com`
- **UUID**: `9ea69134-f7a1-41fc-b79b-63b5b0158fa6`
- **Firebase UID**: `xToN9OwB5ISaLhYtcDI1M39g8zR2`
- **Patient ID**: TODO. The `patient_identifier` lives only in the
  PHI-gated `patient` table in the Prod monolith, which my
  non-PHI DB role cannot read.

## My Dev QA Accounts

Personal QA/test users in Function Health Dev, keyed by plus-addressed
email on my `nickolashkraus`/`nickolas.kraus` bases. The `UUID` is
`patient.id`, `Patient ID` is `patient.patient_identifier`, and
`Firebase UID` is `patient.patient_firebase_id`.

| Email                                         | Name                                 | UUID                                   | Patient ID         | Firebase UID                   | Joined     |
| --------------------------------------------- | ------------------------------------ | -------------------------------------- | ------------------ | ------------------------------ | ---------- |
| `nickolashkraus+ppp-qa-1@gmail.com`           | PPP QA One                           | `27d8c597-6107-4523-ad99-f5ea4f695be1` | `dcXCWfAxaiCW7fGi` | `b1rgf9giWVcGsmp0jlZiHSqOIAU2` | 2026-07-09 |
| `nickolashkraus+ppp-qa-3@gmail.com`           | PPP QA Three                         | `1e4eeb1f-236c-48fb-97b9-6856514346dd` | `ZFPywmGtsqZyNY2E` | `2kFO2d48NaTy9MpnpIHCCwaTJJR2` | 2026-07-09 |
| `nickolashkraus+ppp-qa-5@gmail.com`           | PPP QA Five                          | `86dafb7b-5395-4ad3-bb45-66145a5d39bb` | `tToBAfu8Q6KQijuW` | `kRWshaqvyYbWwaMWVupCuDbqAdv1` | 2026-07-09 |
| `nickolashkraus+ppp-qa-7@gmail.com`           | PPP QA Seven                         | `d486f334-3773-48a7-9a5e-9bfd971faf30` | `gtqf6rUG4WGgkUwL` | `5Y59Sl4gwxXLcModR6tRK2WYvit1` | 2026-07-10 |
| `nickolashkraus+ppp-qa-9@gmail.com`           | PPP QA Nine                          | `93b6d57d-cb5a-4765-908d-b515d4ca711a` | `Vtx9q5yppstztzMM` | `luWBdpo3FGNfYIWcbdwiKVxRHTA3` | 2026-07-10 |
| `nickolashkraus+ppp-qa-10@gmail.com`          | PPP QA Ten                           | `b2f0ee37-0e9c-4919-ae63-6519f6051f55` | `RhJe2eTNCom99MPV` | `X1QMdEunZnVuNoHKgCbpRoX7HK42` | 2026-07-10 |
| `nickolas.kraus+ppp-qa-p1@functionhealth.com` | QA PPPTester                         | `9191e8ce-e980-4fec-a6bc-74f699c57096` | `rCYtAjmszJVeQXXD` | `qBSSXF3EhGNXUarjjWgczTiZbU33` | 2026-07-09 |
| `nickolas.kraus+byb1896@functionhealth.com`   | Nickolas-Enterprise Kraus-Enterprise | `ed102123-e189-4c80-a907-5a479c9cbaf6` | `75YjXkozkA5MM4an` | `ig7IRk1dCFhkdc0vS5XhIiaQMfr2` | 2026-05-22 |
| `nickolas.kraus+family-qa@functionhealth.com` | Nickolas Kraus                       | `f4e5f658-e8a4-4f13-a740-02f5f31a28c0` | `NbTSntea9HhdFRz2` | `gNWOjRRtXRbyQMTJmJqUJUnCws43` | 2026-08-14 |
| (none)                                        | PPPLink QAThrowaway                  | `73d67832-1cc2-443c-953b-c928369436a1` | `k9naSNSmRBJHivX4` | (none)                         | 2026-07-10 |

Notes:

- The `byb1896` account is my enterprise test user (BYB-1896). The
  `family-qa` account is for family-plan QA.
- The `PPPLink QAThrowaway` row has no contact email or Firebase UID,
  so it cannot be attributed by email; it is almost certainly my PPP
  payment-link throwaway based on name and creation date.
- To rediscover accounts, sweep the Dev monolith `patient` table by
  name (`lname ilike '%kraus%'`, plus the `PPP`/`PPPTester` fname
  patterns) and cross-check Firebase Auth, not just
  `patient_contact_info.email`. Fresh accounts can have a `patient`
  row before any contact-info email row exists, so an email-only scan
  misses them.

## Dev Member App DevTools

The Dev member app exposes a `/devtools` page that gets and sets member
values (useful for QA account setup and state manipulation):

- URL: https://development-members-app-2jv3ndpkoa-ue.a.run.app/devtools
