# Knowledge Base Transfer Scripts

## Background

## What’s in This Repository

### `original-uillinois-powershell-scripts`

These are PowerShell scripts that I received from Kim Charles. I gather they got to
Kim by-way-of Anthony Marino. They seem to have been used in UIllinois efforts to transfer
data into TDX.

#### `kbimport-uillinois.ps1`

A PowerShell script that reads knowledge base data from a JSON file and attempts to save it
to TDX.

#### `scrubbed importloop.ps1`

A PowerShell script that appears to import TDX data into a SQLite store.

### `example-code-for-kim`

Before I became actively involved in the project to transfer articles, I sent Kim some
example scripts that showed how to use KB APIs.

#### `kim.py`

An example which shows how to connect to the University of Wisconsin knowledge base, execute
a query, and (since it uses a paging API) display the first and last pages of results.