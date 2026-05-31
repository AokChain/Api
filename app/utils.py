from datetime import datetime, timezone, UTC
from typing import Sequence
from app import constants
import typing
import math


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# Convert datetime to timestamp
def to_timestamp(date: datetime | None) -> int | None:
    date = date.replace(tzinfo=timezone.utc) if date else date
    return int(date.timestamp()) if date else None


def token_type(name: str):
    if "#" in name:
        return "unique"
    if "/" in name:
        return "sub"
    if name[0] == "@":
        return "username"
    if name[-1] == "!":
        return "owner"
    return "root"


# Helper function for pagination
def pagination(page: int, size: int = constants.DEFAULT_PAGINATION_SIZE):
    offset = (size * page) - size

    return size, offset  # type: ignore


# Helper function to make pagination dict for api
def pagination_dict(total, page, limit):
    return {
        "pages": math.ceil(total / limit),
        "total": total,
        "page": page,
    }


def paginated_response(
    items: Sequence[typing.Any], total: int, page: int, limit: int
) -> dict[str, typing.Any]:
    return {
        "pagination": pagination_dict(total, page, limit),
        "list": items,
    }


def to_satoshi(x: float) -> int:
    return int(x * math.pow(10, 8))


def get_token_icon(name: str):
    cache_fix = 8

    match name:
        case "AOK":
            return f"https://apiv2.aok.network/static/logo/aok.svg?{cache_fix}"

        case "ARTL":
            return f"https://apiv2.aok.network/static/logo/artl.svg?{cache_fix}"

        case "CCA":
            return f"https://apiv2.aok.network/static/logo/cca.svg?{cache_fix}"

        case "MEC":
            return f"https://apiv2.aok.network/static/logo/mec.svg?{cache_fix}"

        case "SERG":
            return f"https://apiv2.aok.network/static/logo/serg.svg?{cache_fix}"

        case "PAPT":
            return f"https://apiv2.aok.network/static/logo/papt.svg?{cache_fix}"

        case "CCA/USDT":
            return f"https://apiv2.aok.network/static/logo/cca_usdt.svg?{cache_fix}"

        case "MEC/HOWLING2":
            return f"https://apiv2.aok.network/static/logo/mec_howling2.svg?{cache_fix}"

        case "PLB":
            return f"https://apiv2.aok.network/static/logo/plb.svg?{cache_fix}"

        case "NMO":
            return f"https://apiv2.aok.network/static/logo/nmo.svg?{cache_fix}"

        case "NOL":
            return f"https://apiv2.aok.network/static/logo/nol.svg?{cache_fix}"

        case "GND":
            return f"https://apiv2.aok.network/static/logo/gnd.svg?{cache_fix}"

        case "CCL":
            return f"https://apiv2.aok.network/static/logo/ccl.svg?{cache_fix}"

        case "DZTB":
            return f"https://apiv2.aok.network/static/logo/dztb.png?{cache_fix}"

        case "DHTB":
            return f"https://apiv2.aok.network/static/logo/dhtb.png?{cache_fix}"

        case "TONG":
            return f"https://apiv2.aok.network/static/logo/tong.png?{cache_fix}"

        case _:
            return None
