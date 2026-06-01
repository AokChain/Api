import typing
from app.settings import get_settings
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from app import constants
import aiohttp
import json


async def make_request(endpoint: str, requests: list[dict] | dict = None):
    if requests is None:
        requests = []

    async with aiohttp.ClientSession() as session:
        headers = {"content-type": "application/json;"}
        data = json.dumps(requests)

        try:
            async with session.post(endpoint, headers=headers, data=data) as r:
                return await r.json()
        except Exception:
            raise


def parse_meta(spk):
    if spk["type"] in ["new_token", "reissue_token"]:
        return {
            "type": spk["type"],
            "amount": spk["token"]["amount"],
            "name": spk["token"]["name"],
            "units": (
                spk["token"]["units"] if "units" in spk["token"] else False
            ),
            "reissuable": (
                spk["token"]["reissuable"]
                if "reissuable" in spk["token"]
                else False
            ),
        }

    return {}


async def parse_outputs(transaction_data: dict):
    outputs = []

    for vout in transaction_data["vout"]:
        spk = vout["scriptPubKey"]

        if spk["type"] in ["nonstandard", "nulldata"]:
            continue

        if "token" in spk:
            timelock = spk["token"]["token_lock_time"]
            currency = spk["token"]["name"]
            amount = spk["token"]["amount"]

        else:
            timelock = 0

            if spk["type"] == "cltv":
                key = spk["asm"].split(" ", 1)[0]

                if key.isdigit():
                    timelock = int(key)

            currency = constants.DEFAULT_CURRENCY
            amount = vout["value"]

        # Extract metadata like information about token issuance and etc
        meta = parse_meta(spk)

        outputs.append(
            {
                "shortcut": transaction_data["txid"] + ":" + str(vout["n"]),
                "blockhash": transaction_data.get("blockhash"),
                "txid": transaction_data["txid"],
                "address": spk["addresses"][0],
                "timelock": timelock,
                "currency": currency,
                "type": spk["type"],
                "index": vout["n"],
                "amount": Decimal(str(amount)),
                "spent": False,
                "script": spk["hex"],
                "asm": spk["asm"],
                "meta": meta,
            }
        )

    return outputs


async def parse_inputs(transaction_data: dict):
    inputs = []

    for vin in transaction_data["vin"]:
        if "coinbase" in vin:
            continue

        inputs.append(
            {
                "shortcut": vin["txid"] + ":" + str(vin["vout"]),
                "blockhash": transaction_data.get("blockhash"),
                "index": vin["vout"],
                "txid": transaction_data["txid"],
                "source_txid": vin["txid"],
            }
        )

    return inputs


async def resolve_source_outputs(
    settings: typing.Any,
    source_txids: list[str],
) -> dict[str, typing.Any]:
    if not source_txids:
        return {}

    input_transactions_result = await make_request(
        settings.blockchain.endpoint,
        [
            {
                "id": f"input-tx-{txid}",
                "method": "getrawtransaction",
                "params": [txid, True],
            }
            for txid in source_txids
        ],
    )

    input_outputs: dict[str, typing.Any] = {}

    for transaction_result in input_transactions_result:
        transaction_data = transaction_result["result"]
        vin_vouts: list[dict[str, typing.Any]] = await parse_outputs(
            transaction_data
        )

        for vout in vin_vouts:
            input_outputs[vout["shortcut"]] = vout

    return input_outputs


def compute_movements(
    inputs: list[dict[str, typing.Any]],
    outputs: list[dict[str, typing.Any]],
    input_outputs: dict[str, typing.Any],
):
    # Use convenient defaultdict to not bloat code with setdefault calls
    movements: dict[
        str, dict[str, dict[typing.Literal["locked", "amount"], Decimal]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))

    for output in outputs:
        currency = output["currency"]
        address = output["address"]
        amount = output["amount"]

        if output["timelock"]:
            movements[currency][address]["locked"] += amount
        else:
            movements[currency][address]["amount"] += amount

    for input in inputs:  # noqa
        input_output = input_outputs[input["shortcut"]]
        currency = input_output["currency"]
        address = input_output["address"]
        amount = input_output["amount"]

        movements[currency][address]["amount"] -= amount

    return {
        currency: {
            address: {
                "locked": float(amount["locked"]),
                "amount": float(amount["amount"]),
            }
            for address, amount in currency_movement.items()
        }
        for currency, currency_movement in movements.items()
    }


async def build_movements(
    settings: typing.Any,
    inputs: list[dict[str, typing.Any]],
    outputs: list[dict[str, typing.Any]],
):
    source_txids = list(set(vin["source_txid"] for vin in inputs))
    input_outputs = await resolve_source_outputs(settings, source_txids)
    return compute_movements(inputs, outputs, input_outputs)


async def extract_transactions(
    transactions_data: list[dict],
    stake: bool = False,
    block_hash: str | None = None,
):
    # Skip firt tx for pos blocks
    if stake:
        transactions_data = transactions_data[1:]

    transactions = []
    outputs = []
    inputs = []

    for index, transaction_data in enumerate(transactions_data):
        # getblock verbosity 2 inlines transactions without the block context
        # fields getrawtransaction adds, so backfill the blockhash here
        if block_hash is not None:
            transaction_data["blockhash"] = block_hash

        coinbase = index == 0 and not stake

        addresses = list(
            set(
                address
                for vout in transaction_data["vout"]
                for address in vout["scriptPubKey"].get("addresses", [])
            )
        )

        # getrawtransaction exposes the tx time as "time", getblock v2 as "timestamp"
        timestamp = transaction_data.get(
            "time", transaction_data.get("timestamp")
        )
        created = datetime.fromtimestamp(timestamp) if timestamp else None

        transactions.append(
            {
                "created": created,
                "addresses": addresses,
                "blockhash": transaction_data.get("blockhash"),
                "locktime": transaction_data["locktime"],
                "version": transaction_data["version"],
                "timestamp": timestamp,
                "index": index,
                "coinbase": coinbase,
                "size": transaction_data["size"],
                "txid": transaction_data["txid"],
            }
        )

        outputs += await parse_outputs(transaction_data)

        inputs += await parse_inputs(transaction_data)

    return transactions, outputs, inputs


async def process_transactions(
    transactions_data: list[dict],
    stake: bool = False,
    block_hash: str | None = None,
):
    settings = get_settings()

    transactions, outputs, inputs = await extract_transactions(
        transactions_data, stake, block_hash
    )

    movements = await build_movements(settings, inputs, outputs)

    return {
        "transactions": transactions,
        "movements": movements,
        "outputs": outputs,
        "inputs": inputs,
    }


async def parse_transactions(txids: list[str], stake: bool = False):
    settings = get_settings()

    transactions_result = await make_request(
        settings.blockchain.endpoint,
        [
            {
                "id": f"tx-{txid}",
                "method": "getrawtransaction",
                "params": [txid, True],
            }
            for txid in txids
        ],
    )

    # Preserve the requested order regardless of how the node orders the batch
    by_txid = {
        result["result"]["txid"]: result["result"]
        for result in transactions_result
    }
    transactions_data = [by_txid[txid] for txid in txids]

    return await process_transactions(transactions_data, stake)


def build_block_result(
    block_data: dict,
    transactions: list,
    outputs: list,
    inputs: list,
    movements: dict,
):
    return {
        "transactions": transactions,
        "outputs": outputs,
        "inputs": inputs,
        "block": {
            "prev_blockhash": block_data.get("previousblockhash", None),
            "created": datetime.fromtimestamp(block_data["time"]),
            "movements": movements,
            "transactions": [tx["txid"] for tx in block_data["tx"]],
            "blockhash": block_data["hash"],
            "timestamp": block_data["time"],
            "height": block_data["height"],
        },
    }


async def parse_blocks(heights: list[int]):
    settings = get_settings()

    if not heights:
        return []

    # Stage 1: resolve every block hash in a single batched request
    hash_results = await make_request(
        settings.blockchain.endpoint,
        [
            {
                "id": f"blockhash-{height}",
                "method": "getblockhash",
                "params": [height],
            }
            for height in heights
        ],
    )

    hash_by_id = {
        result["id"]: result.get("result") for result in hash_results
    }

    # Stop at the first gap (tip moved or reorg mid-window); the caller resumes
    # from there and the per-tip reorg check handles any rollback
    block_hashes = []
    resolved_heights = []
    for height in heights:
        block_hash = hash_by_id.get(f"blockhash-{height}")
        if block_hash is None:
            break
        resolved_heights.append(height)
        block_hashes.append(block_hash)

    if not block_hashes:
        return []

    # Stage 2: fetch every block with verbosity 2 (transactions inlined) at once
    block_results = await make_request(
        settings.blockchain.endpoint,
        [
            {
                "id": f"block-{block_hash}",
                "method": "getblock",
                "params": [block_hash, 2],
            }
            for block_hash in block_hashes
        ],
    )

    block_by_id = {result["id"]: result["result"] for result in block_results}

    # Parse each block and collect the source txids spent across the whole window
    parsed = []
    source_txids: set[str] = set()

    for height, block_hash in zip(resolved_heights, block_hashes):
        block_data = block_by_id[f"block-{block_hash}"]
        stake = block_data["flags"] == "proof-of-stake"

        transactions, outputs, inputs = await extract_transactions(
            [] if height == 0 else block_data["tx"], stake, block_hash
        )

        parsed.append((block_data, transactions, outputs, inputs))
        source_txids.update(vin["source_txid"] for vin in inputs)

    # Stage 3: resolve the spent outputs for the entire window in one request
    input_outputs = await resolve_source_outputs(settings, list(source_txids))

    return [
        build_block_result(
            block_data,
            transactions,
            outputs,
            inputs,
            compute_movements(inputs, outputs, input_outputs),
        )
        for block_data, transactions, outputs, inputs in parsed
    ]


async def parse_block(height: int):
    blocks = await parse_blocks([height])
    return blocks[0]
