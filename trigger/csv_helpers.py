import csv


def detect_ems(header):
    first_col = header[0].lower()
    if first_col == "houseid":
        return "Idox Eros (Halarose)"
    if first_col == "authoritycode":
        return "Xpress WebLookup"
    if first_col == "electiondate":
        return "Xpress DC"
    if "xordinate" in [h.lower() for h in header]:
        return "Democracy Counts"
    return "unknown"


def attempt_decode(body):
    encodings = ["utf-8", "windows-1252", "latin-1"]
    for encoding in encodings:
        try:
            return body.decode(encoding)
        except UnicodeDecodeError as e:
            last_exception = e
            continue
    raise last_exception


def get_delimiter(sample, content_type):
    # sometimes we get CSVs with a TSV extension or TSVs with a CSV extension,
    # so we'll try and use csv.Sniffer to work it out for us.
    try:
        dialect = csv.Sniffer().sniff(sample, [",", "\t"])
        return dialect.delimiter
    except csv.Error:
        # if that fails, make an assumption based on the MIME type
        # (which S3 guesses from the extension)
        if content_type == "text/tab-separated-values":
            return "\t"
        return ","


def get_csv_report(response):
    report = {"csv_valid": False, "csv_rows": None, "ems": "unknown", "errors": []}

    body = response["Body"].read()
    if len(body) == 0:
        report["errors"].append("File is empty")
        return report

    try:
        decoded = attempt_decode(body)
    except UnicodeDecodeError:
        report["errors"].append("Failed to decode body using any expected encoding")
        return report

    delimiter = get_delimiter(decoded[0:10000], response["ContentType"])

    try:
        records = csv.reader(
            decoded.splitlines(True), delimiter=delimiter, quotechar='"'
        )
        header = next(records)
        expected_row_length = len(header)
        if expected_row_length < 3:
            report["errors"].append(
                f"File has only {expected_row_length} columns. We might have failed to detect the delimiter"
            )
            return report
        report["ems"] = detect_ems(header)
        total_rows = 1
        for record in records:
            length = len(record)
            total_rows += 1
            if length < expected_row_length:
                report["csv_valid"] = False
                report["errors"].append(
                    f"Incomplete file: Expected {expected_row_length} columns on row {total_rows} found {length}"
                )
                report["csv_rows"] = total_rows
                return report

        report["csv_valid"] = True
        report["csv_rows"] = total_rows
        return report
    except csv.Error:
        report["errors"].append("Failed to parse body")
        return report


def get_object_report(response):
    if response["ContentLength"] < 1024:
        return {"errors": ["Expected file to be at least 1KB"]}
    if response["ContentLength"] > 150_000_000:
        return {"errors": ["Expected file to be under 150MB"]}
    if response["ContentType"] not in ("text/tab-separated-values", "text/csv"):
        return {"errors": [f"Unexpected file type {response['ContentType']}"]}
    return {"errors": []}
