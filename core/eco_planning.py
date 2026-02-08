
from dataclasses import dataclass
from datetime import date, timedelta
from django.db.models import Count
from users.models import MealRequest, MealReceipt, Subscription
from menu.models import DailyMenu, MenuItem

@dataclass(frozen=True)
class PlanInputs:
    forecast: int
    history_avg: int
    waste_avg: int

# History stats to calculate waste and average consumption
def _history_stats(day: date, meal_type: str, organization=None, lookback_days: int = 7) -> tuple[int, int]:
    start = day - timedelta(days=lookback_days)
    end = day - timedelta(days=1)
    if end < start:
        return 0, 0
    issued_qs = MealRequest.objects.filter(date__range=(start, end), meal_type=meal_type, status=MealRequest.STATUS_ISSUED)
    conf_qs = MealReceipt.objects.filter(date__range=(start, end), meal_type=meal_type)
    if organization is not None:
        issued_qs = issued_qs.filter(organization=organization)
        conf_qs = conf_qs.filter(organization=organization)

    issued_by_day = {r['date']: r['cnt'] for r in issued_qs.values('date').annotate(cnt=Count('id'))}
    conf_by_day = {r['date']: r['cnt'] for r in conf_qs.values('date').annotate(cnt=Count('id'))}

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if not days:
        return 0, 0

    conf_vals = [int(conf_by_day.get(d, 0)) for d in days]
    waste_vals = [max(0, int(issued_by_day.get(d, 0)) - int(conf_by_day.get(d, 0))) for d in days]

    history_avg = round(sum(conf_vals) / len(conf_vals)) if conf_vals else 0
    waste_avg = round(sum(waste_vals) / len(waste_vals)) if waste_vals else 0
    return history_avg, waste_avg

# Calculate suggested portions based on forecast and waste
def compute_suggested_portions(day: date, meal_type: str, organization=None) -> tuple[int, PlanInputs]:
    forecast = max(_count_active_subscriptions(day, meal_type, organization), _count_forecast_requests(day, meal_type, organization))
    history_avg, waste_avg = _history_stats(day, meal_type, organization)

    suggested = round(0.7 * forecast + 0.3 * history_avg - 0.5 * waste_avg)
    suggested = max(0, int(suggested))

    return suggested, PlanInputs(forecast=forecast, history_avg=history_avg, waste_avg=waste_avg)
