from datetime import date

from digest.utils import WEEKDAYS, pt_date


def date_header(d: date) -> str:
    """E.g.: '✅ Dia 14 de Outubro de 2026, Quarta-Feira'"""
    return f"✅ Dia {pt_date(d)}, {WEEKDAYS[d.weekday()]}"
