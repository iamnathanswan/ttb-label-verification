# Security review

Prototype scope. Reviewed against what this application actually does: accept
untrusted file uploads over a public URL, call a paid API on the caller's behalf,
and return text derived from the uploaded image.

Out of scope by decision (`requirements.md` §I): authentication, persistence,
FedRAMP artefacts. Marcus: *"for a prototype? Just don't do anything crazy."*

## Findings and disposition

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | Decompression bomb — a 136 KB PNG decodes to 144 megapixels | **High** | **Fixed.** Dimensions are checked from the image header before any pixel data is decoded, and again for PDF pages before rasterising. Ceiling 50 MP, which still admits a 24 MP photograph. Pillow only warns by default, so this needed an explicit guard. |
| 2 | CSV injection — extracted label text reaches a spreadsheet | **Medium** | **Fixed.** Brand names come from whatever is printed on an uploaded image, so a value of `=cmd\|'/c calc'!A1` would execute on open. Leading `=`, `+`, `-`, `@`, tab and CR are neutralised with an apostrophe. |
| 3 | Unauthenticated endpoint spends API credit | **Medium** | **Accepted, mitigated.** Authentication is out of scope for the prototype. A sliding-window ceiling per client bounds spend, upload size is capped, and batch size is capped. |
| 4 | Rate-limit key trusts `X-Forwarded-For` | **Low** | **Accepted.** The platform sets this header and it is the only client identity available behind its proxy. A determined caller can rotate it; the upload and batch caps remain. Worth revisiting behind a gateway that provides authenticated identity. |
| 5 | Rate limiter is in-process | **Low** | **Accepted.** One container is the whole deployment. A shared store would add a dependency and its failure modes for no benefit at this scale. |
| 6 | Active content in an uploaded PDF | **Medium** | **Fixed.** PDF is not a passive format: a document can carry JavaScript that Chrome's PDFium, Firefox's pdf.js and Acrobat all execute on open without prompting. The enlarged view hands documents to that viewer, and the documents come from applicants. Scripts, embedded attachments and link actions are stripped server-side before display, and the response is served `Content-Security-Policy: sandbox` with `nosniff`. Form field values are preserved — blanking them would defeat the purpose of showing the form. |
| 7 | Prompt injection via label text | **Low** | **Mitigated by architecture.** Text on a label cannot change a verdict: the model only transcribes, and every determination is a pure function over the transcription (D2). The worst case is a misread field, which is what human review is for. |

## Verified clean

- **API key never leaves the server.** Absent from the built bundle, never interpolated into an error message, and not in the repository or its history (`git log -p --all` finds no key pattern).
- **No injection surface.** No SQL, no shell execution, no template rendering, no user-controlled file paths — nothing is written to disk.
- **No XSS vector.** No `dangerouslySetInnerHTML` or `innerHTML` anywhere; JSX escaping is intact, and all displayed text goes through it.
- **Uploads are not persisted.** Bytes live in memory for the request and are discarded with it (OPS-01), so there is no retention question to answer.
- **Filenames are never used as paths.** They are echoed in results and CSV only.

## Regression cover

`tests/test_load.py` holds the bomb rejection and the realistic-photograph
acceptance, so the ceiling cannot be tightened into uselessness or removed
without a test failing.

`tests/test_sanitize.py` covers finding 6, and its first test asserts that the
*fixture still carries a script*. Without that, every other assertion in the file
would keep passing against a form that had nothing left to strip. The same test
caught a real defect while being written: the form's script sits in a Flate
stream, so the obvious `b"app.alert" in pdf` check is False even for the untouched
original, and a suite built on it would have proved nothing. The assertions run
against decompressed object streams instead.
