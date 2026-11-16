"""Bounded SQL catalog reads; role/scope and filters belong to the caller."""
import re
from dataclasses import dataclass
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import func, select

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


@dataclass(frozen=True)
class PageRequest:
    number: int
    size: int

    @classmethod
    def parse(cls, page="1", page_size="50"):
        values = []
        for value, maximum in ((page, 1_000_000), (page_size, 100)):
            raw = str(value).strip().translate(DIGITS)
            if not re.fullmatch(r"[0-9]{1,7}", raw) or not 1 <= int(raw) <= maximum:
                raise HTTPException(400, "شمارهٔ صفحه باید مثبت و اندازهٔ صفحه بین ۱ تا ۱۰۰ باشد.")
            values.append(int(raw))
        return cls(*values)


@dataclass(frozen=True)
class Page:
    rows: list
    total: int
    number: int
    size: int

    @property
    def pages(self):
        return max(1, (self.total + self.size - 1) // self.size)

    @property
    def first(self):
        return (self.number - 1) * self.size + 1 if self.total else 0

    @property
    def last(self):
        return min(self.number * self.size, self.total)

    def navigation(self, path, filters=None):
        def link(number):
            return path + "?" + urlencode({**(filters or {}), "page": number, "page_size": self.size})
        return {"previous": link(self.number - 1) if self.number > 1 else None,
                "next": link(self.number + 1) if self.number < self.pages else None}


def paginate(db, statement, requested, *, scalars=False):
    """Count only the caller's filtered query, then retrieve a limited ordered slice."""
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    pages = max(1, (total + requested.size - 1) // requested.size)
    number = min(requested.number, pages)
    result = db.execute(statement.limit(requested.size).offset((number - 1) * requested.size))
    rows = result.scalars().all() if scalars else result.all()
    return Page(rows, total, number, requested.size)
