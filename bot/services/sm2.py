from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SM2Result:
    ease_factor: float
    interval: int
    repetition: int
    next_review_date: date


def sm2(
    quality: int,
    ease_factor: float,
    interval: int,
    repetition: int,
    today: date | None = None,
) -> SM2Result:
    """SuperMemo-2 spaced repetition algorithm.

    quality: 0-5, where >=3 is a "correct" recall.
    """
    today = today or date.today()

    if quality < 3:
        repetition = 0
        interval = 1
    else:
        repetition += 1
        if repetition == 1:
            interval = 1
        elif repetition == 2:
            interval = 6
        else:
            interval = round(interval * ease_factor)

    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)

    next_review_date = today + timedelta(days=interval)

    return SM2Result(
        ease_factor=ease_factor,
        interval=interval,
        repetition=repetition,
        next_review_date=next_review_date,
    )
