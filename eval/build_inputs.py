"""Download the public sources and write the pinned inputs under eval/inputs/.

Run once with network access; run_eval.py then works offline from the
committed files. Static sources are checked against fixed SHA-256 digests.
The Wikidata and US Treasury files come from live services, so a rebuild can
change them; their digests are recorded in the manifest and checked by
run_eval.py before anything is measured.

    python eval/build_inputs.py --cache /tmp/tablebeam-eval-cache
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import tarfile
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
USER_AGENT = "tablebeam-eval/1.0 (https://github.com/fortunexbt/tablebeam)"

WTQ_COMMIT = "7d455a5a707b96341ef72aff9428749d443d8aa9"
SQUALL_COMMIT = "ee6dda91eacafd5ee800eb3fdc5d3a6575dc47e7"
ARCHIVES = {
    "wtq": (
        f"https://codeload.github.com/ppasupat/WikiTableQuestions/tar.gz/{WTQ_COMMIT}",
        "e96b3957ce20c4aa619a1863cfd09cbc803fea0380b102e092b9ce1d215c8b84",
    ),
    "squall": (
        f"https://codeload.github.com/tzshi/squall/tar.gz/{SQUALL_COMMIT}",
        "3002d932a5a0b220d3b108a97556d973470e643e63dde64ce35d053469be6e10",
    ),
}
UNSUPPORTED_SAMPLE = 400

# A whole-table aggregate with no condition: the only question shape the
# deterministic engine claims. Measures must be SQUALL's parsed number column.
SUPPORTED_SQL = re.compile(r"^select (count|sum|avg|max|min) \( (\*|c(\d+)(_number)?) \) from w$")
OPERATIONS = {"count": "count", "sum": "sum", "avg": "mean", "max": "max", "min": "min"}

WIKIDATA_QUERY = """\
SELECT ?person ?personLabel ?countryLabel (MIN(xsd:integer(?tid)) AS ?twitter_user_id) WHERE {
  ?person p:P39 ?st . ?st ps:P39 wd:Q27169 ; pq:P2937 wd:Q64038205 .
  OPTIONAL { ?person wdt:P27 ?country . }
  OPTIONAL { ?person p:P2002 ?xs . ?xs pq:P6552 ?tid . FILTER(isLiteral(?tid)) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} GROUP BY ?person ?personLabel ?countryLabel ORDER BY ?person
"""

# Real CSVs whose number formats break common executors. Each measure names
# how a person reads its cells, which is what the exact reference uses.
NUMERIC_TABLES = [
    {
        "file": "us_treasury_debt_to_the_penny.csv",
        "title": "Debt to the Penny, daily, 1993-04-01 to 2026-10-21",
        "source": "U.S. Department of the Treasury, Fiscal Data API",
        "url": "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?"
        + urllib.parse.urlencode({
            "format": "csv", "page[size]": "10000", "sort": "record_date",
            "filter": "record_date:lte:2026-10-21",
        }),
        "licence": "Public domain (work of the U.S. federal government, 17 U.S.C. 105)",
        "sha256": None,
        "why": "dollar amounts with cents near 3.6e13, and the literal text null for missing values",
        "missing": ["", "null"],
        "decimal_separator": ".",
        "measures": ["debt_held_public_amt", "intragov_hold_amt", "tot_pub_debt_out_amt"],
        "operations": ["mean", "median", "min", "max"],
        "groups": ["record_calendar_year"],
    },
    {
        "file": "wikidata_meps_9th_term_x_ids.csv",
        "title": "Members of the 9th European Parliament with their X (Twitter) numeric user ID",
        "source": "Wikidata Query Service",
        "url": "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": WIKIDATA_QUERY}),
        "licence": "CC0 1.0 (Wikidata)",
        "sha256": None,
        "why": "64-bit identifiers above 2^53 in a column with blanks",
        "missing": [""],
        "decimal_separator": ".",
        "measures": ["twitter_user_id"],
        "operations": ["min", "max"],
        "groups": ["countryLabel"],
    },
    {
        "file": "paris_rent_control_2022.csv",
        "title": "Encadrement des loyers de Paris 2022 (reference rents, EUR per m2)",
        "source": "data.gouv.fr, dataset encadrement-des-loyers-de-paris",
        "url": "https://static.data.gouv.fr/resources/donnees-de-lencadrement-des-loyers-de-paris-2022/"
        "20220613-134928/paris2022.csv",
        "licence": "Licence Ouverte / Open Licence 2.0 (as declared on data.gouv.fr)",
        "sha256": "42a9a8bce697b35cc76a9511ab1e0e9e60259375a4d75572d2c51a639c5e47d9",
        "why": "two-decimal prices whose averages land on half-way digits",
        "missing": [""],
        "decimal_separator": ".",
        "measures": ["min", "ref", "max"],
        "operations": ["mean", "median", "min", "max"],
        "groups": ["id_zone", "piece", "epoque", "meuble_txt"],
    },
    {
        "file": "montpellier_rent_control_2023.csv",
        "title": "Encadrement des loyers de Montpellier 2023 (reference rents, EUR per m2)",
        "source": "data.gouv.fr, dataset encadrement-des-loyers-de-montpellier",
        "url": "https://static.data.gouv.fr/resources/encadrement-des-loyers-de-montpellier/"
        "20230708-141512/encadrements-montpellier-2023.csv",
        "licence": "Licence Ouverte / Open Licence 2.0 (as declared on data.gouv.fr)",
        "sha256": "171c1518d9b2b7058d8b9d475eaac7a6d5f859981023d872c9016f562f5ca41b",
        "why": "French decimal commas inside a comma-separated file (\"18,1\")",
        "missing": [""],
        "decimal_separator": ",",
        "measures": ["prix_med", "prix_max", "prix_min"],
        "operations": ["mean", "median", "min", "max"],
        "groups": ["zone", "nombre_de_piece", "annee_de_construction", "meuble"],
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        return response.read()


def archive(name: str, cache: Path) -> Path:
    url, digest = ARCHIVES[name]
    path = cache / f"{name}.tar.gz"
    if not path.exists():
        path.write_bytes(fetch(url))
    if sha256(path.read_bytes()) != digest:
        raise SystemExit(f"{name} archive digest changed: {url}")
    target = cache / name
    if not target.exists():
        with tarfile.open(path) as tar:
            tar.extractall(target, filter="data")
    return next(target.iterdir())


def wtq_unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "p": "|", "\\": "\\"}[m.group(1)], text)


def header_key(text: str) -> str:
    # SQUALL lowercases headers, folds them to ASCII and parses numeric ones.
    folded = unicodedata.normalize("NFKD", " ".join(text.split()).casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = folded.replace("\u2013", "-").replace("\u2014", "-")
    try:
        return repr(float(folded))
    except ValueError:
        return folded


def build_wtq(cache: Path) -> list[dict]:
    wtq, squall = archive("wtq", cache), archive("squall", cache)
    with (wtq / "data" / "training.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE))
    questions = {row[0]: {"question": wtq_unescape(row[1]), "answer": [wtq_unescape(v) for v in row[3].split("|")]}
                 for row in rows[1:]}

    supported, pool, excluded = [], [], []
    for entry in json.loads((squall / "data" / "squall.json").read_text(encoding="utf-8")):
        sql = " ".join(token[1] for token in entry["sql"])
        table = json.loads((squall / "tables" / "json" / f"{entry['tbl']}.json").read_text(encoding="utf-8"))
        page, number = entry["tbl"].split("_")
        csv_path = wtq / "csv" / f"{page}-csv" / f"{number}.csv"
        with csv_path.open(encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        record = {
            "id": entry["nt"], "table": entry["tbl"], "sql": sql,
            **questions[entry["nt"]],
        }
        if [header_key(h) for h in header] != [header_key(h) for h in table["headers"][2:]]:
            # SQUALL reshaped this table, so its SQL does not describe the raw CSV.
            excluded.append({"id": entry["nt"], "reason": "SQUALL reshaped the table's columns"})
            continue
        referenced = sorted(set(re.findall(r"\bc\d+(?:_[a-z0-9_]+)?\b", sql)) | {"id", "agg"})
        variants = {item["col"]: item for column in table["contents"] for item in column}
        record["sql_columns"] = {
            name: {"type": variants[name]["type"], "data": variants[name]["data"]}
            for name in referenced if name in variants
        }
        match = SUPPORTED_SQL.match(sql)
        if match and match.group(1) == "count" and match.group(3):
            # Counting the filled cells of one column is "count rows" only
            # when that column has no blanks outside summary rows.
            cells = variants[match.group(2)]["data"]
            summary = variants["agg"]["data"]
            if any(cell is None for cell, agg in zip(cells, summary) if int(agg) == 0):
                match = None
        if match and (match.group(1) == "count" or match.group(4)):
            index = match.group(3)
            record["stratum"] = "supported"
            record["spec"] = {
                "operation": OPERATIONS[match.group(1)],
                "column": None if match.group(1) == "count" else header[int(index) - 1],
            }
            supported.append(record)
        else:
            record["stratum"] = "unsupported"
            record["spec"] = None
            pool.append(record)

    pool.sort(key=lambda record: sha256(record["id"].encode()))
    selected = sorted(supported + pool[:UNSUPPORTED_SAMPLE], key=lambda r: int(r["id"].split("-")[1]))

    tables_dir = INPUTS / "wtq" / "tables"
    shutil.rmtree(tables_dir, ignore_errors=True)
    tables_dir.mkdir(parents=True)
    tables = {}
    for table_id in sorted({record["table"] for record in selected}):
        page, number = table_id.split("_")
        original = (wtq / "csv" / f"{page}-csv" / f"{number}.csv").read_bytes()
        content = rfc4180(original)
        (tables_dir / f"{table_id}.csv").write_bytes(content)
        meta = json.loads((wtq / "page" / f"{page}-page" / f"{number}.json").read_text(encoding="utf-8"))
        tables[table_id] = {
            "file": f"wtq/tables/{table_id}.csv",
            "sha256": sha256(content),
            "wtq_path": f"csv/{page}-csv/{number}.csv",
            "wtq_sha256": sha256(original),
            "wikipedia_title": meta["title"],
            "wikipedia_revision": f"https://en.wikipedia.org/w/index.php?oldid={meta['revision']}",
        }

    with (INPUTS / "wtq" / "questions.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in selected:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return [tables, excluded, len(supported), len(pool)]


def rfc4180(content: bytes) -> bytes:
    """Re-quote a WikiTableQuestions CSV the way spreadsheet exports do.

    The dataset escapes quotes as \\" and backslashes as \\\\, which RFC 4180
    readers (Python's csv, Tablebeam) reject. Cell values are unchanged.
    """
    reader = csv.reader(io.StringIO(content.decode("utf-8"), newline=""), escapechar="\\", doublequote=False)
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(reader)
    return output.getvalue().encode("utf-8")


def build_numeric(refresh: bool) -> list[dict]:
    target = INPUTS / "numeric"
    target.mkdir(parents=True, exist_ok=True)
    entries = []
    for spec in NUMERIC_TABLES:
        accept = "text/csv" if "wikidata" in spec["url"] else None
        path = target / spec["file"]
        # Live services change; keep the committed snapshot unless asked.
        content = fetch(spec["url"], accept) if refresh or not path.exists() else path.read_bytes()
        if spec["sha256"] and sha256(content) != spec["sha256"]:
            raise SystemExit(f"{spec['file']} changed upstream: {spec['url']}")
        path.write_bytes(content)
        entries.append({**spec, "file": f"numeric/{spec['file']}", "sha256": sha256(content)})
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, required=True, help="download and extraction directory")
    parser.add_argument("--refresh", action="store_true", help="download the Wikidata and Treasury files again")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)

    tables, excluded, supported, pool = build_wtq(args.cache)
    numeric = build_numeric(args.refresh)
    questions = INPUTS / "wtq" / "questions.jsonl"
    manifest = {
        "wtq": {
            "questions_file": "wtq/questions.jsonl",
            "questions_sha256": sha256(questions.read_bytes()),
            "sources": {
                "WikiTableQuestions": {
                    "url": f"https://github.com/ppasupat/WikiTableQuestions/tree/{WTQ_COMMIT}",
                    "licence": "CC BY-SA 4.0",
                    "citation": "Pasupat and Liang, Compositional Semantic Parsing on Semi-Structured Tables, ACL 2015",
                    "used": "data/training.tsv questions and answers, csv/ tables, page/ Wikipedia revisions",
                },
                "SQUALL": {
                    "url": f"https://github.com/tzshi/squall/tree/{SQUALL_COMMIT}",
                    "licence": "CC BY-SA 4.0 (LICENSE-data)",
                    "citation": "Shi, Zhao, Boyd-Graber, Daume III and Lee, On the Potential of Lexico-logical "
                    "Alignments for Semantic Parsing to SQL Queries, Findings of EMNLP 2020",
                    "used": "data/squall.json SQL annotations, tables/json parsed columns referenced by each SQL",
                },
            },
            "selection": {
                "supported": f"all {supported} SQUALL questions whose SQL is a single unconditioned "
                "count/sum/avg/max/min over the whole table (a count of one column's cells only when "
                "that column has no blanks)",
                "unsupported": f"{UNSUPPORTED_SAMPLE} of the other {pool} questions, the lowest SHA-256 of the question id",
                "excluded": excluded,
            },
            "table_format": "re-quoted from the dataset's backslash escapes to RFC 4180 (see rfc4180()); "
            "wtq_sha256 is the original file",
            "table_licence": "CC BY-SA 4.0 via WikiTableQuestions; extracted from the Wikipedia revision listed, "
            "whose text is CC BY-SA",
            "tables": tables,
        },
        "numeric": numeric,
    }
    (INPUTS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
