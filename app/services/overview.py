"""Сервис для сбора метрик дашборда администратора."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory
from app.models import (
    Subscription,
    SubscriptionStatus,
    Transaction,
    User,
    UserStatus,
)


def _count_case(condition: Any) -> Any:
    return func.sum(case((condition, 1), else_=0))


async def fetch_overview_metrics(session: AsyncSession) -> dict[str, Any]:
    """Собрать ключевые метрики для дашборда."""
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ahead = now + timedelta(days=7)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Пользователи
    users_stmt = select(
        func.count(User.id).label("total"),
        _count_case(User.status == UserStatus.ACTIVE.value).label("active"),
        _count_case(User.status == UserStatus.BLOCKED.value).label("blocked"),
        _count_case(User.created_at >= day_ago).label("new_24h"),
        func.coalesce(func.sum(User.balance_kopeks), 0).label("balance_kopeks"),
    )
    users_row = (await session.execute(users_stmt)).one()

    # Подписки
    subscriptions_stmt = select(
        func.count(Subscription.id).label("total"),
        _count_case(Subscription.status == SubscriptionStatus.ACTIVE.value).label("active"),
        _count_case(Subscription.status == SubscriptionStatus.TRIAL.value).label("trial"),
        _count_case(Subscription.status == SubscriptionStatus.EXPIRED.value).label("expired"),
        _count_case(Subscription.status == SubscriptionStatus.DISABLED.value).label("disabled"),
        _count_case(
            and_(
                Subscription.end_date >= now,
                Subscription.end_date <= week_ahead,
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIAL.value]
                ),
            )
        ).label("expiring_7d"),
        _count_case(Subscription.autopay_enabled.is_(True)).label("autopay"),
    )
    subscriptions_row = (await session.execute(subscriptions_stmt)).one()

    # Транзакции за последние 30 дней
    transactions_base = select(
        func.coalesce(func.sum(Transaction.amount_kopeks), 0).label("amount"),
        func.count(Transaction.id).label("count"),
    ).where(
        Transaction.is_completed.is_(True),
        Transaction.created_at >= month_ago,
    )
    transactions_row = (await session.execute(transactions_base)).one()

    payments_by_method_stmt = (
        select(
            Transaction.payment_method,
            func.coalesce(func.sum(Transaction.amount_kopeks), 0).label("amount"),
        )
        .where(
            Transaction.is_completed.is_(True),
            Transaction.created_at >= month_ago,
            Transaction.amount_kopeks > 0,
        )
        .group_by(Transaction.payment_method)
        .order_by(func.sum(Transaction.amount_kopeks).desc())
    )
    payments_by_method = [
        {"method": method or "unknown", "amount_rub": amount / 100}
        for method, amount in (await session.execute(payments_by_method_stmt)).all()
    ]

    # Динамика за последние 7 дней
    daily_revenue_stmt = (
        select(
            func.date_trunc("day", Transaction.created_at).label("bucket"),
            func.coalesce(func.sum(Transaction.amount_kopeks), 0).label("amount"),
        )
        .where(
            Transaction.is_completed.is_(True),
            Transaction.amount_kopeks > 0,
            Transaction.created_at >= week_ago,
        )
        .group_by(func.date_trunc("day", Transaction.created_at))
        .order_by(func.date_trunc("day", Transaction.created_at))
    )
    revenue_rows = (await session.execute(daily_revenue_stmt)).all()
    revenue_map = {row.bucket.date(): row.amount / 100 for row in revenue_rows}

    daily_users_stmt = (
        select(
            func.date_trunc("day", User.created_at).label("bucket"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= week_ago)
        .group_by(func.date_trunc("day", User.created_at))
        .order_by(func.date_trunc("day", User.created_at))
    )
    users_rows = (await session.execute(daily_users_stmt)).all()
    users_map = {row.bucket.date(): row.count for row in users_rows}

    chart_days = [ (now.date() - timedelta(days=i)) for i in range(6, -1, -1)]
    revenue_series = [
        {"date": day.isoformat(), "amount_rub": round(revenue_map.get(day, 0), 2)}
        for day in chart_days
    ]
    new_users_series = [
        {"date": day.isoformat(), "count": users_map.get(day, 0)} for day in chart_days
    ]

    return {
        "generated_at": now,
        "users": {
            "total": int(users_row.total or 0),
            "active": int(users_row.active or 0),
            "blocked": int(users_row.blocked or 0),
            "new_24h": int(users_row.new_24h or 0),
            "balance_rub": round((users_row.balance_kopeks or 0) / 100, 2),
        },
        "subscriptions": {
            "total": int(subscriptions_row.total or 0),
            "active": int(subscriptions_row.active or 0),
            "trial": int(subscriptions_row.trial or 0),
            "expired": int(subscriptions_row.expired or 0),
            "disabled": int(subscriptions_row.disabled or 0),
            "expiring_7d": int(subscriptions_row.expiring_7d or 0),
            "autopay": int(subscriptions_row.autopay or 0),
        },
        "transactions": {
            "count": int(transactions_row.count or 0),
            "amount_rub": round((transactions_row.amount or 0) / 100, 2),
            "payments_by_method": payments_by_method,
            "daily_revenue": revenue_series,
        },
        "charts": {
            "revenue": revenue_series,
            "new_users": new_users_series,
        },
    }


async def get_overview_metrics() -> dict[str, Any]:
    """Обертка для получения метрик при помощи фабрики сессий."""
    async with AsyncSessionFactory() as session:
        return await fetch_overview_metrics(session)


__all__ = ["fetch_overview_metrics", "get_overview_metrics"]
