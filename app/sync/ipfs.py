from app.database import sessionmanager
from app.settings import get_settings
from app.utils import get_ipfs_data
from sqlalchemy import select
from app.models import Token
from app import parser


async def sync_ipfs():
    settings = get_settings()

    async with sessionmanager.session() as session:
        tokens = await session.scalars(
            select(Token)
            .filter(
                Token.has_ipfs == None,  # noqa: E711
            )
            .limit(100)
        )

        for token in tokens:
            response = await parser.make_request(
                settings.blockchain.endpoint,
                {
                    "id": "token-info",
                    "method": "gettokendata",
                    "params": [token.name],
                },
            )

            if response["error"] is not None or response["result"] is None:
                continue

            if response["result"]["has_ipfs"] == 0:
                token.has_ipfs = 0
                continue

            token.has_ipfs = 1
            token.ipfs_hash = response["result"]["ipfs_hash"]
            token.data = await get_ipfs_data(response["result"]["ipfs_hash"])

            print(f"Added token ipfs data to {token.name}")

        await session.commit()
