from __future__ import annotations

import argparse
import calendar
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag


BASE_URL = "https://ods.foi.org.tw/"
HELP_URL = "https://ods.foi.org.tw/help.aspx"

DATA_ROOT = Path("data/foi_ods")

VISIBLE_LIMIT = 100

FIELD_DECISION_CATEGORY = "Foi$cph_content$ddlTypeID"
FIELD_PAGE_SIZE = "Foi$cph_content$ddl_page"
FIELD_DECISION_RESULT = "Foi$cph_content$ddl_ResultKind"
FIELD_RESULT_NAME = "Foi$cph_content$hResName"
FIELD_INDUSTRY = "Foi$cph_content$ddlVerticals"
FIELD_INDUSTRY_SUBCATEGORY = "Foi$cph_content$ddlSubVerticals"
FIELD_DISPUTE_TYPE = "Foi$cph_content$dll_ControversyKind"
FIELD_CASE_YEAR = "Foi$cph_content$txt_BYear"
FIELD_CASE_WORD = "Foi$cph_content$dll_BCase"
FIELD_CASE_NUMBER = "Foi$cph_content$txt_Bno"
FIELD_CONTENT = "Foi$cph_content$txt_Content"
FIELD_START_YEAR = "Foi$cph_content$txt_Syear"
FIELD_START_MONTH = "Foi$cph_content$txt_Smonth"
FIELD_START_DAY = "Foi$cph_content$txt_Sday"
FIELD_END_YEAR = "Foi$cph_content$txt_Eyear"
FIELD_END_MONTH = "Foi$cph_content$txt_Emonth"
FIELD_END_DAY = "Foi$cph_content$txt_Eday"
FIELD_INTERNAL_START_DATE = "Foi$cph_content$sdate"
FIELD_INTERNAL_END_DATE = "Foi$cph_content$edate"
FIELD_SUBMIT = "Foi$cph_content$btn_submit"
FIELD_ORDER_BY = "Foi$cph_content$ddlOrderBy"
FIELD_SORT = "Foi$cph_content$hSort"
FIELD_CURRENT_PAGE = "Foi$cph_content$HFrecCurrentPage"
FIELD_RECORD_COUNT = "Foi$cph_content$HFRecordCount"
FIELD_PAGE_COUNT = "Foi$cph_content$HFrecPageCount"


class CrawlerError(RuntimeError):
    pass


def default_metadata_path(roc_year: int) -> Path:
    return DATA_ROOT / "metadata" / f"foi_ods_life_roc{roc_year}_metadata.json"


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    @property
    def day_count(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class DisputeFilter:
    value: str
    label: str | None


def roc_to_gregorian(roc_year: int) -> int:
    return roc_year + 1911


def gregorian_to_roc(gregorian_year: int) -> int:
    return gregorian_year - 1911


def roc_label(day: date) -> str:
    return f"{gregorian_to_roc(day.year)}/{day.month}/{day.day}"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Origin": "https://ods.foi.org.tw",
            "Referer": BASE_URL,
        }
    )
    return session


def fetch_soup(session: requests.Session) -> BeautifulSoup:
    response = session.get(BASE_URL, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return BeautifulSoup(response.text, "html.parser")


def post_search(session: requests.Session, payload: dict[str, str]) -> BeautifulSoup:
    response = session.post(BASE_URL, data=payload, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    if "runtime error" in title.lower() or "執行階段錯誤" in title:
        raise CrawlerError("FOI ODS returned ASP.NET runtime error for the submitted payload.")
    return soup


def hidden_payload(soup: BeautifulSoup) -> dict[str, str]:
    payload: dict[str, str] = {}
    for input_el in soup.select("input"):
        if not isinstance(input_el, Tag):
            continue
        name = input_el.get("name")
        input_type = (input_el.get("type") or "").lower()
        if isinstance(name, str) and input_type in {"hidden", "text"}:
            payload[name] = str(input_el.get("value") or "")

    # These fields are present in a real browser submission even when the
    # initial HTML omits them. Empty values match the browser form state.
    payload.setdefault("__EVENTTARGET", "")
    payload.setdefault("__EVENTARGUMENT", "")
    payload.setdefault("__LASTFOCUS", "")
    return payload


def get_json_options(session: requests.Session, endpoint: str, payload: dict[str, str]) -> list[dict[str, str]]:
    response = session.post(
        urljoin(BASE_URL, endpoint),
        json=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE_URL,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    options = data.get("d")
    if not isinstance(options, list):
        raise CrawlerError(f"Unexpected dropdown response from {endpoint}: {data!r}")

    normalized: list[dict[str, str]] = []
    for option in options:
        value = option.get("Value")
        label = option.get("Text")
        if value is None or label is None:
            continue
        normalized.append({"value": str(value), "label": str(label)})
    return normalized


def option_label(options: list[dict[str, str]], value: str) -> str:
    for option in options:
        if option["value"] == value:
            return option["label"]
    raise CrawlerError(f"Option value {value!r} was not found in live dropdown options.")


def select_options_from_html(soup: BeautifulSoup, field_id: str) -> list[dict[str, str]]:
    select = soup.select_one(f"select#{field_id}")
    if not isinstance(select, Tag):
        raise CrawlerError(f"Missing select field id: {field_id}")

    options: list[dict[str, str]] = []
    for option in select.select("option"):
        value = str(option.get("value") or "")
        label = option.get_text(strip=True)
        options.append({"value": value, "label": label})
    return options


def input_value_by_id(soup: BeautifulSoup, field_id: str, fallback: str = "") -> str:
    element = soup.select_one(f"#{field_id}")
    if not isinstance(element, Tag):
        return fallback
    value = element.get("value")
    return str(value) if value is not None else fallback


def build_label_value_map(options: list[dict[str, str]]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for option in options:
        if option["value"] == "0":
            continue
        grouped.setdefault(option["label"], []).append(option["value"])
    return {label: values[0] for label, values in grouped.items() if len(values) == 1}


def build_payload(
    soup: BeautifulSoup,
    *,
    target_range: DateRange,
    dispute_filter: DisputeFilter,
) -> dict[str, str]:
    roc_year = gregorian_to_roc(target_range.start.year)
    payload = hidden_payload(soup)
    payload.update(
        {
            FIELD_DECISION_CATEGORY: "I03",
            FIELD_PAGE_SIZE: str(VISIBLE_LIMIT),
            FIELD_DECISION_RESULT: "0",
            FIELD_RESULT_NAME: "",
            FIELD_INDUSTRY: "I01",
            FIELD_INDUSTRY_SUBCATEGORY: "001",
            FIELD_DISPUTE_TYPE: dispute_filter.value,
            FIELD_CASE_YEAR: "",
            FIELD_CASE_WORD: input_value_by_id(soup, "cph_content_dll_BCase", "評"),
            FIELD_CASE_NUMBER: "",
            FIELD_CONTENT: "",
            FIELD_START_YEAR: str(roc_year),
            FIELD_START_MONTH: str(target_range.start.month),
            FIELD_START_DAY: str(target_range.start.day),
            FIELD_END_YEAR: str(gregorian_to_roc(target_range.end.year)),
            FIELD_END_MONTH: str(target_range.end.month),
            FIELD_END_DAY: str(target_range.end.day),
            FIELD_INTERNAL_START_DATE: "",
            FIELD_INTERNAL_END_DATE: "",
            FIELD_SUBMIT: input_value_by_id(soup, "cph_content_btn_submit", "送出查詢"),
            FIELD_ORDER_BY: "1",
            FIELD_SORT: "1",
            FIELD_CURRENT_PAGE: "1",
            FIELD_RECORD_COUNT: "1",
            FIELD_PAGE_COUNT: "1",
        }
    )
    return payload


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    return int(value) if value.isdigit() else None


def field_value(soup: BeautifulSoup, name: str) -> str | None:
    element = soup.select_one(f'input[name="{name}"]')
    if not isinstance(element, Tag):
        return None
    value = element.get("value")
    return str(value) if value is not None else None


def detect_batch_status(soup: BeautifulSoup) -> dict[str, Any]:
    no_results = soup.select_one("#cph_content_noShow.results-msg")
    over_limit = soup.select_one("#cph_content_result_msg.results-msg")
    record_count = parse_int(field_value(soup, FIELD_RECORD_COUNT))
    page_count = parse_int(field_value(soup, FIELD_PAGE_COUNT))

    if isinstance(over_limit, Tag):
        message = over_limit.get_text(" ", strip=True)
        numbers = [int(value) for value in re.findall(r"\d+", message)]
        visible_limit = VISIBLE_LIMIT
        reported_count = record_count
        if numbers:
            visible_limit = numbers[0]
        if len(numbers) >= 2:
            reported_count = numbers[-1]
        return {
            "status": "needs_split",
            "message": message,
            "visible_limit": visible_limit,
            "result_count_reported": reported_count,
            "page_count_reported": page_count,
            "records_created": 0,
        }

    if isinstance(no_results, Tag):
        return {
            "status": "no_results",
            "message": no_results.get_text(" ", strip=True),
            "visible_limit": VISIBLE_LIMIT,
            "result_count_reported": 0,
            "page_count_reported": page_count,
            "records_created": 0,
        }

    return {
        "status": "ok",
        "message": None,
        "visible_limit": VISIBLE_LIMIT,
        "result_count_reported": record_count,
        "page_count_reported": page_count,
        "records_created": 0,
    }


def normalize_pdf_link(href: str) -> tuple[str, str | None]:
    href = href.strip()
    absolute = urljoin(BASE_URL, href)
    parsed = urlparse(absolute)
    query = parse_qs(parsed.query, keep_blank_values=True)
    article_values = query.get("article")
    article = article_values[0].strip() if article_values else None
    if article is not None:
        query["article"] = [article]
        absolute = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    return absolute, article


def next_summary_text(row: Tag) -> str | None:
    sibling = row.find_next_sibling("tr")
    if not isinstance(sibling, Tag):
        return None
    if "summary" not in (sibling.get("class") or []):
        return None
    text = sibling.get_text(" ", strip=True)
    return text or None


def safe_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return cleaned or "unknown_case"


def planned_local_files(case_number: str, roc_year: int) -> dict[str, str | None]:
    stem = safe_filename(case_number)
    return {
        "pdf_path": None,
        "raw_text_path": None,
        "normalized_text_path": None,
        "planned_pdf_path": str(DATA_ROOT / "pdfs" / f"roc{roc_year}" / f"{stem}.pdf"),
        "planned_raw_text_path": str(DATA_ROOT / "texts" / f"roc{roc_year}" / f"{stem}.txt"),
        "planned_normalized_text_path": str(
            DATA_ROOT / "normalized_texts" / f"roc{roc_year}" / f"{stem}.txt"
        ),
    }


def make_batch_context(
    *,
    target_range: DateRange,
    dispute_filter: DisputeFilter,
    result_count_reported: int | None,
    split_reason: str,
) -> dict[str, Any]:
    roc_year = gregorian_to_roc(target_range.start.year)
    return {
        "roc_year": roc_year,
        "date_format": "ROC_SPLIT_FIELDS",
        "date_from": {
            "roc_year": roc_year,
            "month": target_range.start.month,
            "day": target_range.start.day,
        },
        "date_to": {
            "roc_year": gregorian_to_roc(target_range.end.year),
            "month": target_range.end.month,
            "day": target_range.end.day,
        },
        "date_from_label": roc_label(target_range.start),
        "date_to_label": roc_label(target_range.end),
        "dispute_type_filter": {
            "value": dispute_filter.value if dispute_filter.value != "0" else None,
            "label": dispute_filter.label if dispute_filter.value != "0" else None,
        },
        "result_count_reported": result_count_reported,
        "split_reason": split_reason,
    }


def parse_records(
    soup: BeautifulSoup,
    *,
    query_context: dict[str, Any],
    batch_context: dict[str, Any],
    crawled_at: str,
    dispute_filter: DisputeFilter,
    dispute_label_values: dict[str, str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    roc_year = batch_context["roc_year"]
    for row in soup.select("tr"):
        if not isinstance(row, Tag):
            continue
        if "summary" in (row.get("class") or []):
            continue
        cells = row.select("td")
        if len(cells) < 5:
            continue

        link = cells[2].select_one("a[href]")
        if not isinstance(link, Tag):
            continue

        case_number = link.get_text(" ", strip=True)
        href = str(link.get("href") or "")
        pdf_url, article = normalize_pdf_link(href)
        row_index = parse_int(cells[0].get_text(" ", strip=True))
        dispute_type_label = cells[4].get_text(" ", strip=True)
        dispute_type_value = (
            dispute_filter.value if dispute_filter.value != "0" else dispute_label_values.get(dispute_type_label)
        )

        records.append(
            {
                "case_number": case_number,
                "decision_category": query_context["decision_category"],
                "decision_result": query_context["decision_result"],
                "decision_date": cells[3].get_text(" ", strip=True),
                "industry": query_context["industry"],
                "industry_subcategory": query_context["industry_subcategory"],
                "dispute_type": {
                    "value": dispute_type_value,
                    "label": dispute_type_label,
                },
                "source": {
                    "result_url": BASE_URL,
                    "pdf_url": pdf_url,
                    "download_article": article,
                },
                "result_row": {
                    "row_index": row_index,
                    "keyword_context": next_summary_text(row),
                },
                "crawl_batch": batch_context,
                "local_files": planned_local_files(case_number, roc_year),
                "text": {
                    "raw": None,
                    "normalized": None,
                },
                "retrieval": {
                    "keywords": [],
                    "embedding_text": None,
                },
                "crawl": {
                    "crawled_at": crawled_at,
                    "status": "ok",
                    "error": None,
                },
            }
        )
    return records


def date_range_chunks(target_range: DateRange, chunk_days: int) -> list[DateRange]:
    chunks: list[DateRange] = []
    current = target_range.start
    while current <= target_range.end:
        chunk_end = min(current + timedelta(days=chunk_days - 1), target_range.end)
        chunks.append(DateRange(current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def month_ranges(start: date, end: date) -> list[DateRange]:
    ranges: list[DateRange] = []
    current = date(start.year, start.month, 1)
    while current <= end:
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_start = max(current, start)
        month_end = min(date(current.year, current.month, last_day), end)
        ranges.append(DateRange(month_start, month_end))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return ranges


def query_batch(
    *,
    session: requests.Session,
    query_context: dict[str, Any],
    target_range: DateRange,
    dispute_filter: DisputeFilter,
    split_reason: str,
    dispute_label_values: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    soup = fetch_soup(session)
    payload = build_payload(soup, target_range=target_range, dispute_filter=dispute_filter)
    result_soup = post_search(session, payload)
    status = detect_batch_status(result_soup)

    batch_context = make_batch_context(
        target_range=target_range,
        dispute_filter=dispute_filter,
        result_count_reported=status["result_count_reported"],
        split_reason=split_reason,
    )

    records: list[dict[str, Any]]
    if status["status"] == "needs_split":
        records = []
    else:
        records = parse_records(
            result_soup,
            query_context=query_context,
            batch_context=batch_context,
            crawled_at=datetime.now(timezone.utc).isoformat(),
            dispute_filter=dispute_filter,
            dispute_label_values=dispute_label_values,
        )

    if status["status"] == "ok" and status["result_count_reported"] is not None:
        if len(records) != status["result_count_reported"]:
            status["status"] = "partial"
            status["message"] = (
                f"Parsed {len(records)} records but source reported "
                f"{status['result_count_reported']} records."
            )

    status["records_created"] = len(records)
    return records, status | batch_context


def collect_batches(
    *,
    session: requests.Session,
    query_context: dict[str, Any],
    target_range: DateRange,
    dispute_filter: DisputeFilter,
    split_reason: str,
    dispute_split_options: list[DisputeFilter],
    dispute_label_values: dict[str, str],
    delay_seconds: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records, batch = query_batch(
        session=session,
        query_context=query_context,
        target_range=target_range,
        dispute_filter=dispute_filter,
        split_reason=split_reason,
        dispute_label_values=dispute_label_values,
    )
    time.sleep(delay_seconds)

    if batch["status"] != "needs_split":
        return records, [batch]

    all_records: list[dict[str, Any]] = []
    all_batches: list[dict[str, Any]] = [batch]

    if target_range.day_count > 7:
        for child_range in date_range_chunks(target_range, 7):
            child_records, child_batches = collect_batches(
                session=session,
                query_context=query_context,
                target_range=child_range,
                dispute_filter=dispute_filter,
                split_reason="parent_date_range_exceeded_visible_limit",
                dispute_split_options=dispute_split_options,
                dispute_label_values=dispute_label_values,
                delay_seconds=delay_seconds,
            )
            all_records.extend(child_records)
            all_batches.extend(child_batches)
        return all_records, all_batches

    if dispute_filter.value == "0":
        for child_filter in dispute_split_options:
            child_records, child_batches = collect_batches(
                session=session,
                query_context=query_context,
                target_range=target_range,
                dispute_filter=child_filter,
                split_reason="week_exceeded_visible_limit_dispute_type_split",
                dispute_split_options=dispute_split_options,
                dispute_label_values=dispute_label_values,
                delay_seconds=delay_seconds,
            )
            all_records.extend(child_records)
            all_batches.extend(child_batches)
        return all_records, all_batches

    if target_range.day_count > 1:
        for child_range in date_range_chunks(target_range, 1):
            child_records, child_batches = collect_batches(
                session=session,
                query_context=query_context,
                target_range=child_range,
                dispute_filter=dispute_filter,
                split_reason="dispute_type_batch_exceeded_visible_limit_daily_split",
                dispute_split_options=dispute_split_options,
                dispute_label_values=dispute_label_values,
                delay_seconds=delay_seconds,
            )
            all_records.extend(child_records)
            all_batches.extend(child_batches)
        return all_records, all_batches

    batch["status"] = "failed_needs_manual_split"
    batch["message"] = "A single-day dispute-type batch still exceeded the visible result limit."
    return all_records, all_batches


def validate_output(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    records = data.get("records")
    if not isinstance(records, list):
        return ["Top-level records must be a list."]

    seen_case_numbers: set[str] = set()
    for index, record in enumerate(records, start=1):
        case_number = record.get("case_number")
        if not case_number:
            errors.append(f"record {index}: missing case_number")
        elif case_number in seen_case_numbers:
            errors.append(f"record {index}: duplicate case_number {case_number}")
        else:
            seen_case_numbers.add(case_number)

        if not record.get("decision_date"):
            errors.append(f"record {index}: missing decision_date")
        dispute_type = record.get("dispute_type") or {}
        if not dispute_type.get("label"):
            errors.append(f"record {index}: missing dispute_type.label")
        source = record.get("source") or {}
        pdf_url = source.get("pdf_url")
        if not pdf_url:
            errors.append(f"record {index}: missing source.pdf_url")
        elif not str(pdf_url).startswith(urljoin(BASE_URL, "download.aspx")):
            errors.append(f"record {index}: unexpected pdf_url {pdf_url!r}")

        local_files = record.get("local_files") or {}
        for key in ("planned_pdf_path", "planned_raw_text_path", "planned_normalized_text_path"):
            if not local_files.get(key):
                errors.append(f"record {index}: missing local_files.{key}")

    for index, batch in enumerate(data.get("batches", []), start=1):
        if batch.get("status") == "needs_split":
            # Parent batches are retained for traceability, but final collection
            # must also include child batches that resolved the split.
            continue
        if batch.get("status") not in {"ok", "no_results", "partial"}:
            errors.append(f"batch {index}: unresolved status {batch.get('status')!r}")
    return errors


def dedupe_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduped: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for record in records:
        case_number = record["case_number"]
        if case_number in deduped:
            duplicate_count += 1
            continue
        deduped[case_number] = record
    return list(deduped.values()), duplicate_count


def crawl(args: argparse.Namespace) -> dict[str, Any]:
    session = make_session()
    soup = fetch_soup(session)

    decision_category_options = select_options_from_html(soup, "cph_content_ddlTypeID")
    decision_result_options = select_options_from_html(soup, "cph_content_ddl_ResultKind")
    industry_options = select_options_from_html(soup, "cph_content_ddlVerticals")
    subcategory_options = get_json_options(session, "ddlUse.aspx/GetSubVerticals", {"IndID": "I01"})
    raw_dispute_options = get_json_options(
        session,
        "ddlUse.aspx/GetControversyKind1",
        {
            "BType": "I03",
            "ResID": "I03",
            "ResSubID": "0",
            "IndID": "I01",
            "IndSubID": "001",
        },
    )
    dispute_options = [{"value": "0", "label": "請選擇"}, *raw_dispute_options]
    dispute_split_options = [
        DisputeFilter(option["value"], option["label"])
        for option in raw_dispute_options
        if option["value"] != "0" and option["label"].strip()
    ]
    dispute_label_values = build_label_value_map(raw_dispute_options)

    start = date(roc_to_gregorian(args.roc_year), args.start_month, args.start_day)
    end = date(roc_to_gregorian(args.roc_year), args.end_month, args.end_day)
    if start > end:
        raise CrawlerError("Start date must not be later than end date.")

    query_context = {
        "roc_year": args.roc_year,
        "date_format": "ROC_SPLIT_FIELDS",
        "decision_category": {
            "value": "I03",
            "label": option_label(decision_category_options, "I03"),
        },
        "decision_result": {
            "value": "0",
            "label": option_label(decision_result_options, "0"),
        },
        "industry": {
            "value": "I01",
            "label": option_label(industry_options, "I01"),
        },
        "industry_subcategory": {
            "parent_value": "I01",
            "parent_label": option_label(industry_options, "I01"),
            "value": "001",
            "label": option_label(subcategory_options, "001"),
        },
        "date_range": {
            "date_from": {
                "roc_year": args.roc_year,
                "month": args.start_month,
                "day": args.start_day,
            },
            "date_to": {
                "roc_year": args.roc_year,
                "month": args.end_month,
                "day": args.end_day,
            },
        },
        "dispute_type_options_count": len(dispute_options),
    }

    all_records: list[dict[str, Any]] = []
    all_batches: list[dict[str, Any]] = []
    for month_range in month_ranges(start, end):
        records, batches = collect_batches(
            session=session,
            query_context=query_context,
            target_range=month_range,
            dispute_filter=DisputeFilter("0", option_label(dispute_options, "0")),
            split_reason="month_query",
            dispute_split_options=dispute_split_options,
            dispute_label_values=dispute_label_values,
            delay_seconds=args.delay_seconds,
        )
        all_records.extend(records)
        all_batches.extend(batches)

    deduped_records, duplicate_count = dedupe_records(all_records)
    expected_records_from_leaf_batches = sum(
        batch.get("result_count_reported") or 0
        for batch in all_batches
        if batch.get("status") in {"ok", "partial"}
    )

    output = {
        "source": {
            "name": "Financial Ombudsman Institution ODS",
            "system_url": BASE_URL,
            "help_url": HELP_URL,
        },
        "query": query_context,
        "storage": {
            "metadata_path": str(args.output),
            "pdf_directory": str(DATA_ROOT / "pdfs" / f"roc{args.roc_year}"),
            "raw_text_directory": str(DATA_ROOT / "texts" / f"roc{args.roc_year}"),
            "normalized_text_directory": str(DATA_ROOT / "normalized_texts" / f"roc{args.roc_year}"),
            "pdf_downloaded": False,
            "pdf_text_extracted": False,
        },
        "records": deduped_records,
        "batches": all_batches,
        "validation": {
            "json_serializable": True,
            "raw_record_count": len(all_records),
            "unique_record_count": len(deduped_records),
            "duplicate_case_number_count": duplicate_count,
            "expected_records_from_leaf_batches": expected_records_from_leaf_batches,
            "required_field_errors": [],
            "pdf_downloaded": False,
            "pdf_text_extracted": False,
        },
    }
    output["validation"]["required_field_errors"] = validate_output(output)
    if output["validation"]["required_field_errors"]:
        raise CrawlerError(
            "Output validation failed: " + "; ".join(output["validation"]["required_field_errors"])
        )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FOI ODS life-insurance crawler: metadata and official PDF URLs only."
    )
    parser.add_argument("--roc-year", type=int, default=115)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--start-day", type=int, default=1)
    parser.add_argument("--end-month", type=int, default=7)
    parser.add_argument("--end-day", type=int, default=1)
    parser.add_argument("--delay-seconds", type=float, default=0.3)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.output is None:
        args.output = default_metadata_path(args.roc_year)
    return args


def main() -> None:
    args = parse_args()
    data = crawl(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "records": len(data["records"]),
                "batches": len(data["batches"]),
                "duplicate_case_number_count": data["validation"]["duplicate_case_number_count"],
                "expected_records_from_leaf_batches": data["validation"][
                    "expected_records_from_leaf_batches"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
