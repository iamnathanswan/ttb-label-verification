# Sample documents

Ready-made label and COLA application pairs for trying the tool. Each folder holds
one label and, where relevant, the application it belongs to.

Drop both files on the page together — or drop the whole folder.

Applications are the real TTB F 5100.31 filled in programmatically; the blank form
came from ttb.gov. Labels are synthetic, each built with one deliberate defect.

| Folder | What it shows | Expect |
|---|---|---|
| `01-everything-matches` | A compliant label and the application that matches it. | PASS |
| `02-brand-case-differs` | The application says “Old Tom Distillery”, the label says “OLD TOM DISTILLERY”. | NEEDS REVIEW |
| `03-wrong-brand` | The application declares a different brand entirely. | FAILED |
| `04-declared-import-no-origin` | The application declares an imported product but the label states no country of origin. | FAILED |
| `05-wrong-product-type` | The application declares wine; the label is a bourbon. | NEEDS REVIEW |
| `06-scanned-application` | The same application printed and scanned, so it has no form fields left. | PASS |
| `07-warning-body-bold` | The whole government warning is bold. | FAILED |
| `08-warning-title-case` | The warning heading reads “Government Warning:” instead of capitals. | FAILED |
| `09-label-only` | No application at all. | PASS |

## Making your own

`tests/fixtures/generate_labels.py` draws labels and
`tests/fixtures/generate_applications.py` fills applications. Both are small and
commented; adding a case is a few lines in the table at the bottom of either file.

The blank form is at `tests/fixtures/applications/_blank_form_ttb_f_5100_31.pdf` if
you would rather fill one in by hand — it is a normal fillable PDF, and the tool
reads whatever a PDF viewer saves.
