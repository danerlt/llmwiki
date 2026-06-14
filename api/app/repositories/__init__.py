# package
# 所有 repo 已迁移为"类 + 单例(继承 BaseCrud)"。在此重导出单例实例，
# 使 `from app.repositories import X` 拿到单例（调用点写法不变）。
from app.repositories.api_key_repo import api_key_repo
from app.repositories.audit_repo import audit_repo
from app.repositories.comment_repo import comment_repo
from app.repositories.favorite_repo import favorite_repo
from app.repositories.feedback_repo import feedback_repo
from app.repositories.kb_repo import kb_repo
from app.repositories.notification_repo import notification_repo
from app.repositories.org_repo import org_repo
from app.repositories.promotion_repo import promotion_repo
from app.repositories.search_miss_repo import search_miss_repo
from app.repositories.source_repo import source_repo
from app.repositories.subscription_repo import subscription_repo
from app.repositories.user_repo import user_repo
from app.repositories.webhook_repo import webhook_repo
from app.repositories.wiki_repo import wiki_repo

__all__ = [
    "api_key_repo",
    "audit_repo",
    "comment_repo",
    "favorite_repo",
    "feedback_repo",
    "kb_repo",
    "notification_repo",
    "org_repo",
    "promotion_repo",
    "search_miss_repo",
    "source_repo",
    "subscription_repo",
    "user_repo",
    "webhook_repo",
    "wiki_repo",
]
