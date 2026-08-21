from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.url import URL


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url_id: Mapped[int] = mapped_column(
        ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    url: Mapped["URL"] = relationship("URL", back_populates="clicks")

    def __repr__(self) -> str:
        return f"<Click(id={self.id}, url_id={self.url_id}, clicked_at='{self.clicked_at}')>"
