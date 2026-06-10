from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import Numeric, String
from decimal import Decimal
from .base import Base


class Token(Base):
    __tablename__ = "service_tokens"

    amount: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=8))
    blockhash: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    height: Mapped[int] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(index=True)
    reissuable: Mapped[bool]
    units: Mapped[int]

    data: Mapped[dict] = mapped_column(JSONB, default={})
    ipfs_hash: Mapped[str] = mapped_column(nullable=True)
    has_ipfs: Mapped[int] = mapped_column(nullable=True)
